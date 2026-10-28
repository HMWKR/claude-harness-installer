#!/usr/bin/env python3
"""
Checkpoint Save — 세션 간 작업 연속성 보장 스크립트

PreCompact/SessionEnd 훅에서 호출되어 현재 작업 상태를 checkpoint.md에 저장.
다음 세션에서 "어디까지 했는지"를 즉시 파악할 수 있게 함.

사용법:
    python3 checkpoint-save.py precompact    # PreCompact 훅 — 저장
    python3 checkpoint-save.py sessionend    # SessionEnd 훅 — 저장
    python3 checkpoint-save.py sessionstart  # SessionStart 훅 — 다른 세션이 남긴 체크포인트만 알림(stdout)
    python3 checkpoint-save.py stop          # Stop 훅 — 저장하지 않음(기존 등록 호환용)

출력 파일: $CLAUDE_PROJECT_DIR/checkpoint.md (세션이 시작된 프로젝트 루트)
  - CLAUDE_PROJECT_DIR가 없거나, 그 자리의 checkpoint.md가 사람이 쓴 파일이거나 git 추적
    파일이면 ~/.claude/state/checkpoints/<session_id>.md 에 쓴다.
  - 추적 중인 .gitignore는 건드리지 않는다. git repo면 .git/info/exclude(로컬 전용)에만 등록한다.

[2026-09-30] 예전에는 Stop(매 턴)마다 셸이 cd한 곳의 git 루트에 쓰고 그 repo의 .gitignore에
append했다 — 서드파티 repo 오염. 또 매 턴 생긴 파일이 UserPromptSubmit의 '이전 세션 체크포인트
발견' 주입을 같은 세션 안에서도 매번 참으로 만들었다(자기충족 오염). plan 체크박스 자동 [x]
처리는 cwd repo의 파일명만 보고 전역 최신 플랜을 고쳐 제거했다 — 체크는 편집 직후 모델이
직접 갱신한다(loop-prevention 체크마크 프로토콜).
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# 자동 생성본 판별 헤더 — 이 줄로 시작하지 않는 checkpoint.md는 사람이 관리하는 파일로 보고 덮어쓰지 않는다
AUTO_HEADER = "# Checkpoint — 작업 상태 스냅샷"
FALLBACK_DIR = Path.home() / ".claude" / "state" / "checkpoints"
SAVE_TRIGGERS = {"precompact": "컨텍스트 압축 전", "sessionend": "세션 종료"}

_HOOK_INPUT = None


def read_hook_input():
    """훅 stdin JSON (1회만 읽고 캐시). 터미널 수동 실행이면 읽지 않는다."""
    global _HOOK_INPUT
    if _HOOK_INPUT is None:
        _HOOK_INPUT = {}
        try:
            if not sys.stdin.isatty():
                raw = sys.stdin.read()
                if raw.strip():
                    data = json.loads(raw)
                    if isinstance(data, dict):
                        _HOOK_INPUT = data
        except (ValueError, OSError, AttributeError):
            pass
    return _HOOK_INPUT


def _safe_id(value):
    """파일명용 식별자 정규화 — 경로 구분자·점을 치환해 저장 디렉토리 밖으로 못 나가게 한다."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(value or ""))[:100]


def _run_git(*args, cwd=None, timeout=3):
    """git 명령 실행. Windows cp949 인코딩 문제 방지를 위해 encoding='utf-8' 강제.
    cwd는 항상 프로젝트 루트를 넘긴다 — 셸이 cd한 곳의 repo를 읽지 않기 위함."""
    try:
        result = subprocess.run(
            ["git"] + list(args), cwd=cwd,
            capture_output=True, encoding="utf-8", errors="replace", timeout=timeout
        )
        return result
    except (subprocess.TimeoutExpired, OSError):
        return None


def get_project_root():
    """세션이 시작된 프로젝트 루트($CLAUDE_PROJECT_DIR). 없으면 None.
    예전 구현(git rev-parse/getcwd)은 셸이 cd한 repo를 따라가 아무 repo에나 썼다."""
    pd = os.environ.get("CLAUDE_PROJECT_DIR", "")
    return pd if pd and os.path.isdir(pd) else None


def get_git_diff_stat(root):
    """세션 중 변경된 파일 요약."""
    if not root:
        return "git 정보 생략 (CLAUDE_PROJECT_DIR 미지정)"
    try:
        result = _run_git("diff", "--stat", "HEAD", cwd=root)
        staged = _run_git("diff", "--stat", "--cached", cwd=root)
        untracked = _run_git("ls-files", "--others", "--exclude-standard", cwd=root)

        parts = []
        if result and result.stdout and result.stdout.strip():
            parts.append(f"### 수정됨 (unstaged)\n```\n{result.stdout.strip()}\n```")
        if staged and staged.stdout and staged.stdout.strip():
            parts.append(f"### 스테이징됨\n```\n{staged.stdout.strip()}\n```")
        if untracked and untracked.stdout and untracked.stdout.strip():
            files = untracked.stdout.strip().split("\n")
            if len(files) > 10:
                files = files[:10] + [f"... 외 {len(files) - 10}개"]
            parts.append(f"### 새 파일 (untracked)\n```\n" + "\n".join(files) + "\n```")

        return "\n\n".join(parts) if parts else "변경 사항 없음"
    except Exception:
        return "git 정보 수집 실패"


def get_current_branch(root):
    """현재 브랜치명."""
    result = _run_git("branch", "--show-current", cwd=root) if root else None
    if result and result.stdout:
        return result.stdout.strip() or "HEAD detached"
    return "unknown"


def get_recent_commits(root, n=3):
    """최근 커밋 n개."""
    result = _run_git("log", f"-{n}", "--oneline", "--no-decorate", cwd=root) if root else None
    if result and result.stdout:
        return result.stdout.strip() or "커밋 없음"
    return "git log 실패"


def get_todo_state(session_id):
    """Claude Code TodoWrite 상태 파일에서 진행 중인 작업 추출 — 이 세션의 파일만(파일명에 session_id).
    전역 최신 파일을 고르면 다른 세션의 작업 목록이 섞였다(2026-10-02 codex 최종 게이트)."""
    claude_dir = Path.home() / ".claude" / "todos"
    if not session_id or not claude_dir.exists():
        return None

    todo_files = sorted((f for f in claude_dir.glob("*.json") if session_id in f.name),
                        key=lambda f: f.stat().st_mtime, reverse=True)
    if not todo_files:
        return None

    try:
        data = json.loads(todo_files[0].read_text(encoding="utf-8"))
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict) and "todos" in data:
            items = data["todos"]
        else:
            return None

        lines = []
        for item in items:
            status = item.get("status", "unknown")
            content = item.get("content", "")
            icon = {"completed": "[x]", "in_progress": "[~]", "pending": "[ ]"}.get(status, "[?]")
            lines.append(f"- {icon} {content}")
        return "\n".join(lines) if lines else None
    except (json.JSONDecodeError, KeyError, IndexError):
        return None


def _transcript_tail(path, limit=2_000_000):
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - limit))
            return f.read().decode("utf-8", "replace")
    except (OSError, TypeError):
        return ""


def get_active_plan_progress(transcript_path):
    """~/.claude/plans/의 활성 plan 중 이 세션 transcript에 이름이 나온 것만 파싱(읽기 전용).
    연결을 확인하지 못하면 생략한다 — 전역 최신 plan을 고르면 다른 세션의 플랜이 저장됐다(codex 최종 게이트)."""
    plans_dir = (Path.home() / ".claude" / "plans").resolve()
    tail = _transcript_tail(transcript_path) if transcript_path else ""
    if not tail or not plans_dir.exists():
        return None

    # 이 세션의 도구 호출 입력(file_path 등)에 실제로 들어간 플랜 경로만 연결로 인정한다 — 본문의 단순 언급(디렉토리 목록 등)은
    # 연결이 아니다(codex 2차 게이트). 가장 마지막에 다룬 것을 고른다.
    plan_file = None
    for line in tail.splitlines():
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        msg = obj.get("message") if isinstance(obj, dict) else None
        content = msg.get("content") if isinstance(msg, dict) else None
        for c in content if isinstance(content, list) else []:
            inp = c.get("input") if isinstance(c, dict) and c.get("type") == "tool_use" else None
            for v in (inp.values() if isinstance(inp, dict) else []):
                if isinstance(v, str) and v.endswith(".md") and ".completed" not in v:
                    try:
                        cand = Path(v).expanduser().resolve()
                    except (OSError, ValueError):
                        continue
                    if cand.parent == plans_dir and cand.is_file():
                        plan_file = cand
    if plan_file is None:
        return None

    try:
        content = plan_file.read_text(encoding="utf-8")
    except OSError:
        return None

    checked = re.findall(r"- \[x\]\s+(.+)", content)
    unchecked = re.findall(r"- \[ \]\s+(.+)", content)
    total = len(checked) + len(unchecked)

    if total == 0:
        return None

    return {
        "plan_file": plan_file.name,
        "checked": checked,
        "unchecked": unchecked,
        "total": total,
        "done": len(checked),
    }


def resolve_checkpoint_path(root, session_id):
    """저장 위치 결정 → (경로, 프로젝트 루트 여부).
    프로젝트 루트의 checkpoint.md가 없거나 자동 생성본일 때만 그 자리에 쓴다.
    사람이 관리하는 파일은 덮어쓰지 않고, git 추적 파일은 수정하지 않는다."""
    fallback = FALLBACK_DIR / f"{_safe_id(session_id) or 'nosession'}.md"
    if not root:
        return fallback, False
    path = Path(root) / "checkpoint.md"
    if path.exists():
        try:
            head = path.read_text(encoding="utf-8", errors="replace")[:200]
        except OSError:
            return fallback, False
        if not head.startswith(AUTO_HEADER):
            return fallback, False
    tracked = _run_git("ls-files", "--error-unmatch", "--", "checkpoint.md", cwd=root)
    if tracked and tracked.returncode == 0:
        return fallback, False
    return path, True


def _git_exclude(root, name):
    """root가 git 작업트리 안이면 .git/info/exclude(로컬 전용·비추적)에 /<상대경로>를 추가.
    예전 구현은 추적 중인 .gitignore에 append해 남의 repo 작업트리를 더럽혔다."""
    r = _run_git("rev-parse", "--show-toplevel", "--git-path", "info/exclude", cwd=root)
    lines = r.stdout.strip().splitlines() if r and r.returncode == 0 else []
    if len(lines) < 2:
        return
    try:
        top, excl = Path(lines[0]), Path(lines[1])
        if not excl.is_absolute():
            excl = Path(root) / excl  # --git-path는 cwd 기준 상대경로
        entry = "/" + (Path(root).resolve() / name).relative_to(top.resolve()).as_posix()
        text = excl.read_text(encoding="utf-8") if excl.exists() else ""
        if entry in text.splitlines():
            return
        excl.parent.mkdir(parents=True, exist_ok=True)
        with open(excl, "a", encoding="utf-8") as f:
            f.write(("" if not text or text.endswith("\n") else "\n") + entry + "\n")
    except (OSError, ValueError):
        pass


def save_checkpoint(trigger: str):
    """체크포인트 파일 생성/갱신."""
    hook = read_hook_input()
    session_id = _safe_id(hook.get("session_id"))
    project_root = get_project_root()
    checkpoint_path, in_project = resolve_checkpoint_path(project_root, session_id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    branch = get_current_branch(project_root)
    diff_stat = get_git_diff_stat(project_root)
    recent = get_recent_commits(project_root, 3)
    todo = get_todo_state(session_id)
    plan_progress = get_active_plan_progress(hook.get("transcript_path"))

    trigger_label = SAVE_TRIGGERS.get(trigger, trigger)

    content = f"""{AUTO_HEADER}

> 자동 생성됨 | {now} | 트리거: {trigger_label}
> session_id: {session_id or "unknown"}
> 프로젝트: {project_root or "미지정"}
> **다음 세션에서 이 파일을 읽고 작업을 이어가세요.**

## 브랜치: `{branch}`

## 최근 커밋
```
{recent}
```

## 변경 사항
{diff_stat}
"""

    if todo:
        content += f"""
## 작업 목록 (TodoWrite)
{todo}
"""

    if plan_progress:
        done = plan_progress["done"]
        total = plan_progress["total"]
        pct = int(done / total * 100) if total > 0 else 0
        remaining = "\n".join(f"  - [ ] {f}" for f in plan_progress["unchecked"][:10])
        content += f"""
## 플랜 진행 상황
- **파일**: `{plan_progress["plan_file"]}`
- **진행**: {done}/{total} ({pct}%)
- **남은 항목**:
{remaining}
"""

    content += """
---
*이 파일은 PreCompact/SessionEnd 훅이 자동 갱신한다. git repo면 `.git/info/exclude`에만 등록된다(추적 .gitignore는 수정하지 않음).*
"""

    try:
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        with open(checkpoint_path, "w", encoding="utf-8") as f:
            f.write(content)
        if in_project:
            _git_exclude(project_root, "checkpoint.md")
        print(f"[checkpoint] {trigger_label} 저장 완료: {checkpoint_path}")
    except OSError as e:
        print(f"[checkpoint] 저장 실패: {e}", file=sys.stderr)


def _printable(path):
    """SessionStart stdout(모델 컨텍스트)에 싣는 경로의 제어문자를 이스케이프한다 — 파일명으로 줄을 끼워 넣지 못하게(codex 3차)."""
    return re.sub(r"[\x00-\x1f\x7f]", lambda m: "\\x%02x" % ord(m.group(0)), str(path))


def _auto_meta(path):
    """자동 생성 체크포인트의 헤더를 엄격히 읽는다 → {when, sid, project} 또는 None.
    자동 헤더·session_id·한 줄 날짜 형식이 모두 맞아야 한다 — 위조 파일의 임의 줄이 SessionStart 컨텍스트로 새어 나가던
    문제(codex 2차 게이트). 출력에는 검증된 날짜와 우리가 만든 경로만 쓴다."""
    try:
        head = Path(path).read_text(encoding="utf-8", errors="replace")[:800]
    except OSError:
        return None
    if not head.startswith(AUTO_HEADER):
        return None
    when = re.search(r"^> 자동 생성됨 \| (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \|", head, re.MULTILINE)
    sid = re.search(r"^> session_id: ([A-Za-z0-9_-]{1,80})$", head, re.MULTILINE)
    proj = re.search(r"^> 프로젝트: ([^\n\r\x00-\x1f]{1,1000})$", head, re.MULTILINE)
    if not (when and sid and proj):
        return None
    return {"when": when.group(1), "sid": sid.group(1), "project": proj.group(1).strip()}


def _notify_fallback(root):
    """사람이 관리하거나 git 추적 중인 checkpoint.md 때문에 state/checkpoints/로 빠진 스냅샷 중 이 프로젝트·다른 세션의
    최신 것을 알린다 — 저장만 하고 아무도 찾지 않던 경로(2026-10-02 codex 최종 게이트)."""
    if not FALLBACK_DIR.is_dir():
        return
    current = _safe_id(read_hook_input().get("session_id"))
    # 상한 없이 전부 보되(헤더 800바이트만 읽는다) 우리가 만드는 파일명(<session_id>.md)만 인정하고, 프로젝트·세션으로
    # 거른 것 중 최신을 고른다 — 상한을 먼저 걸면 다른 프로젝트 파일에 밀려 못 찾았다(codex 2·3차)
    files = sorted((f for f in FALLBACK_DIR.glob("*.md") if re.fullmatch(r"[A-Za-z0-9_-]{1,80}\.md", f.name)),
                   key=lambda f: f.stat().st_mtime, reverse=True)
    for f in files:
        meta = _auto_meta(f)
        if not meta or meta["project"] != str(root) or (current and meta["sid"] == current):
            continue
        print(f"[checkpoint] 이전 세션의 자동 체크포인트(프로젝트 파일 대신 별도 보관) ({meta['when']} 저장): {_printable(f)}")
        return


def notify_on_session_start():
    """SessionStart: 프로젝트 루트의 checkpoint.md를 알린다 (SessionStart stdout = 모델 컨텍스트).
    자동 생성본이 지금 세션 것이면(compact·resume 재발화) 알리지 않는다 — 자기충족 주입 방지."""
    root = get_project_root()
    if not root:
        return
    _notify_fallback(root)
    path = Path(root) / "checkpoint.md"
    if not path.is_file():
        return
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:600]
    except OSError:
        return
    if head.startswith(AUTO_HEADER):
        meta = _auto_meta(path)
        current = _safe_id(read_hook_input().get("session_id"))
        if meta and current and meta["sid"] == current:
            return
        when = f" ({meta['when']} 저장)" if meta else ""
        print(f"[checkpoint] 이전 세션이 남긴 자동 체크포인트가 있다{when}: {_printable(path)} — 작업 상태 스냅샷(git 변경·할 일)")
    else:
        print(f"[checkpoint] 프로젝트 루트에 checkpoint.md가 있다: {_printable(path)} — 이어받을 작업 상태가 기록돼 있을 수 있다")


def main():
    if len(sys.argv) < 2:
        print("사용법: python3 checkpoint-save.py [precompact|sessionend|sessionstart|stop]", file=sys.stderr)
        sys.exit(1)

    trigger = sys.argv[1].lower()
    if trigger not in ("precompact", "sessionend", "sessionstart", "stop"):
        print(f"[checkpoint] 알 수 없는 트리거: {trigger}", file=sys.stderr)
        sys.exit(1)

    # Stop은 세션 끝이 아니라 응답이 끝날 때마다 발화한다 — 매 턴 저장이 '이전 세션 체크포인트'
    # 주입을 같은 세션 안에서 매번 참으로 만들어 저장하지 않는다(기존 훅 등록 호환용 no-op).
    if trigger == "stop":
        return

    # 훅 실패가 세션을 방해하지 않도록 예외는 삼키고 exit 0
    try:
        if trigger == "sessionstart":
            notify_on_session_start()
        else:
            save_checkpoint(trigger)
    except Exception as e:
        print(f"[checkpoint] 내부 오류 (무시): {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
