# 설계 출처와 적용 범위

확인일: 2026-10-28 (Asia/Seoul). 아래는 기능을 비교하고 선택하기 위한 출처다. 원본의 설명·코드·프리셋을 이 패키지에 복제하지 않았다. 본 패키지의 지침과 검사 코드는 독립 작성했다. 실행 시점의 사용자 요구와 공식 자료가 아래 참고 사례보다 우선한다.

## 공개 스킬 검토

| 원 자료 | 확인한 범위 | 활용한 관점 | 이 스킬의 결정 |
|---|---|---|---|
| [MoAI IR](https://github.com/modu-ai/moai-cowork/blob/main/plugins/moai-accountant/skills/finance-investor-relations/SKILL.md) | 현행 SKILL 전문·관련 스킬 연결; 저장소 Apache-2.0 | 실적·가정 분리, 단계별 IR, 시장·재무·질문 | 실제 주장 원장·HOW·PPT 제작·렌더 검수까지 연결. 예시 12항목은 고정 장수가 아님 |
| [startup-pitch](https://github.com/ferdinandobons/startup-skill/tree/main/startup-pitch) | SKILL, pitch-frameworks, honesty-protocol, verification-agent, research-principles; MIT | 청중 조사, 시간별 이야기, 산출물 일관성 | 한국어 리허설·PREP·큐카드로 확장. BM 하나 강제, 약한 실적 은폐, 일괄 자료 유효기간은 적용하지 않음 |
| [YC-Pitch-Deck](https://github.com/sgatwork/YC-Pitch-Deck) | SKILL, 루트 content.md/design.md, MIT LICENSE | 결론형 제목, 핵심 근거, 실제 PPTX | 원 SKILL의 references/ 경로와 실제 루트 경로 차이를 확인. 스크린샷 금지·표지 수치 3개·창업자 2명·고정 카드 배치를 적용하지 않음 |
| [jameshemson/slides](https://github.com/jameshemson/slides) | build-deck, presentation-craft, composing-in-code, lint_pptx/check_fonts/raster 소스; MIT | 브랜드·장별 시각 설계·파일 검사·렌더와 수정 | 작은 독립 검사기만 제공. 브랜드 결정마다 승인, 특정 런타임·복잡한 스탬프 체계는 요구하지 않음 |
| [JetBrains slides](https://github.com/JetBrains/skills/blob/main/slides/SKILL.md) | SKILL과 slides_test; frontmatter Apache-2.0 | 편집 가능한 결과와 재생성 소스, 실제 렌더 확인 | 검사 가능한 항목과 육안 확인이 필요한 항목을 분리 |
| [Pitch Deck Advisor](https://github.com/amaklakov-droid/pitch-deck-skill/tree/main/pitch-deck-advisor) | SKILL·slide-guide·deep-tech·review-checklist; MIT | 증명한 기술과 다음 검증, 자금·성과 연결 | 특정 국가·프로젝트의 개인 선호, 고정 10~15장, 기업가치/회수전략 일괄 금지 미적용 |

라이선스 확인은 당시 공개 원문 기준이다. 추후 원본 일부를 직접 복사하거나 재배포한다면 해당 파일의 최신 조건과 고지 의무를 따로 확인하라. 본 스킬 사용을 위해 위 패키지를 전부 설치할 필요는 없다.

## 분석했지만 구현·지침을 차용하지 않은 자료

- [Anthropic pptx](https://github.com/anthropics/skills/tree/main/skills/pptx): 기능과 [별도 이용조건](https://github.com/anthropics/skills/blob/main/skills/pptx/LICENSE.txt)을 확인했다. Proprietary 지침·코드·검사기를 본 스킬에 포함하거나 파생 구현하지 않았다. 일반 PPT 기술은 아래 공식 형식·라이브러리 문서와 독립 구현을 사용한다.
- [정석biz seed-ir 안내](https://campiel.com/resources/seed-ir-deck/docs/advanced-guide.html): 공개 안내를 분석했다. 코드 패키지·GitHub·재배포 조건은 미확인이다. 14목차/최소18장·투자요청 제외는 해당 교육 범위이며 한국 IR 보편 규정이 아니다. 그 문구·구현을 복제하지 않았다.
- [Microsoft KoreaCopilotAgent 참고 스킬](https://github.com/microsoft/KoreaCopilotAgent/blob/main/templates/skill_deck-design-studio/SKILL.md): 한국어 설계 접근을 확인했지만 원문이 다른 core 스킬 유래 규칙을 포함하고 재사용 조건을 확정하지 못했다. 프리셋·문구·코드는 포함하지 않았다.

## 기술 1차 자료

- [PptxGenJS 문서](https://gitbrent.github.io/PptxGenJS/docs/usage/): 신규 슬라이드 제작 API를 실행 시 버전에 맞춰 확인하라.
- [Text](https://gitbrent.github.io/PptxGenJS/docs/api-text/), [Charts](https://gitbrent.github.io/PptxGenJS/docs/api-charts/): 텍스트·언어·차트 데이터와 축 설정을 확인하라.
- [python-pptx 문서](https://python-pptx.readthedocs.io/en/latest/): 읽기·생성·편집 범위와 보존 한계를 확인하라.
- [Microsoft PresentationML 구조](https://learn.microsoft.com/en-us/office/open-xml/presentation/structure-of-a-presentationml-document): 실제 슬라이드 순서·관계·마스터·테마가 별도 부분으로 구성됨을 확인하라. 파일명 순서를 발표 순서로 단정하지 마라.

국내 기관·공고·통계는 korean-context.md의 출처를 사용하라. 자료의 발행일·관측기간·적용 대상을 확인하고 과거 안내를 현재의 공통 규정으로 재사용하지 마라.
