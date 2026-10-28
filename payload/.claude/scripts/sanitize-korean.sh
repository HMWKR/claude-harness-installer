#!/usr/bin/env bash
# sanitize-korean.sh — PreToolUse 가드 래퍼 (FAIL-OPEN).
# 손상 한글 토큰이 포함된 Write/Edit/MultiEdit/git commit 을 차단한다.
# 정책: ~/.claude/rules/safety.md  |  로직: 동일 디렉토리 sanitize-korean.py
# 프로토콜: stdin=JSON, stdout=차단 시 {"decision":"block",...} / 허용 시 {}, exit 0 고정.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
input="$(cat 2>/dev/null || true)"

# python3 부재 시 안전하게 허용 (fail-open)
if ! command -v python3 >/dev/null 2>&1; then
  printf '{}\n'
  exit 0
fi

out="$(printf '%s' "$input" | python3 "$DIR/sanitize-korean.py" 2>/dev/null)"
rc=$?
if [ $rc -ne 0 ] || [ -z "$out" ]; then
  printf '{}\n'   # 로직 실패 시 허용 (fail-open)
else
  printf '%s\n' "$out"
fi
exit 0
