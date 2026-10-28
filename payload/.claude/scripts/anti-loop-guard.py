#!/usr/bin/env python3
"""
Anti-Loop Guard - 무한 루프 방지 시스템 (Layer 1: Core Guard Script)

Claude Code 훅에서 호출되어 도구 반복 호출, 압축 빈도, 플랜 파일 잔류를 감지/차단.
Phase 0: 상태 파일(.task-state.md) 기반 컨텍스트 복원
Phase 1: 스마트 파일 읽기 감지 + 의미적 루프 감지
Phase 2: 근본 원인 분석 + MD 인시던트 로깅

사용법:
    python3 anti-loop-guard.py pretooluse   # PreToolUse 훅에서 호출
    python3 anti-loop-guard.py posttooluse  # PostToolUse 훅에서 호출 (PostToolUseFailure 입력도 처리)
    python3 anti-loop-guard.py precompact   # PreCompact 훅에서 호출
    python3 anti-loop-guard.py health       # 세션 건강도 리포트
    python3 anti-loop-guard.py analyze      # 루프 근본 원인 분석
    python3 anti-loop-guard.py reset        # 상태 리셋

상태 파일: ~/.claude/state/anti-loop/<session_id>[__<agent_id>].json (세션·에이전트별, 훅 stdin 키)
프로젝트 기준(persistent 키·.task-state.md): $CLAUDE_PROJECT_DIR

[2026-09-30] 예전에는 상태를 os.getcwd()/.claude/에 두어, 셸이 cd할 때마다 상태가 새 파일로
흩어지고 같은 cwd를 쓰는 동시 에이전트끼리 이력이 섞였다. 훅은 셸이 cd한 곳에서 돌기 때문에
cwd·git 루트를 쓰지 않는다. 경고도 exit 0 stderr로 내면 모델에 가지 않는다(공식 hooks 문서) —
SessionStart는 stdout, 도구 이벤트는 hookSpecificOutput.additionalContext로 내고, PreCompact
경고는 전달 채널이 없어 다음 SessionStart(compact)·도구 이벤트로 넘긴다.
"""

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

# === 기존 설정 상수 ===
TOOL_REPEAT_WARN_THRESHOLD = 2
TOOL_REPEAT_BLOCK_THRESHOLD = 3
COMPACT_FREQ_WINDOW_SEC = 600
COMPACT_FREQ_THRESHOLD = 3
TOOL_HISTORY_MAX = 50
# [2026-09-30] 상태는 cwd가 아니라 홈의 세션별 파일 (~/.claude/.gitignore의 **/state/로 백업 repo에서 제외)
STATE_DIR = Path.home() / ".claude" / "state" / "anti-loop"
PENDING_NOTICES_MAX = 5            # 다음 이벤트로 넘길 보류 경고 최대 수

# === Phase 1 신규 상수 ===
FILE_READ_WARN_THRESHOLD = 5      # 같은 파일 동일 파라미터 5회 → 경고
FILE_READ_BLOCK_THRESHOLD = 7     # 같은 파일 동일 파라미터 7회 → 차단
TIME_GAP_RESET_SEC = 30           # 30초 이상 간격 → 카운트 리셋
POST_COMPACT_GRACE = 3            # 압축 직후 3회 무조건 허용
SEMANTIC_PATTERN_WINDOW = 24      # 최근 24개 도구 호출 (P0-3: 12→24 확장)
SEMANTIC_LOOP_THRESHOLD = 2       # 동일 패턴 2회 반복 = 경고
# [2026-07-27] 퍼지 매칭의 최근성 요구. 이 값보다 오래된 위치에서 패턴이 끝났으면
# '진행 중인 루프'가 아니므로 카운트하지 않는다. 없으면 접근 방식을 바꿔도 해제되지 않는다.
SEMANTIC_RECENT_TAIL = 6          # 다른 도구 6개면 탐지 해제
SEMANTIC_LOOP_BLOCK = 3            # 동일 패턴 3회 반복 = 차단

# === 파일 크기 상수 ===

MAX_CONTENT_SIZE = 30000             # 파일 크기 ~30KB 이상 시 분할 읽기 권장
# === P0-2: 파일명 기반 절대 카운터 상수 ===
FILE_ABSOLUTE_WARN = 15            # 동일 파일 15회 읽기 → 경고
FILE_ABSOLUTE_BLOCK = 20           # 동일 파일 20회 읽기 → 차단
FILE_WHITELIST_WARN = 30           # 화이트리스트 파일 30회 → 경고
FILE_WHITELIST_BLOCK = 40          # 화이트리스트 파일 40회 → 차단

# === P0-4: Write 도구 추적 상수 ===
FILE_WRITE_WARN = 10               # 동일 파일 Write 10회 → 경고
FILE_WRITE_BLOCK = 15              # 동일 파일 Write 15회 → 차단

# === 크로스-세션 상수 ===
PERSISTENT_FILE = Path.home() / ".claude" / "anti-loop-persistent.json"
CROSS_SESSION_FILE_THRESHOLD = 10  # 크로스-세션 동일 파일 읽기 10회 → 차단
CROSS_SESSION_WHITELIST_THRESHOLD = 30  # 화이트리스트(설정 파일)는 완화 임계
SESSION_HISTORY_MAX = 20           # 최근 20개 세션 이력 보존

CONFIG_WHITELIST = [
    "package.json", "tsconfig.json", "CLAUDE.md",
    ".claude/settings.local.json", ".claude/settings.json", "config.json",
    ".env", ".gitignore", "Cargo.toml", "pyproject.toml",
]

# === Phase 2 신규 상수 ===
INCIDENTS_PATH = Path.home() / ".claude" / "loop-incidents.md"
INCIDENTS_MAX = 100

# [2026-09-30] 플랜 완료 판정은 명시 마커 줄만 인정 (첫 5줄 중 한 줄 전체가 마커)
PLAN_DONE_MARKER = re.compile(r"^\s*(STATUS:\s*COMPLETED|상태:\s*완료)\s*$", re.IGNORECASE)

# === P1-2: No-op Edit 감지 상수 ===
NOOP_EDIT_WARN = 3                 # 동일 파일 no-op Edit 3회 → 경고
NOOP_EDIT_BLOCK = 5                # 동일 파일 no-op Edit 5회 → 차단

# === P3-1: Persistent 정리 상수 ===
PROJECT_EXPIRY_DAYS = 90           # 90일+ 미접근 프로젝트 삭제
FILE_EXPIRY_DAYS = 30              # 30일+ 미접근 file_reads 엔트리 삭제

# === P3-2: 패턴 감지 결과 보존 상수 ===
DETECTED_PATTERNS_MAX = 20         # 감지된 패턴 최대 보존 수

# 의미적 루프 패턴 5종 (도구명 시퀀스)
SEMANTIC_PATTERNS = [
    ["Read", "Edit", "Read", "Edit"],
    ["Read", "Grep", "Read", "Grep"],
    ["Bash", "Read", "Bash", "Read"],
    ["Glob", "Read", "Glob", "Read"],
    ["Edit", "Bash", "Edit", "Bash"],
    # P0-4: Write 도구 포함 패턴
    ["Write", "Bash", "Write", "Bash"],
    ["Write", "Read", "Write", "Read"],
]

# 루프 유형별 근본 원인 분석 테이블
ROOT_CAUSE_TABLE = {
    "tool_repeat": {
        "causes": ["경로 오류", "권한 부족", "의존성 누락", "명령어 오타"],
        "actions": ["대안 도구/경로 시도", "에러 메시지 분석", "의존성 설치 확인"],
    },
    "file_repeat": {
        "causes": ["컨텍스트 유실(압축)", "offset/limit 미사용", "파일 변경 미감지"],
        "actions": ["offset/limit 분할 읽기", ".task-state.md 참조", "요약 파일 생성"],
    },
    "semantic": {
        "causes": ["해결책 미작동", "요구사항 오해", "동일 에러 반복"],
        "actions": ["접근 방식 전환", "에러 메시지 비교", "사용자에게 질문"],
    },
    "compact_freq": {
        "causes": ["대용량 파일 반복 읽기", "컨텍스트 과소비"],
        "actions": ["요약 파일 생성", "범위 축소", "offset/limit 활용"],
    },
}


def _normalize_path(p):
    """경로를 소문자 + forward-slash로 정규화."""
    return p.replace("\\", "/").lower().rstrip("/")



def _format_file_display(path_key):
    """전체 경로 키에서 사용자 표시용 파일명 추출."""
    return Path(path_key).name

def _safe_id(value):
    """파일명용 식별자 정규화 — 경로 구분자·점을 치환해 상태 디렉토리 밖으로 못 나가게 한다."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(value or ""))[:100]


def get_state_path():
    """세션·에이전트별 상태 파일 경로 (2026-09-30 재작성).

    키는 훅 stdin의 session_id와 agent_id(서브에이전트 안에서만 오는 공식 필드)다.
    예전 키 CLAUDE_AGENT_ID 환경변수는 공식 문서에 없는 변수라 쓰지 않는다.
    훅 밖 수동 실행(health/analyze/reset)은 stdin을 읽지 않고 가장 최근에 갱신된 상태 파일을 쓴다.
    한 프로세스 안에서는 1회만 결정한다 — reset이 파일을 지운 뒤 다시 고르면 다른 세션 파일을 덮어쓴다.
    """
    global _STATE_PATH
    if _STATE_PATH is None:
        _STATE_PATH = _resolve_state_path()
    return _STATE_PATH


def _resolve_state_path():
    hook_input = read_hook_input()
    sid = _safe_id(hook_input.get("session_id"))
    if sid:
        aid = _safe_id(hook_input.get("agent_id"))
        return STATE_DIR / (f"{sid}__{aid}.json" if aid else f"{sid}.json")
    if _MANUAL_RUN:
        try:
            files = list(STATE_DIR.glob("*.json"))
            if files:
                return max(files, key=lambda p: p.stat().st_mtime)
        except OSError:
            pass
    return STATE_DIR / "_nosession.json"


def _project_dir():
    """세션이 시작된 프로젝트 루트($CLAUDE_PROJECT_DIR). 훅 밖 수동 실행이면 None."""
    pd = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if pd and os.path.isdir(pd):
        return Path(pd)
    return None


def _git_exclude(root, name):
    """root가 git 작업트리 안이면 .git/info/exclude(로컬 전용·비추적)에 /<상대경로>를 추가.
    추적 중인 .gitignore는 건드리지 않는다 — 사용자 repo 작업트리를 더럽히지 않기 위함."""
    try:
        r = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel", "--git-path", "info/exclude"],
            capture_output=True, text=True, timeout=3,
        )
        lines = r.stdout.strip().splitlines() if r.returncode == 0 else []
        if len(lines) < 2:
            return
        top, excl = Path(lines[0]), Path(lines[1])
        if not excl.is_absolute():
            excl = Path(root) / excl  # --git-path는 -C 디렉토리 기준 상대경로
        entry = "/" + (Path(root).resolve() / name).relative_to(top.resolve()).as_posix()
        text = excl.read_text(encoding="utf-8") if excl.exists() else ""
        if entry in text.splitlines():
            return
        excl.parent.mkdir(parents=True, exist_ok=True)
        with open(excl, "a", encoding="utf-8") as f:
            f.write(("" if not text or text.endswith("\n") else "\n") + entry + "\n")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass


# === [2026-09-30] 모델 전달 경고 ===
# exit 0 훅의 stderr는 디버그 로그에만 남고, 도구 이벤트의 plain stdout도 모델에 가지 않는다.
# 경고는 여기 모아 이벤트별 채널로 내보낸다 (디버그 로그용 stderr 사본은 유지).
_NOTICES = []


def _warn(msg):
    """모델에 전달할 경고 누적."""
    _NOTICES.append(msg)
    print(msg, file=sys.stderr)


def _context_output(event_name):
    """누적 경고를 hookSpecificOutput.additionalContext로 담은 출력 dict (경고 없으면 {})."""
    if not _NOTICES:
        return {}
    return {"hookSpecificOutput": {"hookEventName": event_name, "additionalContext": "\n".join(_NOTICES)}}


# === P2-2: DS-1 — 파일 잠금 (Windows/Unix 겸용) ===

@contextmanager
def _file_lock(f):
    """파일 잠금 컨텍스트 매니저. 3회 재시도 후 포기 (경고만)."""
    locked = False
    for attempt in range(3):
        try:
            if platform.system() == "Windows":
                import msvcrt
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, max(1, os.fstat(f.fileno()).st_size or 1))
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
            break
        except (OSError, IOError):
            time.sleep(0.1)
    if not locked:
        print("[Anti-Loop Guard] 파일 잠금 획득 실패 (계속 진행)", file=sys.stderr)
    try:
        yield locked
    finally:
        if locked:
            try:
                if platform.system() == "Windows":
                    import msvcrt
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, max(1, os.fstat(f.fileno()).st_size or 1))
                else:
                    import fcntl
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except (OSError, IOError):
                pass


def load_state():
    """현재 훅 세션의 상태 로드. session_id는 훅 stdin 값으로 맞춘다."""
    state = _load_state_file(get_state_path())
    sid = read_hook_input().get("session_id")
    if sid and isinstance(state, dict):
        state["session_id"] = str(sid)
    return state


def _load_state_file(path):
    """상태 파일 로드. 없거나 손상 시 .bak에서 복원 시도."""
    bak = path.with_suffix(".json.bak")
    # 1차: 원본 파일 시도
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                with _file_lock(f):
                    content = f.read()
                    return json.loads(content)
    except (json.JSONDecodeError, OSError, KeyError):
        pass
    # 2차: .bak 파일에서 복원
    try:
        if bak.exists():
            with open(bak, "r", encoding="utf-8") as f:
                data = json.load(f)
            print("[Anti-Loop Guard] .bak 파일에서 상태 복원 성공", file=sys.stderr)
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return _initial_state()


def save_state(state):
    """상태 파일 원자적 저장 (백업 후 임시파일 → rename)."""
    path = get_state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"[Anti-Loop Guard] 상태 디렉토리 생성 실패 (저장 생략): {e}", file=sys.stderr)
        return
    # .bak 백업
    if path.exists():
        try:
            shutil.copy2(str(path), str(path.with_suffix(".json.bak")))
        except OSError:
            pass
    tmp = path.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            with _file_lock(f):
                json.dump(state, f, indent=2, ensure_ascii=False)
        tmp.replace(path)
    except OSError:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _get_project_key():
    """현재 프로젝트의 persistent 키 반환 ($CLAUDE_PROJECT_DIR, 정규화).
    [2026-09-30] git rev-parse/getcwd는 셸이 cd한 repo를 따라가 키가 흩어지고, 세션 완료 마킹이
    다른 키에서 세션을 못 찾아 실패했다. cwd는 훅 밖 수동 실행에서만 쓴다."""
    pd = _project_dir()
    return _normalize_path(str(pd) if pd else os.getcwd())


def load_persistent():
    """크로스-세션 persistent 상태 로드 (.bak 복원 지원)."""
    bak = PERSISTENT_FILE.with_suffix(".json.bak")
    # 1차: 원본 파일
    try:
        if PERSISTENT_FILE.exists():
            with open(PERSISTENT_FILE, "r", encoding="utf-8") as f:
                with _file_lock(f):
                    content = f.read()
                    return json.loads(content)
    except (json.JSONDecodeError, OSError):
        pass
    # 2차: .bak 복원
    try:
        if bak.exists():
            with open(bak, "r", encoding="utf-8") as f:
                data = json.load(f)
            print("[Anti-Loop Guard] persistent .bak 복원 성공", file=sys.stderr)
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return {"projects": {}, "last_updated": 0}


def save_persistent(pdata):
    """크로스-세션 persistent 상태 원자적 저장 (백업 포함)."""
    pdata["last_updated"] = time.time()
    PERSISTENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    # .bak 백업
    if PERSISTENT_FILE.exists():
        try:
            shutil.copy2(str(PERSISTENT_FILE), str(PERSISTENT_FILE.with_suffix(".json.bak")))
        except OSError:
            pass
    tmp = PERSISTENT_FILE.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            with _file_lock(f):
                json.dump(pdata, f, indent=2, ensure_ascii=False)
        tmp.replace(PERSISTENT_FILE)
    except OSError:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _get_project_persistent(pdata):
    """현재 프로젝트의 persistent 데이터 반환 (없으면 초기화)."""
    key = _get_project_key()
    if key not in pdata["projects"]:
        pdata["projects"][key] = {
            "file_reads": {},
            "sessions": [],
            "cross_patterns": [],
        }
    return pdata["projects"][key]


def _initial_state():
    """초기 상태 딕셔너리 (Phase 1 필드 포함)."""
    return {
        "session_start": time.time(),
        "compact_count": 0,
        "compact_timestamps": [],
        "tool_history": [],
        "consecutive_fail": {},
        "last_activity": time.time(),
        # Phase 1 신규 필드
        "file_reads": {},
        "last_results": {},
        "post_compact_grace": {},
        # P0-4: Write 도구 추적
        "file_writes": {},
        # P1-2: No-op Edit 감지
        "noop_edit_count": {},
        # P3-2: 패턴 감지 결과 보존
        "detected_patterns": [],
    }


def compute_hash(data):
    """입력 데이터의 SHA-256 해시 (첫 12자)."""
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


_HOOK_INPUT = None
_STATE_PATH = None
_MANUAL_RUN = False  # main()이 health/analyze/reset에서 True로 — 이때는 stdin을 읽지 않는다


def read_hook_input():
    """stdin에서 JSON 훅 입력 읽기. 1회만 읽고 캐시한다(상태 경로 결정과 서브커맨드가 같이 쓴다)."""
    global _HOOK_INPUT
    if _HOOK_INPUT is None:
        _HOOK_INPUT = {}
        if not _MANUAL_RUN:
            try:
                raw = sys.stdin.read()
                if raw.strip():
                    data = json.loads(raw)
                    if isinstance(data, dict):
                        _HOOK_INPUT = data
            except (ValueError, OSError):
                pass
    return _HOOK_INPUT


def _get_actionable_advice(file_path, count, tool_type="Read"):
    """P1-4: DX-1 — 파일/도구별 구체적 조언 생성."""
    advice = []
    if tool_type == "Write":
        advice.append("Write 대신 Edit 부분 수정 권장")
        return " | ".join(advice)
    try:
        size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
    except OSError:
        size = 0
    if size >= MAX_CONTENT_SIZE:  # ~30KB ≈ ~1000줄
        advice.append(
            f"대형 파일({size // 1024}KB) — 서브에이전트에 분석 위임 권장. "
            f"예: Read(offset=0, limit=100) 분할 읽기"
        )
    else:
        advice.append("요약 변수 생성 후 참조 권장")
    return " | ".join(advice)


def _is_whitelisted(file_path):
    """설정 파일 화이트리스트 체크. casefold 비교 — 크로스-세션 경로의 fkey는
    소문자 정규화된 경로라서 대소문자 구분 비교로는 CLAUDE.md·Cargo.toml이
    화이트리스트로 인식되지 않았다(2026-08-09 codex 검수 발견)."""
    if not file_path:
        return False
    fp = str(file_path).casefold()
    name = _format_file_display(file_path).casefold()
    for wl in CONFIG_WHITELIST:
        wlc = wl.casefold()
        if fp.endswith(wlc) or name == Path(wlc).name:
            return True
    return False


def _cross_session_threshold(file_path):
    """크로스-세션 차단/경고 임계 — 화이트리스트(설정 파일)는 완화 임계."""
    return CROSS_SESSION_WHITELIST_THRESHOLD if _is_whitelisted(file_path) else CROSS_SESSION_FILE_THRESHOLD


def _compute_param_hash(tool_name, tool_input):
    """도구별 파라미터 해시 계산 (의미적 루프 감지용)."""
    if tool_name == "Read":
        return compute_hash({
            "tool": tool_name,
            "file": tool_input.get("file_path", ""),
            "offset": tool_input.get("offset", 0),
            "limit": tool_input.get("limit", 0),
        })
    elif tool_name == "Edit":
        old = tool_input.get("old_string", "")[:50]
        return compute_hash({
            "tool": tool_name,
            "file": tool_input.get("file_path", ""),
            "old": old,
        })
    elif tool_name == "Bash":
        return compute_hash({
            "tool": tool_name,
            "cmd": tool_input.get("command", "")[:100],
        })
    elif tool_name == "Grep":
        return compute_hash({
            "tool": tool_name,
            "pattern": tool_input.get("pattern", ""),
            "path": tool_input.get("path", ""),
        })
    elif tool_name == "Glob":
        return compute_hash({
            "tool": tool_name,
            "pattern": tool_input.get("pattern", ""),
            "path": tool_input.get("path", ""),
        })
    elif tool_name == "Write":
        return compute_hash({
            "tool": tool_name,
            "file": tool_input.get("file_path", ""),
        })
    else:
        return compute_hash({"tool": tool_name, "input": tool_input})


# === Phase 1-2: 의미적 루프 감지 ===

def _fuzzy_detect_semantic_loop(history):
    """P0-3: 노이즈 도구를 제거한 뒤 패턴 매칭 (퍼지 매칭).

    각 SEMANTIC_PATTERN에 대해 패턴에 포함된 도구만 필터링한 뒤 정확 매칭.
    Returns: max_count (int) - 가장 많이 반복된 횟수
    """
    tools = [h.get("tool", "") for h in history[-SEMANTIC_PATTERN_WINDOW:]]

    max_count = 0
    for pattern in SEMANTIC_PATTERNS:
        pattern_set = set(pattern)
        # 패턴에 포함된 도구만 필터링 (원본 위치를 함께 보존)
        filtered = [(idx, tool) for idx, tool in enumerate(tools) if tool in pattern_set]
        # 필터링된 시퀀스에서 정확 매칭
        count = 0
        last_end = None
        pat_len = len(pattern)
        for i in range(len(filtered) - pat_len + 1):
            if [tool for _, tool in filtered[i:i + pat_len]] == pattern:
                count += 1
                last_end = filtered[i + pat_len - 1][0]
        # [2026-07-27] 최근성 요구. 필터링이 사이에 낀 다른 도구를 전부 제거하므로,
        # 이 조건이 없으면 접근 방식을 바꿔도 옛 패턴이 윈도우 밖으로 밀려날 때까지
        # 차단이 계속된다 — "다른 접근을 쓰라"는 처방을 따라도 해제되지 않는 상태.
        if last_end is not None and last_end < len(tools) - SEMANTIC_RECENT_TAIL:
            continue
        max_count = max(max_count, count)

    return max_count


def _detect_semantic_loop(state):
    """최근 도구 호출에서 의미적 루프 패턴 감지.

    Returns: (detected: bool, pattern_name: str, repeat_count: int)
    """
    history = state.get("tool_history", [])
    if len(history) < SEMANTIC_PATTERN_WINDOW:
        return False, "", 0

    recent = history[-SEMANTIC_PATTERN_WINDOW:]

    for pattern in SEMANTIC_PATTERNS:
        pat_len = len(pattern)
        # 패턴 매칭: 도구명 + 파라미터 해시 + 결과 해시 모두 동일해야 루프
        matches = 0
        i = 0
        first_match_hashes = None

        while i <= len(recent) - pat_len:
            # 도구명 매칭
            tool_names = [e.get("tool", "") for e in recent[i:i + pat_len]]
            if tool_names == pattern:
                param_hashes = tuple(e.get("param_hash", "") for e in recent[i:i + pat_len])
                result_hashes = tuple(e.get("result_hash", "") for e in recent[i:i + pat_len])

                if first_match_hashes is None:
                    first_match_hashes = (param_hashes, result_hashes)
                    matches = 1
                elif param_hashes == first_match_hashes[0] and result_hashes == first_match_hashes[1]:
                    matches += 1

                i += pat_len
            else:
                i += 1

        if matches >= SEMANTIC_LOOP_THRESHOLD:
            pat_name = "→".join(pattern)
            return True, pat_name, matches

    # P0-3: 퍼지 매칭 count도 확인
    history = state.get("tool_history", [])
    fuzzy_count = _fuzzy_detect_semantic_loop(history)
    if fuzzy_count >= SEMANTIC_LOOP_THRESHOLD:
        # 퍼지 매칭에서 감지된 경우, 가장 높은 카운트의 패턴명 찾기
        tools = [h.get("tool", "") for h in history[-SEMANTIC_PATTERN_WINDOW:]]
        best_pattern = "fuzzy"
        for pattern in SEMANTIC_PATTERNS:
            pattern_set = set(pattern)
            filtered = [t for t in tools if t in pattern_set]
            count = 0
            pat_len = len(pattern)
            for i in range(len(filtered) - pat_len + 1):
                if filtered[i:i + pat_len] == pattern:
                    count += 1
            if count == fuzzy_count:
                best_pattern = "→".join(pattern)
                break
        return True, best_pattern, fuzzy_count

    return False, "", 0


def _detect_cross_session_loop(proj):
    """크로스-세션 파일 접근 패턴 분석.

    각 세션의 '가장 많이 읽은 파일 Top 3'를 비교.
    3+ 세션 연속 동일 파일 집합이면 루프 경고.

    Returns: (detected: bool, file_set: set, session_count: int)
    """
    sessions = proj.get("sessions", [])
    file_reads = proj.get("file_reads", {})

    if len(sessions) < 3:
        return False, set(), 0

    # 각 세션별 Top 3 파일 집합 구성
    session_file_sets = []
    for sess in sessions[-6:]:  # 최근 6개 세션만 분석
        sid = sess.get("id", "")
        # 이 세션에서 읽힌 파일과 횟수
        sess_files = {}
        for fname, info in file_reads.items():
            if sid in info.get("sessions", []):
                sess_files[fname] = info.get("total_count", 0)
        # Top 3 파일
        top3 = sorted(sess_files.keys(), key=lambda f: -sess_files[f])[:3]
        session_file_sets.append(frozenset(top3))

    # 연속 동일 파일 집합 감지
    if len(session_file_sets) < 3:
        return False, set(), 0

    max_streak = 1
    current_streak = 1
    streak_set = session_file_sets[0]

    for i in range(1, len(session_file_sets)):
        # 2개 이상 겹치면 '동일 패턴'으로 판정
        overlap = session_file_sets[i] & session_file_sets[i - 1]
        if len(overlap) >= 2 and len(session_file_sets[i]) >= 2:
            current_streak += 1
            if current_streak > max_streak:
                max_streak = current_streak
                streak_set = session_file_sets[i]
        else:
            current_streak = 1

    if max_streak >= 3:
        return True, set(streak_set), max_streak

    return False, set(), 0


# === 서브커맨드: pretooluse ===

def cmd_pretooluse():
    """PreToolUse 훅: 동일 도구 연속 실패 감지 + 스마트 파일 읽기 감지."""
    hook_input = read_hook_input()
    state = load_state()

    tool_name = hook_input.get("tool_name", "unknown")
    tool_input = hook_input.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    now = time.time()

    # --- 기존 로직: 동일 도구 연속 실패 감지 ---
    if tool_name == "Bash":
        hash_key = compute_hash({"tool": tool_name, "cmd": tool_input.get("command", "")})
    else:
        hash_key = compute_hash({"tool": tool_name, "input": tool_input})

    fail_count = state["consecutive_fail"].get(hash_key, 0)

    if fail_count >= TOOL_REPEAT_BLOCK_THRESHOLD:
        state["consecutive_fail"][hash_key] = fail_count
        save_state(state)
        _log_incident(state, "tool_repeat", tool_name, hash_key, fail_count)
        output = {
            "decision": "block",
            "reason": (
                f"[Anti-Loop Guard] 동일 도구 호출이 연속 {fail_count}회 실패했습니다. "
                f"무한 루프 방지를 위해 차단합니다. "
                f"다른 접근 방법을 시도하세요. "
                f"(tool={tool_name}, "
                f"{state.get('hash_to_context', {}).get(hash_key, {}).get('file', state.get('hash_to_context', {}).get(hash_key, {}).get('cmd', hash_key[:16]))})"
            ),
        }
        json.dump(output, sys.stdout, ensure_ascii=False)
        return

    if fail_count >= TOOL_REPEAT_WARN_THRESHOLD:
        msg = (
            f"[Anti-Loop Guard] 주의: 동일 도구 호출이 연속 {fail_count}회 실패했습니다. "
            f"1회 더 실패하면 차단됩니다. "
            f"(tool={tool_name}, "
            f"{state.get('hash_to_context', {}).get(hash_key, {}).get('file', state.get('hash_to_context', {}).get(hash_key, {}).get('cmd', hash_key[:16]))})"
        )
        _warn(msg)

    # --- Phase 1-1: 스마트 파일 읽기 감지 ---
    if tool_name == "Read":
        file_path = tool_input.get("file_path", "")
        offset = tool_input.get("offset", 0)
        limit = tool_input.get("limit", 0)

        if file_path:
            fr = state.setdefault("file_reads", {})
            info = fr.setdefault(file_path, {
                "count": 0, "params": [], "identical_count": 0
            })
            is_whitelisted_file = _is_whitelisted(file_path)

            # 압축 직후 파일별 유예 체크 (화이트리스트 파일은 identical_count 건너뜀)
            grace_map = state.get("post_compact_grace", {})
            file_grace = grace_map.get(file_path, 0)
            if file_grace > 0:
                grace_map[file_path] = file_grace - 1
                state["post_compact_grace"] = grace_map
            elif not is_whitelisted_file:
                # 파라미터 동일 여부 체크 (화이트리스트 제외)
                current_params = {"offset": offset, "limit": limit}
                last_params = info["params"][-1] if info["params"] else None

                if last_params:
                    last_p = {"offset": last_params.get("offset", 0), "limit": last_params.get("limit", 0)}
                    time_gap = now - last_params.get("ts", 0)

                    if current_params == last_p and time_gap < TIME_GAP_RESET_SEC:
                        info["identical_count"] += 1
                    else:
                        # 파라미터 다르거나 시간 간격 충분 → 리셋
                        info["identical_count"] = 0

                    # 임계값 체크
                    ic = info["identical_count"]
                    if ic >= FILE_READ_BLOCK_THRESHOLD:
                        save_state(state)
                        _log_incident(state, "file_repeat", tool_name, file_path, ic)
                        output = {
                            "decision": "block",
                            "reason": (
                                f"[Anti-Loop Guard] 동일 파일을 동일 파라미터로 {ic}회 연속 읽었습니다. "
                                f"offset/limit을 변경하거나 다른 접근을 시도하세요. "
                                f"(file={_format_file_display(file_path)})"
                            ),
                        }
                        json.dump(output, sys.stdout, ensure_ascii=False)
                        return

                    if ic >= FILE_READ_WARN_THRESHOLD:
                        _warn(
                            f"[Anti-Loop Guard] 주의: {_format_file_display(file_path)}을 동일 파라미터로 "
                            f"{ic}회 연속 읽었습니다. {FILE_READ_BLOCK_THRESHOLD}회 시 차단."
                        )

            info["count"] = info.get("count", 0) + 1

            # P0-2: 파일명 기반 절대 카운터 체크 (param_hash 무관)
            abs_count = info["count"]
            is_wl = _is_whitelisted(file_path)
            abs_warn = FILE_WHITELIST_WARN if is_wl else FILE_ABSOLUTE_WARN
            abs_block = FILE_WHITELIST_BLOCK if is_wl else FILE_ABSOLUTE_BLOCK

            if abs_count >= abs_block:
                save_state(state)
                _log_incident(state, "file_repeat", tool_name, file_path, abs_count)
                output = {
                    "decision": "block",
                    "reason": (
                        f"[Anti-Loop Guard] 파일 절대 읽기 횟수 초과: "
                        f"{_format_file_display(file_path)}을 {abs_count}회 읽었습니다. "
                        f"서브에이전트 위임 또는 요약 파일 생성을 권장합니다."
                    ),
                }
                json.dump(output, sys.stdout, ensure_ascii=False)
                return
            elif abs_count >= abs_warn:
                _warn(
                    f"[Anti-Loop Guard] 파일 절대 읽기 경고: {_format_file_display(file_path)}을 "
                    f"{abs_count}회 읽었습니다. {abs_block}회 시 차단."
                )

            info["params"].append({"offset": offset, "limit": limit, "ts": now})
            # params 최대 20개 유지
            if len(info["params"]) > 20:
                info["params"] = info["params"][-20:]

            # --- 크로스-세션 persistent 카운터 ---
            try:
                pdata = load_persistent()
                proj = _get_project_persistent(pdata)
                pfr = proj.setdefault("file_reads", {})
                fkey = _normalize_path(os.path.abspath(file_path))
                pinfo = pfr.setdefault(fkey, {"total_count": 0, "sessions": []})
                pinfo["total_count"] = pinfo.get("total_count", 0) + 1

                # 현재 세션 ID 기록
                session_id = state.get("session_id", "")
                if session_id and session_id not in pinfo.get("sessions", []):
                    pinfo.setdefault("sessions", []).append(session_id)

                # 크로스-세션 임계값 체크 — 설정 파일(화이트리스트)은 세션마다
                # 정당하게 다시 읽히므로 완화 임계를 쓴다(하네스가 자기 설정을
                # 영구 차단해 점검 불능이 되는 자기 방해 방지, 2026-08-09).
                total = pinfo["total_count"]
                sess_count = len(pinfo.get("sessions", []))
                cross_threshold = _cross_session_threshold(fkey)
                if total >= cross_threshold and sess_count >= 2:
                    save_persistent(pdata)
                    save_state(state)
                    output = {
                        "decision": "block",
                        "reason": (
                            f"[Anti-Loop Guard] 크로스-세션 루프 감지: {_format_file_display(fkey)}이 "
                            f"{sess_count}개 세션에 걸쳐 총 {total}회 읽혔습니다. "
                            f"서브에이전트 위임(Task 도구)을 권장합니다."
                        ),
                    }
                    json.dump(output, sys.stdout, ensure_ascii=False)
                    return

                if total >= cross_threshold - 3 and sess_count >= 2:
                    _warn(
                        f"[Anti-Loop Guard] 크로스-세션 주의: {_format_file_display(fkey)}이 {sess_count}개 세션에서 "
                        f"총 {total}회 읽힘. {cross_threshold}회 시 차단."
                    )

                save_persistent(pdata)
            except (OSError, ValueError, json.JSONDecodeError) as e:
                print(f"[ALG] persistent 경고: {e}", file=sys.stderr)

    # --- P0-4: Write 도구 파일 경로 기반 추적 ---
    if tool_name == "Write":
        file_path = tool_input.get("file_path", "")
        if file_path:
            fw = state.setdefault("file_writes", {})
            winfo = fw.setdefault(file_path, {"count": 0})
            winfo["count"] = winfo.get("count", 0) + 1
            wc = winfo["count"]

            if wc >= FILE_WRITE_BLOCK:
                save_state(state)
                _log_incident(state, "file_repeat", tool_name, file_path, wc)
                output = {
                    "decision": "block",
                    "reason": (
                        f"[Anti-Loop Guard] 동일 파일 Write 횟수 초과: "
                        f"{_format_file_display(file_path)}에 {wc}회 쓰기 시도. "
                        f"{_get_actionable_advice(file_path, wc, 'Write')}"
                    ),
                }
                json.dump(output, sys.stdout, ensure_ascii=False)
                return
            elif wc >= FILE_WRITE_WARN:
                _warn(
                    f"[Anti-Loop Guard] Write 경고: {_format_file_display(file_path)}에 "
                    f"{wc}회 쓰기. {FILE_WRITE_BLOCK}회 시 차단."
                )

    # 도구 호출 히스토리 기록 (Phase 1 확장: param_hash 포함)
    param_hash = _compute_param_hash(tool_name, tool_input)
    entry = {
        "tool": tool_name,
        "hash": hash_key,
        "param_hash": param_hash,
        "timestamp": now,
    }
    state["tool_history"].append(entry)
    if len(state["tool_history"]) > TOOL_HISTORY_MAX:
        state["tool_history"] = state["tool_history"][-TOOL_HISTORY_MAX:]

    state["last_activity"] = now
    # PreCompact가 남긴 보류 경고도 함께 전달 (PreCompact에는 모델 전달 채널이 없다)
    _NOTICES[:0] = state.pop("pending_notices", [])
    save_state(state)
    json.dump(_context_output("PreToolUse"), sys.stdout, ensure_ascii=False)


# === 서브커맨드: posttooluse ===

def cmd_posttooluse():
    """PostToolUse 훅: 도구 실행 결과 기록 + 의미적 루프 감지."""
    hook_input = read_hook_input()
    state = load_state()

    tool_name = hook_input.get("tool_name", "unknown")
    tool_input = hook_input.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    # [2026-09-30] Claude Code는 성공 시 tool_response, 실패 시 PostToolUseFailure 이벤트의 error를 보낸다.
    # 예전 코드는 존재하지 않는 tool_output 필드만 읽어 실패 감지가 설치 이래 한 번도 동작하지 않았다.
    event_name = hook_input.get("hook_event_name")
    if event_name not in ("PostToolUse", "PostToolUseFailure"):
        event_name = "PostToolUse"
    tool_output = _response_text(hook_input)
    is_failure = _detect_failure(tool_name, hook_input)

    # 해시 계산
    if tool_name == "Bash":
        hash_key = compute_hash({"tool": tool_name, "cmd": tool_input.get("command", "")})
    else:
        hash_key = compute_hash({"tool": tool_name, "input": tool_input})

    # 해시→컨텍스트 역매핑 저장
    h2c = state.setdefault("hash_to_context", {})
    if tool_name == "Bash":
        cmd_raw = tool_input.get("command", "")
        h2c[hash_key] = {"tool": tool_name, "cmd": cmd_raw[:60]}
    elif tool_name == "Read":
        h2c[hash_key] = {"tool": tool_name, "file": tool_input.get("file_path", "")[-60:]}
    else:
        h2c[hash_key] = {"tool": tool_name}

    # 결과 해시 저장 (의미적 루프 감지용)
    output_str = str(tool_output)[:500] if tool_output else ""
    result_hash = compute_hash({"out": output_str})
    state.setdefault("last_results", {})[hash_key] = result_hash

    # 최근 히스토리에 result_hash 추가
    if state["tool_history"]:
        last_entry = state["tool_history"][-1]
        if last_entry.get("hash") == hash_key:
            last_entry["result_hash"] = result_hash

    # P1-2: RT-4 — No-op Edit 감지
    if tool_name == "Edit":
        output_str = str(tool_output).lower() if tool_output else ""
        old_s = tool_input.get("old_string", "")
        new_s = tool_input.get("new_string", "")
        is_noop = ("no changes" in output_str) or (old_s == new_s and old_s != "")
        if is_noop:
            noop_map = state.setdefault("noop_edit_count", {})
            fp = tool_input.get("file_path", "unknown")
            noop_map[fp] = noop_map.get(fp, 0) + 1
            nc = noop_map[fp]
            if nc >= NOOP_EDIT_BLOCK:
                _log_incident(state, "tool_repeat", "Edit(no-op)", fp, nc)
                save_state(state)
                output = {
                    "decision": "block",
                    "reason": (
                        f"[Anti-Loop Guard] No-op Edit 차단: {_format_file_display(fp)}에 "
                        f"변경 없는 Edit가 {nc}회 반복. "
                        f"old_string/new_string을 재확인하세요."
                    ),
                }
                json.dump(output, sys.stdout, ensure_ascii=False)
                return
            elif nc >= NOOP_EDIT_WARN:
                _warn(
                    f"[Anti-Loop Guard] No-op Edit 경고: {_format_file_display(fp)}에 "
                    f"변경 없는 Edit {nc}회. {NOOP_EDIT_BLOCK}회 시 차단."
                )

    # Track modified files for quality check
    if tool_name in ("Edit", "Write") and not is_failure:
        file_path = tool_input.get("file_path", "")
        if file_path:
            if "modified_files" not in state:
                state["modified_files"] = []
            if file_path not in state["modified_files"]:
                state["modified_files"].append(file_path)

    # Track tool call count
    state["tool_call_count"] = state.get("tool_call_count", 0) + 1

    # P2-3: DS-3 — Stop 도구 감지 시 세션 완료 마킹
    if tool_name == "Stop":
        _mark_session_completed(state)

    # 실패 판정 (is_failure는 위에서 계산)
    if is_failure:
        # '연속'은 바로 앞 호출도 같은 호출의 실패일 때만 센다 — 사이에 다른 호출이 끼면 1부터 다시 센다
        # (2026-10-01 검토 회귀: 누적 카운트가 리셋되지 않아 3회 누적 실패 뒤 그 명령이 세션 내내 차단됐다)
        prev = state.get("last_fail_hash")
        count = (state["consecutive_fail"].get(hash_key, 0) if prev == hash_key else 0) + 1
        state["consecutive_fail"] = {hash_key: count}
        state["last_fail_hash"] = hash_key
        if count >= TOOL_REPEAT_WARN_THRESHOLD:
            ctx = state.get("hash_to_context", {}).get(hash_key, {})
            fail_label = ctx.get("file", ctx.get("cmd", hash_key[:16]))[:60]
            _warn(
                f"[Anti-Loop Guard] 도구 실패 누적: {tool_name} "
                f"({fail_label}) 연속 {count}회 실패. {TOOL_REPEAT_BLOCK_THRESHOLD}회면 같은 호출이 차단된다."
            )
    else:
        # 성공한 호출이 하나라도 끼면 모든 연속 실패를 비운다 — 차단된 호출은 실행되지 않아 스스로 성공할 수 없으므로
        # 다른 작업(코드 수정 등) 뒤에는 다시 시도할 수 있어야 한다
        state["consecutive_fail"] = {}
        state["last_fail_hash"] = None

    # 오래된 실패 카운트 정리
    if len(state["consecutive_fail"]) > 30:
        keys = sorted(state["consecutive_fail"].keys())
        for k in keys[:len(keys) - 30]:
            del state["consecutive_fail"][k]

    # Phase 1-2: 의미적 루프 감지
    detected, pattern_name, repeat_count = _detect_semantic_loop(state)
    if detected:
        # P3-2: PE-3 — 패턴 감지 결과 보존
        dp = state.setdefault("detected_patterns", [])
        dp.append({
            "pattern": pattern_name,
            "count": repeat_count,
            "timestamp": time.time(),
            "fuzzy": "fuzzy" in pattern_name,
        })
        if len(dp) > DETECTED_PATTERNS_MAX:
            state["detected_patterns"] = dp[-DETECTED_PATTERNS_MAX:]

        if repeat_count >= SEMANTIC_LOOP_BLOCK:
            # P0-1: 5회 이상 반복 시 BLOCK 반환
            _log_incident(state, "semantic", pattern_name, "", repeat_count)
            state["last_activity"] = time.time()
            save_state(state)
            output = {
                "decision": "block",
                "reason": (
                    f"[Anti-Loop Guard] 🚫 시맨틱 루프 차단: 동일 패턴이 "
                    f"{repeat_count}회 반복되었습니다. 다른 접근 방식을 사용하세요. "
                    f"(패턴: [{pattern_name}])"
                ),
            }
            json.dump(output, sys.stdout, ensure_ascii=False)
            return
        else:
            _warn(
                f"[Anti-Loop Guard] 의미적 루프 감지! 패턴: [{pattern_name}] "
                f"{repeat_count}회 반복. 접근 방식을 변경하세요."
            )
            _log_incident(state, "semantic", pattern_name, "", repeat_count)

    # Mid-check reminder every 15 tool calls
    call_count = state.get("tool_call_count", 0)
    mod_count = len(state.get("modified_files", []))
    if call_count > 0 and call_count % 15 == 0 and mod_count > 0:
        print(
            f"\n💡 중간 검증 리마인더: {mod_count}개 파일 수정됨 — "
            f"`npx tsc --noEmit` 실행을 고려하세요.",
            file=sys.stderr,
        )

    state["last_activity"] = time.time()
    _NOTICES[:0] = state.pop("pending_notices", [])
    save_state(state)
    if _NOTICES:
        json.dump(_context_output(event_name), sys.stdout, ensure_ascii=False)


def _response_text(hook_input):
    """도구 결과를 문자열로 (결과 해시·no-op 판정용). 실패 이벤트는 error 문자열."""
    if hook_input.get("hook_event_name") == "PostToolUseFailure":
        return str(hook_input.get("error") or "")
    resp = hook_input.get("tool_response", hook_input.get("tool_output", ""))
    if resp is None:
        return ""
    if isinstance(resp, str):
        return resp
    return json.dumps(resp, ensure_ascii=False, sort_keys=True, default=str)


def _detect_failure(tool_name, hook_input):
    """도구 실행 실패 여부 판정 (2026-09-30 재작성).

    - PostToolUseFailure: 실패. 단 is_interrupt(중단)는 루프가 아니므로 세지 않는다.
    - PostToolUse(성공 이벤트): Bash는 종료코드 0이어도 stderr에 에러가 찍힌 경우만 실패로 본다.
      stdout 본문(grep 결과 등)·Read 본문의 'not found'는 실패가 아니다 — 결과 전체를 훑으면 오탐한다.
    - 구 형식 문자열 결과(tool_output)는 예전 규칙 그대로.
    """
    if hook_input.get("hook_event_name") == "PostToolUseFailure":
        return not hook_input.get("is_interrupt", False)
    resp = hook_input.get("tool_response", hook_input.get("tool_output"))
    if tool_name == "Bash":
        if isinstance(resp, dict):
            if resp.get("interrupted"):
                return False
            text = str(resp.get("stderr") or "")
        else:
            text = str(resp or "")
        output_str = text.lower()
        error_patterns = [
            "error:", "fatal:", "command not found",
            "permission denied", "no such file", "traceback",
            "syntaxerror", "typeerror", "nameerror",
            "modulenotfounderror", "filenotfounderror",
        ]
        return any(p in output_str for p in error_patterns)

    if tool_name in ("Read", "Glob") and isinstance(resp, str):
        output_str = resp.lower()
        return "no such file" in output_str or "not found" in output_str

    return False


# === Phase 0: 상태 파일 (.task-state.md) ===

def _update_task_state(state):
    """PreCompact 시 .task-state.md 자동 업데이트."""
    # [2026-09-30] cwd가 아니라 세션 프로젝트 루트 — cwd 기준이면 셸이 cd한 repo마다 파일이 생겼다
    project = _project_dir()
    if project is None:
        return
    task_state_path = project / ".task-state.md"
    now = time.time()

    try:
        # 1. 최근 접근 파일 Top 5 추출
        fr = state.get("file_reads", {})
        top_files = sorted(
            fr.items(),
            key=lambda x: x[1].get("count", 0),
            reverse=True,
        )[:5]

        # 2. 마지막 실패 정보
        last_fails = state.get("consecutive_fail", {})
        top_fails = sorted(last_fails.items(), key=lambda x: -x[1])[:3]

        # 3. MD 파일 생성
        lines = [
            "# Task State (auto-generated by anti-loop-guard.py)",
            f"> 마지막 업데이트: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 읽은 파일 요약 (컨텍스트 복원용)",
            "| 파일 | 접근 횟수 | 마지막 확인 |",
            "|------|:--------:|------------|",
        ]
        for fpath, info in top_files:
            count = info.get("count", 0)
            params = info.get("params", [])
            last_ts = time.strftime(
                "%H:%M:%S", time.localtime(params[-1]["ts"])
            ) if params else "-"
            short = fpath if len(fpath) < 60 else "..." + fpath[-57:]
            lines.append(f"| `{short}` | {count} | {last_ts} |")

        if not top_files:
            lines.append("| (없음) | - | - |")

        if top_fails:
            lines.extend(["", "## 활성 실패 추적"])
            h2c = state.get("hash_to_context", {})
            for h, cnt in top_fails:
                ctx = h2c.get(h, {})
                label = ctx.get("file", ctx.get("cmd", h[:16]))[:60]
                lines.append(f"- {label}: {cnt}회 연속 실패")

        elapsed = int((now - state.get("session_start", now)) / 60)
        lines.extend([
            "",
            "## 세션 통계",
            f"- 압축 횟수: {state.get('compact_count', 0)}",
            f"- 도구 호출: {len(state.get('tool_history', []))}",
            f"- 세션 경과: {elapsed}분",
        ])

        # Session handoff reminder
        handoff_path = project / "session-handoff.md"
        if handoff_path.exists():
            lines.append("")
            lines.append("⚠️ **session-handoff.md 감지** — 컨텍스트 압축 전 핸드오프 파일을 갱신하세요!")
            lines.append("   → 현재 목표, 완료/남은 항목, 핵심 결정사항을 최신 상태로 업데이트")

        task_state_path.write_text("\n".join(lines), encoding="utf-8")
        _git_exclude(project, ".task-state.md")

    except OSError:
        # 실패해도 작업 차단 안 함
        pass


# === 서브커맨드: precompact ===

def cmd_precompact():
    """PreCompact 훅: 압축 빈도 감시 + 상태 보존 + 플랜 파일 정리."""
    state = load_state()
    now = time.time()

    # 1. 압축 카운터 증가
    state["compact_count"] += 1
    state["compact_timestamps"].append(now)

    cutoff = now - COMPACT_FREQ_WINDOW_SEC
    state["compact_timestamps"] = [
        ts for ts in state["compact_timestamps"] if ts > cutoff
    ]
    recent_count = len(state["compact_timestamps"])

    # 2. 압축 빈도 경고 (P2-4: health 점수 첨부)
    if recent_count >= COMPACT_FREQ_THRESHOLD:
        hs = _quick_health_score(state)
        msg = (
            f"[Anti-Loop Guard] 경고: {COMPACT_FREQ_WINDOW_SEC // 60}분 내 "
            f"{recent_count}회 압축 발생! 컨텍스트 소모가 과도합니다. "
            f"큰 파일 반복 읽기를 줄이고, offset/limit을 사용하세요. "
            f"(건강도: {hs}/100)"
        )
        print(msg, file=sys.stderr)
        # PreCompact는 systemMessage를 버리고 stdout도 모델에 가지 않는다(공식 문서) →
        # 압축 직후 SessionStart(compact)나 다음 도구 이벤트에서 전달되도록 보류한다
        pending = state.setdefault("pending_notices", [])
        pending.append(msg)
        state["pending_notices"] = pending[-PENDING_NOTICES_MAX:]
        _log_incident(state, "compact_freq", "PreCompact", "", recent_count)

    # 3. 압축 후 파일별 유예 설정 (최근 읽힌 Top 3 파일만)
    fr = state.get("file_reads", {})
    top_files = sorted(
        fr.items(),
        key=lambda x: x[1].get("count", 0),
        reverse=True,
    )[:3]
    grace_map = {}
    for fname, _ in top_files:
        grace_map[fname] = POST_COMPACT_GRACE
    state["post_compact_grace"] = grace_map

    # 4. 플랜 파일 정리
    _cleanup_plan_files()

    # 5. Phase 0: .task-state.md 자동 업데이트
    _update_task_state(state)

    # 6. 세션 건강도 요약
    elapsed = now - state.get("session_start", now)
    elapsed_min = int(elapsed / 60)
    tool_count = len(state["tool_history"])
    active_fails = len(state["consecutive_fail"])

    print(
        f"[Anti-Loop Guard] 압축 #{state['compact_count']} | "
        f"세션 {elapsed_min}분 | 도구 호출 {tool_count}회 | "
        f"활성 실패 추적 {active_fails}건",
        file=sys.stderr,
    )

    state["last_activity"] = now
    save_state(state)

    # 7. Persistent: 현재 세션 compact_count 동기화
    try:
        pdata = load_persistent()
        proj = _get_project_persistent(pdata)
        sessions = proj.get("sessions", [])
        sid = state.get("session_id", "")
        if sid and sessions:
            for sess in reversed(sessions):
                if sess.get("id") == sid:
                    sess["compact_count"] = state["compact_count"]
                    break
            save_persistent(pdata)
    except (OSError, KeyError, json.JSONDecodeError) as e:
        print(f"[ALG] compact persistent 경고: {e}", file=sys.stderr)


def _cleanup_plan_files():
    """완료된 플랜 파일을 .completed로 리네임."""
    plans_dir = Path.home() / ".claude" / "plans"
    if not plans_dir.exists():
        return

    for plan_file in plans_dir.glob("*.md"):
        if plan_file.name.endswith(".completed.md"):
            continue
        try:
            content = plan_file.read_text(encoding="utf-8")
            # [2026-09-30] 명시 마커 줄만 인정 — 예전 부분문자열 판정은 '완료 기준' 같은
            # DoD 헤더에도 걸려 진행 중인 플랜을 .completed로 치웠다
            if any(PLAN_DONE_MARKER.match(line) for line in content.splitlines()[:5]):
                new_name = plan_file.with_suffix(".completed.md")
                plan_file.rename(new_name)
                print(
                    f"[Anti-Loop Guard] 완료된 플랜 파일 정리: "
                    f"{plan_file.name} → {new_name.name}",
                    file=sys.stderr,
                )
        except (OSError, UnicodeDecodeError):
            pass


# === Phase 2: MD 인시던트 로깅 ===

def _log_incident(state, loop_type, tool_or_pattern, detail, count):
    """루프 인시던트를 ~/.claude/loop-incidents.md에 기록."""
    try:
        INCIDENTS_PATH.parent.mkdir(parents=True, exist_ok=True)

        # 기존 내용 읽기
        if INCIDENTS_PATH.exists():
            content = INCIDENTS_PATH.read_text(encoding="utf-8")
        else:
            content = (
                "# Loop Incidents Log\n"
                "> anti-loop-guard.py가 루프 감지 시 자동 기록\n\n"
                "## 통계 요약\n"
                "- 총 인시던트: 0건\n"
                "- 가장 빈번한 유형: -\n"
                "- 가장 빈번한 원인: -\n\n"
                "---\n"
                "## 인시던트 기록\n\n"
            )

        # 인시던트 번호 추출 — [2026-09-30] 아카이브까지 합친 최대값 (본 로그만 보면 아카이브로
        # 넘어간 번호가 재사용돼 INC-101이 수백 번 중복됐다)
        existing_ids = re.findall(r"\[INC-(\d+)\]", content)
        archive_path = INCIDENTS_PATH.with_name("loop-incidents-archive.md")
        if archive_path.exists():
            existing_ids += re.findall(r"\[INC-(\d+)\]", archive_path.read_text(encoding="utf-8"))
        next_id = max((int(x) for x in existing_ids), default=0) + 1

        # 근본 원인 분석
        rc = ROOT_CAUSE_TABLE.get(loop_type, {})
        causes = rc.get("causes", ["분석 필요"])
        actions = rc.get("actions", ["수동 확인"])

        # 프로젝트명
        project = (_project_dir() or Path(os.getcwd())).name

        timestamp = time.strftime("%Y-%m-%d %H:%M")
        incident = (
            f"\n### [INC-{next_id:03d}] {timestamp} | {loop_type}\n"
            f"- **프로젝트**: {project}\n"
            f"- **루프 유형**: {loop_type}\n"
            f"- **도구/패턴**: {tool_or_pattern}\n"
            f"- **반복 횟수**: {count}회\n"
            f"- **상세**: {detail}\n"
            f"- **추정 원인**: {', '.join(causes)}\n"
            f"- **권장 조치**: {', '.join(actions)}\n"
        )

        # 인시던트 기록 섹션에 추가
        if "## 인시던트 기록" in content:
            content = content.replace(
                "## 인시던트 기록\n",
                f"## 인시던트 기록\n{incident}",
            )
        else:
            content += incident

        # 통계 요약 업데이트
        content = re.sub(
            r"총 인시던트: \d+건",
            f"총 인시던트: {next_id}건",
            content,
        )
        content = re.sub(
            r"가장 빈번한 유형: .+",
            f"가장 빈번한 유형: {loop_type}",
            content,
        )

        INCIDENTS_PATH.write_text(content, encoding="utf-8")

        # 아카이브 체크
        if next_id > INCIDENTS_MAX:
            _archive_incidents()

    except (OSError, ValueError):
        pass


def _archive_incidents():
    """100건 초과 시 오래된 인시던트를 아카이브로 이동."""
    try:
        content = INCIDENTS_PATH.read_text(encoding="utf-8")
        incidents = re.findall(r"(### \[INC-\d+\].*?)(?=### \[INC-|\Z)", content, re.DOTALL)

        if len(incidents) <= INCIDENTS_MAX:
            return

        # 오래된 것 분리 — 새 인시던트는 '## 인시던트 기록' 바로 아래(맨 앞)에 들어가므로 앞쪽이 최신이다.
        # [2026-09-30] 예전 슬라이스는 앞쪽(최신)을 아카이브해 본 로그가 07-07에 멈췄다.
        to_keep = incidents[:INCIDENTS_MAX]
        to_archive = incidents[INCIDENTS_MAX:]

        # 아카이브 파일에 추가
        archive_path = INCIDENTS_PATH.with_name("loop-incidents-archive.md")
        archive_content = ""
        if archive_path.exists():
            archive_content = archive_path.read_text(encoding="utf-8")
        else:
            archive_content = "# Loop Incidents Archive\n> 오래된 인시던트 보관\n\n"

        archive_content += "\n".join(to_archive)
        archive_path.write_text(archive_content, encoding="utf-8")

        # 메인 파일에서 유지할 것만 남기기
        header_end = content.find("## 인시던트 기록\n")
        if header_end >= 0:
            header = content[:header_end + len("## 인시던트 기록\n")]
            new_content = header + "\n".join(to_keep)
            INCIDENTS_PATH.write_text(new_content, encoding="utf-8")

        print(
            f"[Anti-Loop Guard] {len(to_archive)}건 인시던트 아카이브로 이동",
            file=sys.stderr,
        )
    except OSError:
        pass


# === P2-3: DS-3 — 세션 완료 마킹 ===

def _mark_session_completed(state):
    """현재 세션을 persistent.json에서 completed=True로 마킹."""
    try:
        pdata = load_persistent()
        proj = _get_project_persistent(pdata)
        sessions = proj.get("sessions", [])
        sid = state.get("session_id", "")
        if sid:
            for sess in reversed(sessions):
                if sess.get("id") == sid:
                    sess["completed"] = True
                    break
            save_persistent(pdata)
    except (OSError, KeyError, json.JSONDecodeError) as e:
        print(f"[ALG] session mark 경고: {e}", file=sys.stderr)


# === P2-4: DX-2 — Health 자동 점수 ===

def _quick_health_score(state):
    """경량 건강도 점수 계산 (0-100). cmd_health의 간이 버전."""
    score = 100
    now = time.time()

    # 압축 빈도 감점
    cutoff = now - COMPACT_FREQ_WINDOW_SEC
    recent_compacts = len([
        ts for ts in state.get("compact_timestamps", []) if ts > cutoff
    ])
    if recent_compacts >= COMPACT_FREQ_THRESHOLD:
        score -= 30

    # 활성 실패 감점
    active_fails = state.get("consecutive_fail", {})
    if len(active_fails) > 5:
        score -= 20
    if any(v >= TOOL_REPEAT_BLOCK_THRESHOLD for v in active_fails.values()):
        score -= 30

    # 파일 반복 읽기 감점
    fr = state.get("file_reads", {})
    heavy = sum(1 for v in fr.values() if v.get("identical_count", 0) >= 3)
    if heavy > 0:
        score -= 10

    # 인시던트 수 감점
    dp = state.get("detected_patterns", [])
    if len(dp) >= 5:
        score -= 10

    return max(0, score)




def _migrate_persistent_file_keys(proj):
    """파일명-only 레거시 키를 정리 (전체 경로 키로의 마이그레이션)."""
    pfr = proj.get("file_reads", {})
    legacy_keys = [k for k in pfr if "/" not in k and "\\" not in k]
    for k in legacy_keys:
        del pfr[k]
    if legacy_keys:
        print(f"[Anti-Loop Guard] 레거시 키 {len(legacy_keys)}개 정리", file=sys.stderr)
    return len(legacy_keys)


def _migrate_persistent_project_keys(pdata):
    """대소문자 중복 프로젝트 키를 정규화된 단일 키로 병합."""
    projects = pdata.get("projects", {})
    normalized = {}
    to_delete = []
    to_rename = {}

    for key in list(projects.keys()):
        norm_key = _normalize_path(key)
        if norm_key in normalized:
            existing_key = normalized[norm_key]
            existing = projects[existing_key]
            duplicate = projects[key]
            existing_sessions = existing.get("sessions", [])
            existing_ids = {s.get("id") for s in existing_sessions if isinstance(s, dict)}
            for sess in duplicate.get("sessions", []):
                if isinstance(sess, dict) and sess.get("id") not in existing_ids:
                    existing_sessions.append(sess)
            efr = existing.setdefault("file_reads", {})
            for fk, fv in duplicate.get("file_reads", {}).items():
                if fk not in efr:
                    efr[fk] = fv
                else:
                    efr[fk]["total_count"] = max(
                        efr[fk].get("total_count", 0),
                        fv.get("total_count", 0)
                    )
            to_delete.append(key)
        else:
            normalized[norm_key] = key

    for key in to_delete:
        del projects[key]

    for norm_key, orig_key in normalized.items():
        if orig_key != norm_key and orig_key in projects:
            projects[norm_key] = projects.pop(orig_key)
            to_rename[orig_key] = norm_key

    total = len(to_delete) + len(to_rename)
    if total:
        print(
            f"[Anti-Loop Guard] 프로젝트 키 정리: 중복 {len(to_delete)}개 병합, "
            f"정규화 {len(to_rename)}개",
            file=sys.stderr,
        )
    return total


# === P3-1: PE-2 — Persistent.json 정리 ===

def _cleanup_persistent(pdata):
    """오래된 프로젝트/파일 데이터 정리 (SessionStart 시 1회 호출)."""
    now = time.time()
    project_expiry = PROJECT_EXPIRY_DAYS * 86400
    file_expiry = FILE_EXPIRY_DAYS * 86400

    to_remove_projects = []
    for pkey, proj in pdata.get("projects", {}).items():
        # 프로젝트 마지막 접근 시간 추정 (마지막 세션 start)
        sessions = proj.get("sessions", [])
        if sessions:
            last_access = max(s.get("start", 0) for s in sessions)
        else:
            last_access = 0

        if last_access > 0 and (now - last_access) > project_expiry:
            to_remove_projects.append(pkey)
            continue

        # 프로젝트 내 오래된 file_reads 정리
        pfr = proj.get("file_reads", {})
        to_remove_files = []
        for fname, info in pfr.items():
            # 마지막 세션 접근 시간으로 판단
            file_sessions = info.get("sessions", [])
            if not file_sessions:
                to_remove_files.append(fname)
                continue
            # 가장 최근 세션 시간 추정
            latest_session_id = file_sessions[-1] if file_sessions else ""
            latest_time = 0
            for sess in sessions:
                if sess.get("id") == latest_session_id:
                    latest_time = sess.get("start", 0)
                    break
            if latest_time > 0 and (now - latest_time) > file_expiry:
                to_remove_files.append(fname)

        for fname in to_remove_files:
            del pfr[fname]

    for pkey in to_remove_projects:
        del pdata["projects"][pkey]

    cleaned = len(to_remove_projects)
    if cleaned > 0:
        print(
            f"[Anti-Loop Guard] Persistent 정리: {cleaned}개 프로젝트 만료 삭제",
            file=sys.stderr,
        )


# === P3-3: DX-3 — 인시던트 로그 SessionStart 요약 ===

def _summarize_recent_incidents():
    """최근 24시간 인시던트 요약 반환. 0건이면 빈 문자열."""
    try:
        if not INCIDENTS_PATH.exists():
            return ""
        content = INCIDENTS_PATH.read_text(encoding="utf-8")

        now = time.time()
        cutoff_24h = now - 86400

        # 타임스탬프 파싱: ### [INC-NNN] YYYY-MM-DD HH:MM | type
        incidents = re.findall(
            r"### \[INC-\d+\] (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \| (\w+)",
            content,
        )

        type_counts = {}
        total = 0
        for ts_str, inc_type in incidents:
            try:
                ts = time.mktime(time.strptime(ts_str, "%Y-%m-%d %H:%M"))
                if ts >= cutoff_24h:
                    total += 1
                    type_counts[inc_type] = type_counts.get(inc_type, 0) + 1
            except (ValueError, OverflowError):
                continue

        if total == 0:
            return ""

        types_str = ", ".join(f"{k}({v})" for k, v in type_counts.items())
        return f"지난 24시간: 루프 인시던트 {total}건 (유형별: {types_str})"

    except (OSError, UnicodeDecodeError):
        return ""


# === 서브커맨드: analyze ===

def cmd_analyze():
    """루프 근본 원인 분석 리포트 출력."""
    state = load_state()
    now = time.time()

    print("=" * 55)
    print("  Anti-Loop Guard - 근본 원인 분석 리포트")
    print("=" * 55)

    # 1. 연속 실패 분석
    fails = state.get("consecutive_fail", {})
    if fails:
        print("\n  [도구 반복 실패 분석]")
        h2c = state.get("hash_to_context", {})
        for h, cnt in sorted(fails.items(), key=lambda x: -x[1])[:5]:
            rc = ROOT_CAUSE_TABLE["tool_repeat"]
            ctx = h2c.get(h, {})
            label = ctx.get("file", ctx.get("cmd", h[:16]))[:60]
            print(f"    {label}: {cnt}회 연속 실패")
            print(f"    추정 원인: {', '.join(rc['causes'])}")
            print(f"    권장 조치: {', '.join(rc['actions'])}")
            print()

    # 2. 파일 반복 읽기 분석
    fr = state.get("file_reads", {})
    heavy_reads = {k: v for k, v in fr.items() if v.get("identical_count", 0) >= 3}
    if heavy_reads:
        print("\n  [파일 반복 읽기 분석]")
        for fpath, info in sorted(heavy_reads.items(), key=lambda x: -x[1].get("identical_count", 0)):
            ic = info.get("identical_count", 0)
            rc = ROOT_CAUSE_TABLE["file_repeat"]
            print(f"    {_format_file_display(fpath)}: 동일 파라미터 {ic}회 연속")
            print(f"    추정 원인: {', '.join(rc['causes'])}")
            print(f"    권장 조치: {', '.join(rc['actions'])}")
            print()

    # 3. 의미적 루프 분석
    detected, pattern_name, repeat_count = _detect_semantic_loop(state)
    if detected:
        rc = ROOT_CAUSE_TABLE["semantic"]
        print(f"\n  [의미적 루프 분석]")
        print(f"    패턴: [{pattern_name}] {repeat_count}회 반복")
        print(f"    추정 원인: {', '.join(rc['causes'])}")
        print(f"    권장 조치: {', '.join(rc['actions'])}")
        print()

    # 4. 압축 빈도 분석
    cutoff = now - COMPACT_FREQ_WINDOW_SEC
    recent_compacts = len([
        ts for ts in state.get("compact_timestamps", []) if ts > cutoff
    ])
    if recent_compacts >= 2:
        rc = ROOT_CAUSE_TABLE["compact_freq"]
        print(f"\n  [압축 빈도 분석]")
        print(f"    최근 {COMPACT_FREQ_WINDOW_SEC // 60}분: {recent_compacts}회 압축")
        print(f"    추정 원인: {', '.join(rc['causes'])}")
        print(f"    권장 조치: {', '.join(rc['actions'])}")
        print()

    # 5. 종합 건강도
    if not fails and not heavy_reads and not detected and recent_compacts < 2:
        print("\n  상태: 정상 (루프 징후 없음)")

    print("=" * 55)


# === 서브커맨드: health ===

def cmd_health():
    """세션 건강도 리포트 출력."""
    state = load_state()
    now = time.time()

    elapsed = now - state.get("session_start", now)
    elapsed_min = int(elapsed / 60)
    tool_count = len(state["tool_history"])
    compact_total = state["compact_count"]
    active_fails = state["consecutive_fail"]

    cutoff = now - COMPACT_FREQ_WINDOW_SEC
    recent_compacts = len([
        ts for ts in state["compact_timestamps"] if ts > cutoff
    ])

    top_fails = sorted(active_fails.items(), key=lambda x: -x[1])[:5]

    # Phase 1 추가 카운터
    fr = state.get("file_reads", {})
    heavy_reads = sum(1 for v in fr.values() if v.get("identical_count", 0) >= 3)

    print("=" * 55)
    print("  Anti-Loop Guard - 세션 건강도 리포트")
    print("=" * 55)
    print(f"  세션 경과: {elapsed_min}분")
    print(f"  도구 호출 수: {tool_count}")
    print(f"  총 압축 횟수: {compact_total}")
    print(f"  최근 {COMPACT_FREQ_WINDOW_SEC // 60}분 압축: {recent_compacts}회")
    print(f"  활성 실패 추적: {len(active_fails)}건")
    print(f"  파일 반복 읽기 경고: {heavy_reads}건")
    # P3-2: 감지된 패턴 이력
    dp = state.get("detected_patterns", [])
    if dp:
        print(f"  감지된 패턴 이력: {len(dp)}건")
    grace_map = state.get("post_compact_grace", {})
    active_grace = {f: g for f, g in grace_map.items() if g > 0}
    if active_grace:
        grace_str = ", ".join(f"{f}({g}회)" for f, g in active_grace.items())
        print(f"  압축 후 유예 잔여: {grace_str}")
    else:
        print(f"  압축 후 유예 잔여: 없음")

    if top_fails:
        print("\n  상위 실패 도구:")
        h2c = state.get("hash_to_context", {})
        for h, cnt in top_fails:
            ctx = h2c.get(h, {})
            label = ctx.get("file", ctx.get("cmd", h[:16]))[:60]
            print(f"    - {label}: {cnt}회 연속 실패")

    # 건강도 등급
    health_score = 100
    if recent_compacts >= COMPACT_FREQ_THRESHOLD:
        health_score -= 30
    if len(active_fails) > 5:
        health_score -= 20
    if any(v >= TOOL_REPEAT_BLOCK_THRESHOLD for v in active_fails.values()):
        health_score -= 30
    if heavy_reads > 0:
        health_score -= 10

    grade = (
        "GOOD" if health_score >= 80
        else "WARNING" if health_score >= 50
        else "CRITICAL"
    )
    print(f"\n  건강도: {health_score}/100 ({grade})")
    print("=" * 55)


# === 서브커맨드: sessionstart ===

def cmd_sessionstart():
    """SessionStart 훅: 새 세션 등록 + 이전 세션 분석."""
    now = time.time()
    hook_input = read_hook_input()
    # [2026-09-30] 세션 ID는 훅 stdin의 session_id (예전: 매번 s_<시각>을 새로 만들어 compact·resume
    # 재발화 때마다 세션이 중복 등록되고 상태가 초기화됐다)
    session_id = str(hook_input.get("session_id") or "") or f"s_{int(now)}"

    # 1. Persistent 로드 및 이전 세션 분석
    pdata = load_persistent()
    proj = _get_project_persistent(pdata)
    sessions = proj.get("sessions", [])

    # 같은 세션의 재발화(compact·resume): 재등록·상태 초기화 없이 보류 경고만 전달
    # (세션 목록에서 밀려났어도 상태 파일이 있으면 같은 세션이다)
    known = any(isinstance(s, dict) and s.get("id") == session_id for s in sessions)
    if known or (hook_input.get("session_id") and get_state_path().exists()):
        if not known:
            sessions.append({"id": session_id, "start": now, "compact_count": 0, "completed": False})
            proj["sessions"] = sessions[-SESSION_HISTORY_MAX:]
            save_persistent(pdata)
        state = load_state()
        pending = state.pop("pending_notices", [])
        if pending:
            save_state(state)
            print("[Anti-Loop Guard] 경고:")
            for w in pending:
                print(f"  ⚠ {w}")
        else:
            print(f"[Anti-Loop Guard] 세션 재개: {session_id} ({hook_input.get('source', '?')})", file=sys.stderr)
        return

    warnings = []

    # 2. 이전 세션의 미완료 여부 확인
    if sessions:
        prev = sessions[-1]
        prev_compacts = prev.get("compact_count", 0)
        if prev_compacts >= 3 and not prev.get("completed", True):
            warnings.append(
                f"이전 세션(ID={prev.get('id','?')})에서 압축 {prev_compacts}회 발생 "
                f"후 미완료 종료. 동일 작업 반복 위험."
            )

    # 3. 크로스-세션 파일 읽기 패턴 분석
    pfr = proj.get("file_reads", {})
    hot_files = [
        (fname, info)
        for fname, info in pfr.items()
        if info.get("total_count", 0) >= _cross_session_threshold(fname) - 3
        and len(info.get("sessions", [])) >= 2
    ]
    if hot_files:
        for fname, info in hot_files:
            total = info["total_count"]
            sess_cnt = len(info["sessions"])
            warnings.append(
                f"파일 '{fname}'이 {sess_cnt}개 세션에서 총 {total}회 읽힘. "
                f"서브에이전트 위임 권장."
            )

    # 3.5 크로스-세션 의미적 루프 감지
    detected, file_set, streak = _detect_cross_session_loop(proj)
    if detected:
        files_str = ", ".join(sorted(file_set)[:3])
        warnings.append(
            f"🔴 크로스-세션 루프 감지: {streak}개 세션 연속 동일 파일 집합 "
            f"({files_str}). 작업 전략 변경 필수 — "
            f"서브에이전트 위임 또는 파일 분할 편집 권장."
        )

    # 3.5.1 레거시 파일명 키 마이그레이션
    _migrate_persistent_file_keys(proj)

    # 3.5.2 프로젝트 키 대소문자 중복 병합
    _migrate_persistent_project_keys(pdata)

    # 3.6 P3-1: Persistent 정리 (세션 시작 시 1회)
    _cleanup_persistent(pdata)

    # 3.7 P2-4: 이전 세션 health 점수 표시 (이전 세션의 상태 파일)
    prev_state = {}
    if sessions and isinstance(sessions[-1], dict):
        prev_path = STATE_DIR / f"{_safe_id(sessions[-1].get('id'))}.json"
        if prev_path.exists():
            prev_state = _load_state_file(prev_path)
    if prev_state.get("session_start", 0) > 0:
        prev_health = _quick_health_score(prev_state)
        if prev_health < 80:
            warnings.append(f"이전 세션 건강도: {prev_health}/100")

    # 3.8 P3-3: 인시던트 로그 요약
    incident_summary = _summarize_recent_incidents()
    if incident_summary:
        warnings.append(incident_summary)

    # 4. 새 세션 등록
    new_session = {
        "id": session_id,
        "start": now,
        "compact_count": 0,
        "completed": False,
    }
    sessions.append(new_session)

    # 세션 이력 제한
    if len(sessions) > SESSION_HISTORY_MAX:
        sessions[:] = sessions[-SESSION_HISTORY_MAX:]
    proj["sessions"] = sessions

    save_persistent(pdata)

    # 5. 로컬 상태 초기화 (session_id 포함)
    state = _initial_state()
    state["session_id"] = session_id
    save_state(state)

    # 6. 경고 출력
    if warnings:
        # [2026-09-30] SessionStart는 stdout만 모델 컨텍스트로 들어간다 (exit 0 stderr는 디버그 로그뿐)
        print("[Anti-Loop Guard] 세션 시작 경고:")
        for w in warnings:
            print(f"  ⚠ {w}")
    else:
        print(
            f"[Anti-Loop Guard] 새 세션 등록: {session_id}",
            file=sys.stderr,
        )


# === P2-3: DS-3 — 서브커맨드: stop ===

def cmd_stop():
    """세션 완료 마킹. 현재 세션을 persistent에서 completed=True로 표시."""
    state = load_state()
    _mark_session_completed(state)
    print("[Anti-Loop Guard] 세션이 완료로 마킹되었습니다.", file=sys.stderr)

    # Quality check reminder on stop
    modified = state.get("modified_files", [])
    result_msg = "Session marked as completed"
    if modified:
        msg_lines = []
        msg_lines.append("")
        msg_lines.append("📋 **수정된 파일 목록** ({} 개):".format(len(modified)))
        for f in modified[-20:]:  # 최근 20개까지만 표시
            msg_lines.append("   - {}".format(f))
        if len(modified) > 20:
            msg_lines.append("   ... 외 {}개".format(len(modified) - 20))
        msg_lines.append("")
        msg_lines.append("🔍 **품질 검증 권장**:")
        msg_lines.append("   1. `npx tsc --noEmit` — 타입 체크")
        msg_lines.append("   2. `vitest --related {}` — 관련 테스트".format(" ".join(modified[-5:])))
        msg_lines.append("   3. 수정 파일 diff 확인: `git diff`")
        result_msg += "\n".join(msg_lines)

    json.dump({"result": result_msg}, sys.stdout, ensure_ascii=False)


# === 서브커맨드: reset ===

def cmd_reset():
    """상태 파일 리셋 (새 세션 시작). .task-state.md도 삭제."""
    path = get_state_path()
    if path.exists():
        path.unlink()
    save_state(_initial_state())

    # .task-state.md 삭제
    task_state = (_project_dir() or Path(os.getcwd())) / ".task-state.md"
    if task_state.exists():
        task_state.unlink()
        print("[Anti-Loop Guard] .task-state.md 삭제됨.", file=sys.stderr)

    print("[Anti-Loop Guard] 상태 파일이 리셋되었습니다.", file=sys.stderr)


# === 메인 디스패치 ===

COMMANDS = {
    "pretooluse": cmd_pretooluse,
    "posttooluse": cmd_posttooluse,
    "precompact": cmd_precompact,
    "sessionstart": cmd_sessionstart,
    "health": cmd_health,
    "analyze": cmd_analyze,
    "stop": cmd_stop,
    "reset": cmd_reset,
}


def main():
    global _MANUAL_RUN
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(
            f"Usage: {sys.argv[0]} <{'|'.join(COMMANDS.keys())}>",
            file=sys.stderr,
        )
        sys.exit(1)

    # 수동 명령은 stdin을 읽지 않는다 (터미널에서 실행하면 EOF까지 멈춘다)
    _MANUAL_RUN = sys.argv[1] in ("health", "analyze", "reset")
    try:
        COMMANDS[sys.argv[1]]()
    except Exception as e:
        print(f"[Anti-Loop Guard] 내부 오류 (pass-through): {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
