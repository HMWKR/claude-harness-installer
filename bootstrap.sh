#!/usr/bin/env bash
# 한 줄 설치: curl -fsSL https://raw.githubusercontent.com/HMWKR/claude-harness-installer/main/bootstrap.sh | bash
# 인자는 install.sh 로 넘긴다: ... | bash -s -- --with-mcp
set -euo pipefail
DIR="${HARNESS_DIR:-$HOME/claude-harness-installer}"
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" pull --ff-only
else
  git clone --depth 1 https://github.com/HMWKR/claude-harness-installer.git "$DIR"
fi
exec bash "$DIR/install.sh" "$@"
