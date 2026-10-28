# ThreeUI 사이트 해부 (2026-10-16 실측 — aside repl 스냅샷·curl)

## 무엇인가
- threeui.com(designcode.io 운영, 2026-10-16 기준 Pro 포함 799개 항목, 사이트 검색 상자 표기). Three.js·WebGL·GLSL·Canvas·CSS로 만든 **인터랙티브 UI 카탈로그**: 랜딩 페이지·히어로·Three.js 장면·배경·버튼·텍스트 애니메이션·UI 요소·CSS·모션 디자인·3D 에셋·섹션.
- **Community(무료)**: 공개 저장소 github.com/MengTo/threeui(MIT, ★6.6k) + npm `@designcodeio/threeui`(1.2.0, MIT). 2026-10-16 동기화본 기준 패밀리 43개·탐색 결과 176개(변형 포함).
- **Pro(유료)**: 2026-10-16 가격 Lifetime $299(정가 $599 할인 표기)·Yearly $199(정가 $399). Pro 디자인 580개·완성 랜딩 74개. 완전 소스·상업 이용·MCP·CLI 포함. **비회원에게는 10초 미리보기 영상만** — 소스·복사 도구·설치 스니펫·컨트롤이 모두 잠긴다.

## URL 규칙
- 카테고리: `/landing-pages` `/hero` `/three-js` `/backgrounds` `/buttons` `/text-animation` `/ui-elements` `/css` `/motion-design` `/3d-assets` `/sections`
- 항목: `/<카테고리>/<패밀리 slug>` · 변형: `/<카테고리>/<패밀리>/<변형 id>` · 태그: `/browse/tag/<태그>`
- 검색: `/browse`의 입력 상자(클라이언트 검색 — `?q=`는 필터하지 않음) 또는 ⌘K. 카드에 `FREE`/`PRO` 배지와 태그 3개가 붙는다.
- **소스 번들(Community만)**: `https://threeui.com/source-code/<패밀리>.json` — 로그인 없이 200, 구조 `{schemaVersion, id, files[{path, language, role, bytes, lines, sha256, code}], assets[{path, mimeType, bytes, sha256}]}`. Pro 패밀리는 404. 사이트 "Copy Prompt"가 링크하는 바로 그 파일이다.
- 전체 Community 번들 한 파일: 저장소 `public/source-code.json`(32.8MB) — 보통은 패밀리별 JSON으로 충분.

## 상세 페이지 해부(Community)
- 머리: 제목 · **Copy Prompt**(클릭 → 클립보드에 "프롬프트 + 정확 소스" 텍스트, 상태 메시지 "Prompt + exact source copied") · **More export options** 메뉴(Copy Prompt / Copy Code / Copy SKILL.md) · Open Preview(독립 미리보기 창) · GET PRO.
- 설명 1줄 + 태그 링크 + 조회수.
- Usage 영역: 라이브 iframe 렌더러 · 변형 선택기 · **Renderer** 요약(READY, 패스 수, 런타임, 에셋 수·용량) · 탭 **Usage**(import 코드) / **Code**(파일 선택 콤보: 컴포넌트 TSX·canonical HTML·공유 threeui.css, "Complete source html · N lines · <해시>") / **Skill.md**("Codex skill markdown · N lines", frontmatter `name: add-<패밀리>`).
- About · **Renderer contract** 표(renderer, control, variants, geometry, appearance, interaction, pixelRatio ≤2, **motion: Reduced-motion freeze**, assets: 외부 Inter 스타일시트 + fallback) · Installation(`npm install @designcodeio/threeui`, import 한 줄) · Source integrity(해시 고정).
- Copy Prompt 텍스트의 뼈대(실측 2,137자): 제목 `# Integrate <ImportName /> from ThreeUI using its exact source` → 정확 소스로 구현하라는 지시 → Component/Variant/Runtime/Source revision → Reference brief → `## Current configured usage`(tsx) → `## Exact implementation source`(번들 JSON 링크 + 파일별 role·SHA-256) → `## Implementation requirements`(구조·셰이더·모션·에셋 경로 보존, 문서 페이지 임베드 금지, 소스를 못 받으면 멈추고 보고, 구현 후 브라우저 검증). `scripts/threeui-fetch.sh`가 같은 뼈대를 로컬 파일로 만든다.

## Pro 페이지(비회원)
- 제목 · Open Preview · 태그 · "PRO" 표시 · "This is a Pro template" 대화상자(영상 미리보기, Upgrade to unlock) · Member source / Private delivery 안내. 라이브 렌더러도 소스도 내려오지 않는다.

## Pro MCP · CLI (참고용 — 유료라 쓰지 않는다, 2026-10-16 사용자 규칙)
- MCP: `https://threeui.com/api/mcp` (Streamable HTTP, OAuth 2.1 → Supabase 토큰, Pro 자격 검사). 도구: `search_catalog`, `get_catalog_item`, `get_item_source`, `get_item_prompt`. 클라이언트 설정 `{"mcpServers":{"threeui":{"type":"http","url":"https://threeui.com/api/mcp"}}}` → **등록하지 않는다**(유료 Pro 전용 — 결제 필요 도구 금지, 예외는 Refero뿐).
- CLI: `npx @designcodeio/threeui-cli add <slug>` — OAuth PKCE, Pro 자격 서버 검사, 바뀐 파일 덮어쓰기 거부(`--force`).

## 약관·라이선스 (2026-09-24 판)
- Community 코드: 포함된 라이선스(현재 MIT). 항목별 attribution·제3자 고지 유지. 글꼴 SIL OFL 1.1, Three.js 런타임 MIT. 사이트에서 불러오는 썸네일·미리보기 미디어는 재배포 대상 아님.
- Pro: 유효 자격 보유 중 무제한 개인·상업·클라이언트 프로젝트 사용·수정. 단독 자산·템플릿·라이브러리·생성기로 재판매·재배포·공개 금지. 클라이언트가 다른 프로젝트에 재사용하려면 자체 라이선스.
- 금지: 접근 통제 우회, **보호된 Pro 소스 스크래핑**, 남용 자동 요청. → 이 스킬은 Pro 미리보기 영상·DOM을 긁지 않고, 공개 번들 JSON과 공개 저장소만 쓴다.

## 이 하네스와의 연결
- 브라우저 = `aside repl`만(미리보기 확인·검증). 사이트 검색은 로컬 `threeui-search.py`가 먼저.
- 이미지·래스터는 codex(rules/cross-vendor-routing.md). ThreeUI는 코드·셰이더 소스이므로 이미지 생성과 무관.
- 회수물 저장은 `web-crawling/threeui/<패밀리>/`(크롤 규칙) — 프로젝트에 넣을 때는 SOURCE.md의 출처·해시·라이선스를 제3자 고지에 옮긴다.
- 공개 사이트(Astro, CSP `default-src 'self'`·`style-src 'self'`): 외부 Inter 스타일시트·CDN 의존을 로컬로 바꾼다. `@designcodeio/threeui` 컴포넌트는 런타임 파일을 ThreeUI 미리보기와 같은 루트 상대 URL에서 기대한다 — `node_modules/@designcodeio/threeui/lib-dist/assets/`를 `public/`으로 복사하거나 `sourceUrl`/`assetBaseUrl` prop으로 바꾼다(저장소 README).

## 갱신
- `python3 -I scripts/build-catalog.py` — sitemap.xml + GitHub raw `src/data/shaders.tsx`를 다시 읽어 `catalog/`를 다시 만든다(네트워크 2회, 쓰기는 catalog/ 안만).
