---
name: threeui-reference
description: 3D·인터랙티브·WebGL·Three.js·셰이더 UI(버튼·배경·히어로·텍스트 애니메이션·UI 요소·3D 에셋·섹션)를 만들거나 참고가 필요할 때 threeui.com 카탈로그에서 레퍼런스를 찾고, 사이트의 "Copy Prompt"와 같은 프롬프트와 해시 검증된 정확 소스 번들을 회수해 그대로 이식·검증하는 스킬. Use when the user mentions "threeui", "3D 버튼", "3D 인터랙티브", "인터랙티브 배경", "리퀴드 메탈/글래스/홀로 버튼", "셰이더 효과", "WebGL 히어로", or asks to find references and copy prompts for 3D or interactive UI. NOT for: 2D 모션 품질(emil-design-eng·animate), 영상 파일(remotion-best-practices), 이미지 생성(codex), 랜딩 방향 잡기 자체(design-taste-frontend — 방향이 선 뒤 소재가 필요할 때 이 스킬).
---

# ThreeUI 레퍼런스 → 카피 프롬프트 → 정확 소스 이식

threeui.com은 Three.js·WebGL·GLSL·Canvas·CSS 인터랙티브 UI 카탈로그다(2026-10-16 기준 799개, Community 무료·MIT + Pro 유료). 항목마다 **Copy Prompt / Copy Code / Copy SKILL.md**를 주고, Community는 소스 번들 JSON을 공개한다(`https://threeui.com/source-code/<패밀리>.json`, 파일별 SHA-256). 이 스킬은 그 프롬프트를 로컬에서 재현하고 소스를 해시 검증해 가져온다. 사이트 구조·약관·Pro 경계는 `references/site-anatomy.md`.

## 0. 쓸지 판단 (1줄)
- design-brief.md의 대상·느낌에 3D·셰이더 요소가 **도움이 되는지** 먼저 적는다. 장식이면 쓰지 않는다(이 저장소의 공개 사이트는 신뢰·명료가 우선 — DESIGN.md). 쓴다면 "어느 화면의 어느 요소에, 왜"를 작업 문서에 1줄.

## 1. 후보 찾기 — 로컬 검색이 먼저, 사이트는 눈으로 확인만
```bash
python3 -I ~/.claude/skills/threeui-reference/scripts/threeui-search.py <검색어...> [--category Buttons|Backgrounds|Hero|Three.js|"Text Animation"|"UI Elements"|CSS|"Landing Pages"] [--free|--pro] [--probe]
```
- 출력 1부 = Community(메타·변형·fetch 명령), 2부 = 색인 전용(Pro 또는 공개 저장소보다 새 항목). `--probe`가 번들 200/404로 둘을 가른다.
- 후보 2~3개를 고르고 **시각 확인은 aside**(`aside-browser` 스킬 → `aside guide`): `openTab('<url>')` → `snapshot(page, {selector:'main'})`로 Renderer 요약(런타임·패스·에셋 용량)·Renderer contract(reduced-motion·pixelRatio·외부 에셋)를 읽고 `page.screenshot({type:'png'})`로 모양을 본다. 선택은 벤치마크 근거로 직접 정하고(묻지 않음) 이유 1줄을 남긴다.
- 사이트 검색 상자(`/browse`, ⌘K)는 클라이언트 검색이라 `?q=`로는 안 된다 — 필요하면 aside로 입력한다.

## 2. 회수 — 사이트 Copy Prompt와 같은 산출물을 파일로
```bash
~/.claude/skills/threeui-reference/scripts/threeui-fetch.sh <패밀리 slug> [저장 폴더=web-crawling/threeui] [--variant <변형 id>]
```
- 결과: `<폴더>/<패밀리>/prompt.md`(프롬프트), `SOURCE.md`(출처·해시·라이선스), `bundle.json`, 소스 파일(번들 경로 그대로 `src/shaders/...`). 파일 해시가 하나라도 어긋나면 rc=1로 멈춘다.
- rc=2 = 번들 없음 → Pro(또는 slug 오류). **Pro는 쓰지 않는다**(2026-10-16 사용자 규칙: 결제가 필요한 도구·층은 설치도 제안도 하지 않음 — 구매를 권하지 말고 "Pro라 제외" 한 줄만 적는다). 미리보기는 방향 참고로만 보고, 미리보기 영상·DOM을 긁지 않는다(약관 "scrape protected Pro source" 금지). Community(MIT)에서 가장 가까운 패밀리를 고른다.
- 사이트에서 직접 읽어야 할 때(아주 새 항목·탭 내용 대조): aside repl로 Code/Skill.md 탭의 스크롤 영역 `innerText`를 읽는다. "Copy Prompt" 클릭은 `navigator.clipboard.writeText`에만 잡힌다.

## 3. 이식 — prompt.md의 Implementation requirements가 계약
- 정확 소스로 구현한다. 미리보기·스크린샷을 보고 흉내 내지 않는다. 소스를 못 받으면 멈추고 보고한다.
- **React 표면**(admin 등): `npm i @designcodeio/threeui@<고정 버전>` → `import { X } from "@designcodeio/threeui"; import "@designcodeio/threeui/style.css";` 번들의 `Usage`대로. 전체 문서형 컴포넌트는 런타임 파일을 루트 상대 URL에서 기대한다 — `node_modules/@designcodeio/threeui/lib-dist/assets/`를 `public/`에 복사하거나 `sourceUrl`/`assetBaseUrl` prop으로 지정(저장소 README).
- **Astro·바닐라 표면**(공개 사이트): 번들의 canonical-source HTML(독립 문서)을 Astro 컴포넌트로 옮긴다 — 마크업·`<style>`·`<script type="module">`을 컴포넌트 범위로 가두고, 외부 Inter 스타일시트·CDN 참조는 CSP(`default-src 'self'`, `style-src 'self'`)에 맞춰 로컬 자산으로 바꾼다. 사이트 로고·색·글꼴 규칙(DESIGN.md)이 우선이고 셰이더 팔레트만 맞춘다.
- **공통 계약**: Renderer contract의 reduced-motion freeze 유지, pixelRatio ≤ 2, 뷰포트 밖이면 렌더 루프 정지(IntersectionObserver), Enter/Space·포커스 링·접근 가능한 이름 보존. 번들 `assets`가 MB 단위면 공개 사이트 용량·CSS 예산(`site/scripts/gate.mjs`)과 먼저 대조하고 가벼운 변형(DOM+CSS·Canvas)을 우선한다.
- 사이트에 처음 넣을 때 라이선스 1줄 고지: Community MIT(항목 attribution 유지).

## 4. 검증 — 완료 선언 전 필수 (rules/live-feature-verify.md)
- `aside repl`: 캔버스 마운트(`canvas` 존재·크기), hover/press/키보드 상호작용 후 `snapshot(page).diff`, 인페이지 계측으로 콘솔 오류 0·외부 요청 0(CSP). reduced-motion은 `page.emulateMedia({reducedMotion:'reduce'})`가 되면 그것으로, 안 되면 소스의 freeze 경로를 코드로 확인하고 사용자 OS 설정 전환을 요청한다.
- `~/.claude/skills/design-toolchain/scripts/run-qa.sh <URL> <출력폴더> [태그]`(375·1280 × 다크·라이트, LCP·CLS, axe) → PNG를 직접 연다. design-detect 훅 결과는 트리아지.

## 5. 기록
- `SOURCE.md`의 출처·해시·라이선스를 프로젝트 제3자 고지에 옮기고, 선택 이유·기각 후보·검증 증거를 작업 문서에 남긴다(변경 이유 기록 규칙).

## 경계
- 브라우저 = aside만(Playwright·Chrome MCP 없음). 이미지 = codex. 영상 = Remotion. 2D 모션 폴리시 = emil-design-eng/animate.
- ThreeUI MCP(`https://threeui.com/api/mcp`, Pro OAuth)·`@designcodeio/threeui-cli`는 유료 Pro 전용이라 등록·사용하지 않는다(유료 도구 금지 규칙 — 예외는 Refero뿐).
- 이 스킬의 스크립트는 네트워크 GET만 하고, 쓰기는 지정한 저장 폴더와 `catalog/` 안에서만 한다.

## 파일
- `scripts/threeui-search.py` 로컬 검색 · `scripts/threeui-fetch.sh` 번들 회수+프롬프트 · `scripts/build-catalog.py` 카탈로그 재생성(sitemap + GitHub raw, 네트워크 2회)
- `catalog/community.json`(Community 43 패밀리·176 결과, 2026-10-16) · `catalog/sitemap-index.md`(273 패밀리·905 URL)
- `references/site-anatomy.md` 사이트 해부·Pro·MCP·약관·하네스 연결
