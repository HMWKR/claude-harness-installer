#!/usr/bin/env bash
# MCP 서버 등록 템플릿 (user 스코프). install.sh --with-mcp 가 호출한다. 단독 실행도 된다.
# - 이미 등록된 이름은 건너뛴다. 필요한 CLI가 없으면 설치 방법만 알리고 건너뛴다.
# - 비밀값은 이 파일에 없다. 필요한 것은 환경변수로 넘긴다:
#     read -rs REFERO_TOKEN && export REFERO_TOKEN   (Refero 유료 토큰 — 셸 기록에 남기지 않기)
#     등록된 토큰은 Claude 설정(~/.claude.json)에 평문으로 저장된다.
#     KNOT_VAULT=~/my-vault ./install.sh --with-mcp (Obsidian vault 경로, 기본 ~/knot-vault)
# - HTTP 서버(figma·motion·refero·miricanvas)는 등록 후 Claude Code 안에서 /mcp 로 로그인한다.
set -uo pipefail
RC=0

have() { command -v "$1" >/dev/null 2>&1; }
added() { claude mcp get "$1" >/dev/null 2>&1; }
add() {  # add <name> <설명> -- <claude mcp add 인자...>
  local name="$1" note="$2"; shift 3
  if added "$name"; then echo "  - $name: 이미 등록됨"; return; fi
  if claude mcp add -s user "$@" >/dev/null 2>&1; then echo "  ✓ $name"; else echo "  ✗ $name ($note)"; RC=1; fi
}
skip() { echo "  · $1 건너뜀 — $2"; }

# 코드 검증·이미지 생성 교차벤더 (rules/cross-vendor-routing.md)
if have codex; then add codex "codex CLI" -- codex -- codex mcp-server
else skip codex "codex CLI 필요: npm i -g @openai/codex && codex login"; fi

# 심볼 리네임·참조 추적
if have uvx; then add serena "uvx" -- serena -- uvx --from git+https://github.com/oraios/serena serena start-mcp-server --context claude-code --project-from-cwd
else skip serena "uv 필요: https://docs.astral.sh/uv/"; fi

# knot 지식 vault (Obsidian)
VAULT="${KNOT_VAULT:-$HOME/knot-vault}"
if [ -d "$VAULT" ]; then add obsidian "npx" -- obsidian -- npx -y obsidian-mcp "$VAULT"
else skip obsidian "vault 폴더 없음: $VAULT (KNOT_VAULT로 지정)"; fi

# 디자인 계열 HTTP 서버
add figma "http" -- --transport http figma https://mcp.figma.com/mcp
add motion "http" -- --transport http motion https://mcp.motion.dev
add motion-plus "http" -- --transport http motion-plus https://mcp.motion.dev/plus
add miricanvas "http" -- --transport http miricanvas https://mcp.miricanvas.com/mcp
if [ -n "${REFERO_TOKEN:-}" ]; then
  add refero "http" -- --transport http refero https://api.refero.design/mcp -H "Authorization: Bearer $REFERO_TOKEN"
else skip refero "REFERO_TOKEN 환경변수 필요(유료)"; fi

# 역공학 (morluto/rea)
if have rea; then add rea "rea CLI" -- rea -- rea mcp
else skip rea "rea CLI 필요: npm i -g rea-agents"; fi

# Blender
if have uvx; then add blender "uvx" -- blender -- uvx mcp-for-blender
else skip blender "uv 필요"; fi

# 의도적으로 넣지 않는 것:
# - playwright: settings.json permissions.deny 가 mcp__playwright 를 막는다(브라우저는 aside CLI 단일).
# - figma-bridge: 로컬 빌드 서버(~/.local/share/figma-mcp-bridge)라 원격 설치 경로가 없다.

exit $RC
