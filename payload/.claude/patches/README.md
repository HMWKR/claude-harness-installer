# patches/ — 조달물(플러그인 캐시)에 적용한 수정과 재적용 경로

> `plugins/cache/`는 **휘발성**이다. `claude plugin install/uninstall`이 덮고,
> 여기 적힌 수정은 그때 사라진다(내구성 실측표: `~/.thoughts/2026-07-25-harness-direction-and-rejections.md` §6).
> 그래서 이 디렉토리는 **패치 파일 보관소가 아니라 재적용 레시피**다.

## 규율

- 기본은 **패치하지 않고 등재만 한다** — `harness-lint.py`의 `KNOWN_HOOK_ISSUES`,
  `harness-sweep.py`의 `KNOWN_ISSUES`. 캐시를 고쳐도 되돌아오기 때문이다.
- **예외 둘.** ① **크래시** — 매 도구 호출마다 스택 트레이스를 뱉는 것은 "오류 없는
  하네스"와 양립하지 않는다. ② **자산이 로드되지 않는 파손** — 스킬·에이전트가
  메타데이터 없이 로드되면 이름으로 부를 수 없다. 둘 다 "조용한 기능 결손"보다
  심각하고, 어느 쪽이든 고친 뒤 **탐지기를 남겨** 패치가 사라지면 다시 잡히게 한다.
  (①만 예외로 두었다가 2026-07-27 7라운드에서 ②를 만나 넓혔다.)
- 판단 기준은 "무엇이 망가졌나"가 아니라 **"사용자가 실제로 쓰는 능력이 사라지는가"**다.
  쓰지 않는 기능의 조용한 미발화는 등재로 충분하다.
- 패치는 항상 **최소·외과수술식**이고, 원본 의도를 바꾸지 않는다.

## 적용된 패치

### 1. bkit 2.1.31 — 훅이 `process.cwd()`를 플러그인 루트로 착각 (2026-07-27)

**증상**: `PreToolUse(Write|Edit)`에 배선된 `scripts/lint-skill-md.js`가 플러그인 루트
밖의 모든 cwd에서 **모듈 로드 시점에 크래시**했다 — `rc=1`, stderr 1,156B 스택 트레이스.
파일 헤더는 `Exit: 0 always (warning-only, never blocks write)`라고 선언하는데 실제와
반대였다. 즉 bkit의 SKILL.md 린트는 배선된 이래 한 번도 동작한 적이 없다.

**원인**: 저장소 개발용 스크립트(`npm run lint`로 bkit 소스에서 도는 self-dogfood 검사)를
사용자 훅으로 배선하면서 "프로젝트 루트"와 "플러그인 루트"를 한 변수로 혼용했다.
2단 캐스케이드였다 — `lint-skill-md.js` → `check-skills-docs-code-sync.js`.

**탐지기**: `harness-sweep.py`의 `check_cwd_require()`. 훅이 참조하는 `.js`에서
`X = process.cwd()` 와 `require(... X ...)`가 동시에 있으면 HIGH로 신고한다.
캐시가 갱신돼 패치가 사라지면 이 검사가 다시 잡는다.

**재적용**:

```bash
python3 - <<'PY'
from pathlib import Path
import glob
base = glob.glob(str(Path.home()/".claude/plugins/cache/bkit-marketplace/bkit/*"))
R = Path(sorted(base)[-1])          # 설치된 최신 버전

p = R/"scripts/lint-skill-md.js"
s = p.read_text()
if "const ROOT = process.cwd();" in s:
    p.write_text(s.replace(
        "const ROOT = process.cwd();",
        "const ROOT = process.env.CLAUDE_PLUGIN_ROOT || path.join(__dirname, '..');"))
    print("patched:", p.name)

p = R/"scripts/check-skills-docs-code-sync.js"
s = p.read_text()
old = "const MD_PARSE = require(path.join(ROOT, 'lib/util/markdown-parse.js'));"
if old in s:
    p.write_text(s.replace(old,
        "const PLUGIN_ROOT = process.env.CLAUDE_PLUGIN_ROOT || path.join(__dirname, '..');\n"
        "const MD_PARSE = require(path.join(PLUGIN_ROOT, 'lib/util/markdown-parse.js'));"))
    print("patched:", p.name)
PY
```

**검증** (플러그인 루트 밖에서 rc=0·무출력이어야 한다):

```bash
R=$(ls -d ~/.claude/plugins/cache/bkit-marketplace/bkit/* | tail -1)
cd /tmp && echo '{"hook_event_name":"PreToolUse","tool_name":"Edit","tool_input":{"file_path":"/tmp/x.md"}}' \
  | CLAUDE_PLUGIN_ROOT="$R" node "$R/scripts/lint-skill-md.js"; echo "rc=$?"
python3 ~/.claude/scripts/harness-sweep.py     # HIGH 0 이어야 한다
```

**주의**: 린트 **대상** 경로(`ROOT/skills`, `ROOT/<doc ref>`)는 의도대로 cwd를 유지했다.
그것까지 플러그인 루트로 바꾸면 사용자 프로젝트가 아니라 bkit 자기 자신을 린트하게 된다.

### 2. 활성 플러그인 4개 — YAML frontmatter 파싱 실패 (2026-07-27)

**증상**: `description:` 값에 따옴표 없이 콜론이 들어가(`NOT for:`, `Examples:`) YAML이
매핑으로 오해하고 `mapping values are not allowed here` 로 죽는다. 07-27에는 런타임이 frontmatter를
빈 메타데이터로 읽는다고 판단했으나, 2026-09-28·30 세션 에이전트 목록에서 설명이 정상 노출돼 **현재 런타임은
관대 파서로 읽는 것**이 확인됐다 — 엄격 파서가 실패하는 결함이라는 점은 그대로다. `claude plugin validate` 는 rc=1로 알려주지만 아무도 안 돌렸다.

**대상**(설치·활성 경로만):
`pr-review-toolkit/.../agents/silent-failure-hunter.md` ·
`jusan-harness/.../skills/{reference-match,owner-friendly-explainer,design-intent-lock}/SKILL.md`
— 뒤 3개는 사용자가 만든 **납품 라인 UI 스킬**이라 손실이 크다.

**수리 방식**: 값을 따옴표로 감싸는 대신 **블록 스칼라(`>-`)로 전환**한다. 원문에 이미
따옴표·콜론·줄바꿈이 섞여 있어 이스케이프보다 안전하고, 내용을 한 글자도 바꾸지 않는다.

**탐지기**: `harness-sweep.py` 의 `check_plugin_frontmatter()` — 활성 플러그인의
`SKILL.md`·`agents/*.md` frontmatter를 실제 YAML 파서로 검증한다(267개 대상).

**재적용**:

```bash
python3 - <<'PY'
import json, os, re, yaml
from pathlib import Path
C = Path.home()/".claude"
inst = json.load(open(C/"plugins/installed_plugins.json"))["plugins"]
en = json.load(open(C/"settings.json")).get("enabledPlugins") or {}
for pid, a in inst.items():
    if not en.get(pid) or not a: continue
    root = Path(a[0]["installPath"])
    files = list(root.rglob("SKILL.md"))
    if (root/"agents").is_dir(): files += list((root/"agents").glob("*.md"))
    for p in files:
        t = p.read_text(errors="replace")
        m = re.match(r"\A---\r?\n(.*?)\r?\n---", t, re.S)
        if not m: continue
        try: yaml.safe_load(m.group(1)); continue
        except Exception: pass
        lines, out, i = m.group(1).splitlines(), [], 0
        while i < len(lines):
            km = re.match(r"^(\w[\w-]*):\s*(.*)$", lines[i])
            if km and ":" in km.group(2) and not km.group(2).startswith(("|", ">", '"', "'")):
                body = [km.group(2)]
                while i+1 < len(lines) and not re.match(r"^\w[\w-]*:", lines[i+1]):
                    i += 1; body.append(lines[i].strip())
                out.append(f"{km.group(1)}: >-"); out += ["  "+b for b in body if b]
            else:
                out.append(lines[i])
            i += 1
        new = "\n".join(out)
        try:
            d = yaml.safe_load(new); assert isinstance(d, dict) and d.get("name")
        except Exception:
            print("SKIP", p); continue
        p.write_text(t[:m.start(1)] + new + t[m.end(1):]); print("patched:", p.name)
PY
```

**검증**:

```bash
python3 ~/.claude/scripts/harness-sweep.py     # 플러그인 frontmatter 결함 0
for pid in pr-review-toolkit@claude-plugins-official jusan-harness@claude-templates; do
  claude plugin validate "$(python3 -c "import json;print(json.load(open('$HOME/.claude/plugins/installed_plugins.json'))['plugins']['$pid'][0]['installPath'])")"
done                                            # 둘 다 rc=0
```

**영구 해법**: `jusan-harness` 는 `HMWKR/CLAUDE-TEMPLATES`(사용자 소유)에서 오므로
업스트림 수정이 가능하다 — 단 **PUBLIC 저장소라 푸시는 사용자 결정**이다.
`pr-review-toolkit` 은 Anthropic 공식이라 업스트림 이슈 경로만 있다.

### 3. understand-anything — PostToolUse 가 존재하지 않는 `$TOOL_INPUT` 을 읽음 (2026-07-27)

**증상**: 훅 입력은 **stdin JSON**인데 `$TOOL_INPUT` 환경변수를 읽는다. 빈 값이 grep에
들어가 `&&` 체인 전체가 항상 실패하므로, git 커밋 후 지식그래프 자동갱신이 **한 번도
발화한 적이 없다**. 크래시가 아니라 조용한 미발화라 오래 보이지 않았다.

**현재 실질 손실은 0** — 사용자 홈에 `.understand-anything/` 프로젝트가 0개다. 그래도
고친 이유는 "선언한 것이 발화하지 않는다"가 이 하네스의 핵심 실패 모드이고, 나중에 이
기능을 쓰기 시작하면 조용히 안 도는 상태로 들어가기 때문이다. 처음엔 등재만 했다가
2026-07-27에 수리로 전환했다.

**수리**: `hooks/hooks.json` 의 `printf '%s' "$TOOL_INPUT"` 부분을 stdin JSON 파서로
교체한다. 재적용 스크립트는 `patches/fix-understand-anything.py` (멱등).

```bash
python3 ~/.claude/patches/fix-understand-anything.py
```

**검증**(격리 임시 디렉토리, 부작용 없음): `git commit …` 입력에는 안내 메시지가 나오고
무관한 명령에는 무출력이어야 한다. 스크립트가 `--verify` 로 이 대조를 직접 수행한다.

```bash
python3 ~/.claude/patches/fix-understand-anything.py --verify
```

### 4. bkit 2.1.31 — `sprint-memory-writer` 경로 오류 (2026-07-27)

**증상**: `scripts/lib/sprint-handlers-core.js:422` 가 `require('./sprint-memory-writer')`
하는데 그 파일은 `scripts/sprint-memory-writer.js` 에 있다(한 단계 위). 리팩터링 때
파일이 옮겨지며 참조가 갱신되지 않았다. try/catch 안이라 크래시는 없지만 **MEMORY.md
스프린트 자동 기록이 항상 실패**했다 — 관측:
`memoryUpdated=false, memoryReason="writer_error: Cannot find module './sprint-memory-writer'"`.

**수리**: `'./sprint-memory-writer'` → `'../sprint-memory-writer'` (한 곳).
검증: `require.resolve` 성공 + `appendSprintToMemory` 가 function.

### 5. bkit 2.1.31 — `pdca-post-write.js` 복원 (2026-07-27)

**증상**: `scripts/unified-write-post.js` 가 매 Write 마다 `pdca-post-write.js` 를
로드하고 주석은 `always runs - core bkit-rules` 라고 선언하는데 **파일이 없었다.**
bkit 문서(`trigger-matrix.md`·`scenario-write-code.md`·`test-checklist.md`)는 Write 후
`/pdca-analyze` 안내를 **계약**으로 명시한다 — 즉 살아 있는 계약이 무발화 상태였다.

**수리**: 삭제 직전 원문(91줄, `d2d07b8^:scripts/pdca-post-write.js`)을 회수해
**import 한 줄만** 현행 모듈에 맞춰 복원했다 — `../lib/core/hook-io` →
`../lib/core/io`(필요한 4개 심볼을 그대로 내보낸다, 실측). 나머지 의존
(`core/debug`·`core/file`·`task/creator`·`core/platform`)은 전부 현존한다.

**종단 검증**: `src/features/payments/index.js` Write + `docs/02-design/features/
payments.design.md` 존재 → `/pdca-analyze payments` 안내 387B 출력. 설계문서가 없으면
무출력(오탐 없음).

> **내 오판 2회 기록.** ①처음엔 "고칠 수 없다"며 등재만 했다 — 마켓플레이스 클론이
> 2.1.22로 낡은 걸 확인하지 않았다. ②다음엔 "try/catch 안이니 선택적 로드 = 결함 아님"
> 으로 재분류해 무신고했다 — **try/catch 는 실패 격리이지 기능이 선택이라는 증거가
> 아니다.** ③그 다음엔 "업스트림이 의도적으로 지웠고 의존 모듈도 없으니 잔재"라며
> 호출부를 **삭제**했다 — `hook-io` 는 삭제가 아니라 `./io` shim 이 됐던 것이고,
> import 한 줄이면 복원됐다. 교차검증이 세 번 다 반박했다.
> **교훈: "고칠 수 없다"는 대개 조사를 덜 한 상태의 이름이다.**

### 6. bkit 2.1.31 — `currentFeature` 필드 오류 (2026-07-27)

`scripts/unified-write-post.js:242` 의 메트릭 가드가 `pdcaStatus.currentFeature` 를 보는데
**bkit 자신의 주석**(`scripts/pre-write.js:99`)이 "currentFeature는 v2/v3 schema에
존재하지 않는 필드 → primaryFeature 로 normalize 됨"이라고 적고 있다. v2.1.7/v2.1.15
정정에서 이 자리만 빠져 가드가 항상 false 였다. 한 단어 교체.

### 7. bkit 2.1.31 — v2→v3 스키마 이행 누락 16곳, 단일점 복구 (2026-07-27)

**증상**: v3 는 상태를 `primaryFeature` + `features[<name>].phase` 로 정규화했는데
(`status-migration.js:74,80`, `pre-write.js:99` 주석이 명시), **읽기 지점 16곳이 여전히
최상위 `currentFeature`/`currentPhase` 를 본다** — `next-action-engine`(3) ·
`context-compaction`(5) · `session-title` · `cwd-changed-handler` ·
`file-changed-handler` · `notification-handler` · `session-end-handler` ·
`unified-stop` · `runtime-guidance` · `code-review-stop`.
관측: `feature="none"`, `phase=none`, next-action `null`, PreCompact phase 게이트 항상 false.

**사용 실태**: 사용자는 bkit 을 실제로 쓴다 — `.bkit` 디렉토리 12곳, 런타임 JSON 57개,
최근 트랜스크립트에 `/pdca-*` 8회. 즉 이 16곳은 살아 있는 기능의 손실이다.

**수리 — 16곳이 아니라 1곳**: 모든 읽기가 통과하는 `lib/pdca/status-core.js` 의
`getPdcaStatusFull()` 반환 직전에 파생 별칭을 붙인다(`_attachLegacyAliases`).
각 호출부 로직을 건드리지 않아 위험이 최소다.

- **값이 아니라 getter** 로 붙인다. 값으로 고정했더니 `setActiveFeature()`·
  `updatePdcaStatus()` 로 상태가 바뀐 뒤에도 옛 값이 남았다(14차 반증: 실제
  `orders/act` 인데 별칭은 `payments/check`). getter 는 읽을 때마다 현재 상태에서
  계산하므로 낡지 않는다.
- **캐시 히트 경로에도 붙인다.** `savePdcaStatus()` 가 별칭 없는 객체를 캐시에 넣어,
  저장 직후 읽기가 `if (cached) return cached;` 로 떨어지면 별칭이 없었다
  (14차 반증: `sameObject:true, currentFeature:null`).
- `Object.defineProperty(..., {enumerable:false})` 라 **`JSON.stringify` 에 잡히지
  않는다** → `savePdcaStatus()` 가 디스크로 흘리지 않는다(v3 스키마 무오염, 실증).
- 이미 값이 있으면 덮지 않는다(구 스키마 호환).

**검증**(14차 반례 전부): 초기 `payments/check` · 저장 직후에도 유지 ·
`primaryFeature` 변경 시 `orders/act` · `phase` 변경 시 즉시 반영 · 직렬화 누출 false ·
디스크 키 불변(`lastUpdated` 만 추가, `savePdcaStatus` 의 정상 동작).
`context-compaction` 의 `['do','check','act'].includes(...)` 게이트가 false → **true**.

**한계**: 별칭은 `getPdcaStatusFull()` 를 거치는 읽기만 덮는다. 상태 파일을 **직접**
읽는 경로 2곳은 §9 에서 따로 고쳤다. 근본 해법은 업스트림이 16곳을 정정하는 것이다.

### 9. bkit 2.1.31 — `getPdcaStatusFull()` 우회 직접 읽기 2곳 (2026-07-27)

§7 의 별칭이 닿지 않는 경로다(14차 반증).

- `scripts/cwd-changed-handler.js:49` — **다른 cwd** 의 상태 파일을 직접 읽으므로
  중앙 접근자를 쓸 수 없다. `status.currentPhase || status.phase || 'idle'` 이라
  v3 입력에 항상 `idle` 을 냈다 → `features[primaryFeature].phase` 를 우선 해석하도록
  수정(구 필드는 폴백 유지). 검증: v3 `payments/check` 입력 → **`check`**.
- `scripts/notification-handler.js:61` — `pdcaStatus.feature || pdcaStatus.featureName`
  는 **어느 스키마에도 없는 필드**라 항상 `'none'` 이었다 → `primaryFeature` 우선.
  검증: v3 입력 → **`payments`**.

### 8. bkit 2.1.31 — 미등록 메트릭 수집 블록 제거 (2026-07-27)

**증상**: `scripts/unified-write-post.js` 가 매 Write 마다
`collectMetric('file_change_count', …)` 을 부르는데 그 ID 는 `METRIC_SPECS`(M1~M15)에
없다. `collectMetric` 은 `if (!spec) return;` 로 즉시 반환하므로 **처음부터 아무 일도
하지 않았다.**

**조사**(등재 전 두 확인):
1. **내 사본이 낡았나** — 업스트림 v2.1.31 에도 동일하다.
2. **한 번이라도 등록된 적이 있나** — `git log --all -S"file_change_count"` 결과 도입
   커밋 `18b0982`(v2.0.0 통합) 하나뿐이고 `metrics-collector.js` 에는 **한 번도 들어간
   적이 없다.** 문서 언급도 0. 즉 정의 없이 호출만 쓴 코드다.

**처분**: 블록 제거(동작 무변화 실증 — rc·stdout·stderr 동일). 되살리려면 먼저
metrics-collector 에 메트릭을 정의해야 한다는 사실을 주석으로 남겼다. 가드 필드는
이미 §6 에서 `primaryFeature` 로 정정해 뒀다.

### 10. figma-mcp-bridge v0.0.22 — 로컬 전용 보안 강화 (2026-09-28)

**근거**: 플러그인 캐시가 아니라 `~/.local/share/figma-mcp-bridge`에 **소스로 설치한 도구**이고, 사용자가
"소스 설치 + 보안 패치"를 선택했다(2026-09-28). 위 규율의 "등재만" 원칙은 캐시 되돌림 때문인데, 이 경우는
업데이트를 우리가 통제하므로 해당하지 않는다.

**증상(원본)**: `server.listen(port)`가 주소 없이 열려 LAN 전체에 노출, `/rpc`에 인증·Origin·Content-Type 검사
없음(웹페이지가 로컬 서버에 쓰기 도구를 실행시킬 수 있는 구조), 웹소켓 출처 무검사, Host 무검사(DNS 리바인딩).

**패치**(`figma-mcp-bridge-local-hardening.patch`, 6파일 +185/-16 — 3차 포함): ① `listen(port, "127.0.0.1")` ② Host가
`localhost:<port>`·`127.0.0.1:<port>`가 아니면 403 ③ `/rpc`는 Origin 헤더가 있으면 거부 + `x-figma-bridge: 1`
필수(follower 두 호출부에 헤더 추가) ④ 웹소켓은 Origin 없음·`null`·`*.figma.com`만 허용, 거부 출처는 stderr 로그. ⑤ **2차(codex 2차 검수)**: `Origin: null`은 샌드박스 iframe을 쓰는 웹페이지도 만들 수 있어 사칭 가능 → **페어링 토큰** 필수(경로 `/ws/<토큰>`, `~/.config/figma-mcp-bridge/token` 0600 또는 `FIGMA_BRIDGE_TOKEN`, 없으면 전부 거부, timingSafeEqual 비교). 플러그인은 원본 대신 토큰을 넣은 사본 `~/.local/share/figma-mcp-bridge/plugin-local/`을 가져온다(`dist/index.html`의 `"ws://localhost:1994/ws"` 1곳 치환). ⑥ 응답은 요청을 보낸 연결에서 온 것만 채택(타 연결 위조 차단). ⑦ **3차(2026-09-30 감사 #19)**: 리더는 127.0.0.1에만 바인드하는데 팔로워·선거 핑·list_files 폴백은 `localhost`로 접속해, `[::1]:<port>`를 먼저 잡은 프로세스가 RPC·핑을 가로챌 수 있었다 → 셋 다 `http://127.0.0.1:<port>`로 고정(node.ts·election.ts·tools.ts), 리더는 같은 포트의 `[::1]`도 함께 점유(받은 연결은 같은 http 서버로 넘김 — 플러그인의 `ws://localhost` 경로 보호). `[::1]`이 이미 점유돼 있으면 stderr에 경고(`WARNING: [::1]:<port> is held by another process`)를 한 번 남기고 127.0.0.1로 계속 리더를 맡는다 — 리더를 포기하던 첫 판본은 127.0.0.1을 비워 IPv4 실패 후 IPv6로 넘어가는 클라이언트까지 점유자에게 보내고 선거 주기마다 로그를 쌓았다(2026-09-30 검토 회귀 수정). ⑧ **3차(#20)**: `save_screenshots` 출력 경로와 `create_image` 로컬 소스가 어휘 검사만 해서 작업 폴더 안의 심볼릭 링크로 밖을 쓰고 읽을 수 있었다 → 실경로(realpath)로 다시 검사(쓰기는 가장 가까운 기존 상위 폴더 기준 + 플러그인 응답 뒤 mkdir 전·후 재검사, 읽기는 검사한 실경로를 그대로 읽음). 또 격리 기준인 작업 폴더(cwd)가 **홈이거나 홈을 품은 상위 폴더**면 홈 전체가 범위가 되므로(`.ssh/…`가 "안"으로 통과) 로컬 경로를 쓰는 세 도구(`save_screenshots`·`create_image`·`import_html_layers`)를 거부한다 — 세션을 프로젝트 폴더에서 열어야 한다. URL·data URI 소스는 영향 없음.

**검증(2026-09-28 실측)**: 바인딩 127.0.0.1만, `/ping` 200, Host 위조 403, 헤더 없는 `/rpc` 403, Origin 달린
`/rpc` 403, 정상 로컬 `/rpc` 200, LAN IP 접속 실패, 악성 출처 웹소켓 거부·`null` 허용, 두 번째 인스턴스가
follower로 붙어 list_files 전체 경로 성공. 2차: 토큰 없음·틀린 토큰·악성 출처 거부, 정상 토큰+null 연결, 타 연결의 위조 응답 무시·진짜 응답 채택(REAL_FROM_A). 실제 Figma 플러그인 출처는 `null`로 가정 [추정] — 연결 시 로그로 확인.
3차(2026-09-30 실측, 포트 19944~19947): 리더 기동 후 `[::1]` 선점 시도 `EADDRINUSE`·선점자 수신 0건(수정 전 5건,
위조 응답 채택), 와일드카드 `[::]` 선점도 수신 0건(수정 전 3건), 선점자가 먼저 있으면(수정본, 포트 19944 실측) 경고 1회 후 127.0.0.1 리더 유지·`/ping` 200·팔로워 RPC·핑은
127.0.0.1로만 가므로 가로채기 0건 — 단 `localhost`를 ::1로 푸는 플러그인 연결은 점유자에게 갈 수 있다(아래 한계). 실제 `dist/index.js`가 `127.0.0.1`·`[::1]` 양쪽 LISTEN·`[::1]` 경유 토큰 WS 연결
성공·틀린 토큰 거부·두 번째 인스턴스 follower list_files 성공, 구 빌드 리더 아래 새 빌드가 follower로 붙고 구 리더 종료
시 양 스택으로 인계. 링크 탈출: 폴더 링크·중첩 경로·검사 후 끼어든 링크(파일·새 하위 폴더 모두) 쓰기와 폴더·파일 링크
읽기가 모두 거부되고(수정 전 성공 — 밖에 파일·폴더 생성, 밖의 비밀 바이트 전송), 안쪽을 가리키는 링크·일반 경로는 그대로
성공. 홈 범위: 가짜 HOME에서 cwd=홈·홈의 상위일 때 세 도구 모두 거부(수정 전 `.ssh/id_fake` 바이트와 `type` 필드가 있는
JSON 비밀이 플러그인 쪽으로 전송됨), cwd=홈/프로젝트는 정상, cwd=홈이어도 data URI는 정상.
**남은 한계**: 리더보다 먼저 누군가 `[::1]`(또는 리더가 없을 때 `127.0.0.1`)의 1994를 잡으면 플러그인(`ws://localhost`)은
그쪽에 붙어 페어링 토큰을 넘길 수 있다 — 리더는 stderr 경고로 드러낼 뿐 막지 못한다(포트 기반 로컬 서비스의 한계).
플러그인 사본을 `ws://127.0.0.1`로 바꾸면 줄어들지만 Figma 매니페스트 허용 도메인 확인이 필요해 보류[미확인]. 실행 중인
구 빌드(다른 세션)는 그 세션을 재시작하거나 `/mcp`로 재연결해야 새 dist가 적용된다.

**재적용**(태그 갱신 시). **작업 트리를 먼저 원본으로 되돌린다** — 패치가 이미 들어간 채로 두면 `checkout`은 성공해도
`git apply`가 원본 구조와 무관하게 반드시 실패한다(2026-09-30 감사 재현: `patch does not apply`, rc=1).

```bash
cd ~/.local/share/figma-mcp-bridge
# ① 적용돼 있던 패치를 치운다 — 지우지 않고 stash에 보존(되돌림: 원래 태그로 checkout 후 git stash pop). 변경이 없으면 아무 일도 안 한다.
git stash push -m "local-hardening before <새태그>" -- server/src
# ② 새 태그로 이동 → --check로 들어가는지 확인 → 적용 → ③ 빌드·확인. ②와 ③은 반드시 한 && 사슬로 잇는다 —
#    따로 두면 --check가 실패해도 빌드가 돌아 패치 없는 빌드가 dist를 덮는다(새 세션이 무방비 빌드를 띄움, 2026-09-30 실측).
git fetch --depth 1 origin tag <새태그> && git checkout <새태그> \
  && git apply --check ~/.claude/patches/figma-mcp-bridge-local-hardening.patch \
  && git apply ~/.claude/patches/figma-mcp-bridge-local-hardening.patch \
  && cd server && npm install --ignore-scripts --no-audit --no-fund && npm run build \
  && grep -c local-hardening dist/leader.js dist/tools.js   # leader 7·tools 6 이상이어야 패치가 들어간 것
# 플러그인 사본 재생성(토큰 삽입): 릴리스 zip을 plugin-release/unpacked에 풀고 plugin-local로 복사 후
# dist/index.html의 "ws://localhost:1994/ws" → "ws://localhost:1994/ws/<토큰>" 1곳 치환, chmod -R go-rwx
# 이미 떠 있는 다른 Claude 세션의 figma-bridge는 옛 빌드를 메모리에 쥐고 있다 — 세션 재시작(/mcp 재연결) 필요
```

①을 거친 뒤에도 `git apply --check`가 실패하면 그때가 원본 구조가 바뀐 것이다 — 사슬이 거기서 멈추므로 `dist`는 이전
패치 빌드 그대로다. `git stash show -p`로 이전 적용분을 보며 hunk 지점(현재 6파일)을 다시 찾아 수동 적용하고 위 검증을 반복한다. 소스를 고친 뒤에는 패치를 다시 만든다:
`git diff -- server/src > ~/.claude/patches/figma-mcp-bridge-local-hardening.patch`.
(2026-09-30 스크래치 클론 실증 — 위 블록을 그대로 실행, `npm install`만 생략: 같은 태그·중간 줄이 밀린 태그는 rc=0·
leader 7/tools 6, 파일 첫 줄이 바뀐 태그는 `--check`에서 rc=1로 멈추고 `dist` 바이트 불변, 세 경우 모두 이전 적용분은 stash에 보존.
옛 절차는 같은 태그 `patch does not apply`, 밀린 태그 `checkout` 중단으로 둘 다 rc=1.)

## 등재만 하고 고치지 않은 것 — 정적 관측기 범위 밖

아래는 **실행해 봐야 드러나는 조달물 로직 결함**이다. `harness-lint`·`harness-sweep` 는
**정적** 관측기라(존재·로드·파싱) 런타임 의미까지 검사하지 않는다 — 그 경계를 여기
적어 두어 두 도구의 `오류 0건` 을 과신하지 않게 한다.

| 항목 | 처분 |
|---|---|
| ~~`collectMetric('file_change_count', …)` 가 미등록 ID~~ | **제거함** — §8 참조. 도입 이래 전 이력·전 코드베이스·문서에 등장이 그 호출 1곳뿐인 죽은 문장이었다. |
| 훅 payload 의 `agent_name` 이 `getActiveAgent()` 에 도달하지 않아 `qa-monitor` 분기가 실행되지 않는다 | **구현하지 않음** — 아래 사유. |

### `agent_name` 전파를 만들지 않은 이유 (2026-07-27 판단)

사실관계부터 — **내가 처음 쓴 근거는 틀렸다**(교차검증 14차가 반증):

- 나는 "agent 를 담을 자리가 없다"고 적었다. **틀렸다.** `SubagentStart` 핸들러가
  `agent_type` 을 `.bkit/runtime/agent-state.json` 에 **이미 교차프로세스로 저장**한다
  (격리 실행으로 `agent_type:"qa-monitor"` 기록 확인). 마커 모듈에 agent 필드가 없는
  것은 사실이나, 저장 자리가 없는 것은 아니다.
- 실제 상태는 **`unified-bash-pre.js` 가 그 파일을 읽지 않는 것**이다 — 같은 필드를
  넣고 돌려도 `Bash command validated.` 를 반환한다. 즉 배선 한쪽이 비어 있다.

그래도 **하지 않는다.** 이유는 인프라 부재가 아니라 **활성화되는 것의 성격**이다:

- 배선하면 `unified-bash-pre.js:225` 의 `handleQaPreBash` 가 `qa-monitor` 에이전트
  실행 중 **bash 명령을 차단**하기 시작한다.
- 방향성 정본 축① 은 **"차단은 오탐률이 실측된 지점에만"** 이다. 이 경로는 사용자가
  한 번도 돌려본 적이 없어 **오탐률이 미측정**이다. 같은 근거로 "셸 메타문자 무조건
  거부"(실측 99.0% 마찰)가 명시 기각된 전례가 있다.
- 안전 기능이라는 점은 인정하지만, 미측정 차단을 조용히 켜는 것은 이 하네스가
  하지 않기로 한 일이다.

**필요해지면 사용자 결정으로 진행한다** — 그때 순서는 ①`qa-monitor` 세션에서
`handleQaPreBash` 를 **관측 전용**으로 먼저 돌려 오탐률을 재고 ②그 수치를 근거로
차단 전환을 결정한다.

## (참고) 억제 목록

**현재 없음.** 두 관측기의 `KNOWN_*` 목록이 비어 있고 `--all` 에서도 `오류 0건` rc=0 이다.

억제는 **고칠 수 없는 것에만** 쓴다. 등재할 때는 **왜 고칠 수 없는지**를 사유에 적고
탐지기는 남긴다. 다만 등재 전에 반드시 두 가지를 먼저 확인한다 — 2026-07-27에 둘 다
걸렸다:

1. **내 사본이 낡은 것 아닌가.** bkit 마켓플레이스 클론이 2.1.22인데 캐시는 2.1.31이었다.
   업스트림을 직접 조회(`git fetch --depth=1` → `ls-tree FETCH_HEAD`)해야 사실이 나온다.
2. **애초에 결함이 맞는가 — 그리고 정말 못 고치는가.** `pdca-post-write.js` 부재를
   두고 나는 세 번 연속 틀렸다: 등재("못 고침") → 재분류("try/catch 안이니 선택적
   로드, 결함 아님") → 삭제("의도적으로 지워진 잔재"). 실제로는 **import 한 줄이면
   복원되는 살아 있는 계약**이었다(§5). `try/catch` 는 **실패 격리**이지 기능이
   선택이라는 증거가 아니다. 등재도 재분류도 **조사 부족을 덮는 데 쓰이기 쉽다** —
   그래서 이 확인이 먼저다.
