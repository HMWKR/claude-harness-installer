# 근거 원장과 검사 계약

명령의 `IR_SKILL_DIR`와 `IR_PROJECT_DIR`는 [claude-runtime.md](claude-runtime.md)에 따라 실제로 확인한 스킬 폴더와 작업 폴더의 절대 경로로 먼저 설정한다. 기본 제공 환경변수라고 가정하지 않는다.

전체 덱 제작에는 `ir-plan.json` 하나로 주장·장표·규정을 연결하라. 에이전트가 읽은 자료에서 작성하라. 사용자에게 JSON을 요구하지 마라. 작은 수정/검토에는 전체 원장을 강제하지 마라.

## 최소 형태

```json
{
  "schema_version": 1,
  "brief": {
    "project": "회사명",
    "purpose": "fundraising",
    "consumption": "live",
    "stage": "MVP 시험",
    "language": "ko-KR",
    "as_of": "2026-10-28",
    "duration_seconds": 300,
    "reserve_seconds": 20,
    "max_slides": null
  },
  "sources": [
    {"id":"E1", "reference":"제공자료/사용기록.xlsx", "locator":"시트1 B2:B4", "status":"inspected", "accessed_on":"2026-10-28"}
  ],
  "claims": [
    {"id":"C1", "statement":"무료 파일럿 3개사", "kind":"fact", "source_ids":["E1"], "value":3, "unit":"기업", "period":"2026-10", "scope":"중복 제거한 무료 시험 고객사"}
  ],
  "requirements": [],
  "slides": [
    {"id":"S1", "title":"무료 시험에서 사용 흐름을 확인했습니다", "takeaway":"현재 증거는 무료 파일럿 범위다", "visual":"실제 흐름과 관찰 조건", "claim_ids":["C1"], "requirement_ids":[], "seconds":30, "notes":"기록과 확인 한계를 설명한다."}
  ]
}
```

위 수치는 형식 설명용이다. 실제 회사 실적으로 사용하지 마라. `duration_seconds`는 발표 본문 시간이며 별도 Q&A를 더하지 마라. 각 장의 `seconds`에 그 장의 데모·멈춤을 포함하고 `reserve_seconds`는 전체 전환·여유로 두어 이중 계산하지 마라. 읽기용은 `consumption: read`, 시간은 null로 두어라.

## 필드 의미

| 필드 | 규칙 |
|---|---|
| `purpose` | fundraising / demo-day / program / partnership. 기관·공고명은 추가 필드로 기록 |
| `consumption` | live / read. 둘 다 필요하면 같은 source/claim ID를 공유한 별도 원장으로 관리 |
| `as_of` | 사업 자료 기준일. 생성일과 다르면 구분 |
| `max_slides` | 실제 제한을 알 때 양의 정수. 이 파일로 내보내는 전체 장수 기준. 부록 제외 제한이면 별도 부록 파일을 만들거나 직접 적용 범위 대조 |
| `sources[].reference/locator` | 실제 URL·파일·사용자 진술 위치와 페이지·셀·문단 |
| `sources[].status` | inspected / unread. 검색 제목만 보고 원문을 읽었다고 쓰지 말 것 |
| `claims[].kind` | fact / reported / derived / forecast / hypothesis / missing |
| `value/unit/period/scope` | 핵심 수치의 값·단위·기간·대상. value는 유한 숫자 |
| `qualification` | reported/forecast/hypothesis/missing의 한정 문구. 실제 장표·노트에도 혼동 없이 반영 |
| `requirements` | id, text, required, source_id, weight. 공개 배점 없으면 null. 자체 기준을 공식 규정으로 표현하지 말 것 |
| `slides[].claim_ids` | 이 장의 핵심 주장·숫자·차트가 쓰는 claim ID |
| `slides[].requirement_ids` | 실질적으로 답하는 요구 ID. 제목만 넣고 충족으로 판단하지 말 것 |
| `slides[].seconds` | live일 때 0 이상 유한 숫자. 합계 확인은 실제 낭독 측정이 아님 |

reported는 제공된 진술이지 독립 확인된 관측이 아니다. fact도 출처가 존재한다는 이유만으로 자동 참이 되지 않는다. 출처가 지지하는 범위와 해석을 직접 검토하라.

## 수치 재계산

derived 수치에는 입력 claim과 산식을 연결하라.

```json
{"id":"C3", "statement":"연간 시장 추정", "kind":"derived", "source_ids":[],
 "value":24000000, "unit":"원/년", "period":"2026 추정", "scope":"가정된 고객군",
 "calculation":{"op":"product", "inputs":["C1","C2"]},
 "qualification":"고객 수와 단가에 따른 추정치"}
```

지원 연산은 sum / difference / product / ratio / percent_change다. 입력 A,B에 대해 difference=A-B, ratio=A/B, percent_change=(B-A)/A*100이다. inputs는 다른 claim ID다. 가정·전망 입력을 포함한 결과를 실적으로 바꾸지 마라.

복잡한 모델은 `calculation: {"op":"external", "reference":"모델.xlsx/시트/셀", "checked":true}`로 연결하라. 직접 재계산했을 때만 checked를 true로 기록하라. helper가 외부 계산을 검증하는 것은 아니다. 환율·단위변환·계수에도 정의와 근거를 남겨라.

## 검수 기록

`review.json`을 원장과 분리하라. 해시는 검수한 실제 최종 파일에서 계산하라.

```json
{
  "plan_sha256": "실제 원장 SHA256",
  "pptx_sha256": "실제 최종 PPTX SHA256",
  "checks": {
    "evidence": {"status":"pass","note":"원문 대조 범위"},
    "numbers": {"status":"pass","note":"계산·단위 대조 범위"},
    "requirements": {"status":"not_applicable","note":"지정 공고 없음"},
    "story": {"status":"pass","note":"제목과 HOW 흐름 확인"},
    "structure": {"status":"pass","note":"최종 pptx_audit 실행"},
    "visual": {"status":"pass","note":"최종 렌더 모든 장 확인"},
    "timing": {"status":"pass","note":"시간배분 확인; 실제 리허설 미실시"}
  },
  "renders": [
    {"slide_id":"S1","path":"renders/slide-1.png","sha256":"실제 PNG SHA256","reviewed":true}
  ]
}
```

상태는 pass / fail / not_run / not_applicable이다. 해당 없음은 이유를 적어라. 전체 PPTX 전달 준비 검사에서 evidence/story/structure/visual은 생략할 수 없다. 사용한 수치 주장이나 그 계산 입력이 있으면 numbers, 필수 요구사항이 있으면 requirements, 발표용이면 timing도 pass여야 한다. 해당 대상이 실제로 없을 때만 not_applicable을 허용하라. 경로는 review.json 기준 상대 경로 또는 절대 경로다. 실제 보기 전에 reviewed:true를 채우지 마라.

```bash
python3 "$IR_SKILL_DIR/scripts/ir_audit.py" --plan "$IR_PROJECT_DIR/ir-plan.json" --pptx "$IR_PROJECT_DIR/ir.pptx" --review "$IR_PROJECT_DIR/review.json" --release --out "$IR_PROJECT_DIR/release-audit.json"
```

이 검사는 원장·수치·연결·해시·기록의 완결성을 확인한다. 발표 품질·사실의 진실성·심사 통과를 인증하지 않는다. 자료/렌더 부족 시 유용한 초안을 전달하되 부족한 검사를 남겨라. 통과시키려고 기준이나 사실 분류를 낮추지 마라.
