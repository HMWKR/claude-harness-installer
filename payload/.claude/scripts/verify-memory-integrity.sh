#!/usr/bin/env bash
# verify-memory-integrity.sh — SessionStart 가드 래퍼 (FAIL-OPEN).
# 메모리 파일의 손상 한글 토큰을 스캔해 경고한다 (차단 없음).
# 정책: ~/.claude/rules/safety.md  |  로직: 동일 디렉토리 verify-memory-integrity.py
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
command -v python3 >/dev/null 2>&1 || exit 0
python3 "$DIR/verify-memory-integrity.py" 2>/dev/null || true
exit 0
