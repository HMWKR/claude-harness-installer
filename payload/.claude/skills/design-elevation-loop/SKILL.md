---
name: design-elevation-loop
description: Runs an outer design-elevation loop for a web page or web app screen — asks how complete each quality dimension must be, locks the answers as criteria with a goal, researches competitors first when none exists, then repeats measure → improve → re-measure with tool measurements and blind judges until every locked criterion passes. Use when a site, landing page or web app UI must be redesigned, restyled or elevated AND kept improving to a bar — "디자인 고도화", "리디자인", "디자인 퀄리티·완성도 올려", "고급스럽게", "경쟁사 수준으로", "경쟁사처럼", "벤치마킹해서 개선", "기준 충족까지 반복", "redesign our landing page", "make it premium / award-level", "match competitors' design", "iterate until it meets the bar". Not for one small tweak (a button, a color), research or scoring alone, accessibility- or performance-only fixes, Figma or mockup-only work, native mobile apps, logos, non-visual QA or whole-project release checks.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/dloop.py *)
metadata:
  version: "1.2"
---

# 디자인 고도화 루프

사용자가 고른 완성도 기준을 잠그고, 측정과 판정이 그 기준을 넘을 때까지 개선 회차를 반복한다.

- **기준은 사용자가 고르고, 고른 뒤에는 잠근다.** 바꿀 때는 사용자 승인 원문을 받고 `compile --relock`으로 기록한다. 기준을 낮춰 통과시키는 것은 개선이 아니다.
- **점수는 실행 모델 밖에서 나온다.** dloop가 직접 돌린 측정 도구, 블라인드 판정단, 다른 벤더 판정석이 점수를 낸다. 고친 사람은 채점하지 않는다. 잠금 해시·출처·원 출력 지문은 실수와 지름길을 막는 장치이고, 의도적 위조까지 막는 보장은 최종 독립 검증이 한다.
- **모르는 것은 조사한다.** 경쟁사·레퍼런스 리서치가 없으면 리서치부터 한다. 결정에 필요한 사실은 공식 문서·웹 검색·크롤로 확인한 뒤 정한다. 조사로 알 수 있는 것은 사용자에게 묻지 않는다.

`D` = `python3 <이 스킬 폴더>/scripts/dloop.py`. 스킬 폴더는 이 문서 맨 위 "Base directory for this skill" 줄의 경로다. dloop 명령에는 늘 `--dir W`(측정 명령은 `--round N`까지)를 붙인다. 작업 폴더 W는 저장소에 `tasks/`가 있으면 `tasks/design-loop-<YYYY-MM-DD>/`, 없으면 `.design-loop/<YYYY-MM-DD>/`이다.

## 0. 흐름 — 압축 뒤에는 이 절만으로 이어 간다

- **재개**: `D resume --root <저장소 루트>`가 진행 중인 W를 찾는다. 날짜가 바뀌어도 그 폴더가 W다. 새 W는 사용자가 새 루프를 원할 때만 만든다(`init --new`). 이어서 최신 `rounds/rN/verdict.json`과 `gaps.md`를 본다. goal이 있으면 `cd W && python3 <goals.py> status`를 실행한다.

1. **착수**: 지침·디자인 문서를 읽는다. 브리프가 없으면 기준 질문 전에 만든다(8절). 그다음 `D init --dir W --root <저장소 루트> --url …`.
2. **기준 질문**: `D questions` 출력을 AskUserQuestion으로 그대로 묻는다. 순서는 범위 → 세부(또는 묶음) → 과정이다. 답은 `W/answers.json`에 쓴다.
3. **잠금·goal**: `D compile`을 실행하고 DoD를 요약해 보여 준 뒤, 고른 goal을 건다. goals.py는 매번 `cd W &&`로 부르고, 마지막 단계는 `D gate`로만 닫는다. 네이티브 /goal 문구를 줬다면 이번 턴을 끝낸다.
4. **리서치 게이트**: 비교 대상을 확보하고 `D lockset`을 실행한다.
5. **기준선 r0**: `D measure`, 봉인(`D seal`)과 판정단, 페르소나를 마친 뒤 `D check`.
6. **회차**: `gaps.md` → (리디자인이면 방향 단계) → 개선 → **새 rN+1 폴더**에 전부 다시 측정 → `D check`. check 출력은 응답에 그대로 붙인다.
7. **check 해석**:

   | 결과 | 다음 |
   |---|---|
   | 0 | 8로 |
   | 1 | 6으로 |
   | 2 | 측정 수단을 고친다 |
   | 3 | 멈추고 보고 |
   | `STALLED` | 접근을 바꾼다. 바꾼 뒤 같은 기준이 다시 STALLED면 묻는다 |
   | `ROUND_CAP` | 멈추고 묻는다. 답이 오기 전에는 relock하지 않는다 |
   | 엄격에서 `rg.final`만 남음 | 8의 검증으로 채운다 |

8. **최종 검증**: 실행 모델 밖에서 검증 → `D check` exit 0 → goal 마지막 checkpoint → 보고.

**하지 않는 것**: 미측정을 통과로 보기 · 승인과 relock 없이 기준·한도 바꾸기 · 같은 방법 반복 · 회차 기록 지우기·덮어쓰기 · 한도를 넘겨 계속하기 · 페르소나의 자연어 답을 증거로 쓰기 · 고친 사람이 점수 매기기.

## 1. 착수

- 프로젝트 지침(CLAUDE.md·AGENTS.md), 디자인 문서(DESIGN.md·PRODUCT.md·design-brief.md), 브랜드 금지 규칙을 읽는다. 금지 규칙(가짜 수치·고객 로고·인물 사진·로고 변형 등)은 어떤 기준보다 우선한다.
- 환경 규칙이 도구를 지정하면 그것을 따른다. 이 하네스의 지정은 전역 지침에 있다.
- `D init --dir W --root <저장소 루트> --url <대표 URL>`. 측정 도구와 기존 리서치를 `state.json`에 기록한다. 다른 진행 중 W가 있으면 거부한다(재개는 `resume`).

## 2. 기준 질문 — 기준에 관한 질문은 여기서 끝낸다

0. 사용자가 요청에서 이미 답한 항목(예: "프로덕션 수준이면 돼", "리서치는 예전 것 써", "goal 걸어줘")은 다시 묻지 않는다. 먼저 `W/answers.json`에 넣고, 이후 `questions` 호출에는 모두 `--answers W/answers.json`을 붙인다.
1. `D questions --dir W --set scope --answers W/answers.json`이 낸 JSON의 `questions`를 AskUserQuestion에 그대로 넘긴다. 항목은 대상 범위·변경 깊이·리서치·기준 설정 방식이다. `questions`가 비면 묻지 않는다.
2. 기준 설정 방식에 따라 이어서 묻는다.
   - 항목별 세부 선택: `--set quality1`(시각 완성도 / 타이포·색 / 이미지 / 모션·효과), `--set quality2`(반응형 / 접근성 / 성능 / 문구·신뢰). 선택지 미리보기에 누적 검사 항목이 보인다. 이 환경에서 잴 수 없는 수준은 설명에 표시된다.
   - 묶음으로 한 번에: `--set preset`
   - 권장값으로 진행: 이 단계는 건너뛴다.
3. 마지막으로 `--set process`를 묻는다. 경쟁 우위 목표·판정 엄격도·반복 한도(r0 포함)·goal 방식이다.
4. 답을 `W/answers.json`에 쓴다. 키는 질문 머리(header), 값은 고른 선택지 이름이다.
   `{"answers": {"대상 범위": "핵심 여정", …}, "targets": {"urls": […]}, "custom": [], "notes": ""}`
   - **기타(직접 입력)**: 가장 가까운 수준으로 옮기거나 `custom` 기준으로 넣는다. 원문을 `notes`에 남기고, 어떻게 해석했는지 사용자에게 한 줄로 알린다.
   - **서브에이전트로 돌 때**: 질문 페이로드를 호출자에게 돌려주고 멈춘다.
   - **`-p` 실행·무응답일 때**: 이 착수 질문에 한해 권장안을 가정하고 `notes`와 보고에 "가정: 권장안"을 적는다. 잠근 뒤의 결정은 가정하지 않는다(6절).
5. 범위에 맞는 실제 URL(라우트·사이트맵에서 찾음)을 `targets.urls`에 넣는다. 측정 폭은 반응형 수준이 정한다. 승인된 범위 안에서 나중에 새로 만드는 페이지는 만든 뒤 `compile --relock --reason "승인된 범위의 새 페이지: <범위 원문>"`으로 대상에 넣는다.
6. 리서치로 알 수 없는 사업 사실(전환 행동, 쓸 수 있는 실제 자료·제품 화면, 로고 원본)이 결과를 가르면 이 단계에서 한 번(최대 4문항) 묻는다. 톤·레이아웃·색처럼 리서치로 정할 수 있는 것은 묻지 않는다.

## 3. 잠금과 goal

- `D compile --dir W --answers W/answers.json`을 실행한다. 결과로 `criteria.lock.json`·해시·`DoD.md`와 잠금 이력 `locks/chain.jsonl`이 생긴다.
  - compile이 "참고"로 알리는 것은 사용자에게 한 줄로 전한다: 이 환경에 없는 검출기라 뺀 기준, 다른 도구로 원 출력을 만들어 `ingest`로 잴 출처, 다른 벤더 판정 도구가 없음(그러면 엄격도 "표준(동종)"을 권한다).
  - exit 4는 페르소나 기준이 있는데 엄격도가 "가볍게"일 때다. 엄격도를 올리거나 수준을 사용자와 다시 정한다.
- DoD 요약을 보여 준다: 차원별 수준, 핵심 임계값, 반복 한도.
- goal 방식별 동작:
  - **기록+멈춤 차단(권장)**: 아래 둘을 모두 한다.
  - **goals.py 기록만**: compile이 출력한 goals.py 명령을 모두 `cd W &&` 형태로 실행한다. 이것은 단계 기록과 재개용 장부이고 멈춤을 막지 않는다. 마지막 단계는 손으로 닫지 않고 `D gate --dir W --id <마지막 id>`로 닫는다. gate가 check를 직접 돌려 0일 때만 그 출력 원문을 붙여 checkpoint를 부른다. 저장소 루트에 있는 다른 계획은 건드리지 않는다.
  - **네이티브 /goal만**: compile이 출력한 `/goal …` 문구를 사용자에게 주고 이번 턴을 끝낸다. 모델은 /goal을 설정할 수 없다. 판정은 대화만 보는 작은 모델이 한다. 그래서 회차마다 `D check` 출력을 응답에 그대로 붙인다.
  - **goal 없이**: 완료 판정은 여전히 `D check` exit 0이다.
- 미달로 마무리하기로 사용자가 정하면, 남은 goal 단계를 `--status blocked --evidence "<사용자 결정 원문> + <check 출력>"`으로 닫는다. complete로 닫지 않는다.
- 기준·한도를 바꿔야 하면 사용자 승인 원문을 받고 `D compile --relock --reason "<원문>" [--round-cap N]`을 실행한다.
  - 이전 잠금은 `locks/`에, 판마다의 해시와 사유는 `locks/chain.jsonl`에 남는다. check는 잠금 해시와 다시 잠금 횟수를 매번 출력한다.
  - 대상이나 폭이 바뀌면 그 전에 잰 지표는 미측정이 된다. 다시 잰다.
  - 검출기 설정 기준선은 이어받는다. 새로 찍는 `--reset-guards`는 사용자 승인 시에만 쓴다.

## 4. 리서치 게이트와 수시 조사

- 기존 리서치를 재사용하기로 했으면 충분한지 넷으로 본다: 대상 수, 잠긴 폭의 캡처, 대응 페이지, 90일 이내. 0바이트 캡처와 템플릿 메모는 없는 것으로 친다. 빠진 것만 보강한다.
- 리서치가 없거나 새로 하기로 했으면 수행한다.
  - 후보는 프로젝트 문서와 웹 검색으로 찾는다. 직접 경쟁·인접·디자인 레퍼런스로 나눈다.
  - 공개 페이지만 같은 폭으로 수집하고 robots를 지킨다.
  - 종합한 뒤 적대 검수를 거친다. 절차는 [references/research.md](references/research.md).
- `W/research/comparison-set.json`(직접 경쟁만)을 쓰고, 기준선 전에 `D lockset`으로 잠근다. 결과를 보고 비교 대상을 바꾸지 못하게 하려는 것이다. 경쟁사 화면은 리서치 날짜의 캡처를 고정해 쓰고, 회차마다 새로 찍는 것은 우리 화면뿐이다.
- 작업 중 사실이 필요하면 언제든 조사하고, 출처를 `W/decision-log.md`에 남긴다.

## 5. 회차 절차 (r0 = 기준선)

1. **측정**: 잠긴 기준에 있는 것만 잰다. `D measure --round N --kind audit`, `--kind axe`, `--kind inspect`, `--kind detect --target <빌드된 HTML 폴더>`.
   - 회차는 차례로 잰다. r0부터, check로 판정한 회차의 다음 회차로만 넣을 수 있다. 건너뛰거나 지난 회차에 넣으면 거부된다.
   - dloop가 도구를 직접 돌려 원 출력과 지표를 만든다. 도구가 있는 환경에서 손으로 만든 원 출력은 인정하지 않는다.
   - 성능과 전송량은 배포용 빌드 미리보기(build + preview)에서 잰다. 개발 서버는 값이 부풀려진다.
   - 도구가 없는 환경은 원 출력을 `rounds/rN/` 아래에 두고 `D ingest`를 실행한다. 세부는 [references/measurement.md](references/measurement.md).
2. **판정단·페르소나**(인원은 DoD.md의 엄격도대로):
   - 자극은 같은 페이지·같은 폭으로 찍는다. 그림 형식을 통일하고 메타데이터를 지운 뒤, 무작위 라벨을 붙여 저장소 밖 임시 폴더에 둔다.
   - 라벨 대응표(경쟁사는 잠긴 목록과 같게, 기준점은 `ref:`)를 저장소 밖 파일로 쓰고, 판정자를 띄우기 **전에** `D seal --round N --key <그 파일>`로 봉인한다. 점수를 본 뒤 어느 자극이 우리인지 바꾸지 못하게 하려는 것이다.
   - 판정자는 회차마다 새로 띄운다. 쓰기 도구 없는 Claude 판정자와 다른 벤더 판정석은 모든 자극·축에 점수와 근거를 붙인 JSON을 응답으로 돌려주고, 메인이 원문 그대로 `judge-*.json`으로 저장한다. 빈칸이나 근거 없는 점수가 있으면 panel이 거부하므로 그 판정자에게서 다시 받는다.
   - 판정이 끝나면 봉인한 파일을 `rounds/rN/panel/key.json`으로 복사하고 `D panel`을 실행한다. 판정자 절반 이상이 회사를 알아봤거나 우리를 맞혔으면 점수 지표가 나오지 않는다. 자극을 다시 가려 새 판정자로 다시 판정한다.
   - 페르소나(결정권자·실사용자·시니어 디자이너)가 실제로 써 본다. 답 원문(NN/g 심각도 숫자 포함)을 `personas/<이름>.md`로, 이 회차에 나온 지적을 그대로 `findings.jsonl`로 옮긴 뒤 `D personas`를 실행한다. 고쳤는지는 다음 회차의 새 실행이 확인한다.
   - 형식과 프롬프트는 [references/evaluation.md](references/evaluation.md).
3. **수동 기준**: 이번 회차에 작업 폴더 안에 증거 파일을 만든 뒤 `D set --metric … --value … --evidence …`. 회차 시작 전에 만든 파일은 받지 않는다.
4. **예외**: 측정은 소스 안 예외 표식(`impeccable-disable` 등)과 저장소의 허용 목록을 따르지 않는다. 검출기 오탐은 `W/exceptions.json`에만 적는다.
   - 결함 하나(`detect`: 규칙·파일·줄)는 사유와 증거를 적는다.
   - 규칙 전체(`allow`)나 검출기 설정 변경(`config`)은 사용자 승인 원문까지 적는다.
   - check가 적용된 예외를 매번 출력한다.
5. **판정**: `D check`. 엄격에서 `rg.final`만 남으면 7절 검증을 해서 `rigor.final_ok`를 기록하고 다시 돌린다.
6. **r0가 이미 통과**: 사실을 보고하고 기준 상향(relock)이나 종료를 묻는다. 리디자인 깊이면 잠긴 기준을 회귀 하한으로 두고 방향 단계로 간다.
7. **격차 → 개선**: `rounds/rN/gaps.md`를 쓴다.
   - 담을 것: FAIL·미측정 기준, 페르소나 High, 판정 근거, 측정 표본(예: LCP 요소), 이전 회차에 쓴 접근.
   - 원인을 확인한 뒤 접근을 정하고, 접근마다 맞는 동반 스킬(9절)을 부른다.
   - 디자인 결정은 리서치 근거와 기각안을 남긴다. 다듬기 깊이면 구조·문구를 바꾸지 않는다.
   - 막힌 기준(사업 사실·도구 없음)은 gaps.md에 표시하고 나머지는 계속한다.
8. **다음 회차**: 새 rN+1에 전부 다시 측정한다. 이미 판정한 회차에는 측정이 거부된다. 측정 오류를 고치는 재측정일 때만 `--fix-reason`을 쓴다.

## 6. 멈춤 규칙

| check 출력 | 할 일 |
|---|---|
| exit 0 | 루프를 끝내고 최종 검증으로 간다 |
| `STALLED <기준>` | 같은 방법을 반복하지 않는다. 원인을 다시 확인하고 접근을 바꾼다(다른 기법, 추가 리서치, 구조 변경). 바꾼 뒤 같은 기준이 다시 STALLED면 사용자에게 묻는다 |
| `ROUND_CAP` | 멈추고 AskUserQuestion으로 묻는다: 한도 늘리기 / 기준 조정 / 현재 상태로 마무리(미달 항목 명시). 답이 오기 전에는 relock하지 않는다. 무응답·서브에이전트면 "결정 대기"를 기록하고 멈춘다 |
| 미측정이 계속됨 | 측정 수단을 고친다. 고칠 수 없으면(도구 없음·접근 차단) 사유를 들어 묻는다 |
| exit 3 | 작업을 멈추고 무엇이 바뀌었는지 보고한다(잠금 변조·한도 초과·비교 대상 미잠금·판정 차례가 아닌 회차) |

사업 사실(법인 정보, 실제 고객, 파트너 승인)이 있어야 풀리는 기준은 지어내지 않는다. 막힘으로 보고한다.

## 7. 최종 검증과 보고

- 엄격도 표대로 실행 모델 밖에서 검증한다(가볍게 1석, 표준 이상은 쓰기 도구 없는 Claude 검증자 + 다른 벤더).
- 확인 항목:
  - 수동 기준의 증거
  - `exceptions.json`의 사유
  - 페르소나 원문과 findings 대조
  - 판정단 블라인드 여부(`panel.blind_breaches`)
  - check 출력의 잠금 해시·다시 잠금 사유, 적용된 예외
  - 측정 지표 1~2개 재측정 대조
  - 잠금 무결성
- goal 장부를 쓰면 마지막 단계를 `D gate --dir W --id <id>`로 닫는다. check가 0일 때만 닫힌다. 통과한 check는 "all locked criteria passed"를 출력한다.
- 기준을 충족하면 루프는 끝난다. 시각 결과를 받아들일지는 사용자가 정하므로, 캡처 경로를 붙여 확인을 요청한다.
- 보고에는 한 일, 안 한 일·남은 빈칸, 가정, 미검증을 나눠 적는다. 기준별 최종값, 경쟁사 대비 점수표("블라인드 AI 판정단 기준"), 회차별 추이, 남은 결함을 포함하고 프로젝트 문서를 갱신한다.

## 8. 방향 단계 — 리디자인·디자인 시스템 깊이(r1 전)

- 브리프 → 시안 2~3안 → 판정단과 리서치 근거로 선택 → `decision-log.md`에 기각안을 기록한다. 사용자에게는 고른 결과와 이유만 보고한다(개별 시안 선택은 묻지 않는다).
- 브리프가 없으면 `jusan-harness:design-intent-lock`(있으면)으로 빈 축만 채운다. 없으면 8축(목적·대상·톤·레이아웃·필수 요소·제약·레퍼런스·성공 기준)을 직접 쓴다.
- 시안은 이 하네스의 Claude Design 캔버스로 만든다. 시안은 방향 결정용이고, 완료 증거는 구현된 페이지의 측정이다.

## 9. 동반 스킬 — 단계별로 부른다

있는 스킬만 부른다. 없으면 [references/companions.md](references/companions.md)의 대체 수단을 쓴다. 바깥 루프는 이 스킬 하나이고, 다른 스킬 안의 짧은 반복은 회차마다 한 번만 부른다.

- **리서치**: **Refero MCP + `refero-design` 먼저**(사용자 결제 — 유일한 허용 유료) · `aside-browser`(크롤·캡처) · `clone-site-from-source` · `motiscope-analyze`(경쟁사 모션 녹화) · `jusan-harness:domain-researcher` 또는 `anthropic-skills:deep-research`
- **방향**: 마케팅 페이지면 `design-taste-frontend`, 앱 화면이면 `frontend-design:frontend-design`(둘 중 하나만)
- **구현**: `emil-design-eng`(구체 질문을 인자로) · `animate` · `motion`(무료 문서) · `apple-design` · `mobile-native` · `threeui-reference`(3D일 때만) · `dataviz` · `cross-vendor`(codex 이미지)
- **게이트**: `impeccable` `critique`·`audit`·`polish` + 대상 인자 · `improve-animations` · `find-animation-opportunities` · `animation-performance` · `break-ui`
- **판정**: `cross-vendor`(codex 판정석) · `amplify-presets` · critic 에이전트
- **완료**: `fablize:fablize`. 디자인 밖 전 차원 출시 판정은 사용자에게 `/project-quality-loop`을 권한다.
