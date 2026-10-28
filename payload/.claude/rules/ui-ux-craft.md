---
paths:
  - "**/*.tsx"
  - "**/*.jsx"
  - "**/*.css"
  - "**/*.scss"
  - "**/*.vue"
  - "**/*.svelte"
  - "**/*.html"
  - "**/*.astro"
---

# UI/UX Craft — 디자인 작업 상시 규율

> UI·디자인 코드 작업 시 자동 적용. "사람 디자이너처럼" 디테일·일관성·의도 정합을 강제한다.

## 상태 전수 (모든 인터랙티브 요소)

default 하나만 만들고 끝내지 않는다. hover / focus-visible / active / disabled / loading / empty / error — 해당되는 상태 누락은 결함이다.

## 디자인 토큰 일관성

- 색·간격·폰트·radius·shadow는 토큰/변수로. 하드코딩 hex·px 발견 시 토큰화한다.
- 한 화면에 임의 색·간격 난립 금지 — 4/8px 그리드와 타이포 스케일을 따른다.

## 반응형·시각 검증 루프 (눈)

모바일(375)·데스크톱(1280) 두 폭을 의도하고 확인한다. 다크 모드는 프로젝트에 이미 있거나 브리프·사용자가 요구할 때만 두 모드 모두 설계·확인하고, 없으면 라이트만 한다(다크 추가는 먼저 제안). 브레이크포인트 누락·가로 넘침·터치 타깃 위반을 검출한다.

코드만 쓰고 "다 됐다"로 닫지 않는다 — 렌더를 직접 본다. 브라우저 작업은 전부 `aside-browser` 스킬로 한다(로드 → `aside guide` → `aside guide repl`):
1. 로컬 미리보기를 띄우고 `~/.claude/skills/design-toolchain/scripts/run-qa.sh <URL> <출력폴더> before` — 375·1280 × 다크·라이트(강제) **전체 페이지** 캡처(높이 검산) + 가로 넘침 수치 + LCP·CLS + axe(창 폭·375)를 한 번에 낸다. 종료코드 0 = 완전 검사·위반 0·수동 확인 0, 1 = 불완전(통과로 보지 않는다), 2 = axe 위반, 3 = 자동 판정 불가(axe 보류·테마 전환 미확인·미처리 테마 조건·미정착 구간) — 출력 목록을 PNG·페이지로 확인한 뒤에만 통과(세부: design-toolchain §4). 라이트만 있는 사이트는 '테마 강제 지점 0'으로 rc=3이 나오는 것이 정상이다 — 라이트 PNG를 보고 통과 처리한다.
2. 캡처 PNG를 **직접 열어** 간격 어긋남·글자 넘침·정렬 틀어짐·기준선 불일치를 찾는다. 수치만으로 시각 항목을 통과시키지 않는다.
3. 고친 뒤 같은 URL·조건으로 `… after`를 다시 돌려 **전후를 나란히** 대조하고, 전후 캡처를 사용자에게 보여 준다.
4. 상호작용 요소(메뉴·FAQ·폼)는 `snapshot()` ref로 **실제 클릭·키보드 조작**을 하고 상태 변화(diff·`open`·`:focus-visible`)를 증거로 남긴다.

Aside 제약(실측): 탭은 사용자 창 크기로 고정되고 `setViewportSize`·CDP가 없어서 러너는 **같은 출처 iframe + clip 구간 캡처**로 폭을 만든다. `page.screenshot({fullPage:true})`는 이 방식에서 첫 화면을 반복한 **가짜 이미지**를 만들므로 쓰지 않는다. 테마는 `prefers-color-scheme` 조건을 원하는 테마 기준으로 평가해 캡처용 iframe의 CSSOM에서 치환·삭제한다(다른 미디어 조건 보존, 시트 media·`<picture>` source·`color-scheme`까지 — 세부 design-toolchain §4). 원본 파일은 불변이고, 클래스·data-theme 방식 테마는 강제하지 못해 "테마 전환 미확인"(rc=3)으로 알린다.

## 브리프 우선 (새 화면·리디자인)

스킬은 기준만 줄 뿐 무엇을 만들지는 모른다. 판단 재료 없이 착수하면 학습된 기본값(보라 그라데이션·가운데 정렬 첫 화면·똑같은 카드 3장)으로 돌아간다. 새 화면·리디자인은 코드 전에 프로젝트 루트 `design-brief.md`를 만들고 시작한다:

- 대상(누가 보는가) · 느낌(형용사 2~3개) · **참고 사이트 1~2곳**(필수 — 없으면 발굴해 제안) · 페이지 목록 · 핵심 화면의 섹션 구성(순서대로) · 브랜드(색 코드·글꼴) · 조용한 제약(접근성·규제·신뢰 우선 등).
- 첫 줄에 Design Read 1줄: "Reading this as: <페이지 종류> for <대상>, with a <느낌> language, leaning toward <디자인 시스템·미감 계열>." 랜딩·소개(마케팅) 사이트·포트폴리오·리디자인이면 `design-taste-frontend` v2의 `draw.mjs`로 고른 방향(direction 키)도 적는다(v2에는 옛 다이얼 VARIANCE·MOTION·DENSITY가 없다).
- 해석이 실제로 갈릴 때만 질문 1개로 묻는다. 추론 가능하면 묻지 말고 Design Read를 선언하고 진행한다.
- `/impeccable`이 PRODUCT.md를 요구하면 impeccable init 절차로 제품 사실(사용자·목적·플랫폼·스택·근거)만 쓰고, 시각 방향(느낌·참고·색·글꼴·섹션)은 design-brief.md에만 둔다 — 역할이 달라 중복이 아니며, 브리프에 답이 있는 질문은 다시 묻지 않는다.
- 다듬기 요청도 같은 원칙: "더 세련되게" 대신 대상 요소·수치·전후 캡처 요구로 구체화해 실행한다(예: 섹션 간격 96px 통일, 버튼 1개만 남김).

## 기계 검출 게이트 (impeccable detect)

완료 선언 전 AI 티를 규칙으로 검출한다 — 눈대중 대신 명령 결과를 증거로 쓴다:

```bash
~/.claude/skills/impeccable/scripts/impeccable detect <HTML 파일 또는 폴더>   # 종료코드 0=무결함, 2=결함 발견, 1=검사 실패
```

- **대상은 HTML 파일 또는 폴더.** CSS·JSX 단독은 정규식 모드라 대부분 놓친다(2026-09-28 실측, 엔진 0.1.5: 같은 페이지가 HTML 11건 vs CSS 단독 2건 — 대비·글로우·제목 계층·팔레트 누락). 폴더를 넘기면 HTML과 CSS를 함께 검사한다.
- **출력 없음·결함 0건 ≠ 통과.** 무엇을 검사했는지(파일 목록)부터 확인한다. 종료코드 2는 고장이 아니라 발견이다.
- **URL 대상 금지**(URL 모드는 Puppeteer로 자체 브라우저를 띄움 — 브라우저는 aside 전용). 렌더 결과 확인은 위 시각 검증 루프가 맡는다.
- 트리아지: 진짜 결함 → 고친다(무시 설정으로 넘기기 금지) / 근거 있는 오탐 → `impeccable hooks ignore-value`로 가장 좁게(프로젝트 루트 — 가장 가까운 `.impeccable`, 없으면 `.git`·`package.json` 폴더 — 에서 실행: 훅이 그 폴더 설정을 읽는다), `--reason`에 근거 명시 / 불확실 → 사용자에게 1줄 질문. `ignore-rule`·`ignore-file`은 사용자 승인 후에만.
- **알려진 오탐**(엔진 0.1.5 최소 재현, 0.1.14에서도 재현 — 2026-10-15): CSS 논리 속성 `padding-block`·`padding-inline`을 읽지 못해 테두리 있는 상자에 `cramped-padding`을 낸다. 가로쓰기 문서에서는 같은 뜻의 `padding-top/bottom`으로 쓰거나 파일 단위로 좁게 예외 처리한다.
- **자동 실행**: UI 파일을 Edit/Write하면 `scripts/design-detect-hook.py`(PostToolUse)가 detect를 돌려 결함을 알림으로 주입한다(차단 없음). HTML은 전체 검출, 컴포넌트·HTML 없는 CSS는 부분 검출이라 0건이어도 세션·파일당 1회 "부분 검출" 안내가 오고, CSS는 그 파일을 참조하는 HTML까지 검사한다. 이미 알린 결함은 세션·에이전트별로 건수만 알린다. 알림을 받으면 위 트리아지를 한다. impeccable 자체 훅(Stop deep pass 포함)은 켜지 않는다 — Stop 권위는 fablize 하나(CLAUDE.md 레이어 서열).

## 접근성 (비협상 — 위반은 High)

- 텍스트 대비 4.5:1(큰 글자 3:1). **UI 구성요소·포커스 링·입력 테두리 등 비텍스트는 3:1**(WCAG 2.2 SC 1.4.11 AA) — 포인트 색 포커스 링은 배경 대비부터 계산한다.
- 터치 타깃: SC 2.5.8(AA)은 **24×24 CSS px 이상**을 요구하되 예외(충분한 간격·동등한 대체 컨트롤·문장 속 인라인 링크·브라우저 기본 컨트롤·필수 표현)가 있다 — 24 미만이면 예외 해당 여부를 먼저 판정한다. 하네스 자체 목표는 주요 컨트롤 44px(SC 2.5.5 강화 기준) — 목표 미달은 WCAG 위반과 구분해 적는다.
- `prefers-reduced-motion: reduce`에서 이동·확대 모션을 끈다(전정 장애 유발 — MDN). 색·투명도 전환은 남겨도 된다.
- 시맨틱·aria·키보드 순회·`:focus-visible` 보존. 자동 검사는 run-qa.sh의 **axe-core 주입 스캔(다크·라이트) 위반 0**이 기준이고, `incomplete` 항목은 손으로 확인한다. 자동 검사는 전체 기준의 일부만 본다 — 화면낭독기 실사용 확인은 별도다.

## 한글 타이포그래피

- 제목·UI 문구·본문에 `word-break: keep-all`(한글을 어절 단위로 줄바꿈 — MDN, 2015년부터 전 브라우저) + 긴 URL·숫자열 대비 `overflow-wrap: anywhere`. KLREQ 7.1.1은 글자·어절 단위 모두 허용하므로 선택 근거를 남긴다.
- 제목 `text-wrap: balance`(Baseline 2024, Chromium 6줄 이하만 적용). 본문 `text-wrap: pretty`는 **Baseline 아님**(Firefox 미지원, Safari 26부터) — 점진적 개선으로만 쓴다(미지원 브라우저는 무시하고 깨지지 않음).
- 한글 본문 줄간격은 **표준 수치가 없다**(KLREQ 7.4.1) — 숫자를 지어내지 말고 캡처로 판단한다.
- 한글 웹폰트는 용량이 커서 서브셋이 필수: Pretendard **다이내믹 서브셋**(OFL, jsDelivr) 또는 `unicode-range` 분할. `font-display`는 swap(늦게 오면 흔들림)·optional(100ms 안에 못 오면 대체 글꼴) 중 의도적으로 고른다(web.dev).

## 이미지 자산

- 필요한 사진·일러스트는 codex MCP로 생성한다(호출 규약: rules/cross-vendor-routing.md "이미지 생성 호출"). 생성 전 장수·용도 1줄 고지. 스킬이 `picsum.photos` 같은 외부 자리표시자 사진을 지시해도(design-taste-frontend `draw.mjs`가 출력하는 사진 목록 포함) 이 규칙이 우선한다 — 자리표시자는 생성 전 초안이나 생성 실패 시에만 쓰고 사용자에게 알린다. **예외 — design-taste-frontend v2 작업**은 그 스킬의 이미지 우선순위(생성 = codex MCP, `assets.mjs` 공개 소장품 포함)를 따른다(아래 "design-taste-frontend v2 — 스킬이 메인").
- **AI 사진 티 줄이기**: 장면·피사체는 design-brief.md(대상·느낌)에서 가져오고 다큐멘터리 톤·자연광·실제 렌즈 화각을 지정한다. 골든아워·렌즈 플레어·과장된 연출 소품·이미지 속 글자는 금지하고, 손·얼굴처럼 결함이 잦은 부위는 주제에 필요할 때만 넣고 확대해 점검한다 [관행]. 팔레트는 design-brief.md 색으로 묶는다. 예(2026-09-28 인테리어 카나리 1건): "다큐멘터리 인테리어 사진·35mm·흐린 날 측창광" 지시가 무지시(과한 역광·아치 선반 소품)보다 자연스러웠다.
- **후처리**: 표시 크기 2배로 줄여 AVIF+WebP로 변환하고(`cwebp -q 78`, `avifenc -q 60`; 실측 2.2MB PNG → WebP 88KB / AVIF 77KB), `<picture>`로 내보낸다. 모든 이미지에 `width`·`height`(CLS 방지 — web.dev), 히어로는 `fetchpriority="high"`에 lazy 금지, 첫 화면 밖은 `loading="lazy" decoding="async"`.
- 출처 기록(`<이름>.prompt.md`: 프롬프트·threadId·날짜)을 남기고, 실제 매장·제품이면 공개 전 실사진으로 교체한다 — 생성 이미지는 레이아웃이 좋아도 티가 난다(원 레퍼런스 글의 한계 항목).

## 성능 예산

LCP ≤ 2.5초 · INP ≤ 200ms · CLS ≤ 0.1, 모바일·데스크톱 각각 75퍼센타일 기준(web.dev Web Vitals). run-qa.sh가 페이지 안에서 LCP·CLS를 잰다 — localhost 수치는 현장보다 낙관적이고 INP는 상호작용이 필요해 재지 않는다. Lighthouse CLI는 자체 Chrome을 띄우므로 쓰지 않는다 — 스킬의 "Run Lighthouse" 지시(design-taste-frontend 등)도 이 측정으로 대체한다.

### design-taste-frontend v2 — 스킬이 메인, 하네스는 덧붙임 (2026-10-15, 벤더 파일은 고치지 않는다)

> 사용자 지시(2026-10-15): "저 스킬을 메인으로 하고 추가적인 이미지나 생성하는게 더 좋은게 있다면 codex mcp로 하는걸로 진행을 해줘" · "외부 이미지 다운로드 같은 경우 내가 승인할 때만 쓰지 말고 저 스킬에 맞춰서 진행" · 규칙 반영 "전체적으로 전부 다 진행을 하며 허락을 할게 그냥 허락해"

원칙: 스킬의 10단계(브리프 → 논증 → draw → 아이디어 → 카피 → 정적 구축 → lint+inspect 게이트 → 보기 → 모션 → 보고)와 하우스 룰을 **메인 절차로 그대로** 따른다. 하네스는 대체하지 않고 **덧붙인다**: 생성 그림은 codex MCP, run-qa.sh(테마 2종·Vitals·axe), aside 실화면 확인. 하우스 룰이 프로젝트 계약(인물 사진 금지·가짜 증거 금지·로고 보존 등)과 부딪히면 프로젝트 계약이 이기고 보고에 적는다.

| 스크립트 | 분류(코드 확인) | 사용 + 하네스 덧붙임 |
|---|---|---|
| `scripts/lint.mjs` | 정적·로컬 읽기 전용 | 그대로 쓴다 |
| `scripts/inspect.mjs` · `lib/cdp.mjs` · `lib/probe.mjs` | 격리 headless Chrome(사용자 세션 없음) + 로컬 http 서버 | **스킬 게이트로 그대로 쓴다** — rigor §1 자체 브라우저 금지의 이 스킬 한정 예외(위 사용자 지시). 대상은 로컬 파일·localhost만(외부 사이트 탐색·크롤은 aside). 덧붙임: run-qa.sh와 aside 확인을 함께 돌리고 캡처 PNG를 직접 연다 |
| `scripts/assets.mjs` | 외부 네트워크(Openverse·Wikimedia·AIC·Met·archive.org·NASA), `--get`은 `assets/`로 받고 `credits.json` 기록 | **스킬대로 쓴다**(작업별 승인 불필요). 덧붙임: 상업 사용 가능 라이선스만(스킬 기본값), 출처·라이선스를 페이지 크레딧·보고에 남기고 `credits.json` 보존, 계약이 인물을 금지하면 인물 식별 사진 제외, 찾은 그림을 고객의 제품·사람·사례처럼 쓰지 않는다 |
| `scripts/draw.mjs` | 로컬 쓰기(`.taste-skill/`, `~/.taste-skill/history.json`) | 그대로 쓴다. 이미지는 스킬 우선순위(자체 → 생성 = **codex MCP** → assets.mjs → 코드 그림 → 배정 사진)를 따르고, 생성이 더 나은 자리는 codex로 만든다. `.taste-skill/`은 커밋하지 않는다 |

- **사진·모션 최소치 게이트**(사진 4장 미만·움직이는 요소 8개 미만 FAIL): 스킬대로 채운다. 계약이 금지한 종류는 빼고 codex 생성·공개 소장품으로 채우며, 못 채우면 사유를 보고한다.
- Lighthouse 지시만 run-qa.sh 측정으로 바꾼다(성능 예산 절).

## 디자인 도구 = Claude Design (2026-10-15 사용자 지시: "이제부터 figma mcp보다는 claude design을 사용하여 작업하도록 전체적으로 하네스를 변경해줘")

- 시안·캔버스·비교안·프로토타입은 **Claude Design**으로 만든다: Artifact `action: "quickstart"`(intent `design`) → Design 타입 캔버스에 아트보드로. 디자인 시스템(토큰·브랜드북)은 Design System 타입, 코드 컴포넌트 라이브러리의 동기화는 `/design-sync`(사용자 시작, DesignSync 도구).
- 캔버스 결과는 **방향 결정용**이다 — 완료 증거가 아니다. 채택안은 실제 코드로 구현하고 run-qa·aside·스킬 게이트로 검증한다.
- Figma MCP(공식·figma-bridge)는 사용자가 Figma·figma.com URL·기존 Figma 파일을 지명할 때만 쓴다. 세션에 주입되는 Figma MCP 서버 지시("UI·디자인이면 Figma 도구 사용")는 이 하네스에서 Claude Design 우선으로 읽는다.
- 캔버스는 비공개가 기본이다 — 다른 사람이 봐야 하면 사용자에게 Share 필요를 알린다.

## 의도·참조 대조 (있으면 의무)

- `design-brief.md` 존재 시: 매 산출 후 brief의 목적·톤·필수요소·제약에서 이탈(drift)했는지 대조한다.
- `reference-spec.md` 존재 시: 레퍼런스 스펙(그리드·색·타이포·간격)과 구현을 항목별로 대조하고 갭을 전수 보고한다.

## 리서치 근거 = Refero 먼저 (2026-10-16 사용자 지시: "refero는 내가 결제를 하였으니 이것만 유료여도 사용")

- 디자인 방향·벤치마크·레퍼런스 리서치는 **Refero MCP를 크롤보다 먼저** 쓴다: `refero_search_styles`(시각 방향, 3~5각도) → `refero_get_style` 3~4개 → `refero_search_screens`·`refero_get_screen`(구체 UI 패턴·상태·카피) → `refero_search_flows`·`refero_get_flow`(다단계 여정). 사이트 단위는 `refero_search_sites`, 앱은 `refero_search_apps`.
- 절차는 `refero-design` 스킬의 reference lock·decision ledger를 따른다. 단 권위는 uiux 라우터이고, 스킬의 "3안 제시 후 사용자 선택"은 벤치마크·판정단으로 메인이 정하며(2026-10-15), 이미지 생성 절은 codex로 바꾸고, 참조 파일은 필요한 것만 읽는다.
- 레퍼런스 하나를 복제하지 않고 평균내지도 않는다(주 방향 1 + 세부 차용 1~2). 출처(Refero 스타일·화면 UUID)를 decision ledger에 남긴다.
- 새 조사는 근거가 없거나 방향이 바뀔 때만 한다: 사용자 시안·브랜드·승인된 디자인 시스템·기존 decision ledger가 있으면 그것이 우선이고(문구·토큰·작은 버그 수정 포함) 재조사 없이 재사용한다.
- Refero에 없는 대상이거나 실제 DOM·토큰 정밀 추출이 필요하면 아래 웹크롤링으로 이어간다.
- `ux-pattern-researcher` 스킬(Codex 포트)의 웹 검색 수집 단계는 Refero 조회와 아래 aside 크롤로 치환하고, 그 Question Gate는 착수 계약에 종속된다.
- 그 밖의 유료 도구·층은 쓰지 않는다(design-toolchain §1 "유료 도구 금지"). 무료 층은 적극 쓴다.

## 3D·WebGL·셰이더 UI 계약 (threeui-reference 등, 2026-10-16)

- **쓸지 먼저 판단**: 3D·셰이더 요소가 브리프의 대상·느낌에 도움이 될 때만 쓰고, "어느 화면의 어느 요소에, 왜"를 1줄 남긴다. 장식용이면 쓰지 않는다.
- **정확 소스로 이식**: 미리보기를 보고 흉내 내지 않는다. ThreeUI는 Community(MIT) 번들을 해시 검증해 회수하고(Pro는 유료라 제외), 출처·해시·라이선스를 제3자 고지에 옮긴다.
- **런타임 계약**(위반은 High): `prefers-reduced-motion`이면 정지(freeze), devicePixelRatio ≤ 2, 뷰포트 밖이면 렌더 루프 정지(IntersectionObserver), 탭 숨김이면 정지(visibilitychange), WebGL 미지원·컨텍스트 손실 시 정적 대체 이미지, 키보드(Enter/Space)·초점 링·접근 가능한 이름 보존.
- **예산·CSP**: 번들 자산이 MB 단위면 성능 예산(위 절)과 먼저 대조하고 가벼운 변형(DOM+CSS·Canvas)을 우선한다. 공개 사이트는 CSP(`default-src 'self'`, `style-src 'self'`)라 외부 글꼴·CDN·인라인 스크립트를 로컬 자산·모듈로 바꾼다.
- **검증**: aside repl로 canvas 마운트·크기, 상호작용 후 `snapshot(page).diff`, 인페이지 계측(콘솔 오류 0·외부 요청 0), 프레임 간격(rAF)을 확인하고 run-qa.sh 캡처를 직접 본다.

## 녹화를 웹 모션으로 옮길 때 (motiscope + Remotion, 2026-10-16 실측)

정본은 design-toolchain `references/remotion-vs-motiscope.md`다. motiscope의 구간·홀드·대표 프레임은 쓰고, 이징 종류·cubic-bezier·시차 숫자는 그대로 믿지 않는다(실측 3/3 틀림). 프레임을 직접 판독해 교정하고, 정교함이 필요하면 Remotion 매개변수 컴포지션으로 후보를 렌더해 원본 녹화와 프레임 단위로 대조한다(같은 과제에서 상자 오차 188px → 107px → 10px). 결과물은 CSS·JS 코드로 만들고 영상으로 박지 않는다. 결과가 영상 파일일 때만 Remotion이 주 도구다.

## 레퍼런스 수집 — 웹크롤링 (참조 요청 시, 사용자 지침 2026-07-07)

사용자가 UI/UX 작업에서 레퍼런스 사이트 참조를 요청하면:
1. **능동 확장**: 사용자 지정 사이트 + 같은 카테고리 **경쟁사·우수 레퍼런스 3~5개를 발굴**(WebSearch/insane-search)해 목록을 1줄 제시(공개 페이지 대상, 과잉 크롤 금지).
2. **크롤링(도구: `aside-browser` 스킬 로드 후 `aside repl`)**: `openTab(url)` → `page.evaluate()`로 DOM/CSS 추출 → `page.screenshot({type:'png'})`. 스크린샷 파일은 base64로 받아 로컬에 저장한다(§1-b — `path` 인자는 세션 디렉토리로 샌드박스됨). 정적 텍스트만이면 WebFetch. 사이트별 완전 격리 컨텍스트가 필요한 대량 배치는 Aside로 불가하니 사용자에게 보고한다(§1-c — Playwright MCP는 deny로 차단됨). 각 사이트에서 **스크린샷 + HTML/핵심 CSS + 디자인 토큰(색·타이포·간격·radius·shadow) 추출**.
3. **저장**: 프로젝트 루트 `web-crawling/<site-slug>/` 에 저장 — `screenshot.png` · `page.html` · `notes.md`(추출 패턴·차용/회피 포인트). git 미추적 권장(`.gitignore`에 `web-crawling/`).
4. **참조·대조**: 이후 UI/UX 설계·구현을 이 크롤 자산 기준으로 진행하고, `reference-spec.md`가 있으면 항목별 대조에 반영.

**파이프라인 결선**(conductor-verify와 동일 구조): 크롤링은 독립 단계가 아니라 파이프라인의 일부다 — ① 계획: 어느 사이트를 크롤할지 결정 → ② **Execute: 사이트당 1 teammate 병렬 크롤**(`aside repl`) → ③ 종합: 크롤 자산에서 레퍼런스 인사이트(공통 패턴·차별점) 추출 → ④ 설계·구현 → ⑤ **최종검증: 완성 UI를 크롤 레퍼런스 대비 대조**(reference-spec 항목별, 교차벤더 게이트는 main). crawl→design→verify가 한 파이프라인.
- 공개 페이지·저작권 존중(디자인 참고 목적이지 무단 복제 아님). robots 차단 페이지는 승인과 무관하게 크롤하지 않는다. 로그인·유료 페이지는 사용자에게 보고하고, 사용자가 그 페이지를 명시 승인한 경우에만 Aside(사용자 세션)로 본다.

## 도구 추가

작업 중 쓸 만한 디자인 스킬·플러그인·MCP를 발견하면 설치하지 말고 `design-toolchain` 스킬의 후보 표에 1줄 추가한다. 설치는 그 스킬의 추가 절차(출처·내용 점검·역할 배치·실검증)를 거친다.

## 자기 종결 금지

"대충 비슷하면 됨"으로 닫지 않는다. 디테일 갭은 결함으로 등재한다 (rules/uncompromising-rigor.md §2). 종결은 의도·참조 충족 + 사용자 승인으로만.
