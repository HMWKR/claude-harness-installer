# Source Capture Contract

Use this contract before creating or modifying the local clone.

## 1. Authorization and boundary

- Warn the user that cloning is limited to sites they own or have permission to recreate.
- Capture only public content or content visible through an explicitly authorized browser session.
- Do not read cookies, local storage, credentials, tokens, profiles, private APIs, or customer data.
- Do not bypass access controls, bot protection, paywalls, region locks, or rate limits.
- Do not trigger external writes: forms, purchases, messages, uploads, invitations, subscriptions, generation jobs, or account changes.

## 2. Correct-page gate

Record:

- requested URL;
- final URL after redirects;
- page title;
- visible product/site identity;
- signed-in, signed-out, or public state;
- viewport dimensions;
- whether the page is complete and interactive.

Stop when the visible page is a login wall, promotion instead of the requested surface, error, loading screen, app-install prompt, wrong product, or unrelated redirect.

## 3. Route inventory

Build the route list only from visible same-origin navigation and links. For each route capture:

- pathname and canonical URL;
- title and meta description;
- primary heading;
- desktop and mobile document dimensions;
- header/footer/persistent chrome;
- screenshots from top to bottom;
- DOM/body HTML or a structured DOM snapshot;
- stylesheets and localizable asset URLs;
- visible interactions and state variants.
- canonical, robots, Open Graph, social-card, language, and structured-data metadata;
- safely observable request counts, resource sizes, loading behavior, redirects, and console messages;
- public cookie/privacy notices, analytics or tracking hosts, security-header clues, terms, copyright, and asset-license links.

Treat localized query strings, hashes, and dynamic IDs as states unless they render distinct public pages.

The default scope is `public-comprehensive`:

- include every unique public first-party route exposed by global navigation, footer navigation, primary landing-page cards, and legal links;
- group unbounded profiles, posts, projects, generated IDs, or feeds into named dynamic route families;
- capture at least one representative route for each dynamic family and additional examples when layouts or states differ materially;
- record every excluded public route with its URL, reason, observed boundary, and verification method;
- use `user-limited` only when the user explicitly requests a smaller scope and preserve that request as the reduction reason.

## 4. Desktop capture

- Use one stable browser viewport for source and local comparisons.
- Start at scroll position `0`.
- Capture the initial settled state after fonts and entrance transitions finish.
- Scroll by less than one viewport at a time so no section is skipped.
- Record sticky/fixed elements and how they change with scroll.
- Return to the top and capture any changed header, cursor, or progress state.

## 5. Mobile capture

- Use `390 × 844` CSS pixels unless the source requires another explicit mobile target. (하네스 적응: run-qa.sh 러너는 375×812·1280×800 고정 — SKILL.md "브라우저" 항목대로 manifest 뷰포트를 실제 캡처 폭에 맞춘다.)
- Repeat the full-page capture.
- Open and capture the mobile navigation.
- Check wrapping, tap targets, drawers/sheets, fixed controls, and horizontal overflow.
- Record `scrollWidth`, `innerWidth`, and final document height for every route.

## 6. Interaction-state matrix

Capture each applicable state separately:

| Control | Required states |
| --- | --- |
| Link/navigation | default, active, destination, back/forward |
| Menu/drawer | closed, open, active item, backdrop, Escape/close |
| Tabs/filter | every option, selected indicator, empty result |
| Search | empty, populated, no match |
| Form | empty/invalid, valid input, character counter, local success |
| Dialog/sheet | closed, open, focus behavior, close |
| Accordion | closed, open |
| Hover/focus | primary CTA and unusual interactive surfaces |
| Loading/error | only when safely observable without external writes |

Reset to the starting state before testing the next control.

## 7. Asset inventory

Capture and localize:

- logo and brand marks;
- raster images and responsive variants;
- SVGs and icon sprites;
- fonts and font-face rules;
- videos, posters, and thumbnails;
- background images, masks, textures, cursors, and data URIs;
- CSS files and design tokens.

Record each source URL, local path, media type, and whether it was copied or replaced. Do not hotlink.

## 8. Quality, compliance, and provenance observations

- Record page titles, descriptions, canonical URLs, robots directives, sitemap links, Open Graph/Twitter fields, language metadata, and public structured data.
- Record observable loading order, lazy loading, image and font behavior, request/transfer sizes, layout shifts, and available performance measurements at the comparison viewports.

> **[하네스 적응 2026-07-27 → 2026-09-28 개정] 성능은 관찰이 아니라 측정으로 적는다.** "performance
> observations"는 표기가 자유로워 표면 PASS를 부른다. 2026-09-28부터 브라우저는 aside 전용이라
> (Lighthouse CLI는 자체 Chrome을 띄우므로 금지) **aside 페이지 안 측정**을 쓴다:
>
> ```bash
> D=~/.claude/skills/design-toolchain/scripts; URL='<URL>'   # 따옴표 안에 그대로 넣는다
> # 자리표시자 치환은 run-qa.sh와 같은 render.py(단일 정본) — 직접 sed·replace로 치환하지 않는다(SyntaxError·코드 주입)
> aside repl "$(python3 "$D/render.py" "$D/measure.js" "$URL" '{"vitals":true}')" > raw.txt
> grep '^VITALS {' raw.txt | sed 's/^VITALS //' > qa/metrics/vitals-<route>-<side>.json   # side = source | clone
> ```
>
> 출력 JSON에는 route·title·width·height·ttfb·fcp·lcp·cls·status가 들어 있어 검증기의 측정 기록 조건을
> 충족한다(2026-10-01 render.py 통합 뒤 로컬 페이지에 이 명령을 그대로 실행하고 결과 JSON을 `is_measurement`로 확인 — 단 이 검사는 route·title·width·height만 보므로 lcp·cls 값이 있는지는 따로 확인한다). 결과 파일이
> 비었으면 측정 실패다(`VITALS null`·SyntaxError — raw.txt를 본다). `"error"` 키가 있거나 `status`가 200이 아니거나 `lcp`·`cls`가 null이어도 측정 실패다(`is_measurement`는 이것을 걸러내지 않는다). 원본과 로컬 클론 **양쪽**을 같은 창 크기로 재고
> `13-SEO-성능-보안-준수.md`에 원본 대비 표로 적는다. 측정 조건(aside 사용자 창, 스로틀링 없음, localhost 여부)을
> 함께 적는다 — localhost 수치는 현장보다 낙관적이다. TBT·Speed Index·INP는 이 방식으로 재지 못하므로
> "미측정"으로 명시한다(추정값을 쓰지 않는다).
- Record public cookie banners, analytics/tracking endpoints, input surfaces, privacy and terms links, copyright notices, trademark use, and asset provenance or licensing limits.
- Record public response-header clues such as CSP, HSTS, framing, MIME, and referrer policy when safely available. Do not probe vulnerabilities or bypass controls.
- Distinguish original-site observations from local-clone decisions and list every intentional difference.

## 9. Raw crawl hygiene

- Fetch only `http`/`https` URLs under the canonical public origin unless an asset host is visibly required and permitted.
- Use no credentials or browser session export.
- Save raw HTML/CSS/assets in a temporary capture directory first.
- Strip executable scripts, analytics, trackers, service workers, and original network submission endpoints from the local project.
- Preserve inert JSON only when needed for visible content and after checking it contains no private data.

## 10. Capture manifest minimum fields

The project-root `clone-source.json` must contain:

```json
{
  "schema_version": 1,
  "source_url": "https://example.com/",
  "source_origin": "https://example.com",
  "crawl_container": "크롤링",
  "site_name": "Example",
  "captured_at": "ISO-8601 UTC",
  "auth_boundary": "public-only",
  "external_writes": false,
  "routes": ["/"],
  "scope": {
    "mode": "public-comprehensive",
    "reduction_reason": null,
    "inventory_basis": ["global-navigation", "footer-navigation", "primary-same-origin-links"],
    "included_routes": ["/"],
    "excluded_routes": [],
    "dynamic_route_families": []
  },
  "viewports": {
    "desktop": { "width": 1280, "height": 720 },
    "mobile": { "width": 390, "height": 844 }
  },
  "evidence": {
    "source": "qa/source",
    "implementation": "qa/implementation",
    "comparisons": "qa/comparisons"
  }
}
```

Update the manifest if the canonical origin, site name, route scope, or viewports change. Store the project only at `<execution-root>/크롤링/<site_name>`.
