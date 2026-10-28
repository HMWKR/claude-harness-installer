# 증거와 보고서 스키마

## 1. 품질 작업공간

```text
.claude/quality/
├── manifest.md
├── test-matrix.md
├── findings.jsonl
├── decision-log.md
├── final-report.md
├── project-detection.json
└── evidence/
    └── <run-id>/
        ├── environment.json
        ├── commands.log
        ├── screenshots/
        ├── snapshots/
        ├── network/
        ├── console/
        ├── traces/
        ├── outputs/
        └── diffs/
```

`run-id`는 날짜·시간 또는 `${CLAUDE_SESSION_ID}`처럼 충돌하지 않는 값을 사용한다.

## 2. Finding JSONL 스키마

각 줄은 독립된 JSON 객체다.

```json
{
  "id": "WEB-A11Y-001",
  "title": "모바일 결제 버튼의 접근성 이름 누락",
  "domain": "accessibility",
  "severity": "Critical",
  "confidence": "HIGH",
  "status": "OPEN",
  "requirement": ["REQ-CHECKOUT-003"],
  "environment": {
    "platform": "web",
    "browser": "webkit",
    "viewport": "393x852",
    "route": "/checkout",
    "commit": "<sha>"
  },
  "reproduction": [
    "결제 페이지를 연다",
    "배송지를 입력한다",
    "화면 하단 CTA로 이동한다"
  ],
  "expected": "버튼이 접근성 트리에서 '결제하기'로 인식되고 클릭 가능해야 한다.",
  "actual": "버튼 이름이 비어 있고 하단 내비게이션에 일부 가려진다.",
  "evidence": [
    ".claude/quality/evidence/<run-id>/screenshots/checkout-mobile.png",
    ".claude/quality/evidence/<run-id>/snapshots/checkout-aria.yml"
  ],
  "rootCause": "아이콘 전용 버튼에 aria-label이 없고 고정 하단 높이를 계산하지 않았다.",
  "remediation": "접근성 이름을 제공하고 safe-area 및 하단 내비게이션 높이를 포함한 여백을 적용한다.",
  "verification": {
    "method": "모바일 WebKit 재실행 + 키보드/접근성 스냅샷",
    "result": "PENDING"
  },
  "residualRisk": "다른 언어에서 버튼명이 누락될 가능성"
}
```

## 3. 증거 품질 기준

좋은 증거는 다음 질문에 답한다.

- 언제, 어디서, 어떤 버전에서 발생했는가?
- 어떤 입력과 행동으로 재현되는가?
- 예상과 실제 차이는 무엇인가?
- 결론을 다시 확인할 수 있는가?
- 수정 전후가 같은 조건인가?

### 권장 증거

- 명령과 종료 코드가 포함된 로그
- 테스트 이름과 실패 메시지
- 파일 경로와 줄 번호
- 전후 스크린샷과 diff
- DOM·접근성·상태 snapshot
- API 요청·응답과 상태 코드
- trace와 timing
- 출력 파일과 해시
- 실제 렌더링 또는 재생 확인

### 피해야 할 증거

- "보기에 괜찮다" 같은 인상만 기록
- 재현 절차 없는 스크린샷
- 환경과 버전을 알 수 없는 로그
- AI의 결론만 있고 원본 결과가 없음
- 수정 전후 조건이 다른 비교
- 비밀·토큰·개인정보가 포함된 원본 로그

## 4. Decision Log 스키마

```markdown
## DEC-001 — 테스트 DB를 로컬 컨테이너로 사용

- 날짜/Run: 2026-07-28 / <run-id>
- 상태: Accepted
- 배경: 기존 테스트 DB 접속 정보가 없고 로컬 Docker 구성이 존재함
- 선택: 로컬 컨테이너를 사용해 통합 테스트 수행
- 대안: mock만 사용 / 외부 테스트 DB 요청
- 근거: 실제 트랜잭션과 마이그레이션 검증이 필요함
- 영향: 운영 환경 특유의 설정 차이는 별도 caveat로 남음
- 되돌림: 컨테이너와 생성 데이터 삭제
```

가정, 기준 변경, 범위 확대·축소, 테스트 생략, 위험 수용은 반드시 기록한다.

## 5. Test Matrix 스키마

```markdown
| ID | 요구사항 | 사용자/환경 | 시나리오 | 검사 계층 | 예상 결과 | 증거 | 상태 |
|---|---|---|---|---|---|---|---|
| TEST-001 | REQ-LOGIN-001 | 일반 사용자 / Mobile WebKit | 올바른 계정으로 로그인 | E2E + Network + Storage | 대시보드 이동, 세션 생성, 오류 0건 | evidence/... | PASS |
```

상태 값:

- `PASS`
- `FAIL`
- `BLOCKED`
- `NOT_RUN`
- `N/A`

## 6. Final Report 구조

```markdown
# Final Verification Report

## 1. 최종 판정
GO | GO_WITH_CAVEATS | NO_GO | BLOCKED

## 2. 실행 요약
- 모드:
- 범위:
- 프로젝트 유형:
- 위험 등급:
- Run ID:
- 기준 commit:

## 3. 목표 및 요구사항 추적
| 요구사항 | 구현 | 테스트 | 증거 | 결과 |

## 4. 적용한 검수 모듈
| 모듈 | 적용 여부 | 결과 | 비고 |

## 5. 수정 사항
| 변경 | 파일 | 이유 | 검증 |

## 6. 테스트와 실제 시나리오
| 시나리오 | 환경 | 결과 | 증거 |

## 7. Findings 요약
| 심각도 | Open | Verified | Accepted Risk | Blocked |

## 8. 미해결 이슈와 잔여 위험
각 항목에 영향, 완화책, 후속 조치를 포함한다.

## 9. 실행·재현·롤백
실제 명령과 필요한 환경을 적는다.

## 10. 독립 검수
- 판정:
- 주요 반박:
- 반영 결과:

## 11. 최종 근거
왜 이 판정이 타당한지 증거 중심으로 설명한다.
```

## 7. 최종 사용자 응답 형식

```text
판정: GO / GO_WITH_CAVEATS / NO_GO / BLOCKED

검수·수정한 핵심:
- ...

실행한 실제 검증:
- ...

남은 문제:
- ...

증거·보고서:
- ...
```

사용자 응답에서 작업량을 과장하지 않는다. 실행하지 않은 검사를 실행했다고 표현하지 않는다.

## 8. 민감정보 처리

- 토큰, 비밀번호, 쿠키, 개인 식별자, 결제 정보는 마스킹한다.
- 원본 증거가 필요하면 접근 제한된 위치와 공유용 정제본을 분리한다.
- 스크린샷에 실제 개인정보가 있으면 블러 또는 테스트 데이터로 대체한다.
- `findings.jsonl`과 보고서에 비밀값을 복사하지 않는다.
