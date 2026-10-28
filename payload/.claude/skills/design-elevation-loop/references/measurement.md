# 측정 — 지표를 만드는 법

지표는 일곱 출처에서 나온다. 손으로 숫자를 옮기지 않는다. 측정 도구는 dloop가 직접 돌리고(`measure`), 판정단·페르소나는 원 파일에서 계산하며(`panel`·`personas`), 수동 기준만 증거 파일과 함께 `set`으로 기록한다.

| 출처 | 만드는 지표 | 원 출력 | 명령 |
|---|---|---|---|
| audit | 넘침·대비·글자·누를 크기·그림·모션 규칙·구조·문구·LCP·CLS·전송량 | `rounds/rN/audit/<페이지>@<폭>.json` | `D measure --kind audit` |
| axe | `axe.serious_critical`·`axe.violations`·`axe.incomplete` | `rounds/rN/qa/<페이지>/measure-*.txt` | `D measure --kind axe` |
| inspect | `inspect.fail`(예외로 뺀 수는 `inspect.excepted`) | `rounds/rN/inspect/<페이지>.json` | `D measure --kind inspect` |
| detect | `detect.count`(예외로 뺀 수는 `detect.excepted`) | `rounds/rN/detect/detect.json`·`scope.json` | `D measure --kind detect --target <빌드 폴더>` |
| manual | `*_ok` 참·거짓 | 작업 폴더 안 증거 파일 | `D set` |
| panel | `panel.*` | `rounds/rN/panel/` | `D seal` → 판정 → `D panel` |
| persona | `persona.*` | `rounds/rN/personas/` | `D personas` |

회차는 차례로 잰다. r0부터, check로 판정한 회차의 다음 회차로만 기록할 수 있고, 반복 한도를 넘는 회차는 거부된다. 판정한 회차를 다시 재는 것은 측정 오류를 고칠 때뿐이다(`--fix-reason`, 옛 판정은 `verdict.<시각>.json`으로 보존).

`D check`가 지표마다 확인하는 것은 여섯 가지다. 하나라도 어긋나면 그 기준은 미측정이다.
- 출처가 기준과 맞는가
- 이 회차의 값인가
- 지금 잠금의 대상·폭으로 잰 값인가(다시 잠가 대상이 바뀌면 옛 값은 미측정)
- 집계한 뒤 원 출력이 바뀌지 않았는가(지문)
- 이 환경에 도구가 있다면 이 회차에 dloop가 직접 잰 값인가
- 수동 증거가 기록 뒤에 바뀌지 않았는가

다시 측정하면 그 출처의 지표는 통째로 바뀐다. 대상 URL × 폭이 하나라도 빠지면 그 출처의 지표는 만들어지지 않는다.

## 1. audit — page-audit.js

`D measure --round N --kind audit`은 대상 URL × 잠긴 폭마다 다음을 한다.
- 대상 페이지를 열고, 같은 출처 iframe을 그 폭으로 만들어 `scripts/page-audit.js`를 실행한다(이 하네스는 `aside repl`).
- 결과의 `width`가 요청한 폭과 정확히 같은지 확인한다.
- 원 출력을 저장하고 지표로 묶는다. 결과 주소의 `r` 쿼리가 다른 회차를 가리키면 받지 않는다.
- 대상이 200을 돌려주지 않거나 iframe을 막으면(`X-Frame-Options`·`frame-ancestors`) 멈추고 알린다. 막지 않는 로컬 빌드를 띄운다.

결과에는 지표 말고도 `samples`가 있다: 대비가 낮은 글자, 작은 누를 것, 글자 크기 목록, 잘려 숨겨진 넘침 요소, **LCP 요소**(태그·클래스·글자·그림 주소), 서버 응답 시간. 격차를 고칠 때는 이 표본으로 원인을 확인한다. 예컨대 LCP 요소가 문단인데 이미지를 압축하는 일은 하지 않는다.

**다른 환경**: 그 환경의 브라우저 도구로 페이지를 그 폭으로 열고 `page-audit.js` 내용을 evaluate에 넘긴다(Playwright류는 `page.setViewportSize` 뒤 `page.evaluate(src)`). 결과를 `rounds/rN/audit/<페이지>@<폭>.json`에 두고 `D ingest --kind audit`을 실행한다.

**측정 정의와 한계**(page-audit 주석과 같다):
- 넘침: 문서 폭 넘침(scrollWidth − clientWidth)에 더해, 루트(html·body)가 잘라 숨긴 내용(글자·그림, 또는 화면보다 넓은 요소)이 화면 밖으로 나간 양을 센다. 화면 밖에 통째로 둔 것(숨김 패턴), position fixed, aria-hidden·inert, 안쪽 스크롤 상자 안의 것은 세지 않는다.
- 대비: 배경을 불투명해질 때까지 쌓아 계산한다. 그림·그라디언트·투명도·필터·혼합 모드가 끼면 계산하지 않고 `contrast.unknown_bg`로 센다. 그 글자들은 수동 기준 `contrast.unknown_ok`로 캡처를 보고 확인한다.
- 큰 글자: 24px 이상, 또는 굵은 14pt(18.67px) 이상.
- 본문: 40자 이상인 p·li·dd·blockquote·figcaption, 그리고 직접 글자가 40자 이상인 모든 요소(div·span·td 등)의 글자. 제목(h1~h6)은 뺀다. 줄 길이(em)는 두 줄 이상으로 접힌 문단의 내용 폭을 글자 크기로 나눈 값이다.
- 누를 크기: 24×24px 미만을 센다. 문장 속 링크만 예외로 둔다. WCAG의 간격 예외는 적용하지 않는 보수적 자체 규칙이다.
- 모션: 레이아웃 애니메이션은 키프레임이 폭·높이·위치·여백을 바꾸거나, 시간이 0보다 긴 전이가 그 속성(또는 all)에 걸린 요소다. 변형(transform)·투명도만 쓰는 것은 세지 않는다. 다른 출처 시트의 키프레임은 읽지 못한다(`css.unreadable_sheets`).
- 감속·초점 규칙: `prefers-reduced-motion` 규칙은 안에 실제 선언이 있어야, `:focus` 규칙은 보이는 표시(outline·box-shadow·테두리·배경·글자색·밑줄)를 줘야 센다. 빈 규칙과 `outline: none`만 있는 규칙은 세지 않는다. 다른 출처 시트를 못 읽었는데 규칙을 못 찾았으면 '모름'(값 없음)이다.
- LCP·CLS: 지원할 때만 잰다. 새 항목이 1초 멈출 때까지(최대 4초) 모은다. 로컬 측정이라 실제 사용자 값보다 낙관적이다.
- 전송량: 압축 본문 크기 기준이다. 크기를 알 수 없는 다른 출처 자원이 있으면 값이 없다(미측정). 이 경우 빌드 산출물 크기로 따로 확인하고 수동 기준으로 바꿀지 사용자와 정한다.

**착시 주의**(실제로 겪은 것들):
- 캡처 색은 디스플레이 색 공간(Display P3 등)에 따라 달라 보인다. 색 판정은 계산된 CSS 값으로 한다.
- 스크롤바와 기기 배율(DPR)이 레이아웃 폭과 캡처를 바꾼다. 캡처할 때는 스크롤바를 숨기고 배율을 확인한다.
- 같은 주소는 캐시된다. dloop는 회차 번호를 `?r=N`으로 붙인다.
- 쿠키 동의 배너가 내용을 가리면 그 요소만 숨기고 기록한다.

## 2. axe — run-qa.sh(이 하네스)

`D measure --kind axe`가 페이지마다 `run-qa.sh <URL> rounds/rN/qa/<페이지> r<N>`을 돌리고 출력을 `stdout.txt`에 남긴다.
- 종료 코드: 0 완전·위반 0, 1 불완전(통과 아님), 2 위반 있음, 3 수동 확인 필요.
- 4조합(dark·light × 창 폭·375) 중 하나라도 오류면 그 페이지는 미측정이다.
- CSP가 외부 스크립트를 막으면 axe가 로드되지 않는다(`AXE_LOAD_ERROR`). CSP를 끈 로컬 빌드에서 재거나 막혔다고 보고한다.
- VITALS의 경로(route)만으로 페이지를 맞춘다. 출처(호스트)가 다른 같은 경로는 구분하지 못하는 한계가 있다.

**다른 환경**: axe-core를 페이지에 주입해 네 조합을 재고, 페이지마다 `rounds/rN/qa/<페이지>/measure-rN.txt`에 다음 줄을 남긴 뒤 `D ingest --kind axe`를 실행한다. `violations`·`incomplete`는 axe-core 결과의 배열 그대로이고, `impact`가 serious·critical이면 심각으로 센다.

```
VITALS {"route": "/경로", "status": 200}
AXE {"dark_window": {"violations": [{"id": "color-contrast", "impact": "serious"}], "incomplete": []}}
AXE {"dark_375": {"violations": [], "incomplete": []}}
AXE {"light_window": {"violations": [], "incomplete": []}}
AXE {"light_375": {"violations": [], "incomplete": []}}
```

## 3. inspect.mjs — 마케팅 페이지 하우스 규칙(design-taste-frontend v2)

`D measure --kind inspect`의 동작:
- 로컬 주소만 받는다. 실행 전에 200인지 확인한다(inspect는 404 페이지도 그대로 검사한다).
- 회차의 inspect 폴더(중립 폴더)에서 `--widths 1280,375 --json`으로 돌린다. inspect는 실행 폴더의 `.taste-skill/direction.json` 허용 목록에 든 결함을 보고서에서 아예 지우므로, 저장소에서 돌리지 않는다.

보고서는 다음 조건을 모두 채워야 지표로 쓴다.
- 회차 시작 뒤, 지금 앞의 시각이다. inspect는 크래시해도 옛 보고서를 남긴다.
- 데스크톱(≥1100)과 모바일(≤480) 폭을 둘 다 쟀다.
- 대상 URL과 하나씩 맞는다.

허용 규칙은 `exceptions.json`의 `allow` 항목(사유·증거·사용자 승인 원문)으로만 적용한다. 예외로 뺀 FAIL은 `inspect.excepted`로 따로 센다. 정지 시안(캔버스)에는 모션 규칙(still-page)을 적용하지 않는다. 구현된 페이지에만 적용한다.

## 4. impeccable detect

`D measure --kind detect --target <빌드된 HTML 폴더>`가 impeccable 실행기(스킬의 `scripts/impeccable`, 없으면 엔진)를 저장소 루트에서 `--json --no-advisory --no-inline-ignores`로 돌린다. 소스 안 `impeccable-disable` 표식은 따르지 않는다. 검사한 HTML 수·종료 코드·플래그를 `scope.json`에 남긴다. 다음이면 미측정이다: HTML이 대상 페이지 수보다 적다, 종료 코드가 0·2가 아니다, `--no-inline-ignores`(또는 `--no-config`) 없이 돌린 결과다. CSS·JSX만 넣으면 대부분 놓친다.

프로젝트 설정(`.impeccable/config*.json`)과 디자인 맥락(`DESIGN.md`·`.impeccable/design.json`)은 그대로 쓴다. 설정 파일은 잠글 때의 해시와 비교한다(5절). DESIGN.md를 고쳐도 검출 결과가 바뀔 수 있으니, 최종 검증자는 `--no-config`로 한 번 더 돌려 차이를 본다.

## 5. 예외 — exceptions.json

결함을 빼는 길은 이 파일 하나다. 항목마다 사유(`reason`)와 작업 폴더·저장소 안의 증거 파일(`evidence`)이 있어야 하고, 규칙 전체를 끄는 항목은 사용자 승인 원문(`approval`)까지 있어야 한다. 조건을 못 채운 항목은 무시되고 check가 "예외 무시"로 알린다.

```json
[
  {"kind": "detect", "antipattern": "low-contrast", "file": "dist/index.html", "line": 42, "reason": "그라디언트 위 글자 — 실측 7.1:1", "evidence": "rounds/r2/contrast-check.md"},
  {"kind": "allow", "rule": "still-page", "reason": "정지 시안 단계", "evidence": "approvals/still-page.md", "approval": "사용자: '시안 단계는 모션 규칙 빼도 돼'"},
  {"kind": "config", "file": ".impeccable/config.json", "reason": "…", "evidence": "…", "approval": "사용자: '…'"}
]
```

| 종류 | 빼는 것 | 필수 |
|---|---|---|
| detect | detect 결함 하나(규칙 + 파일 경로 일부 + 선택한 줄) | reason·evidence |
| allow | inspect 규칙 전체 | reason·evidence·approval |
| config | 잠근 뒤 바뀐 검출기 설정 파일(`.impeccable/config.json`·`config.local.json`·`design.json`) | reason·evidence·approval |

설정 파일이 잠근 뒤 바뀌었는데 config 항목이 없으면 `guard.<파일>` FAIL이다. check는 적용된 예외를 매번 출력하고 verdict.json에 남긴다. 검출기 오탐은 가장 좁게(결함 하나) 뺀다. 최종 검증자는 예외마다 근거를 다시 본다.

## 6. 수동 기준의 증거

수동 기준은 `D set --metric <id> --value true --evidence <파일>`로 기록한다. 증거는 작업 폴더 안의 비어 있지 않은 파일이어야 하고, 이번 회차가 시작된 뒤에 만들거나 고친 파일이어야 한다. 기록할 때의 해시와 판정할 때의 해시가 다르면 미측정이 된다. 최종 검증자가 다시 본다.

| 지표 | 증거로 남길 것 |
|---|---|
| `contrast.unknown_ok` | 측정 불가로 잡힌 글자(audit `contrast.unknown_bg`)마다 캡처와 확인한 대비. 0개면 그 audit 결과 파일 |
| `a11y.keyboard_ok` | Tab 순서대로 초점이 간 요소, 초점 표시가 보였는지, 핵심 행동을 키보드만으로 끝냈는지(단계별 기록, 상태 캡처) |
| `resp.zoom200_ok` | 200% 확대 상태의 캡처(1280 창 = 640 CSS px 폭)에서 잘림·겹침이 없는지 |
| `resp.text_spacing_ok` | WCAG 1.4.12 값(줄 간격 1.5, 문단 간격 2, 자간 0.12, 단어 간격 0.16em)을 주입한 뒤의 캡처와 넘침 값 |
| `a11y.checklist_ok` | WCAG 2.2 AA 점검표: 기준마다 통과·해당 없음과 근거 |
| `a11y.screenreader_ok` | 스크린리더로 핵심 여정을 진행한 기록: 읽힌 이름·역할·상태. 모델이 할 수 없으면 사용자에게 요청한다 |
| `a11y.focus_appearance_ok` | 초점 표시의 크기·대비(WCAG 2.4.13)를 잰 캡처와 값 |
| `motion.pause_ok` | 5초 넘게 스스로 움직이는 요소 목록과 정지 수단. 없으면 "해당 요소 없음"과 확인 방법 |
| `motion.tokens_ok` | 시간·이징 값의 정의 위치와, 다른 곳에 하드코딩이 없다는 검색 결과 |
| `motion.audit_ok` | 모션 감사 보고서(High 0) |
| `motion.signature_ok` | 상호작용 녹화(Remotion이나 프레임 캡처)와 감속 모드의 대체 표현 |
| `img.custom_ok` | 핵심 절마다 쓴 그래픽 목록과 출처(자체 제작·생성 기록·제품 화면) |
| `img.ai_tell_ok` | 생성 그림 점검표 결과(글자 깨짐·손·과한 광택·무의미한 장식)와 검증자 확인 |
| `content.claims_ok` | 숫자·고객·순위·후기 표현 검색 결과와, 각 표현의 근거 또는 삭제 기록 |
| `rigor.final_ok` | 최종 독립 검증 2인 보고서 |
