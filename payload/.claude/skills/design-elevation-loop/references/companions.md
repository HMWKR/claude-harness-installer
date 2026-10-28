# 동반 스킬 — 단계별 트리거와 겹침

SKILL.md 8절의 상세판이다. 이름은 이 하네스의 Skill 도구 이름이다. 다른 환경에서는 세션 스킬 목록에 있는 것만 부르고, 없으면 "없을 때"를 쓴다.

## 원칙

- **바깥 루프는 하나.** project-quality-loop, harness-loop, bkit pdca·sprint·development-pipeline 같은 다른 루프 엔진은 이 루프 안에서 돌리지 않는다. 종료 조건이 서로 부딪힌다.
- **스킬 안의 짧은 반복은 회차당 한 번.** design-taste-frontend의 look(최대 3라운드), impeccable의 bounded pass는 바깥 회차 하나 안에서 끝낸다.
- **방향은 택1.** 같은 화면에 방향 스킬 두 개를 동시에 쓰지 않는다.
- **인자를 준다.** impeccable은 명령 없이 부르면 메뉴만 보이고 멈춘다. emil-design-eng는 질문 없이 부르면 인사만 하고 멈춘다. 둘 다 `<명령/질문> <대상>`을 넘긴다.
- **질문은 한 번씩만.** 이미 있는 design-brief.md를 먼저 읽고, 브리프 질문과 완성도 질문이 같은 것을 다시 묻지 않게 한다.
- **모델이 못 부르는 스킬**(disable-model-invocation)은 사용자에게 `/이름`으로 권한다.

## 단계 × 스킬

| 단계 | 스킬 | 언제 | 주의 | 없을 때 |
|---|---|---|---|---|
| 의도 | `jusan-harness:what` / `what-you` | 목적·범위가 흐릴 때만 | 둘 중 하나. goal 게이트 형식 A/B/C의 정본 | 4프레임(왜·무엇·어떻게·기대 가치)을 한 문단으로 |
| 브리프 | `jusan-harness:design-intent-lock` | design-brief.md가 없을 때 | 빈 축만 묻는다. 완성도 질문과 축이 다르다(의도 vs 수준) | 8축 브리프를 직접 쓴다 |
| 리서치 | `aside-browser` | 경쟁사 캡처·DOM·토큰 추출 | `aside repl` = 증거, `aside "<작업>"` = 탐색. 한 요청에 섞지 않는다. 직렬 | 환경의 허용된 브라우저 도구 |
| 리서치 | **Refero MCP + `refero-design`**(사용자 결제 — 유일한 허용 유료) | 리서치의 **첫 단계**, 크롤 전 | `refero_search_styles` 3~5각도 → `refero_get_style` 3~4개 → `refero_search_screens`/`refero_search_flows`. reference lock·decision ledger만 가져오고, 스킬의 '3안 제시 후 사용자 선택'은 판정단으로, 이미지 생성 절은 codex로 바꾼다 | aside 크롤 + 출처 표 |
| 리서치 | `clone-site-from-source` | 선정한 경쟁사 1~2곳을 정밀 캡처·문서화할 때 | robots·저작권 존중, 카피·이미지는 가져오지 않는다 | aside repl 캡처 |
| 리서치 | `motiscope-analyze` | 경쟁사 모션 녹화(사용자가 녹화)가 있을 때 | 구간·홀드·대표 프레임만 믿고 이징·시차 숫자는 프레임으로 교정(정본 design-toolchain `references/remotion-vs-motiscope.md`) | 프레임 수동 판독 |
| 리서치 | `jusan-harness:domain-researcher` / `anthropic-skills:deep-research` | 경쟁사 목록·기능 비교·시장 | 둘 중 하나. 텍스트 중심이라 시각 증거는 크롤로 따로 | 웹 검색 + 출처 표 |
| 리서치 | `jusan-harness:reference-match` | 선정 레퍼런스를 7차원(그리드·색·타이포·간격·컴포넌트·모션·톤)으로 정량 대조 | 본문의 Playwright 지시는 aside로 바꾼다 | 같은 7차원 표를 직접 |
| 리서치 | `watch:watch` | 경쟁사 데모·광고 영상 | — | 생략 |
| 방향 | `design-taste-frontend` | 마케팅·소개·랜딩·포트폴리오·리디자인 | 앱 화면 제외. 기존 브랜드는 `--keep palette,type`. inspect는 로컬·localhost만 | `frontend-design:frontend-design` |
| 방향 | `frontend-design:frontend-design` | 앱 화면·대시보드·폼·문서 | 브리프를 먼저 넘긴다 | 브리프 → 방향 1줄 → 토큰 계획 → 비평 |
| 방향 | `jusan-harness:ui-ux-pro-max` | 앱·대시보드에 팔레트·글꼴 후보가 필요할 때 | 마케팅 페이지에서 design-taste 데이터와 섞지 않는다 | — |
| 방향 | `threeui-reference` | 브리프에 3D·WebGL·셰이더 요소가 있을 때만 | Community(MIT)만, Pro는 유료라 제외. 0단계 '쓸지 판단'을 먼저 | 쓰지 않는다(장식 3D 금지) |
| 시안 | Claude Design 캔버스(Artifact `quickstart`, intent `design`) | 리디자인에서 2~3안을 비교해 고를 때 | 시안은 방향 결정용이고 완료 증거가 아니다 | 비교안 HTML 한 장 |
| 디자인 시스템 | Artifact quickstart(intent `other`, Design System 타입) / `/design-sync`(사용자) | 토큰·컴포넌트 재정비 | — | 토큰 표 + 컴포넌트 목록 문서 |
| 시안(Figma) | `figma:figma-use` → `figma:figma-generate-design` | 사용자가 Figma를 지명할 때만 | Claude Design과 같은 시안을 이중으로 만들지 않는다 | — |
| 구현 | `emil-design-eng` | UI 구축·수정의 기본 | 구체 질문 인자 필수 | 상태(기본·호버·초점·눌림·비활성·로딩·오류) 전수 |
| 구현 | `apple-design` | 드래그·스와이프·시트·스프링 | — | transform·opacity, 인터럽트 가능 |
| 구현 | `animate` | 새 모션을 결정 순서(할지→목적→도구→속성→곡선→중단→감속)로 구현 | 질문 인자 필수(인사 대기 문구 건너뜀) | emil-design-eng 모션 절 |
| 구현 | `motion` + MCP `motion`(무료 문서·예제 검색) | Motion 라이브러리나 CSS `linear()` 스프링이 필요할 때 | 유료 Motion+ 결과는 쓰지 않는다. 이 스킬의 'codex'는 Motion 문서 검색이다 | animate 레시피 |
| 구현 | `motiscope-recreate` → C 루프 | 경쟁사 녹화의 모션을 맞춰야 하고 모션 기준이 L3 이상 | A(수치 그대로)에서 멈추지 않는다. 정교함이 필요하면 Remotion 매개변수 컴포지션으로 원본과 프레임 대조(실측 188→107→10px) | B(프레임 판독)까지 |
| 구현 | `mobile-native` | 375px 등 모바일 기준이 잠겼을 때 | 실기기 확인은 사용자 항목, `0.0.0.0` 바인딩은 사용자 확인 뒤 | 모바일 폭 run-qa |
| 구현 | `dataviz`(있으면 — 환경 내장일 수 있다) | 차트·KPI 타일 첫 줄 전 | — | 형태 선택·색 대비·축 표기 점검 |
| 구현 | `vercel:react-best-practices` / `vercel:nextjs` / `vercel:shadcn` | 그 스택일 때만 | — | — |
| 병렬 구현 | `conductor-verify` 워크플로 | 독립 파일 여러 개를 한 회차에 고칠 때 | 교차벤더 게이트는 워크플로 반환 뒤 메인이 직접 | 네이티브 Agent 병렬 |
| 이미지 | `cross-vendor`(codex 이미지 생성) | 사진·일러스트 자리 | 생성 전 장수·용도 고지, 한 작업 5장 초과는 승인 | 코드 그림(SVG·CSS) |
| 영상 | `remotion-best-practices` → `ffmpeg-skill` | 히어로 무음 루프·제품 데모 | 생성형 영상은 fal.ai + Blender 기준 프레임(사용자 비용 상한) | CSS·JS 모션 |
| 모션 감사 | `improve-animations` | 모션 기준이 L3 이상일 때 회차마다 | 소스를 고치지 않고 계획만 낸다 | 모션 하한 점검표 |
| 모션 기회 | `find-animation-opportunities` | 모션 기준 L2 이상, 회차 시작에 한 번 | 읽기 전용 제안. 채택은 기준·벤치마크로 메인이 | 상태 전수표 |
| 모션 성능 | `animation-performance` | 모션이 있는 회차의 게이트, 또는 '끊김·버벅' 보고 | 측정은 aside repl(rAF 간격·long-animation-frame·getAnimations). DevTools·`npx motionscore` 금지 | 합성 전용 속성 점검 |
| 모션 리뷰 | `review-animations` | 모션 diff 엄격 리뷰 | 슬래시 전용 → 사용자에게 권한다 | — |
| 게이트 | `impeccable` `critique <대상>` / `audit <대상>` / `polish <대상>` | 회차 끝 비평·기술 점검 | 이 하네스에서는 게이트 전용. live 모드·이미지 생성 제안은 따르지 않는다 | 휴리스틱 점검표 |
| 게이트 | design-detect 훅 | UI 파일 편집마다 자동 | 0건이 통과는 아니다(부분 검출) | `impeccable detect <HTML>` 수동 |
| 게이트 | `break-ui` | 데이터가 들어가는 화면(카드·표·목록·폼)이 있을 때 회차마다 | 픽스처·토글은 공개 `site/src/pages` 밖. 200% 줌은 반폭 iframe | 긴 이름·0/1/1000건 수동 |
| 게이트 | `jusan-harness:web-design-guidelines`(있으면) / `jusan-harness:frontend-review` / `code-review` | 코드 규칙 점검(택1) | 세션 스킬 목록에 없으면 부르지 않는다 | — |
| 심층 감사 | `jusan-harness:playwright-design-audit` | 이정표 회차·최종 직전 | 무겁다. 브라우저 단계는 aside로 | — |
| QA 캡처 | `design-toolchain`의 `run-qa.sh <URL> <폴더> <태그>` | 매 회차 같은 조건으로 | rc 1 = 불완전(통과 아님). fullPage 캡처 금지 | 브라우저 스크린샷 + axe 주입 |
| 접근성 | run-qa axe + accesslint `audit_html`(정적 HTML) + aside 수동 조작 | 매 회차 | accesslint 라이브 스캔은 이 하네스에서 차단 | axe-core 주입 |
| 판정 | `cross-vendor`(codex read-only, 메인 직접) | 판정단의 다른 벤더 석, 최종 검증 | 워크플로 안 장시간 호출 금지 | 관점이 다른 Claude 판정석 |
| 판정 | `amplify-presets` | 판정단 인원·혼합·불확실성 보존 | — | 판정자 3 + 순서 교환 |
| 판정 | critic 에이전트(agentType) | Claude 판정석·최종 검증자 | agentType을 빼면 쓰기 도구가 열린다 | 쓰기 금지 브리프 |
| 페르소나 | `aside-browser` 에이전트 레인 | 회차마다 3명 | 증거 아님, 결함 후보. 질문을 묶어 적게 부른다 | 서브에이전트에 캡처를 주고 페르소나 평가 |
| 실동작 | `jusan-harness:live-verify-loop` / `ultradetail-walk` | 폼·메뉴·라우팅이 바뀐 회차 | 바깥 루프 안에서는 단발로 | 직접 조작 |
| 완료 | `fablize:fablize` | goal A | 네이티브 `/goal`·`/loop`와 함께 쓰지 않는다 | 검증 명령·결과 기록 |
| 디자인 밖 | `project-quality-loop` | 기능·보안·성능까지 출시 판정이 필요할 때 | 슬래시 전용. 이 루프가 끝난 뒤 사용자에게 권한다 | 보고에 "디자인 밖 차원은 범위 밖" |
| 기록 | Artifact 게시(보고서·점수판) | 다른 사람이 볼 결과 | 기본 비공개 | 마크다운 보고 |

## 쓰지 않는 것(이 하네스)

- 자체 브라우저를 띄우는 경로: accesslint 라이브 스캔, Lighthouse·lighthouse-ci, webapp-testing의 Python Playwright, impeccable live·URL detect, 스킬 본문의 Playwright·Chrome MCP 지시. 모두 aside·run-qa로 바꾼다.
- `superpowers:brainstorming`(루프의 질문 흐름과 중복), `clone-site-from-source`(리디자인 금지라고 스스로 적음), bkit mockup·design-system 단계(중복).
