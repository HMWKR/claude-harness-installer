---
name: clone-site-from-source
description: Faithfully clone and comprehensively document an authorized live website under the current task directory's 크롤링/site-name folder by capturing the source in-browser, crawling public DOM/CSS/assets, mapping information architecture and user flows, documenting design and responsive details, recreating routes/interactions, and passing side-by-side design QA plus local build checks. Use when the user asks for 실제 크롤링, 레퍼런스 사이트 그대로/똑같이, URL-to-code, clone/mirror/recreate a public website, full UX/design documentation, or the same pipeline used for RealizeSoft. Do not use for redesigns or inaccessible login-only/private apps.
---

# Clone Site From Source

Create an evidence-backed frontend clone from the live source, not from memory or visual approximation. Preserve the source information architecture, typography, spacing, assets, responsive behavior, and core interactions.

## Required companion workflows

> **[하네스 적응 2026-07-25]** 이 스킬은 OpenAI/Codex 환경에서 왔고 원문이 요구한 동반
> 워크플로 4종(`product-design:url-to-code`, `browser:control-in-app-browser`,
> `local-prototype-preflight`, `design-qa`)은 이 하네스에 **존재하지 않는다**(실측 확인).
> 아래는 그 등가물로 재결속한 것이다. 게이트·계약·문서 세트의 내용은 원문 그대로다.
> 변경 내역과 원본 zip 위치: [HARNESS-ADAPTATION.md](HARNESS-ADAPTATION.md).

- **브라우저**: `aside-browser` 스킬 전용이다 — `rules/uncompromising-rigor.md` §1 정본
  (2026-09-05 Aside 단일화, Playwright·Chrome MCP는 deny로 툴 자체가 없다). 스킬 로드 →
  `aside guide` → `aside guide repl` 후 `aside repl`로 조작한다.
  스크린샷은 `page.screenshot({type:'png'})` Buffer를 base64로 찍어 셸에서 저장한다(`path`
  인자는 Aside 세션 폴더로 샌드박스됨, §1-b). 뷰포트별 캡처는 `rules/ui-ux-craft.md`
  "시각 검증 루프"대로 `~/.claude/skills/design-toolchain/scripts/run-qa.sh`(375·1280 × 다크·라이트 전체 캡처 + LCP·CLS + axe)를 쓴다.
  **이 러너의 폭은 375×812·1280×800 고정**이다 — `init_clone_run.py`에 `--mobile 375x812
  --desktop 1280x800`을 넘겨 manifest 뷰포트를 실제 캡처와 맞춘다(capture-contract §5·§10의
  390×844·1280×720 대신; 원본·클론을 같은 폭으로 비교하는 것이 목적이다). 러너 출력
  `full-<테마>_<폭>-<태그>.png` 4장 중 비교 증거는 **원본·클론 모두 같은 테마 1장씩**이다 —
  기본 `light`, 원본이 다크 전용이면 `dark`, 고른 테마를 `design-qa.md`에 적는다. 파일명 매핑:
  `full-<테마>_1280-*` → `qa/source/<route>-desktop.png`, `full-<테마>_375-*` →
  `qa/source/<route>-mobile.png`(클론은 `qa/implementation/`). JPEG가 필요하면
  `sips -s format jpeg <in>.png --out <out>.jpeg`로 변환한다.
- **로컬 프로토타입 기동/프리뷰**: `run` 스킬을 쓴다(신규 프로젝트 부트스트랩·기동·확인).
- **차단 게이트(design-qa 대체)**: `jusan-harness:playwright-design-audit`을 blocking
  handoff 게이트로 쓰되 브라우저 조작은 aside repl로 치환하고, 접근성은 run-qa.sh의 axe-core 주입 스캔을 병행한다(accesslint 라이브 스캔은 자체 Chrome이라 쓰지 않는다). **산출 파일명과 마지막 줄
  형식은 원문 그대로 `design-qa.md` / `final result: passed`를 유지한다** —
  `validate_clone_artifacts.py`가 그것을 검사한다.
- **url-to-code 파이프라인**: 별도 스킬이 없으므로 이 문서의 §Pipeline이 정본이다.
- 인접 스킬 경계: `reference-match`는 레퍼런스 1건과 구현의 정합 검사용이고, 이 스킬은
  **전체 공개 라우트 크롤 + 클론 + 22종 증거기반 문서화**다. 겹치면 이 스킬이 상위다.
- Read [capture-contract.md](references/capture-contract.md) before opening the target.
- Read [output-contract.md](references/output-contract.md) before creating the project.
- Read [experience-documentation-contract.md](references/experience-documentation-contract.md) before writing the UX analysis.

If the browser surface is unavailable, stop and report the blocker. Do not replace browser evidence with web search, screenshots alone, or guessed code.

증거 라벨 `[확인]`/`[강한 추론]`/`[검증 필요]`/`[확인 불가]`는 이 하네스의
`[검증됨]`/`[추정]`/`[미확인]` 규약과 정합한다 — 문서 안에서는 원문 라벨을 쓰고, 사용자
보고에서는 하네스 라벨을 쓴다.

## Input contract

Resolve these values from the request and visible source:

- `source_url`: canonical public URL.
- `execution_root`: the directory where the user started the task.
- `site_name`: the visible product/site name, for example `GoogleFlow` or `RealizeSoft`.
- `destination`: always `<execution_root>/크롤링/<site_name>` unless the user explicitly requests another root.
- `scope_mode`: `public-comprehensive` by default. Use `user-limited` only when the user explicitly narrows the scope.
- `scope`: every unique public first-party route exposed by global navigation, footer navigation, and primary same-origin cards, plus representative pages for repeated dynamic route families and all safely observable interaction states.
- `outcome`: a local, frontend-only clone for authorized review or development.
- `auth_boundary`: public-only unless the user explicitly provides access through the chosen browser.

Warn that the user must follow the source site's terms and have permission to recreate it. Play back the target, `크롤링/<site_name>` destination, public/auth boundary, and expected duration. Continue without asking for approval when those values are clear.

`public-comprehensive` is the default even when the request names only the site. Do not silently reduce the run to the home page. Avoid unbounded crawling by grouping infinitely repeated profiles, posts, projects, or generated IDs into route families, capturing representative examples, and recording the family rule and exclusions. Every skipped public route must have an evidence-backed reason in the manifest and documentation.

## Non-negotiable gates

1. Capture source evidence before scaffolding, writing app code, or starting a local server.
2. Stop if the page is wrong, blocked, login-only, promotional instead of the requested surface, still loading, or unrelated after trying the allowed browser recovery path.
3. Never use hotlinked source assets in the finished clone.
4. Never submit live forms, purchases, messages, uploads, or model-generation requests while inspecting or testing.
5. Do not copy executable source scripts, analytics, trackers, credentials, cookies, storage, or authenticated API data.
6. Do not deploy or publish unless the user explicitly asks.
7. Do not hand off until `design-qa.md` says exactly `final result: passed` and the artifact validator succeeds.

## Pipeline

### 1. Verify the source

- Open `source_url` in the selected browser.
- Confirm URL, title, visible product identity, auth state, viewport, and page completeness.
- Record redirects and the canonical origin.
- Identify the public route set from visible navigation and same-origin links; do not invent hidden routes.
- Inventory global navigation, footer navigation, primary landing-page cards, legal links, and representative dynamic route families before declaring the scope complete.

### 2. Capture before crawling

- Capture desktop at the browser's stable viewport and mobile at `390 × 844`. (하네스 적응: run-qa.sh 러너를 쓰면 375×812·1280×800 — 위 "브라우저" 항목의 manifest 정렬 규칙을 따른다.)
- Capture every primary public route at both viewports. For repeated dynamic route families, capture at least one representative route plus any visibly distinct variants.
- Start at the top, scroll in small steps to the bottom, and return to the top.
- Save screenshots and DOM/layout evidence for every visible section.
- Exercise one control at a time and capture each changed state: navigation, menus, drawers, tabs, filters, forms, dialogs, hover/focus/selected, empty/loading/error/success when safely reachable.
- Capture computed fonts, CSS files, colors, spacing, responsive changes, image/video/SVG/font URLs, route titles, descriptions, H1 text, document dimensions, and overflow.
- Follow the complete checklist in [capture-contract.md](references/capture-contract.md).

Do not scaffold the local project until the source capture is sufficient to reproduce every required state.

### 3. Crawl permitted public source material

- Fetch public HTML and same-origin styles/assets without credentials.
- Keep raw captures outside the project until source capture is complete.
- Store a route manifest with canonical URL, status, title, description, viewport, dimensions, asset URLs, and capture paths.
- Copy real images, SVGs, fonts, video posters, CSS, masks, and icons locally.
- Remove executable scripts, analytics, trackers, transition overlays that require the original runtime, and stale loading/cursor state. Recreate required behavior locally.
- Preserve exact source text and legal copy when it is in scope.

Prefer original server-rendered DOM and compiled CSS when they can be sanitized safely. Use a component rewrite only when raw DOM/CSS cannot run locally or would violate the constraints above.

### 4. Create the local project

- Preserve the task's starting directory as `execution_root`; do not default to Desktop or the skill directory.
- Resolve the destination after source capture. Pass the visible product identity explicitly as `site_name` when the hostname alone is ambiguous:

```bash
CLONE_RUN_ROOT="$(pwd)"
CLONE_DEST="$(python3 <skill-dir>/scripts/resolve_clone_destination.py \
  --workspace-root "$CLONE_RUN_ROOT" \
  --source-url <source_url> \
  --site-name <site_name>)"
```

- Require the resolver result to equal `<execution_root>/크롤링/<site_name>`. The resolver creates only the `크롤링` container.
- Bootstrap the web prototype into `CLONE_DEST`; the bootstrap creates the site-name directory. (하네스 적응: Product Design 부트스트랩은 부재 — `run` 스킬 또는 프레임워크 공식 스캐폴드로 만든다.)
- Install dependencies with the configured offline-friendly npm cache.
- Run the following only after the source capture gate passes:

```bash
python3 <skill-dir>/scripts/init_clone_run.py \
  --project-root "$CLONE_DEST" \
  --source-url <source_url> \
  --scope-mode public-comprehensive \
  --authorization-basis <user-owned|user-confirmed-permission|public-documentation-site|other> \
  --authorization-confirmed-by "<권한을 확인해 준 주체>" \
  --robots-txt-status <allowed|absent-404|not-applicable-owned> \
  --route / \
  --route /other-public-route
```

`--authorization-*`는 **필수**다(2026-07-27 추가). capture-contract §1의 권한 경계가 산문
경고뿐이고 게이트가 한 항목도 검사하지 않던 것을 기계화한 것이다.

`--robots-txt-status`는 확인 **결과**를 기록한다 — 붙이지 않으면 검증기가 완료를 거부한다:
- `allowed` — robots.txt를 읽고 크롤 허용을 확인했다. **`qa/robots.txt`에 사본을 남겨야 한다**
  (`curl -sS <robots_txt_url> -o qa/robots.txt`). 사본이 없으면 반려된다.
- `absent-404` — robots.txt가 없다.
- `not-applicable-owned` — 자기 소유 사이트(`--authorization-basis user-owned`일 때만 유효).

검증기는 `robots_txt_url`의 호스트가 `source_url` 호스트와 같은지도 대조한다. 다만 robots.txt를
직접 가져와 내용을 해석하지는 않는다 — 자기 신고의 한계는 `HARNESS-ADAPTATION.md`에 명시했다.

**기존 프로젝트 마이그레이션**: 2026-07-27 이전에 만든 프로젝트에는 authorization 블록이 없어
검증기가 반려한다. 이때 `--force`를 쓰면 **완성된 문서 22개가 플레이스홀더로 되돌아간다** —
대신 `--update-authorization`을 쓴다(manifest의 authorization만 갱신하고 `qa/`·`design-qa.md`·
`문서/`는 손대지 않는다).

- Treat the generated `clone-source.json` as the source-of-truth manifest.
- Keep `scope.included_routes`, `scope.excluded_routes`, and `scope.dynamic_route_families` synchronized with the crawl. An exclusion must include a concrete reason; an unbounded route family must include its representative capture rule.
- Complete every generated Markdown file under `문서/`. Replace all `작성 필요`, `TODO`, and `pending` markers with source-grounded analysis and evidence paths.
- Document information architecture, user flows, screen/state inventory, design details, responsive rules, content/assets, interactions/accessibility, implementation notes, gaps/assumptions/risks, crawl results, source-versus-local differences, and SEO/performance/security/privacy/legal observations. Do not silently invent unobserved behavior; record it in `10-누락-가정-리스크.md` with a verification method.
- Complete the mandatory deep-experience set `14` through `21`: UX strategy and popularity drivers, roles/JTBD/journeys, funnel and growth loops, detailed flows/state/recovery, design rationale and heuristic evaluation, service audit and prioritized improvements, feature/state/test matrix, and the evidence/source registry.
- Apply the evidence labels `[확인]`, `[강한 추론]`, `[검증 필요]`, and `[확인 불가]` as defined in [experience-documentation-contract.md](references/experience-documentation-contract.md). Popularity, growth, conversion, or success claims require dated sources; UI observation alone is not proof of business performance.
- Keep screenshots under `qa/source`, rendered captures under `qa/implementation`, and combined comparisons under `qa/comparisons`.
- Keep source assets inside `public/assets` or a framework-equivalent local asset directory.

### 5. Recreate the experience

- Match the source DOM hierarchy, tokens, fonts, spacing, breakpoints, content, and assets.
- Implement direct URL access and internal navigation for every captured route.
- Recreate menus, drawers, tabs, filters, search, accordions, forms, scroll headers/progress, and visible cursor/motion states with local logic.
- Keep forms and backend-dependent actions local. Show an explicit local-only success state instead of contacting the source service.
- Preserve keyboard operation, focus indicators, reduced motion, labels, alt text, and practical mobile tap targets.
- Do not add a new design direction, placeholder art, handmade SVG substitutes, emoji icons, or CSS drawings.

### 6. Measure route fidelity

For every route at desktop and mobile, record:

- final URL and title;
- H1 or primary screen label;
- document width and height;
- viewport width and height;
- horizontal overflow;
- header or persistent chrome dimensions;
- console error/warning count.

Compare source and local values at the same viewport and state. Investigate every unexplained delta before visual QA.

### 7. Run interaction and visual QA

- Test direct URLs, internal links, browser back/forward, all captured controls, keyboard/Escape, and local-only form states.
- Capture source and implementation at identical viewport, theme, route, scroll position, and interaction state.
- Put each pair into one combined comparison image; do not judge separate images from memory.
- Run the design-qa gate until no actionable P0/P1/P2 remains. (하네스 적응: Product Design `design-qa`는 부재 — 위 "차단 게이트" 항목의 `jusan-harness:playwright-design-audit`(브라우저는 aside repl) + run-qa.sh axe.)
- Run `npm run build`. `npm run test:sites`는 Codex Sites 전용 타깃이므로 **`package.json`에
  실재할 때만** 실행하고, 없으면 프로젝트의 실제 테스트 스크립트(`test`·`test:e2e` 등)로
  대체한 뒤 무엇을 돌렸는지 `design-qa.md`에 기록한다. 대체 대상이 없으면 "테스트 스크립트
  부재"를 명시한다 — 없는 명령을 통과했다고 쓰지 않는다.
- Validate the final artifacts:

```bash
python3 <skill-dir>/scripts/validate_clone_artifacts.py --project-root "$CLONE_DEST"
```

Fix failures and repeat. A successful build alone is not visual verification.

### 8. Handoff

- Keep the verified local preview running and open in the selected browser.
- 보고 첫 줄에 **로컬 프리뷰 URL**을 제시한다(예: `http://localhost:3000`). Codex Desktop
  프리뷰는 이 환경에 없다.
- State which routes and interactions were reproduced, what remains local-only, and which checks passed.
- Link `design-qa.md` and the project directory.
- 배포·공유는 **사용자가 명시 요청할 때만** 한다. `@Sites` 같은 Codex 전용 공유 타깃은 이
  환경에 없으므로 먼저 묻지 않는다.

## Failure handling

- **Authentication required:** ask the user to sign in through the selected browser, then resume capture. Never inspect browser storage or credentials.
- **Source blocks capture:** try the allowed browser recovery path once. If still blocked, set QA to blocked and stop.
- **Uncopyable asset:** generate a replacement only after capturing the original and record the replacement and reason. (하네스 적응: ImageGen은 부재 — codex MCP 이미지 생성, `rules/cross-vendor-routing.md` "이미지 생성 호출".)
- **Dynamic/backend-only state:** reproduce it with realistic local mock data and label destructive/external actions as local-only.
- **Source changes during QA:** recapture the affected route and update `clone-source.json`; do not mix old and new evidence silently.

## Completion standard

Complete only when the project satisfies [output-contract.md](references/output-contract.md) and [experience-documentation-contract.md](references/experience-documentation-contract.md), the browser-rendered source/local comparisons have been judged, core interactions work, console error/warning checks are clean, the build passes, the project's real tests pass (§7 — `test:sites` only when it exists in `package.json`; a missing test script is recorded in `design-qa.md`, never claimed as passed), and the validator exits successfully.
