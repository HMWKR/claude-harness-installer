#!/usr/bin/env python3
"""codex-sandbox-guard — PreToolUse(mcp__codex__codex) 훅.

rules/cross-vendor-routing.md의 "codex 호출은 sandbox 명시 필수"를 코드로 집행한다.
~/.codex/config.toml 기본이 danger-full-access라, sandbox 파라미터를 생략한 호출은
무의식적으로 전체 접근을 상속한다 — 문서 규범만으로는 서브에이전트 경로에서 전달되지
않으므로(CLAUDE.md 미상속) 훅으로 내림 (2026-08-09 리서치 근거).

정책(위반은 exit 2 차단, stderr가 모델에 전달됨):
- 'sandbox' 키 없음 → 차단.
- 'config'로 sandbox 계열 키(sandbox_mode·sandbox_workspace_write 등)를 넘김 → 차단
  (명시한 sandbox를 덮어쓰거나 쓰기 루트를 넓히는 우회로).
- "read-only" → 통과.
- "workspace-write" → cwd가 쓰기 범위가 되므로 cwd를 검사한다(차단 목록 방식). 없음·빈 값·상대 경로(~ 포함),
  홈 자체와 그 상위(/ 포함), 홈 바로 아래 폴더(~/Desktop 등), 홈의 숨김 폴더(~/.ssh·~/.config·~/.claude·~/.codex …)와
  ~/Library 아래, 소스 루트(.git·package.json 있는 폴더)는 차단한다. 그 밖(예: 프로젝트 하위 산출 폴더, /tmp)은 통과
  (2026-09-30 감사 #23, 2026-10-02 최종 검토로 숨김·Library 트리 추가 — 허용 목록 방식 전환은 사용자 결정 대기).
- Bash로 부르는 codex CLI(`codex exec`)도 같은 규칙이다 — config 기본이 danger-full-access라 `-s` 생략은 전체 접근을
  상속한다. `-s read-only`·`-s workspace-write`만 허용하고, workspace-write면 `--cd`(없으면 셸 cwd)를 위 cwd 규칙으로 본다.
- "danger-full-access"·그 밖의 값 → 차단(샌드박스가 없어 cwd로 범위가 좁혀지지 않는다).
파스 실패·비대상 도구는 fail-open — 단 anomaly 로그를 남겨 무발화 드리프트를 관측
가능하게 한다 (2026-07-25 무발화 훅 사고 재발 방지).
재검토: 2026-11 하네스 재검토 목록에 등재됨.
"""

import json
import os
import re
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
ANOMALY_LOG = HOME / ".claude" / "state" / "hook-anomalies.log"
# workspace-write의 cwd로 주면 안 되는 트리(하위 전체) — 하네스 훅·스크립트와 codex 자체 설정
PROTECTED_TREES = (HOME / ".claude", HOME / ".codex")
# 이 표지가 있는 폴더는 소스 루트 — cwd로 주면 소스 트리 전체가 쓰기 범위가 된다
SOURCE_ROOT_MARKERS = (".git", "package.json")


def log_anomaly(msg: str) -> None:
    try:
        ANOMALY_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(ANOMALY_LOG, "a", encoding="utf-8") as f:
            ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
            f.write(f"{ts} codex-sandbox-guard: {msg}\n")
    except OSError:
        pass


def block(reason: str) -> int:
    print(f"[codex-sandbox-guard] 차단: {reason} (rules/cross-vendor-routing.md)", file=sys.stderr)
    return 2


def _real(path) -> Path:
    return Path(os.path.realpath(path))


def _within(path: Path, base: Path) -> bool:
    # APFS 기본은 대소문자를 구분하지 않고 realpath도 대소문자를 고치지 않는다 — 접어서 비교해야
    # `~/.CLAUDE`처럼 대소문자만 바꾼 경로로 보호 트리·홈 판정을 우회하지 못한다(검토 반박 #23)
    a = tuple(p.casefold() for p in path.parts)
    b = tuple(p.casefold() for p in base.parts)
    return a[:len(b)] == b


def cwd_violation(raw):
    """workspace-write의 cwd가 좁은 절대 경로가 아니면 사유 문자열, 괜찮으면 None."""
    if not isinstance(raw, str) or not raw.strip():
        return "cwd가 없다 — 생략하면 codex MCP 서버의 작업 폴더 전체가 쓰기 범위가 된다"
    if not os.path.isabs(raw):
        return f"cwd {raw!r}는 상대 경로다(~ 포함) — 서버 프로세스 기준으로 풀려 쓰기 범위를 확정할 수 없다"
    cwd = _real(raw)
    home = _real(HOME)
    if _within(home, cwd):
        return f"cwd {cwd}는 홈 전체(또는 그 상위)를 쓰기 범위로 연다"
    if _within(cwd, home):
        rel = cwd.parts[len(home.parts):]
        if len(rel) == 1:
            return f"cwd {cwd}는 홈 바로 아래 폴더다 — 그 아래 전체(다른 프로젝트 포함)가 쓰기 범위가 된다"
        if rel[0].startswith(".") or rel[0].casefold() == "library":
            return f"cwd {cwd}는 홈의 숨김·Library 트리({rel[0]}) 아래다 — 설정·자격 증명·자동 실행 파일을 고칠 수 있다"
    for tree in PROTECTED_TREES:
        if _within(cwd, _real(tree)):
            return f"cwd {cwd}는 {tree} 하위다 — 하네스·codex 설정을 고칠 수 있다"
    for marker in SOURCE_ROOT_MARKERS:
        if (cwd / marker).exists():
            return f"cwd {cwd}는 소스 루트다({marker} 있음) — 소스 트리 전체가 쓰기 범위가 된다"
    return None


# codex CLI 판정은 셸 토큰 단위로 한다 — 명령 전체 정규식은 따옴표 안 프롬프트("Review: -s read-only")의 -s를
# 옵션으로 오인했고, `codex -s danger-full-access exec`처럼 전역 옵션을 앞에 둔 형태를 놓쳤다(2026-10-02 codex 최종 게이트).
# 위협 모델: **실수로 sandbox를 빠뜨리는 것**을 막는 장치다. 스크립트 파일 경유·난독화 같은 의도적 우회는 막지 못한다
# (safety.md의 Read deny와 같은 성격 — 실수 방지 장치이지 보안 경계가 아니다). 그 범위 안에서 줄바꿈·`bash -c`·`eval`·
# 명령 위치·전역 옵션 값을 다룬다(codex 2차 게이트).
# 남는 한계(codex 6차까지 확인, 수용): 따옴표 안에서 하위 명령 이름을 줄 연결로 쪼갠 형태, 출력용 `echo codex exec` 오탐,
# heredoc 본문의 짝 안 맞는 따옴표 오탐(판정 불가로 차단). 근본 해결은 ~/.codex/config.toml 기본 sandbox를 read-only로 두는 것.
CODEX_HINT = re.compile(r"\bcodex\b")
VALUE_OPTS = {"-s", "--sandbox", "-C", "--cd", "--add-dir", "-c", "--config", "-m", "--model", "-p", "--profile",
              "-i", "--image", "-o", "--output-last-message", "--output-schema", "--color", "--local-provider",
              "--enable", "--disable"}
WRAPPERS = {"time", "nohup", "env", "command", "exec", "builtin", "nice", "caffeinate", "xargs", "timeout", "sudo", "doas", "stdbuf", "ionice"}
SHELLS = {"bash", "sh", "zsh", "dash"}


def _normalize(cmd: str) -> str:
    """따옴표 문맥을 따라 셸 구문을 정리한다(codex 3·4차): 따옴표 밖 줄바꿈 → ';'(명령 경계 보존), 역슬래시+줄바꿈 → 제거
    (줄 연결), 단어 시작의 '#' → 그 줄 끝까지 주석으로 버림(다음 줄 명령은 살린다). 여러 줄 따옴표 프롬프트는 그대로 둔다."""
    out, q, i, n = [], None, 0, len(cmd)
    while i < n:
        ch = cmd[i]
        if q == "'":
            if ch == "'":
                q = None
        elif q == '"':
            if ch == "\\" and i + 1 < n:
                out.append(ch + cmd[i + 1]); i += 2; continue
            if ch == '"':
                q = None
        else:
            if ch == "\\" and i + 1 < n:
                if cmd[i + 1] == "\n":
                    i += 2; continue                         # 줄 연결
                out.append(ch + cmd[i + 1]); i += 2; continue
            if ch in "'\"":
                q = ch
            elif ch == "#" and (not out or out[-1][-1:] in " \t;&|("):
                while i < n and cmd[i] != "\n":
                    i += 1                                   # 주석은 줄 끝까지만
                continue
            elif ch == "\n":
                ch = ";"
        out.append(ch)
        i += 1
    return "".join(out)


def _segments(cmd: str):
    """명령을 셸 구분자(; & | ( ) 와 따옴표 밖 줄바꿈) 단위 토큰 구간으로 나눈다. 토큰화할 수 없으면 None."""
    try:
        lex = shlex.shlex(_normalize(cmd), posix=True, punctuation_chars=";&|()")
        lex.whitespace_split = True
        lex.commenters = ""                                  # 주석은 _normalize가 이미 처리했다
        segs, cur = [], []
        for t in lex:
            if t and set(t) <= set(";&|()"):
                if cur:
                    segs.append(cur)
                cur = []
            else:
                cur.append(t)
        if cur:
            segs.append(cur)
        return segs
    except ValueError:
        return None


def _from_command(seg, depth):
    """명령 위치에서 시작하는 토큰 목록 → codex 호출 인자 목록들(래퍼·셸·eval은 이어서 본다). 판정 불가면 None."""
    i = 0
    while i < len(seg) and "=" in seg[i] and not seg[i].startswith("-"):
        i += 1                                              # FOO=1 같은 환경 대입
    if i >= len(seg):
        return []
    exe = os.path.basename(seg[i])
    if exe == "codex":
        return [seg[i + 1:]]
    if exe in WRAPPERS:
        # 래퍼(env·nice·timeout 등)의 옵션 형식은 제각각이라 하나씩 해석하지 않고, 처음 나오는 codex·셸·eval부터 이어서 본다
        k = next((k for k in range(i + 1, len(seg))
                  if os.path.basename(seg[k]) in {"codex", "eval"} | SHELLS), None)
        return _from_command(seg[k:], depth) if k is not None else []
    if depth < 3 and exe in SHELLS:
        j = next((k for k in range(i + 1, len(seg)) if re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*", seg[k])), None)
        return _codex_argvs(seg[j + 1], depth + 1) if j is not None and j + 1 < len(seg) else []
    if depth < 3 and exe == "eval":
        return _codex_argvs(" ".join(seg[i + 1:]), depth + 1)
    return []


def _codex_argvs(cmd: str, depth: int = 0):
    """codex 호출의 인자 목록들(구간마다 명령 위치부터 본다). 토큰화할 수 없으면 None."""
    segs = _segments(cmd)
    if segs is None:
        return None
    out = []
    for seg in segs:
        got = _from_command(seg, depth)
        if got is None:
            return None
        out += got
    return out


RAW_CODEX_EXEC = re.compile(r"(?<![\w.-])codex\b(?=[^;&|\n]*?(?<![\w-])(?:exec|e)\b)")


def _executable_text(cmd: str) -> str:
    """실행될 수 있는 텍스트만 남긴다 — 작은따옴표 안은 지우고, 큰따옴표 안은 $(…)·`…`(명령 치환)만 남긴다(안전망 계수용)."""
    out, i, n, q = [], 0, len(cmd), None
    while i < n:
        ch = cmd[i]
        if q == "'":
            if ch == "'":
                q = None
            i += 1
            continue
        if q == '"':
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                q = None
                i += 1
                continue
            if cmd.startswith("$(", i) or ch == "`":
                closer, depth, j = ("`" if ch == "`" else ")"), 0, i + (1 if ch == "`" else 2)
                k = j
                while k < n:
                    c = cmd[k]
                    if closer == ")" and c == "(":
                        depth += 1
                    elif c == closer:
                        if closer == "`" or depth == 0:
                            break
                        depth -= 1
                    k += 1
                out.append(" ; " + cmd[j:k] + " ; ")         # 명령 치환 안은 실행된다
                i = k + 1
                continue
            i += 1
            continue
        if ch in "'\"":
            q = ch
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def _parse_codex(args):
    """(exec 여부, sandbox 값들, --cd 값들, --add-dir 값들, -c 값들, 값 없는 플래그들). 하위 명령은 'exec'·'e' 토큰이
    어디에 있든 찾는다 — 모르는 전역 옵션의 값이 하위 명령으로 오인되던 문제(`--enable x exec`)."""
    is_exec, sb, cds, adds, cfgs, flags, i = False, [], [], [], [], set(), 0
    while i < len(args):
        a = args[i]
        if a == "--":
            break
        if a.startswith("--") and "=" in a:
            k, v = a.split("=", 1)
        elif a in VALUE_OPTS and i + 1 < len(args):
            k, v = a, args[i + 1]
            i += 1
        elif re.fullmatch(r"-[sCc]\S+", a):          # -sread-only · -C/dir 붙여 쓰기
            k, v = a[:2], a[2:]
        else:
            if a.startswith("-"):
                flags.add(a)
            elif a in ("exec", "e"):
                is_exec = True
            i += 1
            continue
        {"-s": sb, "--sandbox": sb, "-C": cds, "--cd": cds, "--add-dir": adds, "-c": cfgs, "--config": cfgs}.get(k, []).append(v)
        i += 1
    return is_exec, sb, cds, adds, cfgs, flags


def check_codex_cli(data) -> int:
    """Bash의 `codex exec`: sandbox 명시·허용 값·우회 옵션·쓰기 범위(--cd·--add-dir)를 MCP 경로와 같은 규칙으로 본다."""
    ti = data.get("tool_input")
    cmd = ti.get("command", "") if isinstance(ti, dict) else ""
    if not isinstance(cmd, str) or not CODEX_HINT.search(cmd):
        return 0
    argvs = _codex_argvs(cmd)
    if argvs is None:
        if re.search(r"\bcodex\s+(?:\S+\s+)*?(?:exec|e)\b", cmd):
            return block("codex 호출이 든 명령의 따옴표를 해석할 수 없다 — 따옴표를 맞춰 다시 실행한다.")
        return 0
    # 안전망(codex 5차): 셸 제어문(if·for·{})·명령 치환·백틱 안 호출은 파서가 못 볼 수 있다. 실행될 수 있는 텍스트에 보이는
    # `codex … exec`가 파서가 확인한 exec 호출보다 많으면 판정 불가로 막는다(출력용 `echo codex exec` 같은 오탐은 감수).
    parsed = [x for x in argvs if _parse_codex(x)[0]]
    if len(RAW_CODEX_EXEC.findall(_executable_text(_normalize(cmd)))) > len(parsed):
        return block("codex exec가 셸 제어문·명령 치환·백틱 안에 있어 sandbox를 판정할 수 없다 — "
                     "단순한 한 줄 `codex exec -s read-only …`로 다시 실행한다.")
    for args in argvs:
        is_exec, sb, cds, adds, cfgs, flags = _parse_codex(args)
        if not is_exec:
            continue                                        # login·mcp 등 실행이 아닌 하위 명령
        if flags & {"-h", "--help", "-V", "--version"}:
            continue                                        # 도움말 — 같은 호출의 argv 안에서만 본다
        if any(f.startswith("--dangerously-bypass-approvals") or f in ("--yolo", "--full-auto") for f in flags):
            return block("codex exec의 sandbox 우회·자동 승인 옵션(--dangerously-bypass-approvals-and-sandbox·--yolo·--full-auto)은 쓰지 않는다.")
        if any(c.split("=", 1)[0].strip().startswith("sandbox") for c in cfgs):
            return block("codex exec에 -c로 sandbox 설정을 넘기지 마라 — -s 하나로만 정한다.")
        if not sb:
            return block("codex exec에 -s(--sandbox)가 없다 — config 기본이 danger-full-access다(-p 프로필보다 -s가 우선). "
                         "검증은 -s read-only, 쓰기는 -s workspace-write + 좁은 --cd.")
        bad = [v for v in sb if v not in ("read-only", "workspace-write")]
        if bad:
            return block(f"codex exec -s {bad[0]}는 허용하지 않는다 — read-only 또는 workspace-write.")
        if "workspace-write" in sb:
            if not cds:
                return block("codex exec -s workspace-write에는 --cd <좁은 산출 폴더>를 명시한다 — 앞선 `cd`는 훅이 볼 수 없다.")
            for path in [cds[-1]] + adds:
                reason = cwd_violation(path)
                if reason:
                    return block(f"codex exec -s workspace-write — 쓰기 경로 검사(--cd·--add-dir): {reason}.")
    return 0


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception as exc:  # noqa: BLE001 — 포맷 드리프트 시 전체 codex 호출 차단 방지
        log_anomaly(f"stdin 파스 실패 fail-open: {exc}")
        return 0

    if data.get("tool_name") == "Bash":
        return check_codex_cli(data)
    if data.get("tool_name") != "mcp__codex__codex":
        return 0

    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        log_anomaly("tool_input 형태 불명 fail-open")
        return 0

    if "sandbox" not in tool_input:
        return block(
            "mcp__codex__codex 호출에 sandbox 파라미터가 없다. "
            "config.toml 기본이 danger-full-access이므로 의도를 명시하라 — 검증·심판은 "
            '"read-only", 쓰기가 필요하면 "workspace-write" + 좁은 절대 경로 cwd.'
        )

    config = tool_input.get("config")
    if isinstance(config, dict):
        keys = sorted(str(k) for k in config if "sandbox" in str(k))
        if keys:
            return block(f"config로 sandbox 설정({', '.join(keys)})을 넘기지 마라 — sandbox 파라미터 하나로만 정한다.")

    sandbox = tool_input["sandbox"]
    if sandbox == "read-only":
        return 0
    if sandbox != "workspace-write":
        return block(
            f'sandbox {sandbox!r}는 허용하지 않는다 — 샌드박스가 없으면 cwd로 쓰기 범위가 좁혀지지 않는다. '
            '"read-only" 또는 "workspace-write" + 좁은 cwd를 쓴다. 전체 접근이 꼭 필요하면 사용자에게 먼저 묻는다.'
        )

    reason = cwd_violation(tool_input.get("cwd"))
    if reason:
        return block(
            f'sandbox "workspace-write"는 cwd 하위 전체에 쓴다 — {reason}. '
            "산출 전용 폴더(예: <프로젝트>/assets/generated/)를 절대 경로로 준다."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
