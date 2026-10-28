# DoD: `claude-templates` 로컬 커밋의 marketplace update 내구성 검증

> **저작자: codex (gpt-5.6-sol), 2026-07-25.** 실행자는 Claude다. 원칙 4에 따라 DoD·verify-cmd의
> 저작·채점을 피검 모델 밖에 두었다. 실행 노드는 이 파일과 아래 판정 predicate를 수정할 수 없다
> (`verify-lock`으로 잠근다).

판정 규칙: 가설 판정 명령은 `exit 0 = MATCH`, `exit 1 = REJECT`이다. 최종적으로 A~D 중
**정확히 하나만** `MATCH`여야 한다. 0개 또는 2개 이상이면 검증 실패이며 임의 분류를 금지한다.

검증할 질문: `claude plugin marketplace update claude-templates` 실행 시
`~/.claude/plugins/marketplaces/claude-templates`의 로컬 커밋 `8248e32`(origin/main보다 1커밋
앞섬)가 어떻게 되는가?

- 가설 A: pull/merge/rebase → 로컬 커밋 **보존**(충돌 또는 merge 커밋)
- 가설 B: 기존 `.git` 유지 + reset/checkout → 로컬 커밋 **유실**
- 가설 C: 클론 삭제 후 재클론 → 로컬 커밋 **유실**
- 가설 D: 미지원 또는 no-op → 변화 없음

## 체크리스트

각 항목의 verify-cmd는 `scripts/verify-marketplace-divergence.sh <step>`으로 구현된다
(단일 파일, step별 함수). 모든 증거는
`~/.claude/verification-evidence/claude-templates-marketplace-update/`에 남는다.

- [ ] **1. 실험 전 안전장치** — 클론 외부에 전체 git bundle을 만들고 `8248e32` 복구 가능성을
  **실제 clone으로** 검증한다. `verify-marketplace-divergence.sh safety`
  최소 증거: exit 0 · `pre-update.bundle` 비어 있지 않음 · `recovery-proof.txt`에 `RECOVERY_OK`
- [ ] **2. 사전조건 고정** — HEAD·clean·ahead=1·커밋 메시지·예시 변경 파일·origin URL이 주어진
  사실과 일치. `.git` 교체 판별용 센티널 생성. `... baseline`
  최소 증거: exit 0 · `BASELINE_OK` · `pre.status`가 빈 파일 · 예시 파일명이 `pre.changed-files`에 존재
- [ ] **3. 서브커맨드 존재 확인** — update 실행 **전에** help를 기록. `... support`
  최소 증거: exit 0 · `update.support`가 정확히 `SUPPORTED` 또는 `UNSUPPORTED`
- [ ] **4. 단일 실험 실행** — 지원 시에만 정확히 **한 번** 실행. stdout·stderr·exit·GIT_TRACE 보존.
  `... run` — 동일 증거 디렉토리에서 재실행하면 반드시 실패해야 한다(noclobber).
  최소 증거: exit 0 · `UPDATE_CAPTURED` · `update.exit`가 숫자
- [ ] **5. 사후 상태 기계 판정값 생성** — HEAD·tree·refs·status·origin·센티널·커밋 도달성·충돌·
  git trace를 기록. `... post`
  최소 증거: exit 0 · `POST_CAPTURED` · 모든 `post.*`/`delta.*`/`trace.*` 파일 생성
- [ ] **6. 가설 A 판정** — 센티널 SAME + `8248e32`가 사후 HEAD의 조상 + (pull/merge/rebase trace
  또는 HEAD 변경) 또는 (비정상 종료 + 충돌 + preserve trace). `... verdictA`
- [ ] **7. 가설 B 판정** — 센티널 SAME + 커밋이 HEAD 조상 아님 + 로컬 ref 0개 + HEAD==origin/main
  + 충돌 0. `... verdictB`
- [ ] **8. 가설 C 판정** — 센티널 MISSING + 커밋 비도달 + (gitdir 변경 또는 clone trace).
  `... verdictC`
- [ ] **9. 가설 D 판정** — 미지원·미실행이거나, 실행했어도 HEAD/tree/origin/refs/status 전부 불변
  + preserve·destructive·clone trace 전부 NO. `... verdictD`
- [ ] **10. 단일 결론 게이트** — A~D 중 정확히 하나만 MATCH. 그 외는 `INCONCLUSIVE`이며 검증
  완료로 보고할 수 없다. `... final`
  최소 증거: exit 0 · `final-verdict.txt`에 `FINAL_HYPOTHESIS=[ABCD]`
- [ ] **11. 실험 범위 규율** — 캐시 전파용 uninstall/install을 이 실험에서 실행하지 않았고,
  기록된 실험 명령이 marketplace update 하나뿐임을 확인. `... scope`
  최소 증거: exit 0 · `SCOPE_OK no-cache-propagation`

**실패 시 금지**: DoD·verify-cmd·판정 predicate를 낮추거나, 증거를 덮어쓰거나, 동일 증거
디렉토리에서 update를 재실행해 유리한 결과를 선택하지 않는다.

전항 PASS + A~D 정확히 하나 MATCH + `verify-lock check` OK 가 완료 조건이다.

## verify-lock 대상

- 이 파일
- `~/.claude/verification-templates/bugfix.md`
- `~/.claude/scripts/verify-lock.py`
- `~/.claude/scripts/verify-marketplace-divergence.sh` (판정 predicate 구현체 — 실행 중 수정 금지)

```bash
python3 ~/.claude/scripts/verify-lock.py lock ~/.claude/.verify-lock-marketplace-update.json \
  ~/.claude/verification-templates/claude-templates-marketplace-update-divergence.md \
  ~/.claude/verification-templates/bugfix.md \
  ~/.claude/scripts/verify-lock.py \
  ~/.claude/scripts/verify-marketplace-divergence.sh
```

완료 판정 직전: `python3 ~/.claude/scripts/verify-lock.py check ~/.claude/.verify-lock-marketplace-update.json`

## 재승인 이력 (게이트 무효 → 재잠금)

**2026-07-25 — 1회.** 단계 1(안전장치)의 **방법**을 codex 원안의 `git bundle`에서
`tar` 전체 백업으로 교체했다. 사유: 이 저장소는 shallow clone(depth 1)이라
`git bundle create --all`이 경계 밖 부모 객체를 참조해 **clone 불가한 번들**을 만든다
(실측 오류: `remote did not send all necessary objects` / `Failed to traverse parents of
commit 0ff6404`). 마켓플레이스 13곳 전부 shallow임을 확인했다.

**기준은 하향하지 않았다** — 요구는 여전히 "실험 전 `8248e32`의 복구 가능성을 실제 복원으로
증명"이고, tar 복원 리허설로 충족했다(507파일 복원 · `8248e32` 존재 · HEAD 일치 · 수정 내용
2건 보존). `verify-lock check`가 이 변경을 TAMPER로 정확히 탐지했고, 그 사실을 기록한 뒤
재잠금했다. 이것이 verify-lock의 첫 실사용이며 설계 의도대로 작동했다.
