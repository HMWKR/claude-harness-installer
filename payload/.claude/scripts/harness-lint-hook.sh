#!/bin/bash
# harness-lint-hook.sh — PostToolUse(Edit|Write|MultiEdit) 래퍼 (2026-09-30 전역화, 감사 #58·#61)
# ~/.claude 아래 파일을 고쳤을 때만 harness-lint를 돌리고, 위반이 있을 때만 additionalContext JSON으로
# 모델에게 알린다. 예전 방식(stdout·exit 0)은 공식 문서상 디버그 로그에만 남아 모델에 닿지 않았다.
f=$(jq -r '.tool_input.file_path // .tool_response.filePath // empty' 2>/dev/null)
case "$f" in
  "$HOME"/.claude/*) ;;
  *) exit 0 ;;
esac
out=$(python3 "$HOME/.claude/scripts/harness-lint.py" 2>&1) && exit 0
jq -n --arg m "$out" '{hookSpecificOutput:{hookEventName:"PostToolUse",additionalContext:("[harness-lint] 하네스 편집 뒤 위반 발견 — 고친 뒤 다시 확인하라:\n" + $m)}}'
exit 0
