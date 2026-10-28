#!/usr/bin/env python3
"""하네스 무결성 린트 — 읽기 전용. 아무것도 삭제·수정하지 않는다.

claude-gc 사고(활성 플러그인 페이로드 무인 삭제)가 9일, 위험명령 훅 오배선이 18일 이상
탐지되지 않은 원인은 강제력 부재가 아니라 **고장이 조용했다는 것**이다. 이 스크립트는
"선언한 것이 실존하는가"만 검사하고, 불일치 시 non-zero로 시끄럽게 끝난다.

검사 항목:
  1. 페이로드   — backups/baseline.json 대비 플러그인 파일수·SKILL.md수 감소
  2. 훅 실존    — settings*.json이 참조하는 스크립트가 실제로 있고 실행 가능한가
  3. 훅 프로토콜 — 존재하지 않는 $TOOL_INPUT_* 환경변수에 의존하는 훅(무발화 확정)
  4. 주장 검증  — rules/safety.md가 단언하는 permissions.deny가 실제로 비어있지 않은가
  5. 정의 자산  — skills/agents 의 SKILL.md 실존·명명, 에이전트 모델 하드코딩
  6. 커버리지   — **아무것도 검사하지 않고 OK를 내는 상태**를 신고한다
  7. GC 안전    — claude-gc.sh가 plugins/ 를 삭제 대상으로 삼고 있지 않은가
  8. 라우터 코퍼스 — uiux-skill-router.sh의 신호 판정이 router-corpus.tsv 기대값과 같은가
  9. 설정 범위  — 보안·게이트(deny·ask·훅)는 settings.json에, cwd 쓰기 훅은 local에만 있는가

깊은 검사(문법 컴파일·MCP 설정·플러그인 전수)는 `harness-sweep.py` 담당 — 이쪽은
PostToolUse 상시 경로라 값싼 것만 둔다. 실측 비용: 전체 프로세스 중앙값 ~76ms
(인터프리터 기동 포함, 무부하 20회). 부하가 걸리면 그보다 늘어난다 — 상한을 단정하지
않는다(2026-07-27 교차검증이 부하 중 183ms를 관측했다).

사용법:
    python3 ~/.claude/scripts/harness-lint.py            # 검사 (exit 1 = 위반 있음)
    python3 ~/.claude/scripts/harness-lint.py --update-baseline
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import sys
import time

C = os.path.expanduser("~/.claude")
BASELINE = os.path.join(C, "backups", "baseline.json")
# 문서가 참조하지만 파일로 존재할 필요가 없는 것들 — 오탐 화이트리스트
IGNORE_REFS = {"/goal", "/what", "/what-ce", "/insight-check", "/loop", "/effort"}
# deny 규칙에 쓸 수 있는 도구명 — 오타/미지 도구는 규칙이 아니라 무발화 문자열이다
DENY_TOOLS = {"Read", "Write", "Edit", "MultiEdit", "Bash", "Glob", "Grep", "WebFetch",
              "WebSearch", "NotebookEdit", "Agent", "Task"}
# `//` 접두 요건은 파일 경로 기반 규칙에만 적용된다 — Bash는 명령 접두 패턴이라
# 별도 문법이고 실집행이 카나리로 확인됨(2026-08-09: Bash(grok -p*) deny 차단 실측).
PATH_DENY_TOOLS = {"Read", "Write", "Edit", "MultiEdit", "NotebookEdit", "Glob", "Grep"}
# 괄호 없이 도구 전체를 막는 bare 규칙에 쓸 수 있는 내장 도구명(2026-09-28 세션 도구 목록 기준).
# 목록에 없는 이름은 오타일 가능성이 높아 형식 불명으로 신고한다 — 새 내장 도구가 생기면 추가한다.
BARE_TOOLS = DENY_TOOLS | {
    "ToolSearch", "Skill", "AskUserQuestion", "EnterPlanMode", "ExitPlanMode", "EnterWorktree",
    "ExitWorktree", "LSP", "Monitor", "ScheduleWakeup", "SendMessage", "TaskStop", "Workflow",
    "Artifact", "CronCreate", "CronDelete", "CronList", "PushNotification", "RemoteTrigger",
    "EndConversation", "NotebookRead", "TodoWrite", "TaskCreate", "TaskUpdate", "TaskList", "TaskGet",
    "TaskOutput", "KillShell", "BashOutput", "SlashCommand", "ListMcpResourcesTool", "ReadMcpResourceTool"}
# MCP 이름: 서버 자리에도 glob 허용(`mcp__github*`), 단 영숫자나 *로 시작해야 한다(`mcp__---` 거부)
_MCP_RULE = re.compile(r"mcp__[A-Za-z0-9*][\w*-]*(__[\w*-]+)?")


def payload(path: str, pred=None) -> int:
    """실존하는 파일만 센다.

    2026-07-27 수리: `os.walk`는 **깨진 심볼릭 링크도 files에 넣는다**. omc는 페이로드가
    07-16에 소실돼 dangling 링크 22개만 남았는데, 이 함수가 그것을 22파일로 계상해
    "감소 없음 = OK"로 통과시켰다. 더 나쁜 것은 베이스라인을 파손 이후(07-25)에 찍어
    22를 정답으로 봉인한 것이다. `scandir` + `is_file()`(follow_symlinks 기본 True)는
    깨진 링크를 False로 거른다.

    **경계(2026-07-27 교차검증)**: `os.walk`+`exists()` 판본과 결과가 항상 같지는 않다 —
    FIFO·소켓 같은 특수 파일에서 `exists()`는 True, `is_file()`은 False다. 실제 플러그인
    37개·3,421파일에서는 완전히 일치했고, "페이로드 파일 수"의 의미로는 일반 파일만 세는
    현재 동작이 옳다. 다만 "두 판본이 무조건 동일"이라는 주장은 거짓이다.
    """
    n = 0
    for name in _iter_files(path):
        if pred is None or pred(name):
            n += 1
    return n


def _iter_files(path: str):
    """실존하는 일반 파일의 **이름**만 흘린다. 순회 로직 단일 정본.

    실행 부산물(`.in_use/`·`__pycache__/`·`.orphaned_at`)은 세지 않는다 — 플러그인이 갱신되면
    부산물만 사라져도 "파일 소실"로 신고됐다(2026-09-30 hookify 32→25, 소스 파일 목록은 동일).
    """
    if not path or not os.path.isdir(path):
        return
    stack = [path]
    while stack:
        cur = stack.pop()
        try:
            entries = list(os.scandir(cur))
        except OSError:
            continue
        for e in entries:
            if e.is_dir(follow_symlinks=False):
                if e.name not in (".in_use", "__pycache__"):
                    stack.append(e.path)
            elif e.is_file() and e.name != ".orphaned_at":  # is_file은 링크를 따라가므로 깨진 링크는 False
                yield e.name


def payload_counts(path: str) -> tuple[int, int]:
    """(전체 실파일 수, SKILL.md 수) 를 **한 번의 순회**로 센다.

    이전에는 `payload()` 를 두 번 불러 트리를 두 번 걸었다(check_payload 111ms의
    대부분). 같은 순회에서 둘 다 세면 절반이 된다.
    """
    n = sk = 0
    for name in _iter_files(path):
        n += 1
        if name.lower() == "skill.md":
            sk += 1
    return (n, sk)


def settings_files() -> list[str]:
    return [p for p in (os.path.join(C, f) for f in ("settings.json", "settings.local.json"))
            if os.path.exists(p)]


def enabled_plugins() -> dict:
    """{plugin_id: installPath} — settings.json에서 enabled인 것만."""
    try:
        inst = json.load(open(os.path.join(C, "plugins", "installed_plugins.json")))["plugins"]
        en = json.load(open(os.path.join(C, "settings.json"))).get("enabledPlugins") or {}
    except Exception:
        return {}
    out = {}
    for pid, arr in inst.items():
        if not en.get(pid):
            continue
        # `arr` 가 빈 배열이면 "설치됐다"는 기록이 실체가 없다 — 조용히 건너뛰면
        # enabled 선언이 거짓인 채로 통과한다(6라운드 지적). 빈 경로로 남겨
        # 절대조건(실파일 0)이 신고하게 한다.
        out[pid] = arr[0].get("installPath", "") if arr else ""
    return out


def hook_commands():
    """(설정파일, 이벤트, matcher, command) 목록."""
    for p in settings_files():
        try:
            d = json.load(open(p))
        except Exception as exc:
            yield (p, "?", "?", f"__PARSE_ERROR__ {exc}")
            continue
        for ev, arr in (d.get("hooks") or {}).items():
            if not isinstance(arr, list):
                continue
            for m in arr:
                for h in m.get("hooks", []):
                    yield (os.path.basename(p), ev, m.get("matcher", ""), h.get("command", ""))


def check_payload(violations: list[str]) -> None:
    # 베이스라인 무관 절대조건. 베이스라인은 "파손 후 캡처"로 오염될 수 있으므로
    # (실제로 omc가 그렇게 봉인됐다) 상대 비교와 별도로 이 조건을 먼저 본다:
    # enabled인데 실파일이 0이면 그 플러그인은 무조건 파손이다.
    empty = set()
    live = enabled_plugins()
    for pid, ip in live.items():
        nfiles, _ = payload_counts(ip)
        if nfiles == 0:
            empty.add(pid)
            violations.append(
                f"페이로드 공백: {pid} 이 enabled인데 실파일 0개 (installPath={ip or '없음'})"
                " — 이 플러그인의 훅·스킬·커맨드는 전부 무발화다")

    if not os.path.exists(BASELINE):
        violations.append(f"베이스라인 없음: {BASELINE} — --update-baseline 으로 생성하라")
        return
    base = json.load(open(BASELINE))
    inst = os.path.join(C, "plugins", "installed_plugins.json")
    if not os.path.exists(inst):
        violations.append("installed_plugins.json 없음")
        return
    plugins = json.load(open(inst))["plugins"]
    for pid, expect in base.get("plugins", {}).items():
        if expect.get("files", 0) == 0:
            continue  # 원래 비어 있던 것(disabled 등)은 기준에서 제외
        if pid not in live:
            # 지금 비활성인 플러그인의 페이로드는 판정 대상이 아니다 — 의도적 은퇴이고
            # 그 사실이 settings.json(git 추적)에 선언돼 있다. 다시 enabled로 돌리는
            # 순간 이 검사가 자동으로 복귀해 소실을 신고한다.
            continue
        if pid in empty:
            continue  # 절대조건이 이미 신고했다 — 같은 파손을 두 줄로 보고하지 않는다
        arr = plugins.get(pid)
        if not arr:
            violations.append(f"플러그인 소실: {pid} (베이스라인 {expect['files']}파일)")
            continue
        path = arr[0].get("installPath", "")
        now, now_skills = payload_counts(path)
        if now < expect["files"]:
            violations.append(
                f"페이로드 감소: {pid} {expect['files']} → {now}파일"
                f" ({expect['files'] - now}개 소실)")
        # 파일수는 그대로인데 SKILL.md가 사라지는 경우(이동·개명)도 파손이다
        if now_skills < expect.get("skills", 0):
            violations.append(
                f"SKILL.md 감소: {pid} {expect['skills']} → {now_skills}개")


# 인터프리터 뒤의 경로 + 직접 실행되는 스크립트 토큰. `/bin/sh '<path>'` 형태를
# 놓쳐서 settings.json의 orca 릴레이 10개가 검사 대상 밖이었다(2026-07-27 수리).
SCRIPT_RE = re.compile(
    r"""(?:^|[\s;&|(])(?:/bin/|/usr/bin/)?(?:bash|sh|zsh|python3?|node|deno)\s+"""
    r"""["']?([^\s"';|&)]+)""")
# 앞은 경로문자가 아니어야 하고(`.foo/config.json` 중간의 `/`부터 잡히는 오탐 차단),
# 확장자 뒤도 단어경계여야 한다(`.js`가 `.json`의 접두로 매칭되던 오탐 차단).
BARE_SCRIPT_RE = re.compile(
    r"""(?:^|[\s;&|(=])["']?((?:/|~/|\$\{?CLAUDE_PLUGIN_ROOT)[^\s"';|&)]*"""
    r"""\.(?:sh|mjs|cjs|js|py|cmd))(?![\w.])""")
# 조달물의 알려진 결함 — 고치지 않고 등재만 하기로 한 것들. 상시 출력되면 사용자가
# 린트 전체를 스킵하도록 훈련되므로(=관측기 신뢰 0) 여기 등재된 것은 조용히 넘긴다.
# 목록 자체가 git 추적 대상이라 리뷰에서는 보인다. 새 항목이 생기면 시끄러워진다.
# 2026-07-27 교차검증 지적: 대상 문자열만 맞으면 **무관한 위반까지** 숨었다
# (같은 훅의 '스크립트 부재'나 `$TOOL_INPUT_EXTRA` 도 함께 억제됨). 그래서 등재는
# (대상, 시그니처) **두 조각이 모두** 포함될 때만 성립한다.
KNOWN_HOOK_ISSUES: list[tuple[str, str, str]] = [
    # (대상, 메시지 시그니처, 사유) — 현재 등재 항목 없음.
    # 2026-07-27: understand-anything 의 `$TOOL_INPUT` 항목은 **수리**되어 해제했다
    # (`patches/README.md` §3). 억제는 고칠 수 없는 것에만 쓴다.
]


def _resolve(raw: str, root: str | None) -> str | None:
    p = raw.strip("\"'")
    if root:
        p = p.replace("${CLAUDE_PLUGIN_ROOT}", root).replace("$CLAUDE_PLUGIN_ROOT", root)
    p = os.path.expanduser(p)
    if "$" in p or not p.startswith("/"):
        return None
    return p


def _scan_hook_cmd(violations, src, ev, matcher, cmd, root=None) -> None:
    # 접미사 없는 `$TOOL_INPUT` 도 같은 부류다 — understand-anything의 PostToolUse가
    # 이 형태였고, 빈 값이 grep에 들어가 && 체인 전체가 조용히 실패한다(2026-07-27 발견).
    if "$TOOL_INPUT" in cmd:
        var = re.search(r"\$TOOL_INPUT\w*", cmd).group(0)
        violations.append(
            f"무발화 훅: {src} {ev}({matcher}) 이 {var} 를 참조한다"
            " — 훅 입력은 stdin JSON이고 이 환경변수는 존재하지 않는다")
    seen = set()
    for raw in SCRIPT_RE.findall(cmd) + BARE_SCRIPT_RE.findall(cmd):
        path = _resolve(raw, root)
        if not path or path in seen:
            continue
        seen.add(path)
        if not os.path.exists(path):
            violations.append(f"훅 스크립트 부재: {src} {ev}({matcher}) → {path}")


def check_hooks(violations: list[str]) -> None:
    for src, ev, matcher, cmd in hook_commands():
        if cmd.startswith("__PARSE_ERROR__"):
            violations.append(f"설정 파싱 실패: {src} {cmd}")
            continue
        _scan_hook_cmd(violations, src, ev, matcher, cmd)

    # 플러그인 훅 — 발화 장치의 다수가 여기에 있는데 07-25 판본은 settings 2파일만 봤다.
    # 정적 검사만 한다: 합성 stdin으로 훅을 **실행**하는 방식은 외부 데몬에 위조
    # 라이프사이클을 발사하고 쓰기 훅을 돌린다(감사 중 checkpoint.md를 덮은 사고의 원인).
    found = []
    for pid, ip in enabled_plugins().items():
        hj = os.path.join(ip, "hooks", "hooks.json")
        if not os.path.exists(hj):
            continue
        try:
            d = json.load(open(hj))
        except Exception as exc:
            violations.append(f"플러그인 훅 파싱 실패: {pid} → {exc}")
            continue
        for ev, groups in (d.get("hooks") or {}).items():
            if not isinstance(groups, list):
                continue
            for g in groups:
                for h in g.get("hooks", []):
                    found.append(1)
                    _scan_hook_cmd(violations, pid, ev, g.get("matcher", ""),
                                   h.get("command", ""), root=ip)
    # 등재된 조달물 결함은 조용히 제외한다(위 KNOWN_HOOK_ISSUES 주석 참조).
    # 대상과 시그니처가 **둘 다** 맞아야 억제된다 — 한쪽만으로는 무관한 위반이 숨는다.
    for target, sig, _reason in KNOWN_HOOK_ISSUES:
        violations[:] = [v for v in violations if not (target in v and sig in v)]


def check_claims(violations: list[str]) -> None:
    """민감파일 deny의 **실효성**을 검사한다.

    2026-07-27 수리: 이전 판본은 `rules/safety.md`에 특정 문자열이 있을 때만 동작했는데,
    같은 날 safety.md를 다시 쓰면서 그 문자열이 사라져 **조용히 죽어 있었다**(grep 0건).
    문서 문구에 결속하는 대신 불변식 자체를 본다 — 07-25에 실측으로 확인된 규칙:
    `permissions.deny`는 `//` 접두 + `**/` glob 형태만 집행되고, 단일 슬래시나
    상대 glob은 **경고 없이 무시**된다. 그래서 개수와 문법을 함께 본다.
    """
    rules = []
    for p in settings_files():
        try:
            rules += (json.load(open(p)).get("permissions") or {}).get("deny", [])
        except Exception:
            pass
    if not rules:
        violations.append("민감파일 방어 없음: permissions.deny 가 전 계층 0개다")
        return
    bad, malformed = [], []
    for r in rules:
        m = re.match(r"^(\w+)\((.*)\)$", r)
        if not m:
            # 괄호 없는 bare 규칙은 도구 이름 전체에 매칭되는 유효 문법이다 — 공식 permissions 문서
            # (2026-09-28 확인): `mcp__puppeteer`는 그 서버의 모든 도구, deny는 tool-name glob
            # (`mcp__*`, `mcp__github__get_*`)도 받는다. 단 괄호 달린 `mcp__x(...)`는 로드 시 건너뛴다.
            # 2026-09-28 codex 교차검수: 느슨한 glob이 `Garbage*`·`mcp__---`까지 통과시켰다 → glob은
            # 알려진 도구와 1개 이상 매칭될 때만, MCP 이름은 서버명이 영숫자로 시작할 때만 인정한다.
            if r in BARE_TOOLS or _MCP_RULE.fullmatch(r):
                continue
            if "*" in r and re.fullmatch(r"[\w*-]+", r) and (
                    r == "*" or any(fnmatch.fnmatchcase(t, r) for t in BARE_TOOLS)):
                continue
            malformed.append(r)          # 알려진 도구명·MCP 이름·glob이 아니면 규칙으로 해석되지 않는다
        elif m.group(1) not in DENY_TOOLS or m.group(2).strip("/") == "":
            # 2라운드 지적: `NoSuchTool(//**/.env)` 와 `Read(//)` 가 통과했다.
            malformed.append(r)
        elif m.group(1) in PATH_DENY_TOOLS and not m.group(2).startswith("//"):
            bad.append(r)
    if bad:
        violations.append(
            f"무발화 deny 규칙 {len(bad)}건: {', '.join(bad[:3])}"
            " — `//` 접두 절대 glob만 집행된다(단일 슬래시·상대 경로는 조용히 무시)")
    if malformed:
        # 2026-07-27 교차검증 지적: deny=["garbage"] 가 그대로 통과했다.
        violations.append(
            f"형식 불명 deny 규칙 {len(malformed)}건: {', '.join(malformed[:3])}"
            " — 알려진 도구명·`mcp__` 이름·glob·`Tool(패턴)` 중 어느 형태도 아니면 규칙으로 해석되지 않는다")


# 설정 범위 불변식(2026-09-30 감사 #60): ~/.claude/settings.local.json은 홈 폴더 프로젝트에서만 읽힌다.
# 보안·게이트 규칙이 거기에만 있으면 다른 프로젝트 세션에서 조용히 빠진다(09-28 Playwright 도구 노출,
# 09-30 ask·verify-lock 누락 실측). 반대로 cwd에 파일을 쓰는 훅을 전역에 두면 아무 폴더에나 흩어진다.
LOCAL_FORBIDDEN_HOOKS = ("sanitize-korean", "codex-sandbox-guard", "verify-lock", "design-detect-hook",
                         "uiux-skill-router", "adapter-inject", "verify-memory-integrity", "emulation-guard",
                         "harness-lint")
GLOBAL_REQUIRED_HOOKS = ("sanitize-korean", "codex-sandbox-guard", "verify-lock-hook")
GLOBAL_FORBIDDEN_HOOKS = ("anti-loop-guard", "checkpoint-save")
REQUIRED_ASK = ("Bash(rm -rf*)", "Bash(git reset --hard*)", "Bash(git push --force*)", "Bash(git clean -f*)")


def check_scope(violations: list[str]) -> None:
    """보안·게이트는 settings.json(전 프로젝트)에, cwd 쓰기 훅은 local(홈)에만 있는지 본다."""
    try:
        g = json.load(open(os.path.join(C, "settings.json")))
    except Exception as exc:
        violations.append(f"설정 범위 검사 불가: settings.json 파싱 실패 {exc}")
        return
    lpath = os.path.join(C, "settings.local.json")
    try:
        loc = json.load(open(lpath)) if os.path.exists(lpath) else {}
    except Exception:
        loc = {}  # 파싱 실패는 check_hooks가 신고한다

    def cmds(d):
        return [h.get("command", "") for arr in (d.get("hooks") or {}).values() if isinstance(arr, list)
                for m in arr for h in m.get("hooks", [])]

    for key in ("deny", "ask"):
        if ((loc.get("permissions") or {}).get(key)):
            violations.append(f"settings.local.json에 permissions.{key}가 있다 — 홈 폴더 프로젝트에서만 적용된다. "
                              "settings.json으로 옮겨라")
    ask = (g.get("permissions") or {}).get("ask") or []
    missing = [a for a in REQUIRED_ASK if a not in ask]
    if missing:
        violations.append(f"파괴 명령 사람 체크포인트 누락(settings.json ask): {', '.join(missing)} "
                          "— rules/safety.md가 단언하는 계층")
    gc, lc = cmds(g), cmds(loc)
    for mk in LOCAL_FORBIDDEN_HOOKS:
        if any(mk in c for c in lc):
            violations.append(f"보안·게이트 훅 '{mk}'이 settings.local.json에 있다 — 홈 밖 세션에서 빠진다")
    for mk in GLOBAL_REQUIRED_HOOKS:
        if not any(mk in c for c in gc):
            violations.append(f"핵심 보안 훅 '{mk}'이 settings.json에 없다")
    for mk in GLOBAL_FORBIDDEN_HOOKS:
        if any(mk in c for c in gc):
            violations.append(f"cwd에 파일을 쓰는 훅 '{mk}'이 settings.json에 있다 — 모든 프로젝트에 상태 파일이 흩어진다")


_FM = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.S)


def check_definitions(violations: list[str]) -> None:
    """로컬 정의 자산(skills·agents)의 값싼 불변식. 파일 읽기뿐이라 상시 경로에 적합하다.

    깊은 검사(문법 컴파일·MCP 설정·플러그인 전수)는 `harness-sweep.py`가 맡는다.
    """
    skills = os.path.join(C, "skills")
    if os.path.isdir(skills):
        for name in sorted(os.listdir(skills)):
            d = os.path.join(skills, name)
            if not os.path.isdir(d):
                continue
            if name == "synced" and any(f.startswith(".bucket-") for f in os.listdir(d)):
                continue  # Claude Code가 관리하는 claude.ai 계정 스킬 동기화 버킷 — SKILL.md는 하위 폴더에 있다
            entries = [f for f in os.listdir(d) if f.lower() == "skill.md"]
            if not entries:
                violations.append(f"스킬 파손: skills/{name}/ 에 SKILL.md 가 없다")
            elif entries[0] != "SKILL.md":
                violations.append(
                    f"스킬 명명: skills/{name}/{entries[0]} — 로컬 관행은 `SKILL.md`")

    agents = os.path.join(C, "agents")
    if os.path.isdir(agents):
        for fn in sorted(f for f in os.listdir(agents) if f.endswith(".md")):
            m = _FM.match(open(os.path.join(agents, fn), errors="replace").read())
            if not m:
                violations.append(f"에이전트 frontmatter 없음: agents/{fn}")
                continue
            if re.search(r"^model:\s*\S", m.group(1), re.M):
                mod = re.search(r"^model:\s*(\S+)", m.group(1), re.M).group(1)
                violations.append(
                    f"모델 하드코딩: agents/{fn} 이 `model: {mod}` 를 박고 있다"
                    " — 서브에이전트는 세션 모델 상속이 기본이다(model-agnostic 1급 목표)")


# 소멸을 **서술하는** 문장에 등장하는 경로는 죽은 참조가 아니라 정확한 기록이다.
# 캐시 drift 검사와 같은 교훈 — 단순 언급 카운트는 지표가 아니다.
#
# 2026-07-27 교차검증 지적 2건을 반영했다:
#  ① 줄 전체를 면제하면 "구 `X`는 폐기됨; 활성 참조 `Y`" 한 줄에서 **진짜 죽은 참조 Y도
#     함께 숨는다**. 그래서 면제 판정을 경로 **직전 문맥**으로 좁힌다.
#  ② `구 `가 `연구 `에 부분 매치해 무관한 줄을 면제했다. 앞이 한글이면 매치하지 않게 한다.
GONE_RE = re.compile(r"폐기|소멸|삭제|제거|부재|없다|없음|미존재|사라졌|유실|이전 판본|더 이상"
                     r"|(?<![가-힣])구 ")


def _clauses(line: str):
    """절 분할 — ASCII `;` `,` + 한국어 `。` + 마침표+공백. 경로 안의 `.`는 쪼개지 않는다."""
    return re.split(r"[;,。]|(?<=\S)\.\s", line)


def _occurs(clause: str, raw: str) -> bool:
    """`raw` 가 그 절에 **경로 하나로** 등장하는가.

    구분자(백틱·괄호·따옴표·공백)를 가리지 않는다 — 3라운드 반증:
    "폐기 `~/x`, 활성 참조 (~/x)" 에서 백틱 등장만 검사해 괄호 등장을 놓쳤다.
    앞뒤 경계 검사로 접두 충돌(`~/a-old` ⊃ `~/a`)만 배제한다.
    """
    return re.search(r"(?<![\w./@-])" + re.escape(raw) + r"(?![\w./@-])", clause) is not None


def _is_gone_context(line: str, raw: str) -> bool:
    """그 줄에서 `raw` 가 등장하는 **모든 절**이 소멸 서술일 때만 면제한다.

    하나라도 활성 문맥이면 죽은 참조로 신고한다 — 소멸 서술과 활성 참조가 한 줄에
    섞여 있을 때 진짜 결함이 숨는 것을 막는다(2·3라운드 교차검증 반영).
    """
    hits = [c for c in _clauses(line) if _occurs(c, raw)]
    if not hits:
        # 경로 위치를 특정하지 못했다 — 면제하지 않는다. 판정 불가는 통과가 아니라
        # 신고 쪽으로 떨어져야 한다(clone-site 게이트에서 배운 것과 같은 규율).
        return False
    return all(GONE_RE.search(c) for c in hits)


def check_doc_paths(violations: list[str]) -> None:
    """상시 주입 문서가 가리키는 절대 경로가 실존하는지.

    CLAUDE.md는 fablize의 goals.py·packs를 버전 고정 경로(.../fablize/2.1.0/...)로
    참조한다. 플러그인이 업데이트되면 그 3줄이 조용히 죽는다 — 여기서 시끄럽게 만든다.
    """
    docs = [os.path.join(C, "CLAUDE.md")]
    rules_dir = os.path.join(C, "rules")
    if os.path.isdir(rules_dir):
        docs += [os.path.join(rules_dir, f) for f in sorted(os.listdir(rules_dir))
                 if f.endswith(".md")]
    path_re = re.compile(r"[`(]((?:/Users/[\w./-]+|~/[\w./-]+))[`)]")
    for doc in docs:
        if not os.path.exists(doc):
            continue
        for i, line in enumerate(open(doc, errors="replace").read().splitlines(), 1):
            for raw in set(path_re.findall(line)):
                if raw in IGNORE_REFS or raw.rstrip("/").endswith("**"):
                    continue
                path = os.path.expanduser(raw)
                # 디렉토리 규약(tasks/<task>/ 같은 플레이스홀더)은 검사 대상이 아니다
                if "<" in path or ">" in path or os.path.exists(path):
                    continue
                if _is_gone_context(line, raw):
                    continue
                violations.append(
                    f"문서의 죽은 경로: {os.path.basename(doc)}:{i} → {raw}")


def check_coverage(violations: list[str]) -> None:
    """**아무것도 검사하지 않고 OK를 내는 상태**를 신고한다.

    2026-07-27 교차검증 지적: 빈 settings·빈 설치목록·빈 baseline만 있는 HOME에서
    `harness-lint: OK` 와 `전역 스윕: 오류 0건` 이 둘 다 rc=0이었다. "오류 0건"과
    "검사 안 함"의 출력이 같으면 관측기는 아무 말도 하지 않은 것과 같다.
    이건 이 하네스가 스스로 세운 원칙(커버리지를 수치로 보고하게 한다)의 자기 적용이다.
    """
    n_settings = len(settings_files())
    n_plugins = len(enabled_plugins())
    # 빈 command 는 훅이 아니다 — 세면 커버리지가 부풀려진다(2라운드 지적)
    n_hooks = sum(1 for *_, cmd in hook_commands() if cmd.strip())
    n_base = 0
    if os.path.exists(BASELINE):
        try:
            n_base = len(json.load(open(BASELINE)).get("plugins", {}))
        except (OSError, ValueError):
            n_base = 0
    if n_settings == 0:
        violations.append("커버리지 0: settings*.json 이 하나도 없다 — 검사할 대상이 없다")
    if n_hooks == 0:
        violations.append("커버리지 0: 훅 커맨드가 0개다 — 훅 검사가 무의미하다")
    if n_plugins == 0:
        violations.append("커버리지 0: enabled 플러그인이 0개다 — 페이로드 검사가 무의미하다")
    if n_base == 0:
        violations.append("커버리지 0: 베이스라인에 플러그인 항목이 0개다")


def check_gc(violations: list[str]) -> None:
    gc = os.path.join(C, "scripts", "claude-gc.sh")
    if not os.path.exists(gc):
        return
    for i, line in enumerate(open(gc), 1):
        code = line.split("#")[0]
        if "plugins/" in code and ("-delete" in code or "rm " in code or "CACHE_DIR=" in code):
            violations.append(f"GC 위험: claude-gc.sh:{i} 가 plugins/ 를 삭제 대상으로 삼는다")
    # 스로틀 회귀 카나리: 마커가 epoch면 호출부(`date +%Y%m%d`)와 영구 불일치해
    # "하루 1회" 가드가 무효화된다. 2026-07-25에 실제로 그 상태로 잠겨 있었다.
    marker = os.path.join(C, ".gc-last-run")
    if os.path.exists(marker):
        val = open(marker).read().strip()
        if val and not re.fullmatch(r"\d{8}", val):
            violations.append(
                f"GC 스로틀 형식 이상: .gc-last-run = {val!r} — YYYYMMDD가 아니면"
                " 호출부 비교가 영구 불일치해 매 실행 모드로 잠긴다")


def check_cache_drift(violations: list[str]) -> None:
    """플러그인 캐시의 죽은 참조 개수가 기준선보다 늘었는지.

    캐시는 휘발성이라(플러그인 업데이트·재설치로 덮인다) 파일을 고쳐도 되돌아온다.
    그래서 고치는 대신 **재발을 시끄럽게** 만든다 — 개수가 늘면 신고한다.
    기준선은 2026-07-25 페이로드 복구 직후 실측값이다.
    """
    # 2026-07-25 실측. 패턴 설계 교훈: `claude-in-chrome`처럼 **도구 이름을 세면 오탐**이다
    # — "Playwright 우선, Chrome MCP는 로그인 세션 재사용 시에만"이라는 **올바른** 서술도
    # 함께 걸려서 marketplace update 직후 3→13으로 튀었다(전부 정상 문장). 그래서 패턴을
    # "역전된 주장"만 잡도록 좁혔다. 단순 언급 카운트는 drift 지표가 아니다.
    baseline = {
        "check-chrome-mcp-priority": 0,   # 부재하는 훅 스크립트 참조
        "claude/skills/_core": 0,         # 구 SSoT 경로(하네스 교체로 소멸)
        "Chrome MCP 우선": 0,             # rigor §1이 2026-07-07에 뒤집은 역전 주장
        "Playwright는 fallback": 0,       # 같은 역전의 다른 표현
        "Playwright 는 fallback": 0,
    }
    cache = os.path.join(C, "plugins", "cache")
    if not os.path.isdir(cache):
        violations.append(f"캐시 디렉토리 부재: {cache} — drift 검사가 무의미하다")
        return
    # 상시 경로 예산: 이 검사는 캐시 전체의 .md를 읽어 373ms로 전체의 70%를 먹었다.
    # 그래서 게이팅하되, **무기한 침묵하지 않게** 상한을 둔다.
    #
    # 2026-07-27 교차검증 지적: `installed_plugins.json` mtime만 서명으로 쓰면
    # 캐시를 직접 수정·부분 복원했을 때 그 mtime이 그대로라 탐지가 **영구 정지**한다
    # (codex가 카나리를 심어 실증). 서명 + 최대 유효기간(MAX_SKIP_H)으로 구멍을 유한하게
    # 만든다. 잔여 위험은 명시한다 — 마지막 스캔 이후 MAX_SKIP_H 안에 일어난 캐시 내용
    # 변경은 그 시간만큼 늦게 발견된다. 무기한이 아니라 유계다.
    MAX_SKIP_H = 12
    stamp = os.path.join(C, "scripts", ".lint-drift-state.json")
    try:
        sig = str(os.stat(os.path.join(C, "plugins", "installed_plugins.json")).st_mtime_ns)
        if os.path.exists(stamp):
            st = json.load(open(stamp))
            age = time.time() - os.stat(stamp).st_mtime
            # 하한 0 — **미래 시각 스탬프**는 age가 음수라 무한정 신선해 보였다
            # (2026-07-27 2라운드 반증). 음수면 신뢰하지 않고 재스캔한다.
            if st.get("sig") == sig and 0 <= age < MAX_SKIP_H * 3600:
                return
    except (OSError, ValueError):
        sig = None   # 스탬프가 깨졌다 — 재스캔 후 아래에서 다시 쓴다
    counts = dict.fromkeys(baseline, 0)
    for root, _, files in os.walk(cache):
        if "/.in_use" in root:
            continue
        for fn in files:
            if not fn.endswith(".md"):
                continue
            try:
                text = open(os.path.join(root, fn), errors="replace").read()
            except OSError:
                continue
            for pat in counts:
                if pat in text:
                    counts[pat] += 1
    hits = [f"캐시 drift 증가: '{p}' 참조 {e} → {counts[p]}파일"
            for p, e in baseline.items() if counts[p] > e]
    violations.extend(hits)
    # 위반이 없을 때만 서명을 기록한다 — 위반이 남아 있으면 매번 다시 신고해야 한다.
    if not hits:
        # 깨진 스탬프도 여기서 복구한다 — 안 하면 매번 전체 스캔한다(2라운드 지적).
        if sig is None:
            try:
                sig = str(os.stat(os.path.join(C, "plugins",
                                               "installed_plugins.json")).st_mtime_ns)
            except OSError:
                sig = None
        if sig:
            try:
                json.dump({"sig": sig, "note": "캐시 무변경 시 drift 스캔 생략용 서명"},
                          open(stamp, "w"))
            except OSError as exc:
                # 쓰기 실패를 삼키면 게이팅이 조용히 죽는다(매번 전체 스캔 = 마찰).
                violations.append(f"drift 스탬프 기록 실패: {stamp} — {exc}")


def update_baseline() -> None:
    import subprocess
    plugins = json.load(open(os.path.join(C, "plugins", "installed_plugins.json")))["plugins"]
    enabled = (json.load(open(os.path.join(C, "settings.json"))).get("enabledPlugins") or {})
    snap = {
        "taken_at": subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                                   capture_output=True, text=True).stdout.strip(),
        "note": "harness-lint.py --update-baseline 로 생성. 파손 상태에서 찍지 말 것.",
        "plugins": {},
    }
    for pid, arr in sorted(plugins.items()):
        ip = arr[0].get("installPath", "")
        nf, ns = payload_counts(ip)
        snap["plugins"][pid] = {
            "files": nf,
            "skills": ns,
            "enabled": enabled.get(pid),
            "version": arr[0].get("version"),
        }
    snap["totals"] = {
        "payload_files": sum(v["files"] for v in snap["plugins"].values()),
        "skill_md": sum(v["skills"] for v in snap["plugins"].values()),
        "local_skills": payload(os.path.join(C, "skills"), lambda f: f.lower() == "skill.md"),
        "local_agents": payload(os.path.join(C, "agents")),
    }
    json.dump(snap, open(BASELINE, "w"), ensure_ascii=False, indent=1)
    print(f"베이스라인 갱신: {BASELINE} (페이로드 {snap['totals']['payload_files']}파일)")


def check_memory_limits(violations: list[str]) -> None:
    """auto-memory MEMORY.md의 공식 한도(200줄/25KB — 초과분 침묵 절단) 접근 감시.

    한도의 90%(180줄/22.5KB)에서 신고해 절단 전에 정리할 여유를 준다. 프론트매터·
    블록 HTML 주석은 공식 한도 계산에서 제외되므로 근사치다(2026-08-09, code.claude.com/docs/en/memory).
    """
    import glob as _glob
    for path in _glob.glob(os.path.join(C, "projects", "*", "memory", "MEMORY.md")):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            continue
        lines = content.count("\n") + 1
        size = len(content.encode("utf-8"))
        if lines > 180 or size > 22_500:
            proj = os.path.basename(os.path.dirname(os.path.dirname(path)))
            violations.append(
                f"MEMORY.md 한도 접근: {proj} {lines}줄/{size}B — 공식 한도(200줄/25KB) "
                f"초과분은 침묵 절단됨. 정리 필요"
            )


def check_router_corpus(violations: list[str]) -> None:
    """라우터 신호 판정을 회귀 코퍼스(scripts/router-corpus.tsv)와 대조한다.

    훅을 실행하지 않고 uiux-skill-router.sh 안의 판정 python 블록만 떼어 같은 프로세스에서
    돌린다(수 ms). 오탐·미탐을 고치면 그 프롬프트를 코퍼스에 추가한다(2026-09-30 감사 #84~#86).
    """
    import contextlib
    import io
    sh = os.path.join(C, "scripts", "uiux-skill-router.sh")
    corpus = os.path.join(C, "scripts", "router-corpus.tsv")
    if not (os.path.exists(sh) and os.path.exists(corpus)):
        violations.append("라우터 코퍼스 검사 불가: uiux-skill-router.sh 또는 router-corpus.tsv 없음")
        return
    with open(sh, encoding="utf-8") as f:
        m = re.search(r"<<'PY'[^\n]*\n(.*?)\nPY\n", f.read(), re.S)
    if not m:
        violations.append("라우터 코퍼스 검사 불가: 판정 python 블록(<<'PY' … PY)을 찾지 못함")
        return
    code = compile(m.group(1), sh, "exec")
    saved = os.environ.get("ROUTER_PROMPT")
    bad = []
    try:
        with open(corpus, encoding="utf-8") as f:
            for line in f:
                if line.startswith("#") or not line.strip():
                    continue
                prompt, _, want = line.rstrip("\n").partition("\t")
                os.environ["ROUTER_PROMPT"] = prompt
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    exec(code, {"__name__": "router"})
                got = buf.getvalue().strip() or "-"
                if got != want.strip():
                    bad.append(f"{prompt!r} 기대={want.strip()} 실제={got}")
    finally:
        if saved is None:
            os.environ.pop("ROUTER_PROMPT", None)
        else:
            os.environ["ROUTER_PROMPT"] = saved
    if bad:
        violations.append(f"라우터 코퍼스 불일치 {len(bad)}건: " + "; ".join(bad[:3]))


def main() -> int:
    if "--update-baseline" in sys.argv:
        update_baseline()
        return 0
    violations: list[str] = []
    for check in (check_payload, check_hooks, check_claims, check_definitions,
                  check_doc_paths, check_coverage, check_gc, check_cache_drift,
                  check_memory_limits, check_router_corpus, check_scope):
        try:
            check(violations)
        except Exception as exc:  # 린트 자체의 버그가 하네스를 막아서는 안 된다
            violations.append(f"린트 오류({check.__name__}): {exc}")
    if not violations:
        print("harness-lint: OK")
        return 0
    print(f"harness-lint: 위반 {len(violations)}건")
    for v in violations:
        print(f"  - {v}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
