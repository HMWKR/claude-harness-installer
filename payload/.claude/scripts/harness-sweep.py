#!/usr/bin/env python3
"""하네스 전역 정적 오류 스윕 — 읽기 전용. 아무것도 실행·수정하지 않는다.

`harness-lint.py`와 역할이 다르다:
  - lint  : PostToolUse 상시 경로. **값싼** 검사만(0.4s). 매 편집마다 돈다.
  - sweep : 수동·심층. 문법 컴파일·frontmatter 전수·MCP 설정까지 본다(1.1s).

훅 스크립트를 합성 stdin으로 '실행'하는 방식은 **채택하지 않는다** — 외부 데몬에 위조
라이프사이클을 발사하고 쓰기 훅을 돌린다(감사 중 checkpoint.md를 덮은 사고의 원인).
문법 검사는 `py_compile`/`node --check`/`bash -n`으로만 한다.

사용법:
    python3 ~/.claude/scripts/harness-sweep.py         # 검사 (exit 1 = 오류 있음)
    python3 ~/.claude/scripts/harness-sweep.py --all   # 등재된 조달물 결함까지 표시
"""
import json, os, re, subprocess, sys
from pathlib import Path

C = Path.home() / ".claude"
findings = []          # (심각도, 범주, 대상, 내용)
notes = []             # 결함이 아닌 **커버리지 고지** — rc에 영향을 주지 않는다

# 조달물의 알려진 결함 — 고치지 않고 등재만 한다(캐시는 휘발성이라 패치가 되돌아온다).
# 상시 출력되면 사용자가 리포트 전체를 스킵하도록 훈련되므로 기본 표시에서 제외하고,
# `--all` 로만 보인다. 목록이 git 추적 대상이라 리뷰에서는 보이고, **새 항목이 생기면
# 다시 시끄러워진다**. harness-lint.py 의 KNOWN_HOOK_ISSUES 와 같은 규율.
KNOWN_ISSUES: list[tuple[str, str, str]] = [
    # (대상, 메시지 시그니처, 사유)
    # 억제는 **고칠 수 없는 것에만** 쓰고, 왜 고칠 수 없는지를 사유에 적는다.
    ("pr-review-toolkit@claude-plugins-official silent-failure-hunter.md",
     "YAML 파싱 실패 — 메타데이터가 통째로 비어 로드된다: mapping values are not allowed here",
     "pr-review-toolkit 벤더 캐시 — description에 따옴표 없는 `: `가 있어 엄격 YAML만 실패한다. "
     "Claude Code는 관대 파서로 정상 로드함(2026-09-28 세션 에이전트 목록에 description 노출 확인) "
     "— 기능 결함 없음, 캐시라 수정은 플러그인 갱신 시 소실."),
    # 고칠 수 있으면 고치고 탐지기를 남긴다. 2026-07-27에 두 번 비웠다:
    #  · understand-anything `$TOOL_INPUT` → 수리(`patches/README.md` §3)
    #  · bkit `pdca-post-write.js` 부재 → **복원**(`patches/README.md` §5).
    #    한때 "try/catch 안이니 선택적 로드, 결함 아님"으로 무신고했으나 반증됐다 —
    #    가드는 실패 격리이지 기능이 선택이라는 증거가 아니다. 지금은 가드 없으면
    #    HIGH(크래시), 가드되면 MED(그 단계 미실행)로 **둘 다 신고**한다.
]


def add(sev, cat, target, msg):
    findings.append((sev, cat, str(target).replace(str(Path.home()), "~"), msg))


def run(cmd):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        return p.returncode, (p.stderr or p.stdout or "").strip()
    except Exception as exc:
        return -1, str(exc)


def enabled_plugin_paths():
    try:
        inst = json.load(open(C / "plugins/installed_plugins.json"))["plugins"]
        en = json.load(open(C / "settings.json")).get("enabledPlugins") or {}
    except Exception as exc:
        add("HIGH", "설정", "installed_plugins.json", f"읽기 실패: {exc}")
        return {}
    return {p: Path(a[0]["installPath"]) for p, a in inst.items() if en.get(p) and a}


# ---------- 1. 실행 자산 문법 ----------
def check_syntax():
    roots = [C / "scripts", C / "workflows", C / "disabled"]
    exts = {".py": None, ".js": None, ".mjs": None, ".cjs": None, ".sh": None}
    for root in roots:
        if not root.is_dir():
            continue
        for f in sorted(root.rglob("*")):
            if not f.is_file() or f.suffix not in exts or "__pycache__" in str(f):
                continue
            if f.suffix == ".py":
                rc, err = run([sys.executable, "-m", "py_compile", str(f)])
            elif f.suffix == ".sh":
                rc, err = run(["bash", "-n", str(f)])
            else:
                rc, err = run(["node", "--check", str(f)])
            if rc != 0:
                add("HIGH", "문법", f.relative_to(C), err.splitlines()[0][:150] if err else f"rc={rc}")


# ---------- 2. frontmatter 유효성 ----------
FM = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.S)


def parse_fm(text):
    m = FM.match(text)
    if not m:
        return None
    out, key = {}, None
    for line in m.group(1).splitlines():
        if re.match(r"^\s*-\s+", line) and key:
            out.setdefault(key, []) if isinstance(out.get(key), list) else out.update({key: []})
            out[key].append(line.strip()[2:].strip())
        elif ":" in line and not line.startswith(" "):
            key, _, val = line.partition(":")
            key = key.strip()
            out[key] = val.strip().strip("\"'") or []
    return out


def check_frontmatter():
    specs = [
        ("skills", "SKILL.md", ("name", "description")),
        ("agents", "*.md", ("name", "description")),
        ("commands", "*.md", ("description",)),
    ]
    for sub, pat, required in specs:
        d = C / sub
        if not d.is_dir():
            continue
        files = sorted(d.rglob(pat)) if pat.startswith("*") else \
            [p for p in d.rglob("*") if p.is_file() and p.name.lower() == pat.lower()]
        for f in files:
            text = f.read_text(errors="replace")
            fm = parse_fm(text)
            if fm is None:
                add("HIGH", "frontmatter", f.relative_to(C), "frontmatter 블록 없음")
                continue
            for k in required:
                if not fm.get(k):
                    add("MED", "frontmatter", f.relative_to(C), f"필수 키 `{k}` 없음/빈값")
            if sub == "skills" and f.name != "SKILL.md":
                add("MED", "명명", f.relative_to(C),
                    f"파일명이 `{f.name}` — 로컬 관행은 `SKILL.md`")
        # 스킬 디렉토리인데 SKILL.md 자체가 없는 경우
        if sub == "skills":
            for sk in sorted(p for p in d.iterdir() if p.is_dir()):
                if sk.name == "synced" and any(p.name.startswith(".bucket-") for p in sk.iterdir()):
                    continue  # Claude Code 관리 계정 스킬 동기화 버킷 — SKILL.md는 하위 폴더에 있다
                if not any(p.name.lower() == "skill.md" for p in sk.iterdir() if p.is_file()):
                    add("HIGH", "스킬", sk.relative_to(C), "SKILL.md 부재")


# ---------- 3. 에이전트 tools 화이트리스트 ----------
KNOWN_TOOLS = {
    "Read", "Write", "Edit", "Glob", "Grep", "Bash", "WebFetch", "WebSearch", "Agent",
    "NotebookEdit", "TaskCreate", "TaskUpdate", "TaskList", "TaskGet", "TaskOutput",
    "TaskStop", "Skill", "ToolSearch", "Artifact", "Monitor", "SendMessage", "Workflow",
    "AskUserQuestion", "EnterPlanMode", "ExitPlanMode", "CronCreate", "CronList",
    "CronDelete", "PushNotification", "RemoteTrigger", "EnterWorktree", "ExitWorktree",
    "ScheduleWakeup", "ReportFindings", "ListMcpResourcesTool", "ReadMcpResourceTool",
}


def check_plugin_frontmatter():
    """**활성 플러그인**의 SKILL.md·agents/*.md frontmatter 가 유효한 YAML인가.

    2026-07-27 7라운드: 로컬 자산만 검사하고 플러그인은 안 봐서, 활성 플러그인
    4개 파일의 YAML 파싱 실패를 놓쳤다(`claude plugin validate` 는 rc=1). 당시에는
    런타임이 frontmatter를 빈 메타데이터로 읽는다고 판단했으나, 2026-09-28·30 세션의
    에이전트 목록에서 silent-failure-hunter의 설명이 정상 노출돼 **현재 런타임은 관대
    파서로 읽는 것**이 확인됐다. 그래도 신고는 유지한다 — 엄격 파서(`plugin validate`)가
    실패하고 런타임 파서가 바뀌면 조용한 능력 상실로 이어진다.
    원인은 대개 따옴표 없는 값 안의 콜론(`NOT for:`, `Examples:`).
    """
    try:
        import yaml
    except ImportError:
        add("MED", "스윕오류", "check_plugin_frontmatter",
            "pyyaml 미설치 — 플러그인 frontmatter 검증을 건너뛴다")
        return
    n = 0
    for pid, root in enabled_plugin_paths().items():
        files = list(root.rglob("SKILL.md"))
        agents = root / "agents"
        if agents.is_dir():
            files += list(agents.glob("*.md"))
        for f in files:
            try:
                text = f.read_text(errors="replace")
            except OSError:
                continue
            m = FM.match(text)
            if not m:
                continue
            n += 1
            try:
                d = yaml.safe_load(m.group(1))
            except Exception as exc:
                add("HIGH", "플러그인 frontmatter", f"{pid} {f.name}",
                    f"YAML 파싱 실패 — 메타데이터가 통째로 비어 로드된다: "
                    f"{str(exc).splitlines()[0][:90]}")
                continue
            if not isinstance(d, dict) or not d.get("name"):
                add("MED", "플러그인 frontmatter", f"{pid} {f.name}",
                    "`name` 이 없다 — 이름으로 호출할 수 없다")
    if n == 0:
        add("HIGH", "커버리지", "플러그인 frontmatter", "검사 대상이 0개다")


def check_plugin_manifest():
    """활성 플러그인이 **매니페스트로 식별 가능한가**.

    두 형태가 모두 정상이다: ① 플러그인 디렉토리에 `.claude-plugin/plugin.json`,
    ② 마켓플레이스의 `.claude-plugin/marketplace.json` 안에 **인라인 선언**
    (`source: ./plugins/x`, 보통 `strict: false`). accesslint 가 ②인데,
    2026-07-27 8라운드에서 `claude plugin validate <플러그인 디렉토리>` 로 검증해
    "매니페스트 없음"으로 오판된 사례가 있다 — **검증 대상을 잘못 잡으면 정상이
    결함으로 보인다.** 여기서는 둘 중 **어느 쪽도 아닐 때만** 신고한다.
    """
    n = 0
    for pid, root in enabled_plugin_paths().items():
        n += 1
        if (root / ".claude-plugin" / "plugin.json").is_file():
            continue
        name = pid.split("@")[0]
        market = pid.split("@")[1] if "@" in pid else ""
        mf = C / "plugins" / "marketplaces" / market / ".claude-plugin" / "marketplace.json"
        declared = False
        if mf.is_file():
            try:
                for entry in (json.load(open(mf)).get("plugins") or []):
                    if entry.get("name") == name:
                        declared = True
                        break
            except (OSError, ValueError):
                add("MED", "플러그인 매니페스트", market,
                    f"marketplace.json 파싱 불가: {mf}")
        if not declared:
            add("HIGH", "플러그인 매니페스트", pid,
                "`.claude-plugin/plugin.json` 도 없고 마켓플레이스 인라인 선언도 없다"
                " — 이 플러그인은 식별 정보 없이 로드된다")
    if n == 0:
        add("HIGH", "커버리지", "플러그인 매니페스트", "검사 대상이 0개다")


def check_agent_tools():
    d = C / "agents"
    if not d.is_dir():
        return
    for f in sorted(d.glob("*.md")):
        fm = parse_fm(f.read_text(errors="replace")) or {}
        tools = fm.get("tools")
        if isinstance(tools, str):
            tools = [t.strip() for t in tools.split(",") if t.strip()]
        for t in tools or []:
            if t not in KNOWN_TOOLS and not t.startswith("mcp__") and t != "*":
                add("MED", "에이전트", f.relative_to(C), f"미지의 도구명 `{t}`")
        if "model" in fm:
            add("MED", "에이전트", f.relative_to(C),
                f"모델 하드코딩 `model: {fm['model']}` — model-agnostic 위반")


# ---------- 4. 상시 문서의 죽은 경로 ----------
# "그것은 이제 없다"고 말하는 문장에 등장하는 경로는 죽은 참조가 아니라 **정확한 서술**이다.
# 캐시 drift 검사에서 배운 것과 같은 교훈 — 단순 언급 카운트는 지표가 아니다.
# 2026-07-27 교차검증 지적: ① 줄 전체를 면제하면 "구 `X`는 폐기됨; 활성 참조 `Y`" 에서
# 진짜 죽은 참조 Y까지 숨는다 → 경로 **주변 문맥**으로 좁힌다. ② `구 `가 `연구 `에
# 부분 매치했다 → 앞이 한글이면 매치하지 않게 한다.
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


def check_doc_refs():
    docs = [C / "CLAUDE.md"] + sorted((C / "rules").glob("*.md"))
    docs += sorted((C / "commands").glob("*.md"))
    path_re = re.compile(r"[`(]((?:/Users/[\w./@-]+|~/[\w./@-]+))[`)]")
    ignore = {"/goal", "/what", "/what-ce", "/insight-check", "/loop", "/effort"}
    for doc in docs:
        if not doc.exists():
            continue
        lines = doc.read_text(errors="replace").splitlines()
        for i, line in enumerate(lines, 1):
            for raw in sorted(set(path_re.findall(line))):
                if raw in ignore or raw.rstrip("/").endswith("**") or "<" in raw:
                    continue
                if os.path.exists(os.path.expanduser(raw)):
                    continue
                if _is_gone_context(line, raw):
                    continue  # 그 경로가 '이제 없다'는 서술 안에 있다 — 정확한 기록이다
                add("MED", "죽은참조", f"{doc.relative_to(C)}:{i}", raw)


# ---------- 5. MCP 설정 무결성 ----------
def check_mcp():
    for name, p in (("~/.claude.json", Path.home() / ".claude.json"),
                    ("~/.claude/.mcp.json", C / ".mcp.json")):
        if not p.exists():
            continue
        try:
            d = json.load(open(p))
        except Exception as exc:
            add("HIGH", "MCP", name, f"파싱 실패: {exc}")
            continue
        servers = d.get("mcpServers") or {}
        for sname, cfg in servers.items():
            cmd = cfg.get("command")
            if not cmd:
                if not cfg.get("url") and not cfg.get("type"):
                    add("MED", "MCP", f"{name}:{sname}", "command·url 모두 없음")
                continue
            if cmd.startswith("/") and not os.path.exists(cmd):
                add("HIGH", "MCP", f"{name}:{sname}", f"실행파일 부재: {cmd}")
            elif not cmd.startswith("/") and run(["command", "-v", cmd])[0] != 0:
                rc, _ = run(["/bin/sh", "-c", f"command -v {cmd}"])
                if rc != 0:
                    add("HIGH", "MCP", f"{name}:{sname}", f"명령 없음: {cmd}")
            for a in cfg.get("args") or []:
                if a.startswith("/") and not os.path.exists(a) and not a.startswith("/tmp"):
                    add("MED", "MCP", f"{name}:{sname}", f"인자 경로 부재: {a}")


# ---------- 6. 플러그인 훅 스크립트 실존 (enabled만) ----------
def check_plugin_hooks():
    for pid, ip in enabled_plugin_paths().items():
        hj = ip / "hooks" / "hooks.json"
        if not hj.exists():
            continue
        try:
            d = json.load(open(hj))
        except Exception as exc:
            add("HIGH", "플러그인훅", pid, f"hooks.json 파싱 실패: {exc}")
            continue
        for ev, groups in (d.get("hooks") or {}).items():
            for g in groups if isinstance(groups, list) else []:
                for h in g.get("hooks", []):
                    cmd = h.get("command", "")
                    for raw in re.findall(r'CLAUDE_PLUGIN_ROOT"?\}?(/[^\s"\';|&)]+)', cmd):
                        if not (ip / raw.lstrip("/")).exists():
                            add("HIGH", "플러그인훅", f"{pid} {ev}", f"스크립트 부재: {raw}")
                    if "$TOOL_INPUT" in cmd:
                        add("MED", "플러그인훅", f"{pid} {ev}",
                            "$TOOL_INPUT 참조 — 훅 입력은 stdin JSON, 이 변수는 없다")
                    check_cwd_require(pid, ev, ip, cmd)
                    check_hook_script_health(pid, ev, ip, cmd)
    # 순회가 끝난 뒤 한 번에 문법 검사한다(단일 node 프로세스).
    _batch_syntax_check()


# 훅은 **프로젝트 디렉토리를 cwd로** 실행된다. 스크립트가 `process.cwd()`를 자기
# 플러그인 루트로 착각해 거기서 모듈을 require하면 플러그인 루트 밖의 모든 세션에서
# 로드 시점에 죽는다. bkit `lint-skill-md.js`가 정확히 이 형태였다(2026-07-27) —
# 파일 헤더는 "Exit: 0 always, never blocks write"라고 선언하는데 실제는 rc=1 + 스택트레이스.
_CWD_VAR = re.compile(r"(?:const|let|var)\s+(\w+)\s*=\s*process\.cwd\(\)")
_CALL_OPEN = re.compile(r"\b(?:require|import)\(")


def _cwd_in_call_args(text: str) -> bool:
    """`require(...)`/`import(...)` 의 **인자 안에** `process.cwd()` 가 있는가.

    정규식으로는 가를 수 없다 — `require('path').resolve(process.cwd(), ...)` 는
    require 가 **닫힌 뒤** cwd 를 쓰는 정상 코드인데(프로젝트 경로 해석),
    문자 창 방식으로는 오탐이 된다(6라운드 후 실제 bkit 에서 적발). 그래서 여는
    괄호부터 깊이를 세어, 깊이가 0으로 돌아가기 **전에** cwd 가 나오는지만 본다.
    """
    for m in _CALL_OPEN.finditer(text):
        i, depth = m.end(), 1
        while i < len(text) and depth:
            c = text[i]
            if c == "(":
                if text.startswith("process.cwd()", i - len("process.cwd")) or \
                   text[i - 11:i] == "process.cwd":
                    return True
                depth += 1
            elif c == ")":
                depth -= 1
            elif c in ";{}":
                break
            i += 1
    return False


# 로컬 모듈 require — `require('./x')`, `require(path.join(ROOT,'scripts/x.js'))` 양쪽.
# `path.join(...)` 뿐 아니라 별칭(`const p = require('path')` → `p.join`)도 잡는다 —
# `path\.join` 만 보면 별칭을 쓴 스크립트에서 추적이 조용히 끊긴다(2026-07-27 자체 회귀).
_LOCAL_REQ = re.compile(
    r"""(?:require|import)\(\s*(?:\w+\.join\([^)]*?['"]([^'"]+\.[cm]?[jt]s)['"]"""
    r"""|['"](\.{1,2}/[^'"]+)['"])""")
# ESM **정적** 구문 — `import x from './y.mjs'`, `export * from './z.js'`,
# `import './side-effect.js'`. 호출형(`import(...)`)만 보던 정규식이 이 24개 파일의
# 전이 의존성을 통째로 놓쳤다(2026-07-27 10라운드, 정적 전이 19개 누락).
# `const h = path.join(__dirname, 'x.js'); require(h)` — 변수에 담았다 부르는 형태.
# 인라인만 보던 정규식이 이걸 놓쳐, bkit 의 **실존하지 않는 모듈 로드**를 못 잡았다
# (2026-07-27 10라운드: `scripts/pdca-post-write.js` 부재가 try/catch 로 조용히 삼켜짐).
_DIRNAME_JOIN = re.compile(
    r"""\w+\.join\(\s*__dirname\s*,\s*['"]([^'"]+\.[cm]?js)['"]""")
_ESM_FROM = re.compile(
    r"""(?:^|\n)\s*(?:import|export)\b[^;\n]*?['"](\.{1,2}/[^'"]+)['"]""")


def _strip_js(text: str) -> tuple[str, str]:
    """(주석만 제거, 주석+문자열 제거) 를 한 번의 문자 스캔으로 만든다.

    정규식으로 주석→문자열 순서로 지웠더니 3라운드가 세 가지를 깼다:
    문자열 안의 프로토콜 상대 URL(`//cdn...`)이 주석으로 먹히고, 템플릿 리터럴의
    `${...}`와 정규식 리터럴이 잘못 처리됐다. 상태를 들고 한 번에 훑는 게 유일하게
    맞는 방법이다.

    두 판본을 따로 돌려주는 이유: cwd 변수·`require(VAR)` 탐지는 문자열까지 지운
    쪽이라야 오탐이 없고, require **경로 추출**은 문자열이 살아 있어야 한다.
    """
    src, nostr = [], []      # 주석만 제거 / 주석+문자열 제거
    i, n = 0, len(text)
    prev = ""                # 직전 유의미 문자 — 정규식 리터럴 판별용
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            j = text.find("\n", i)
            j = n if j < 0 else j
            src.append(" " * (j - i)); nostr.append(" " * (j - i)); i = j
            continue
        if c == "/" and nxt == "*":
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            pad = "".join(ch if ch == "\n" else " " for ch in text[i:j])
            src.append(pad); nostr.append(pad); i = j
            continue
        if c == "/" and prev in ("", "(", ",", "=", ":", "[", "!", "&", "|", "?",
                                 "{", "}", ";", "+", "-", "*", "%", "<", ">", "~", "^"):
            # 정규식 리터럴 — 내용은 코드가 아니므로 양쪽에서 지운다
            j, esc, cls = i + 1, False, False
            while j < n:
                d = text[j]
                if esc: esc = False
                elif d == "\\": esc = True
                elif d == "[": cls = True
                elif d == "]": cls = False
                elif d == "/" and not cls: break
                elif d == "\n": j = i; break
                j += 1
            if j > i:
                src.append(" " * (j + 1 - i)); nostr.append(" " * (j + 1 - i))
                i = j + 1; prev = "/"
                continue
        if c in ("'", '"', "`"):
            q, j, esc = c, i + 1, False
            spans = []            # 템플릿 보간 `${...}` 구간 — 여기는 **실행 코드**다
            while j < n:
                d = text[j]
                if esc:
                    esc = False
                elif d == "\\":
                    esc = True
                elif d == q:
                    break
                elif q == "`" and d == "$" and j + 1 < n and text[j + 1] == "{":
                    k, depth_b = j + 2, 1
                    while k < n and depth_b:
                        if text[k] == "{": depth_b += 1
                        elif text[k] == "}": depth_b -= 1
                        k += 1
                    spans.append((j + 2, k - 1))
                    j = k - 1
                elif q != "`" and d == "\n":
                    break                               # 미종결 문자열
                j += 1
            end = min(j + 1, n)
            body = text[i:end]
            src.append(body)                            # 경로 추출용 — 원문 보존
            # 문자열 제거본: 리터럴 부분만 지우고 `${...}` 안은 코드로 남긴다.
            # 4·5차 반증 — 템플릿 보간 안의 `process.cwd()`/`require()`가 통째로 사라졌다.
            out, cur = [], i
            for a2, b2 in spans:
                out.append("".join(ch if ch == "\n" else " " for ch in text[cur:a2]))
                # 보간 안도 **JS 코드**다 — 그 안의 문자열·주석·중첩 템플릿을 코드로
                # 오인하지 않도록 같은 스캐너를 재귀 적용한다(6라운드 지적).
                out.append(_strip_js(text[a2:b2])[1])
                cur = b2
            out.append("".join(ch if ch == "\n" else " " for ch in text[cur:end]))
            nostr.append("".join(out))
            i = end; prev = q
            continue
        src.append(c); nostr.append(c)
        if not c.isspace():
            prev = c
        i += 1
    return "".join(src), "".join(nostr)


# 파일 단위 분석 결과 캐시 — {경로: (cwd변수명|None, [로컬 require 경로])}.
# `seen` 을 깊이 기반으로 완화하자(형제 탐색 복구) 재탐색이 11,994회로 폭증했다.
# 정확성은 "진입점마다 완전 탐색"에서 오고 비용은 "파일 분석 1회"로 막는다 —
# 둘을 분리하면 둘 다 얻는다(2026-07-27 3라운드 후속).
_JS_CACHE: dict = {}
_TRUNCATED = [0]   # require 추적 상한에서 멈춘 횟수(요약 보고용)
_JS_TO_CHECK: list = []   # 배치 문법 검사 대기열

# 단일 node 프로세스로 전체 문법 검사. `vm.Script` 는 CJS 문법만 받으므로, ESM 고유
# 오류(`Cannot use import statement outside a module` / `Unexpected token 'export'`)는
# **문법 오류가 아니라 모듈 종류 차이**로 보고 통과시킨다.
_BATCH_JS = r"""
const vm = require('vm'), fs = require('fs');
const files = JSON.parse(fs.readFileSync(0, 'utf8'));
// ESM 고유 오류는 **문법 오류가 아니라 모듈 종류 차이**다 — 통과시킨다.
const ESM = /Cannot use import statement outside a module|Unexpected token '(export|import)'|await is only valid/;
const bad = [];
for (const f of files) {
  let src;
  try { src = fs.readFileSync(f, 'utf8'); } catch (e) { continue; }
  // shebang 은 파일 **맨 앞**에서만 유효하다. 래퍼로 감싸면 위치가 밀려
  // `Invalid or unexpected token` 오탐이 된다(2026-07-27 실측 54건). 먼저 벗긴다.
  const body = src.startsWith('#!') ? src.slice(src.indexOf('\n') + 1) : src;
  // Node 의 CJS 모듈 래퍼로 감싼다. 감싸지 않으면 CJS 에서 합법인 최상위 `return` 이
  // `Illegal return statement` 오탐이 된다(실측 4건).
  const wrapped = '(function (exports, require, module, __filename, __dirname) {' +
                  body + '\n});';
  try { new vm.Script(wrapped, { filename: f }); }
  catch (e) {
    const m = String((e && e.message) || e).split('\n')[0];
    if (ESM.test(m)) {
      // ESM 이면 래퍼 없이 다시 시도해 진짜 문법 오류만 남긴다.
      try { new vm.Script(body, { filename: f }); }
      catch (e2) {
        const m2 = String((e2 && e2.message) || e2).split('\n')[0];
        if (!ESM.test(m2)) bad.push([f, m2]);
      }
      continue;
    }
    bad.push([f, m]);
  }
}
process.stdout.write(JSON.stringify(bad));
"""


def _batch_syntax_check():
    """모아 둔 JS 파일을 **한 번의 node 실행**으로 전부 문법 검사한다."""
    files = sorted(set(_JS_TO_CHECK))
    _JS_TO_CHECK.clear()
    if not files:
        return
    try:
        pr = subprocess.run(["node", "-e", _BATCH_JS], input=json.dumps(files),
                            capture_output=True, text=True, timeout=180)
    except Exception as exc:
        add("MED", "스윕오류", "_batch_syntax_check", f"배치 문법 검사 실패: {exc}")
        return
    if pr.returncode != 0:
        add("MED", "스윕오류", "_batch_syntax_check",
            f"node 실행 실패 rc={pr.returncode}: {(pr.stderr or '')[:120]}")
        return
    try:
        for path, msg in json.loads(pr.stdout or "[]"):
            add("HIGH", "플러그인훅", path, f"문법 오류(훅이 로드하는 모듈): {msg[:110]}")
    except ValueError as exc:
        add("MED", "스윕오류", "_batch_syntax_check", f"결과 파싱 실패: {exc}")


def _try_ranges(text: str):
    """`try { … }` 블록의 (시작, 끝) 오프셋 목록. 주석·문자열이 제거된 텍스트를 받는다.

    `require` 가 try 안에 있으면 그것은 **선택적 로드**다 — 대상이 없어도 예외가 잡혀
    크래시하지 않는다. 실제로 bkit 은 그 자리에 `debugLog(...)` 와 `return false` 를
    두어 부재를 설계로 다루고 있다. 가드된 것을 "로드 시점 크래시"로 신고하면
    **정상 코드를 결함으로 부르는 오탐**이다(2026-07-27 10차 후속에서 자각).
    """
    out, i, n = [], 0, len(text)
    while True:
        i = text.find("try", i)
        if i < 0:
            break
        if (i and (text[i - 1].isalnum() or text[i - 1] == "_")):
            i += 3
            continue
        j = i + 3
        while j < n and text[j] in " \t\r\n":
            j += 1
        if j >= n or text[j] != "{":
            i += 3
            continue
        depth, k = 1, j + 1
        while k < n and depth:
            if text[k] == "{":
                depth += 1
            elif text[k] == "}":
                depth -= 1
            k += 1
        out.append((j, k))
        i = j + 1
    return out


def _canon(p: Path) -> Path:
    """경로 정규화. `hooks/../lib/x.js` 와 `scripts/../lib/x.js` 는 같은 파일인데
    문자열로 다뤄서 3,147개 별칭이 165개 실파일을 가리키고 있었다 — 재분석 낭비이자
    같은 파손의 중복 신고 원인이다(2026-07-27 9라운드)."""
    try:
        return Path(os.path.realpath(p))
    except OSError:
        return p


def _analyze_js(f, root, depth=0):
    """(cwd 기반 require를 만드는 변수명 | None, [로컬 require 상대경로]) — 파일당 1회."""
    key = str(f)
    if key in _JS_CACHE:
        return _JS_CACHE[key]
    res = (None, [])
    if f.is_file():
        try:
            raw_text = f.read_text(errors="replace")
        except OSError as exc:
            add("MED", "스윕오류", str(f), f"훅 스크립트 읽기 실패 — 검사 못 함: {exc}")
            _JS_CACHE[key] = res
            return res
        # 문법 검사는 **깊이 제한 없이** 하되, 파일마다 `node --check` 를 띄우면
        # 9,377개 × 46ms = 7분이 된다. 여기서는 대상만 모으고, 순회가 끝난 뒤
        # `_batch_syntax_check()` 가 **단일 node 프로세스**로 한꺼번에 검사한다.
        if f.suffix in {".js", ".cjs", ".mjs"}:
            _JS_TO_CHECK.append(str(f))
        src, text = _strip_js(raw_text)
        bad = None
        for var in set(_CWD_VAR.findall(text)):
            if re.search(rf"(?:require|import)\([^)]*\b{re.escape(var)}\b", text):
                bad = var
                break
        if not bad and _cwd_in_call_args(text):
            # 변수를 거치지 않고 바로 결합하는 형태 — `import(process.cwd() + '/x.js')`.
            # `[^)]*` 로 쓰면 `process.cwd()` 안의 `)` 에서 끊긴다(6라운드 지적) →
            # 문(statement) 경계 문자로 제한한다.
            bad = "process.cwd()"
        tr = _try_ranges(text)

        def _guarded(pat, rel):
            """이 참조가 try 블록 안에 있는가 — 하나라도 가드 밖이면 가드 아님."""
            for m in re.finditer(re.escape(rel), src):
                if not any(a <= m.start() < b for a, b in tr):
                    return False
            return True

        rels = []
        for a, b in _LOCAL_REQ.findall(src):
            r = a or b
            rels.append((r, _guarded(None, r)))
        for r in _ESM_FROM.findall(src):
            rels.append((r, False))     # ESM 정적 import 는 try 로 감쌀 수 없다
        for r in _DIRNAME_JOIN.findall(src):
            rels.append(("./" + r, _guarded(None, r)))
        res = (bad, rels)
    _JS_CACHE[key] = res
    return res


def _scan_js_for_cwd_require(f, root, seen, depth=0, maxdepth=999):
    """cwd 기반 require 를 가진 파일을 찾는다. 로컬 require를 maxdepth 단계까지 따라간다.

    `seen` 은 파일→**최소 방문 깊이** 매핑이다. 집합으로 두면 같은 진입점 안의
    다이아몬드 그래프에서, 먼저 깊게 도달해 깊이 제한에 걸린 파일이 나중에 얕은
    경로로 다시 와도 막혀서 그 아래가 탐색되지 않는다(4라운드 반증). 재방문 비용은
    `_JS_CACHE` 가 흡수하므로 정확성 쪽을 택한다.
    """
    f = _canon(f)
    if depth > maxdepth:
        # 상한 절단을 조용히 넘기지 않되(no silent caps), **파일마다** 신고하면
        # 3,657줄이 된다(실측) = 신호 포화. 세어 두고 플러그인당 한 줄로 요약한다.
        _TRUNCATED[0] += 1
        return None
    # 센티널을 `99` 로 두면 maxdepth(999)와 어긋나 **깊이 99 이상에서 조용히**
    # 절단된다(2026-07-27 9라운드: 실존 경로 72개 포함 216개가 무고지 절단).
    if seen.get(f, float("inf")) <= depth:
        return None
    seen[f] = depth
    bad, rels = _analyze_js(f, root, depth)
    if bad:
        return (f, bad)
    for rel, guarded in rels:
        base = (root / rel.lstrip("./")) if not rel.startswith(".") else (f.parent / rel)
        # **명시 확장자**로 쓴 require가 부재하면 Node가 확실히 죽는다 → 신고한다.
        # 확장자 생략형은 `.js`·`index.js`·package main 어디로든 풀려 근사하면
        # 오탐만 난다(건강한 bkit에서 62건) → 신고하지 않고 추적만 한다.
        if base.suffix in {".js", ".cjs", ".mjs"} and not base.is_file():
            # 가드(try/catch)는 **실패 격리**이지 "이 기능은 선택"이라는 증거가 아니다
            # (2026-07-27 11라운드 반증 — 내가 가드를 근거로 무신고했던 것을 되돌렸다).
            # 심각도만 나눈다: 가드 없으면 로드 시점 크래시, 가드되면 그 단계 기능 상실.
            if guarded:
                add("MED", "플러그인훅", str(f),
                    f"가드된 require 대상이 부재한다: {rel}"
                    " — 크래시는 없으나 그 단계는 **한 번도 실행되지 않는다**")
            else:
                add("HIGH", "플러그인훅", str(f),
                    f"가드 없는 require 대상이 부재한다: {rel} — 로드 시점 크래시")
        for nxt in (base,
                    base.with_name(base.name + ".js"),
                    base.with_name(base.name + ".mjs"),
                    base.with_name(base.name + ".cjs"),
                    base / "index.js"):
            hit = _scan_js_for_cwd_require(nxt, root, seen, depth + 1, maxdepth)
            if hit:
                return hit
    return None


def check_hook_script_health(pid, ev, root, cmd):
    """플러그인 훅 **진입점**의 비-JS 문법(py/sh)만 본다.

    JS 는 `_batch_syntax_check()` 가 진입점·전이 의존성을 한꺼번에 검사하므로
    여기서 또 보면 **같은 파손이 2건으로 신고된다**(2026-07-27 10라운드 지적).
    """
    for raw in re.findall(r'CLAUDE_PLUGIN_ROOT"?\}?(/[^\s"\';|&)]+)', cmd):
        f = root / raw.lstrip("/")
        if not f.is_file():
            continue
        if f.suffix == ".py":
            rc, err = run([sys.executable, "-m", "py_compile", str(f)])
        elif f.suffix == ".sh":
            rc, err = run(["bash", "-n", str(f)])
        else:
            continue          # .js/.mjs/.cjs 는 배치 검사가 맡는다
        if rc != 0:
            add("HIGH", "플러그인훅", f"{pid} {ev} {raw.lstrip('/')}",
                f"문법 오류: {(err or '').splitlines()[0][:120] if err else 'rc=' + str(rc)}")


def check_consistency():
    """enabled ↔ installed ↔ baseline 의 상호 누락(5라운드 지적)."""
    try:
        inst = json.load(open(C / "plugins/installed_plugins.json"))["plugins"]
        en = json.load(open(C / "settings.json")).get("enabledPlugins") or {}
    except Exception:
        return
    for pid, v in en.items():
        if v and pid not in inst:
            add("HIGH", "정합성", pid, "settings.json 에서 enabled 인데 installed_plugins.json 에 없다")
    base_p = C / "backups/baseline.json"
    if base_p.exists():
        try:
            base = json.load(open(base_p)).get("plugins", {})
        except (OSError, ValueError):
            add("HIGH", "정합성", "backups/baseline.json", "파싱 불가")
            return
        for pid in inst:
            if pid not in base and en.get(pid):
                add("MED", "정합성", pid,
                    "enabled 인데 베이스라인에 없다 — 페이로드 감소를 비교할 기준이 없다")


def check_hook_structure():
    """훅 선언 구조 자체가 규격을 벗어나면 그 훅은 조용히 무발화한다(5라운드 지적)."""
    srcs = [(fn, C / fn) for fn in ("settings.json", "settings.local.json")]
    for pid, ip in enabled_plugin_paths().items():
        hj = ip / "hooks" / "hooks.json"
        if hj.exists():
            srcs.append((pid, hj))
    for label, path in srcs:
        if not path.exists():
            continue
        try:
            d = json.load(open(path))
        except (OSError, ValueError) as exc:
            add("HIGH", "훅구조", label, f"파싱 실패: {exc}")
            continue
        hooks = d.get("hooks")
        if hooks is None:
            continue
        if not isinstance(hooks, dict):
            add("HIGH", "훅구조", label, "`hooks` 가 객체가 아니다")
            continue
        for ev, arr in hooks.items():
            if not isinstance(arr, list):
                add("HIGH", "훅구조", f"{label} {ev}", "이벤트 값이 배열이 아니다")
                continue
            for gi, g in enumerate(arr):
                if not isinstance(g, dict) or not isinstance(g.get("hooks"), list):
                    add("HIGH", "훅구조", f"{label} {ev}[{gi}]",
                        "그룹에 `hooks` 배열이 없다 — 이 그룹은 발화하지 않는다")
                    continue
                for h in g["hooks"]:
                    if not isinstance(h, dict):
                        add("HIGH", "훅구조", f"{label} {ev}[{gi}]", "훅 항목이 객체가 아니다")
                        continue
                    # 타입별 필수 필드가 다르다. `command` 만 요구하면 공식 지원
                    # `type: "prompt"` 훅을 오탐한다(6라운드 지적) — 정상 작업을 막는
                    # 오탐은 안티골이므로 타입별로 나눠 본다.
                    htype = h.get("type", "command")
                    required = {"command": "command", "prompt": "prompt"}.get(htype)
                    if required is None:
                        add("MED", "훅구조", f"{label} {ev}[{gi}]",
                            f"미지의 훅 type `{htype}` — 런타임이 무시할 수 있다")
                    elif not str(h.get(required, "")).strip():
                        add("HIGH", "훅구조", f"{label} {ev}[{gi}]",
                            f"type={htype} 인데 `{required}` 가 없다/비어 있다")


def check_cwd_require(pid, ev, root, cmd):
    for raw in re.findall(r'CLAUDE_PLUGIN_ROOT"?\}?(/[^\s"\';|&)]+)', cmd):
        f = root / raw.lstrip("/")
        if f.suffix not in {".js", ".cjs", ".mjs"}:
            continue
        hit = _scan_js_for_cwd_require(f, root, {})
        if hit:
            bad, var = hit
            via = "" if bad == f else f" (경유: {bad.relative_to(root)})"
            add("HIGH", "플러그인훅", f"{pid} {ev} {raw.lstrip('/')}",
                f"`{var} = process.cwd()` 를 플러그인 루트로 삼아 require 한다{via}"
                " — 훅의 cwd는 프로젝트 디렉토리이므로 로드 시점에 크래시한다")


# ---------- 7. settings 훅의 스크립트 실존 ----------
def check_settings_hooks():
    for fn in ("settings.json", "settings.local.json"):
        p = C / fn
        if not p.exists():
            continue
        try:
            d = json.load(open(p))
        except Exception as exc:
            add("HIGH", "설정", fn, f"파싱 실패: {exc}")
            continue
        for ev, arr in (d.get("hooks") or {}).items():
            for m in arr if isinstance(arr, list) else []:
                for h in m.get("hooks", []):
                    cmd = h.get("command", "")
                    for raw in re.findall(
                            r"""(?:^|[\s;&|(])(?:/bin/|/usr/bin/)?(?:bash|sh|python3?|node)\s+["']?([^\s"';|&)]+)""",
                            cmd) + re.findall(r"""["']((?:/|~/)[^\s"';|&)]+\.(?:sh|py|js|mjs|cjs))["']""", cmd):
                        path = os.path.expanduser(raw.strip("\"'"))
                        if "$" in path or not path.startswith("/"):
                            continue
                        if not os.path.exists(path):
                            add("HIGH", "훅", f"{fn} {ev}", f"스크립트 부재: {raw}")


def check_coverage():
    """**아무것도 검사하지 않고 '오류 0건'을 내는 상태**를 신고한다.

    2026-07-27 교차검증 지적: 빈 settings·빈 설치목록만 있는 HOME에서 스윕이
    `오류 0건` rc=0을 냈다. "오류 0"과 "검사 안 함"의 출력이 같으면 안 된다.
    """
    n_exec = sum(1 for r in (C/"scripts", C/"workflows", C/"disabled") if r.is_dir()
                 for f in r.rglob("*")
                 if f.is_file() and f.suffix in {".py", ".js", ".mjs", ".cjs", ".sh"}
                 and "__pycache__" not in str(f))
    n_fm = sum(1 for sub, pat in (("skills", "skill.md"), ("agents", ".md"), ("commands", ".md"))
               if (C/sub).is_dir()
               for f in (C/sub).rglob("*")
               if f.is_file() and (f.name.lower() == pat if pat == "skill.md" else f.suffix == pat))
    n_plug = len(enabled_plugin_paths())
    # 2라운드 지적: settings 훅 커버리지를 재지 않아 hooks 키가 통째로 없어도 통과했다
    n_hooks = 0
    for fn in ("settings.json", "settings.local.json"):
        try:
            d = json.load(open(C / fn))
        except (OSError, ValueError):
            continue
        # `command` 만 세면 공식 `type:"prompt"` 훅만 있는 정상 설정을 0으로 오판한다
        # (7라운드 지적). 타입별 필수 필드 중 하나라도 채워져 있으면 훅으로 센다.
        n_hooks += sum(1 for ev, arr in (d.get("hooks") or {}).items()
                       if isinstance(arr, list) for m in arr
                       for h in m.get("hooks", [])
                       if isinstance(h, dict)
                       and (str(h.get("command", "")).strip() or str(h.get("prompt", "")).strip()))
    if n_hooks == 0:
        add("HIGH", "커버리지", "settings*.json", "훅 커맨드가 0개다 — 훅 검사가 무의미하다")
    if n_exec == 0:
        add("HIGH", "커버리지", "scripts/workflows/disabled", "문법 검사 대상이 0개다")
    if n_fm == 0:
        add("HIGH", "커버리지", "skills/agents/commands", "frontmatter 검사 대상이 0개다")
    if n_plug == 0:
        add("HIGH", "커버리지", "enabled plugins", "enabled 플러그인이 0개 — 훅 검사가 무의미하다")


def main():
    for fn in (check_syntax, check_frontmatter, check_plugin_frontmatter,
               check_plugin_manifest,
               check_agent_tools, check_doc_refs,
               check_mcp, check_plugin_hooks, check_settings_hooks,
               check_consistency, check_hook_structure, check_coverage):
        try:
            fn()
        except Exception as exc:
            add("HIGH", "스윕오류", fn.__name__, repr(exc))

    if _TRUNCATED[0]:
        # "no silent caps" — 상한에서 멈춘 사실을 고지한다. 단 이것은 결함이 아니라
        # 커버리지 경계이므로 **결함 목록이 아니라 주석**으로 낸다. 파일마다 신고하면
        # 3,657줄(실측)이 되고, MED로 올리면 rc가 항상 1이라 게이트가 무의미해진다.
        notes.append(f"require 추적이 깊이 상한에서 {_TRUNCATED[0]}회 멈췄다 —"
                     " 그 아래는 미검사")

    show_all = "--all" in sys.argv
    suppressed = 0
    if not show_all:
        keep = []
        for f in findings:
            if any(t in f[2] and sig in f[3] for t, sig, _ in KNOWN_ISSUES):
                suppressed += 1
            else:
                keep.append(f)
        findings[:] = keep

    order = {"HIGH": 0, "MED": 1, "LOW": 2}
    findings.sort(key=lambda x: (order.get(x[0], 9), x[1], x[2]))
    tail = f" (등재된 조달물 결함 {suppressed}건 제외 — `--all`로 표시)" if suppressed else ""
    for nt in notes:
        print(f"[커버리지] {nt}")
    if not findings:
        print(f"전역 스윕: 오류 0건{tail}")
        return 0
    cur = None
    for sev, cat, target, msg in findings:
        if cat != cur:
            print(f"\n■ {cat}")
            cur = cat
        print(f"  [{sev}] {target}\n        {msg}")
    print(f"\n총 {len(findings)}건 "
          f"(HIGH {sum(1 for f in findings if f[0]=='HIGH')} / "
          f"MED {sum(1 for f in findings if f[0]=='MED')})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
