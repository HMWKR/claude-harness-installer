#!/bin/bash
# verify-lock-hook.sh — verify-lock 변조 게이트 훅 (2026-09-30 전역화, 감사 #53·#58)
# 사용: verify-lock-hook.sh taskcompleted | stop
# 잠금 파일은 세션 프로젝트 루트(CLAUDE_PROJECT_DIR)와 현재 폴더 둘 다에서 찾는다 — 예전 상대 glob은
# 하위 폴더로 cd 한 번이면 아무것도 찾지 못해 통과됐다. 잠금 파일이 없으면 아무 일도 하지 않는다.
# taskcompleted: 변조 시 exit 2(완료 롤백, stderr가 모델에 전달)
# stop: 변조 시 systemMessage로 사용자에게만 알린다 — additionalContext는 대화를 이어가게 해 다음 Stop에서 fablize gate_stop이
#       검사를 건너뛴다(2026-10-02 최종 검토). 모델에게는 TaskCompleted 게이트(exit 2)가 전달한다.
mode="$1"
input=$(cat)
if [ "$mode" = stop ] && [ "$(printf '%s' "$input" | jq -r '.stop_hook_active // false' 2>/dev/null)" = true ]; then
  exit 0
fi
msgs=""
seen=" "
for dir in "${CLAUDE_PROJECT_DIR:-$PWD}" "$PWD"; do
  for f in "$dir"/.verify-lock*.json; do
    [ -f "$f" ] || continue
    case "$seen" in *" $f "*) continue ;; esac
    seen="$seen$f "
    out=$(python3 "$HOME/.claude/scripts/verify-lock.py" check "$f" 2>&1) && continue
    msgs="${msgs}${f}: ${out}
"
  done
done
[ -z "$msgs" ] && exit 0
if [ "$mode" = taskcompleted ]; then
  printf '[verify-lock] 태스크 완료 차단 — 검증자산 변조/누락:\n%s' "$msgs" >&2
  exit 2
fi
jq -n --arg m "$msgs" '{systemMessage:("[verify-lock 관찰] 검증자산 변조/누락 감지 — 게이트 무효, 재승인 필요:\n" + $m)}'
exit 0
