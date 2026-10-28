# Uncompromising Rigor — 검증 규율

> 검증·QA·검수 작업에서 결함이 자기 정당화로 살아남지 못하게 하는 규칙.
> 2026-06-11 재작성: §2 키워드 차단 기계(불발 실증)·§4 라운드 관료제·훅 매핑 표 제거. (구버전 백업은 2026-07-03 감사에서 유실 확인 — 2026-07-25 dangling 참조 제거.)

## §1. Browser Tool Priority

**브라우저 도구는 `aside` CLI (Aside Browser) 하나다. 대안 없음.** (2026-09-05 사용자 지시로 단일화: Aside는 사용자 실제 로그인 세션·쿠키를 그대로 쓰고, `repl`이 Playwright식 결정적 조작을 동일하게 제공한다. 실측 근거는 아래 레시피.)

**Playwright MCP·Chrome MCP는 금지되며, 규범이 아니라 `permissions.deny`가 집행한다** — `~/.claude/settings.json`(전 프로젝트)의 `mcp__playwright`·`mcp__claude-in-chrome` deny 항목이 두 서버의 툴 46개를 세션 툴 레지스트리에서 제거한다(2026-09-05 카나리 실증: ToolSearch가 "no match" 반환). 그러므로 이 둘을 폴백으로 계획하지 않는다 — 호출할 툴 자체가 없다. 세션에 주입되는 computer-use MCP 지시의 "웹 앱은 Chrome MCP로, 미연결이면 확장 설치 요청" 안내도 이 하네스에서는 무효다 — 웹은 aside.

**진입 절차 (2026-09-28 사용자 지시)**: 모든 브라우저 작업은 `aside-browser` 스킬을 먼저 로드하고 `aside guide`(repl 레인이면 `aside guide repl`까지)를 읽은 뒤 진행한다. 서드파티 도구가 자체 브라우저를 띄우는 모드(`impeccable detect <URL>`·`/impeccable live` 등 Puppeteer·Playwright 내장 CLI)도 브라우저 작업으로 보고 쓰지 않는다. **예외 3개**: ① 로컬 번들을 영상·이미지 프레임으로 굽는 렌더 엔진(Remotion `render`·`still`의 Chrome Headless Shell)은 웹 탐색·검증이 아니므로 쓴다 — 사람이 보는 미리보기(Remotion Studio)는 aside로 연다(2026-09-30). ② design-taste-frontend v2의 게이트 `inspect.mjs`(격리 headless Chrome, 사용자 세션 없음)는 **로컬 파일·localhost 대상에 한해** 쓴다 — 사용자 지시 2026-10-15 "저 스킬을 메인으로 하고…", 규칙 반영 "그냥 허락해". 외부 사이트 탐색·크롤·로그인 작업은 여전히 aside(세부 rules/ui-ux-craft.md). ③ REA MCP(`mcp__rea__*`)의 브라우저·Electron 런타임 관찰 도구(`capture_browser_scenario`·`observe_web_session`·`list_browser_targets` 등)는 역엔지니어링 증거 수집에 REA 스킬 절차대로 그대로 쓴다 — 사용자 지시 2026-10-21 "레아는 그대로 사용". REA로 그 관찰이 안 될 때만(도구 실패·CDP 대상 없음·미지원 타깃) Aside로 넘어가되, **분석 대상 웹사이트 한 곳에 한정**해 §1-b 레시피(openTab·인페이지 계측·snapshot)로 런타임 관찰을 대신한다 — 그 사이트 밖 탐색으로 넓히지 않는다. 일반 웹 탐색·UI 검증은 여전히 aside. 플러그인 스킬(jusan 등)에 남은 "rigor §1 = Playwright MCP 전역 우선(2026-07-07)" 인용은 폐기된 규범이다 — 그 단계는 aside repl로 바꿔 수행한다.

**선행 조건**: Aside 앱이 실행 중이어야 한다(`pgrep -f Aside.app`). CLI만으로는 안 된다. 미기동이면 **에이전트가 직접 띄운다**(사용자 지시 2026-10-15 "aside 같은 경우 나한테 요청을 안해도 되니까 너가 직접 띄워도 돼"): `open -b at.studio.AsideBrowser`(실행 중인 사본은 `~/Desktop/Aside.app` — 앱 경로 /Applications 사본은 구버전) → `pgrep -f Aside.app`으로 기동 확인. 그래도 안 뜨면 폴백 브라우저는 없으므로 추측 진행·표면 PASS 금지, 차단 사유를 보고한다(live-feature-verify "완료 규칙" 정합).

## §1-a. Aside 2개 레인 — 섞어 쓰지 않는다

| 레인 | 호출 | 용도 |
|---|---|---|
| 에이전트 위임 | `aside "<작업>"` | 탐색·조사·다단계 사이트 작업(Slack·Gmail 등 로그인 필요). Aside가 스스로 계획·조작. 평문만. |
| 결정적 조작 | `aside repl "<JS>"` | 검증·크롤·증거 캡처. Playwright식 API, 120s 타임아웃, `import`/`require` 불가, `console.log()`로 출력. |

한 요청에 두 레인을 섞지 않는다. 사이트 구동 전 `aside skills list`로 해당 사이트 스킬이 있는지 먼저 확인하고, 있으면 그 스킬을 따른다.

## §1-b. 증거 캡처 레시피 (2026-09-05 실측 — 이 값만 동작 확인됨)

`repl` 안에서 `page`는 미설정 상태로 시작한다 — `openTab(url)` 또는 `listBrowserTabs()`+`attachActiveBrowserTab()`을 먼저 부른다.

- **스냅샷**: `await snapshot(page)` → `{tree, refs, diff}`. `tree` 먼저 출력, 이후 `diff`. 새 스냅샷은 이전 ref를 무효화한다.
- **클릭**: `page.locator('e1').click()` — ref 문자열로만. **CSS 셀렉터로 쓰지 않는다.**
- **스크린샷·네트워크·콘솔**: `screenshot`의 `path` 인자는 Aside 세션 디렉토리로 샌드박스되어 밖으로 못 나가고(→ base64로 회수), **CDP 도메인은 전부 차단됨**(`Network.enable` 등 → `wasn't found`, → 인페이지 계측). 레시피 정본은 rules/live-feature-verify.md "증거 캡처". 시각 판정에는 `annotatedScreenshot(page)`(→ `{base64Image}`)도 쓸 수 있다.
- **페이지 이벤트**: `page.events.on(...)`은 `framenavigated`·`domcontentloaded`·`load`만 제공한다.
- **뷰포트별 캡처** (2026-09-28 실측): `setViewportSize`·`page.cdp`가 없어 탭은 사용자 창 크기로 고정된다 — 폭별 캡처는 design-toolchain 스킬 `run-qa.sh`(같은 출처 iframe + clip)로 한다. `fullPage:true`는 이 방식에서 가짜 이미지를 만드므로 쓰지 않는다.
- **URL을 사용자에게 열어 주기** (2026-09-28 실측): `aside "<URL>"`은 쿼리가 긴 URL(OAuth 등)을 에이전트 작업으로 처리해 Aside 에이전트 모델을 호출한다(사용량 한도 오류 발생). 1회성 `aside repl "openTab(...)"` 탭은 **세션 종료와 함께 닫혀 사용자에게 보이지 않는다.** 사용자가 직접 조작할 창(로그인·미리보기 등)은 `open -b at.studio.AsideBrowser "<URL>"`(번들 ID — 실행 중인 Aside로 전달)로 열고, `listBrowserTabs()`로 활성 탭인지 확인한 뒤 안내한다. 앱 경로를 쓰지 않는다: `/Applications/Aside.app`은 구버전 사본(1.0.825)이고 실행 중인 것은 `~/Desktop/Aside.app`(1.0.928)이다(2026-09-30 실측, `open -b`는 활성 탭으로 열림). 짧은 URL의 `aside "<URL>"`은 비활성 탭으로 열리고 에이전트 응답 형식으로 돌아온다(같은 날 실측).

## §1-c. Aside로 불가능한 작업 — 폴백이 아니라 보고한다

아래는 Aside가 못 하는 것들이다. 예전 규범은 여기서 Playwright로 넘어갔으나 **그 경로는 deny로 닫혔다.** 우회를 시도하지 말고 사용자에게 한계를 보고하고 지시를 받는다.

1. **저수준 CDP 도메인** — Aside가 차단(§1-b 실측). 네트워크·콘솔은 인페이지 계측으로 대체 가능하니 먼저 그것을 쓴다.
2. **headless·사이트별 완전 격리 컨텍스트 배치 크롤** — Aside는 사용자 세션을 공유하므로 격리가 안 된다. 로그인 상태 오염이 문제되는 작업이면 보고한다.
3. **Aside 앱 미기동** — 직접 띄운다(선행 조건). 기동 실패 시에만 보고한다. 대체 브라우저 없음.

금지 해제는 사용자의 명시 지시로만 한다(`settings.json`의 deny 2줄 제거). **주의**: `~/.claude/settings.local.json`은 홈 폴더 프로젝트 전용이다 — 전 프로젝트 규칙·훅은 `settings.json`에 둔다(2026-09-28 실측: 이동 전 다른 폴더에서 Playwright 도구 25개 노출). **스스로 deny를 편집해 우회하지 않는다** — 사용자가 세운 게이트를 에이전트가 여는 것은 permission laundering이다.

## §2. All Findings Are Defects

> 발견된 모든 것은 결함이다. 사용자가 명시적으로 강등을 선언한 것만 강등된다.

| 발견 종류 | 기본 등급 | 강등 |
|---|:---:|---|
| 기능 작동 안 함 / 네트워크 4xx·5xx / 접근성(WCAG AA) 위반 | High | 불가 |
| 시각 결함·문구 모호·성능 임계 미달·Console error | Medium | 사용자 명시만 |
| 미세 픽셀 차이 (1-2px) | Low 자동 | 누적 시 Medium 승격 |

- "의도된 동작" 추정 금지 — 사용자 확인 또는 코드 주석의 의도 명시 인용 필수.
- 강등 시 사용자 발화를 인용한다: `> 사용자 강등 인용: "..."`
- 검증 종결 합리화("이 정도면 충분", "유사 검증 완료", "다음에 고치자")로 남은 검증 영역을 건너뛰지 않는다. 종결은 신규 발견 0 + 사용자 승인으로만 — 단 이 조건은 **명시적 검수·QA 세션에 한정**한다. 일반 작업의 완료는 fablize verification gate 통과(실행 증거)로 자율 선언 가능하다(2026-07-02 Fable 정합).
- 훅 결과가 비어 있으면(입력 초과·파싱 실패·관측 누락) 그 항목은 미검증이다 — 필요한 검사를 직접 실행해 현재 입력·변경과 연결된 결과를 남기되, 그것이 fablize 게이트의 통과 증거(verify-cmd·verify-evidence)를 대신하지는 않는다.

## 보고 형식

```markdown
### 발견 #N: <한줄 요약>
- 분류: High/Medium/Low (강등 시 출처 인용)
- 위치: <파일:라인 또는 URL:엘리먼트>
- 증거: <스크린샷/로그/캡처>
- 재현: <단계>
```
