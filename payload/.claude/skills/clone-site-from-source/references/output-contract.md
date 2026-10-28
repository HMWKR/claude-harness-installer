# Clone Output Contract

Read this before creating the local project and before final handoff.

## Required project shape

```text
<execution-root>/
└── 크롤링/
    └── <SiteName>/             # project root
        ├── .openai/hosting.json
        ├── clone-source.json
        ├── design-qa.md
        ├── package.json
        ├── 문서/
        │   ├── 00-문서-목록.md
        │   ├── 01-사이트-개요.md
        │   ├── 02-정보구조.md
        │   ├── 03-유저-플로우.md
        │   ├── 04-화면-상태-목록.md
        │   ├── 05-디자인-디테일.md
        │   ├── 06-반응형-규칙.md
        │   ├── 07-콘텐츠-에셋.md
        │   ├── 08-인터랙션-접근성.md
        │   ├── 09-기술-구현-메모.md
        │   ├── 10-누락-가정-리스크.md
        │   ├── 11-크롤링-보고서.md
        │   ├── 12-원본-대비-차이.md
        │   ├── 13-SEO-성능-보안-준수.md
        │   ├── 14-UX-전략-인기-성공요인.md
        │   ├── 15-역할-JTBD-사용자-여정.md
        │   ├── 16-서비스-퍼널-성장-루프.md
        │   ├── 17-상세-유저플로우-상태-복구.md
        │   ├── 18-디자인-UX-원리-평가.md
        │   ├── 19-서비스-경험-감사-리스크-개선.md
        │   ├── 20-기능-상태-테스트-매트릭스.md
        │   └── 21-UX-근거-출처-레지스터.md
        ├── public/
        │   └── assets/         # copied local source assets
        ├── qa/
        │   ├── source/         # source screenshots
        │   ├── implementation/ # local screenshots
        │   ├── comparisons/    # source + local in one image
        │   └── metrics/        # route/viewport measurements
        ├── src/                # runnable local frontend
        ├── dist/
        │   ├── client/
        │   ├── server/index.js
        │   └── .openai/hosting.json
        └── tests/              # Sites/worker tests
```

Framework-specific additions are allowed. Do not place crawl runs directly in the execution root, Desktop, or the skill directory. Do not omit the documentation, evidence, and hosting artifacts above.

## Documentation requirements

Complete all generated files under `문서/` from source evidence. The final validator rejects missing files and any remaining `작성 필요`, `TODO`, or `pending` marker.

The `14`–`21` deep-experience set is mandatory and must satisfy [experience-documentation-contract.md](experience-documentation-contract.md). It is not an optional appendix.

- Record observed facts with route, screenshot, DOM, or asset evidence.
- Default to a comprehensive public-site inventory rather than a home-page-only clone. Cover global navigation, footer, primary landing links, legal routes, and representative dynamic route families.
- List every included route, every excluded public route with its reason, and every repeated dynamic route family with its representative capture rule.
- Record unobserved or login-only behavior as an explicit gap or assumption; never present it as confirmed.
- Describe every primary user flow with entry point, user goal, ordered steps, branches, completion condition, empty/error/loading states, and auth/external-service boundaries.
- Document typography, tokens, spacing, grids, surfaces, iconography, imagery, motion, cursor behavior, responsive changes, and design exceptions.
- Include overlooked areas: legal/footer content, error and empty states, keyboard/focus behavior, reduced motion, asset provenance, backend-only actions, and follow-up verification methods.
- Maintain an evidence-linked source-versus-local difference register covering visual, interaction, content, asset, and backend-boundary deltas.
- Record SEO metadata and structured data, performance/loading observations, tracking and privacy behavior, security-header clues, copyright/licensing limits, compatibility, and operational observability without bypassing protections.
- Separate confirmed observation, strong inference, verification needs, and unavailable evidence with the required labels. Map business-success and popularity claims to dated sources rather than inferring them from interface quality.

## Clone behavior requirements

- Every captured route supports direct URL access and internal navigation.
- Source assets load locally; the clone contains no remote `src`, stylesheet, font, video, poster, or CSS `url(http...)` hotlinks.
- Core controls captured from the source work locally.
- External/backend actions are intercepted and represented by explicit local-only states.
- Desktop and mobile layouts have no unintended horizontal overflow.
- Document title and description match each captured route.
- Accessibility semantics, labels, focus, keyboard close behavior, and reduced motion are preserved where the source provides them.

## Required QA evidence

At minimum include:

- one full-view desktop source screenshot and implementation screenshot;
- one full-view mobile source screenshot and implementation screenshot;
- one source/local combined comparison for each;
- combined comparisons for navigation/menu and every core interaction state;
- route metrics for desktop and mobile;
- browser console error/warning check;
- build and Sites test results.

Use focused region comparisons for small type, icons, forms, dense controls, or asset fidelity that cannot be judged in a full-view image.

## `design-qa.md` contract

Include:

- source visual truth paths;
- implementation screenshot paths;
- viewport, CSS size, pixel dimensions, and density normalization;
- routes and states compared;
- full-view comparison evidence;
- focused comparison evidence or why it was unnecessary;
- explicit evaluation of typography, spacing/layout, colors/tokens, image/asset quality, copy/content, icons, responsiveness, interactions, and accessibility;
- P0/P1/P2 history, fixes, and post-fix evidence;
- primary interactions tested;
- console errors checked;
- build and Sites test results;
- exactly one final line: `final result: passed` or `final result: blocked`.

Use `passed` only when no actionable P0/P1/P2 remains.

## Acceptance gates

All must pass:

1. Project root is `<execution-root>/크롤링/<SiteName>`.
2. All 22 generated site-analysis Markdown files (`00`–`21`) are complete, including the mandatory deep-experience set.
3. Correct source and authorized scope were captured.
4. Comprehensive public route inventory is complete, or the user explicitly requested and the manifest records a limited scope.
5. Source capture preceded implementation.
6. Routes, assets, and interaction states match the manifest.
7. Same-viewport combined images were inspected.
8. No actionable P0/P1/P2 remains.
9. No external asset hotlinks remain.
10. No browser console errors or warnings remain.
11. `npm run build` passes.
12. 프로젝트 테스트 통과 — `npm run test:sites`는 Codex Sites 전용이므로 **실재할 때만**
    적용한다. 없으면 프로젝트의 실제 테스트 스크립트로 대체하고 무엇을 돌렸는지 기록하며,
    대체 대상이 없으면 "테스트 스크립트 부재"를 명시한다(없는 명령의 통과를 주장하지 않는다).
13. `validate_clone_artifacts.py` exits `0`.

> **[하네스 적응 2026-07-27] 게이트 내용 검사 5종.** 이전 게이트는 파일 존재·문자열 포함·
> 글자 수만 봐서 1×1 투명 PNG와 `{}` metrics, `"asdf"` 반복 문서로 통과했다(실증). 이제
> 다음을 함께 검사한다 — 정상 작업에서는 걸리지 않고 위조에서만 걸리는 기준만 채택했다:
>
> 1. **전체뷰 캡처** — `qa/{source,implementation,comparisons}` 각각에 320×320 이상 이미지가
>    최소 1장(헤더에서 픽셀 크기를 직접 읽는다). 부분 확대 비교는 함께 두어도 무방하다.
> 2. **측정값 실체** — `qa/metrics/*.json`이 파싱되고, 키에 route·title·width·height 개념이
>    3개 이상 있어야 한다(§6 "Measure route fidelity"가 요구하는 항목).
> 3. **QA 증거 인용** — `design-qa.md`가 **실존하는** `qa/` 증거 파일을 2개 이상 지목해야 한다.
>    `final result: passed` 한 줄이 단독으로 완료 권한을 갖지 못하게 하는 조치다.
> 4. **`captured_at`** — ISO-8601 파싱 가능 + 미래 시각 아님. `--max-evidence-age-days`로
>    신선도 상한을 걸 수 있다(기본 off).
> 5. **권한 근거** — manifest에 `authorization {basis, confirmed_by, robots_txt_checked:true}`.

> **[하네스 적응 2026-07-25]** 위 트리의 `.openai/hosting.json`(프로젝트 루트·`dist/`)은
> Codex Sites 호스팅 전용 산출물이므로 이 환경에서는 **필수가 아니다**. 프레임워크 고유의
> 배포 설정이 있으면 그것을 쓰고, 없으면 생략하고 그 사실을 `09-기술-구현-메모.md`에 적는다.
> 나머지 트리(`문서/` 00–21, `public/assets`, `qa/{source,implementation,comparisons,metrics}`,
> `clone-source.json`, `design-qa.md`)는 **원문 그대로 필수**다 — 검증기가 검사한다.

## Handoff content

- 로컬 프리뷰 URL을 보고 첫 줄에 제시한다(Codex Desktop 프리뷰는 이 환경에 없다).
- Short statement that the build is finished.
- Route and interaction scope.
- Local-only/backend limitations.
- Build, Sites, and QA status.
- Links to the project directory and `design-qa.md`.
- One share prompt through the available target; no implicit deployment.
