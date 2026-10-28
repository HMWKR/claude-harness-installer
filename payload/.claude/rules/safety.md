# Safety Rules — 안전 규칙

## 파괴적 명령어 제어
> 집행 계층(2026-08-09 승격): `rm -rf`·`git reset --hard`·`git push --force`·`git clean -f`는
> **`~/.claude/settings.json`의 `permissions.ask`가 모든 프로젝트에서 사람 체크포인트를 강제**한다
> (2026-09-30 local→전역 이전, 홈 밖 폴더 카나리 실측: `rm -rf` 차단·`rm` 통과. harness-lint가 범위를 감시.
> 분류기·자동 승인이 못 뒤집는 계층.
> 단 인자 패턴 우회 한계는 공식 인정 — 옵션 선행 등). 그 외 실방어는 allowlist의 좁음이다
> (`Bash(python3 *)` 같은 넓은 항목이 약화시킨다). hookify 경고는 cwd=홈 한정. 훅 신설 시
> 프로토콜: **stdin JSON + 차단은 exit 2**(exit 1은 통과). 실측: `~/.thoughts/2026-08-09-harness-audit-and-dual-vendor.md`.

- DB 파괴: `DROP DATABASE`, `TRUNCATE`, `DELETE FROM` (WHERE 없이) 절대 금지
- 파일 파괴: `rm -rf`, `rmdir /s` 등은 설명 → 사용자 승인 → 실행 (3단계, ask 계층이 집행)
- Git 파괴: `git reset --hard`, `git push --force`, `git clean -f` 는 3단계 승인 필수 (ask 계층이 집행)
- 프로세스: `kill -9`, `pkill` 등 프로세스 강제 종료 시 대상 확인 필수
- **무인 삭제 자동화 금지**: 훅 스크립트에 시간 기준 일괄 삭제(`find -mtime -delete`, `rm -rf`)를
  넣지 않는다. 필요하면 기본 dry-run + `--force` 명시 인자 분리(claude-gc 사고 재발 방지 조항 —
  사고 스크립트는 2026-08-09 삭제, git 이력에만 존재).

## 민감정보 보호
- API 키·비밀번호·토큰 하드코딩 금지, `.env`는 git 커밋 금지, 로그 출력 마스킹.
- **`permissions.deny` 8개 규칙은 `Read` 도구만 차단**하며, 문법은 **`//` 접두 + `**/` glob만
  집행된다** — 상대 glob·단일 슬래시는 조용히 무시(2026-07-25 실측, 2026-08-09 v2.1.226
  3형태 카나리 재검증). 즉시 적용됨.
- **셸 경유는 막지 못한다** — `Bash(python3 *)`로 같은 파일이 읽힌다(실증). 이 deny는 실수 방지
  장치이지 유출 방지 장치가 아니다.

## 실행 전 확인 원칙
- 외부 서비스 호출 (API, 배포, 메시지 발송)은 사전 확인
- 프로덕션 환경과 개발 환경을 구분하여 작업
- 불가역적 작업은 반드시 사용자에게 영향 범위를 설명 후 승인 획득

## 한국어 손상 토큰 정책 (2026-05-27 사고 영속 정책)
- 손상 시그니처: "영" 비정상 연속 반복(가드 차단 4회+, 모델은 2회+부터 경계) / U+FFFD 1회+ / □ 3개+ — 발견 즉시 정상 콘텐츠로 인용·재사용 금지
- PreToolUse `sanitize-korean.sh` 가드가 손상 텍스트의 Write/Edit/MultiEdit/git commit을 차단한다 (fail-open)
- SessionStart `verify-memory-integrity.sh` 경고 수신 시: `[손상 메모리 인용]` 명시 + 사용자에게 복구 필요 보고
