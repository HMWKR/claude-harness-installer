#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="user"
PROJECT_ROOT=""

if [[ "${1:-}" == "--project" ]]; then
  MODE="project"
  PROJECT_ROOT="${2:-$PWD}"
fi

if [[ "$MODE" == "user" ]]; then
  TARGET_ROOT="${HOME}/.claude/skills"
else
  TARGET_ROOT="$(cd "$PROJECT_ROOT" && pwd)/.claude/skills"
fi

TARGET="${TARGET_ROOT}/project-quality-loop"
mkdir -p "$TARGET_ROOT"

if [[ "$(cd "$SOURCE_DIR" && pwd)" == "$(cd "$TARGET_ROOT" && pwd)/project-quality-loop" ]]; then
  echo "이미 설치된 위치에서 실행 중입니다: $TARGET"
  exit 0
fi

if [[ -e "$TARGET" ]]; then
  BACKUP="${TARGET}.backup.$(date +%Y%m%d%H%M%S)"
  mv "$TARGET" "$BACKUP"
  echo "기존 스킬 백업: $BACKUP"
fi

cp -R "$SOURCE_DIR" "$TARGET"
rm -rf "$TARGET/__pycache__" "$TARGET/scripts/__pycache__"

echo "설치 완료: $TARGET"
echo "Claude Code에서 /project-quality-loop 를 실행하세요."
