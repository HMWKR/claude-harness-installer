# 루프 방지 규칙

- 작업 시작 전: 이전 결과물/체크포인트 존재 여부 확인
- 데이터 수집: 컨텍스트 30% 이내 완료, 40% 초과 시 즉시 분석 전환
- **대량 파일 수정 (5개+)**: 동일 패턴 치환은 `sed`/스크립트로 일괄 처리. 개별 Read+Edit 반복 금지.
- 동일 도구를 3회 이상 연속 실패하면 접근 방식을 변경한다.
- 재시도 전에 원인 가설·입력 범위·예산 중 무엇을 바꾸는지 정한다. 변경점 없는 재실행은 재시도가 아니라 반복이다.
- 이전 실행(백그라운드 작업·장시간 분석·외부 벤더 호출)의 종료가 확인되지 않으면 같은 작업을 중복 실행하지 않는다.

## Plan 파일 체크마크 프로토콜

- Plan 파일의 각 Task는 **파일 단위 서브태스크**로 분해한다:
  ```
  ### Task 4: 색상 토큰화
  - [x] src/app/globals.css ← 완료
  - [ ] src/frontend/components/ui/button.tsx
  - [ ] src/frontend/components/layout/header.tsx
  ```
- **Edit 완료 즉시** 해당 `[ ]` → `[x]`로 plan 파일 업데이트. 다음 턴 미루기 금지.
- **Continuation 세션 재개 시**: plan 파일 먼저 읽어 `[x]` 건너뛰고 `[ ]`부터 시작.
- **1 Task = 1 File 원칙**: 멀티파일 Task는 4a/4b/4c로 쪼갠다.

## Task 원자화 예시

나쁜 예: `Task 4: 색상 토큰화 (in progress)` — 어느 파일까지 완료했는지 불명
좋은 예:
  - `Task 4a: globals.css 토큰화 [x]`
  - `Task 4b: button.tsx 토큰화 [ ]`
  - `Task 4c: header.tsx 토큰화 [ ]`
