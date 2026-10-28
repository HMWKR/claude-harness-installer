#!/usr/bin/env bash
# Claude Code 하네스 설치기.
#   ./install.sh                 파일 + 플러그인 + 외부 스킬 설치
#   ./install.sh --with-mcp      MCP 서버 등록까지 (manifest/mcp.sh)
#   ./install.sh --skip-plugins --skip-skills --dry-run
# 덮어쓰는 파일은 먼저 ~/.claude/backups/harness-install-<시각>/ 로 복사한다. 성공하면 exit 0.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
WITH_MCP=0 SKIP_PLUGINS=0 SKIP_SKILLS=0 DRY=0

for arg in "$@"; do
  case "$arg" in
    --with-mcp) WITH_MCP=1 ;;
    --skip-plugins) SKIP_PLUGINS=1 ;;
    --skip-skills) SKIP_SKILLS=1 ;;
    --dry-run) DRY=1 ;;
    -h|--help) sed -n '2,6p' "$0"; exit 0 ;;
    *) echo "알 수 없는 옵션: $arg" >&2; exit 2 ;;
  esac
done

log() { printf '\033[1;34m[harness]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[harness]\033[0m %s\n' "$*" >&2; }
FAILED=()

# --- 0. 사전 점검 ------------------------------------------------------------
# 훅 명령과 지침은 ~/.claude 경로로 고정돼 있다 — 다른 설정 폴더에 깔면 훅이 전부 깨진다
if [ -n "${CLAUDE_CONFIG_DIR:-}" ] && [ "${CLAUDE_CONFIG_DIR%/}" != "$CLAUDE_DIR" ]; then
  echo "CLAUDE_CONFIG_DIR($CLAUDE_CONFIG_DIR)는 지원하지 않는다 — 해제하고 다시 실행하라." >&2
  exit 1
fi
for bin in python3 git; do
  command -v "$bin" >/dev/null || { echo "필수 도구 없음: $bin" >&2; exit 1; }
done
HAS_CLAUDE=0; command -v claude >/dev/null && HAS_CLAUDE=1
HAS_NPX=0; command -v npx >/dev/null && HAS_NPX=1
[ "$HAS_CLAUDE" = 1 ] || warn "claude CLI 없음 — 플러그인·MCP 단계는 건너뛴다 (npm i -g @anthropic-ai/claude-code 후 재실행)"
[ "$HAS_NPX" = 1 ] || warn "npx 없음 — 외부 스킬 단계는 건너뛴다 (Node.js 설치 후 재실행)"
command -v jq >/dev/null || warn "jq 없음 — UI·검증 스킬 라우터, harness-lint, verify-lock 알림 훅이 조용히 꺼진다"

STAMP="$(date +%Y%m%d-%H%M%S)-$$"
BACKUP="$CLAUDE_DIR/backups/harness-install-$STAMP"
LOG="$BACKUP/install.log"
log "설치 대상: $CLAUDE_DIR"

if [ "$DRY" = 1 ]; then
  echo "  (dry-run) payload/.claude → $CLAUDE_DIR (바뀌는 파일은 $BACKUP 로 백업)"
  echo "  (dry-run) settings.json 교체, ~/bkit.config.json 없으면 생성"
  [ "$SKIP_PLUGINS" = 1 ] || python3 -c "import json;d=json.load(open('$REPO_DIR/manifest/plugins.json'));print('  (dry-run) 마켓플레이스',len(d['marketplaces']),'곳, 플러그인',len(d['plugins']),'개 설치')"
  [ "$SKIP_SKILLS" = 1 ] || python3 -c "import json;d=json.load(open('$REPO_DIR/manifest/skills.json'));print('  (dry-run) 외부 스킬',len(d['external']),'개 설치 (npx skills)')"
  [ "$WITH_MCP" = 0 ] || echo "  (dry-run) bash manifest/mcp.sh"
  log "dry-run 끝 — 아무것도 바꾸지 않았다."
  exit 0
fi
mkdir -p "$BACKUP"

# --- 1. 백업 + 파일 복사 -----------------------------------------------------
python3 - "$REPO_DIR/payload/.claude" "$CLAUDE_DIR" "$BACKUP" "$HOME" <<'PY'
import os, shutil, sys
from pathlib import Path
src, dst, backup, home = map(Path, sys.argv[1:5])
dst.mkdir(parents=True, exist_ok=True)
backed, copied, unlinked = 0, [], []

def realize(d: Path):
    """dst 아래 경로 d에 심볼릭 링크 조상이 있으면 링크를 실디렉토리로 바꾼다.
    링크 너머(예: ~/.agents/skills/x)의 원본을 덮어쓰지 않기 위해서다. 링크 대상은 백업한다."""
    cur = dst
    for part in d.relative_to(dst).parts:
        cur = cur / part
        if cur.is_symlink():
            b = backup / "links" / cur.relative_to(dst)
            b.parent.mkdir(parents=True, exist_ok=True)
            (b.parent / (b.name + ".symlink")).write_text(os.readlink(cur) + "\n")
            if cur.exists():  # 살아 있는 링크면 내용도 보존
                shutil.copytree(cur, b, symlinks=False) if cur.is_dir() else shutil.copy2(cur, b)
            cur.unlink()
            unlinked.append(str(cur.relative_to(dst)))

for root, _, files in os.walk(src):
    for f in files:
        sp = Path(root, f)
        rel = sp.relative_to(src)
        dp = dst / rel
        realize(dp.parent)
        dp.parent.mkdir(parents=True, exist_ok=True)
        data = sp.read_bytes()
        if b"\0" not in data[:8192]:
            try:
                data = data.decode("utf-8").replace("__HOME__", str(home)).encode("utf-8")
            except UnicodeDecodeError:
                pass
        if dp.is_symlink():
            realize(dp)
        elif dp.exists():
            if dp.read_bytes() == data:
                copied.append(str(rel)); continue
            b = backup / rel
            b.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dp, b)
            backed += 1
        dp.write_bytes(data)
        os.chmod(dp, sp.stat().st_mode & 0o777)
        copied.append(str(rel))
(backup / "installed-files.txt").write_text("\n".join(copied) + "\n")
print(f"  파일 {len(copied)}개 설치, 바뀐 기존 파일 {backed}개 백업")
if unlinked:
    print(f"  심볼릭 링크 {len(unlinked)}개를 실폴더로 교체(원본은 그대로, 링크 정보는 백업): {', '.join(unlinked)}")
PY
chmod +x "$CLAUDE_DIR"/scripts/*.sh "$CLAUDE_DIR"/scripts/*.py 2>/dev/null || true
# bkit 설정은 작업 폴더(cwd) 기준으로 읽힌다 — 홈에 없을 때만 놓는다
if [ ! -e "$HOME/bkit.config.json" ]; then
  cp "$CLAUDE_DIR/bkit.config.json" "$HOME/bkit.config.json" && echo "  ~/bkit.config.json 생성"
fi
echo "  기존 settings.json은 교체됐다. 되돌리기: cp \"$BACKUP/settings.json\" \"$CLAUDE_DIR/\" (백업이 있을 때)"

# --- 2. 플러그인 -------------------------------------------------------------
if [ "$SKIP_PLUGINS" = 0 ] && [ "$HAS_CLAUDE" = 1 ]; then
  log "마켓플레이스·플러그인 설치 (자세한 출력: $LOG)"
  while IFS=$'\t' read -r kind value; do
    if [ "$kind" = M ]; then
      echo "### marketplace add $value" >>"$LOG"
      claude plugin marketplace add "$value" >>"$LOG" 2>&1 \
        || echo "  - 마켓플레이스 $value: 추가 안 됨(이미 있으면 정상)"
    else
      echo "### plugin install $value" >>"$LOG"
      # -y를 주지 않는다: 마켓플레이스가 선언한 명령 실행은 사람이 확인해야 한다
      if claude plugin install "$value" --scope user >>"$LOG" 2>&1 </dev/null; then
        echo "  ✓ $value"
      else
        FAILED+=("plugin:$value"); warn "  ✗ $value"
      fi
    fi
  done < <(python3 - "$REPO_DIR/manifest/plugins.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
for src in d["marketplaces"].values():
    if src.get("source") == "github":
        print("M\t" + src["repo"])
    elif "url" in src:
        print("M\t" + src["url"])
for p in d["plugins"]:
    print("P\t" + p)
PY
)
  # harness-lint는 플러그인 설치 결과를 기준선으로 삼는다 — 새 머신에는 기준선이 없다
  python3 "$CLAUDE_DIR/scripts/harness-lint.py" --update-baseline >>"$LOG" 2>&1 \
    || warn "  harness-lint 기준선 생성 실패 (로그 참고)"
fi

# --- 3. 외부 스킬 (원본 레포에서 받는다) -------------------------------------
if [ "$SKIP_SKILLS" = 0 ] && [ "$HAS_NPX" = 1 ]; then
  log "외부 스킬 설치 (npx skills)"
  while IFS=$'\t' read -r source names; do
    args=()
    for n in $names; do args+=(-s "$n"); done
    echo "### skills add $source $names" >>"$LOG"
    if npx -y skills add "$source" "${args[@]}" -a claude-code -g -y --copy </dev/null >>"$LOG" 2>&1; then
      echo "  ✓ $source ($names)"
    else
      FAILED+=("skills:$source"); warn "  ✗ $source ($names)"
    fi
  done < <(python3 - "$REPO_DIR/manifest/skills.json" <<'PY'
import json, sys
from collections import defaultdict
g = defaultdict(list)
for e in json.load(open(sys.argv[1]))["external"]:
    g[e["source"]].append(e["name"])
for src, names in g.items():
    print(src + "\t" + " ".join(names))
PY
)
fi

# --- 4. MCP (선택) -----------------------------------------------------------
if [ "$WITH_MCP" = 1 ] && [ "$HAS_CLAUDE" = 1 ]; then
  log "MCP 서버 등록 (manifest/mcp.sh)"
  bash "$REPO_DIR/manifest/mcp.sh" || FAILED+=("mcp")
fi

# --- 5. 사후 점검 (이번에 설치한 파일만 본다) --------------------------------
log "사후 점검"
python3 - "$CLAUDE_DIR" "$BACKUP/installed-files.txt" <<'PY' || FAILED+=("post-check")
import json, os, re, sys
from pathlib import Path
d = Path(sys.argv[1]); bad = []
s = json.loads((d / "settings.json").read_text())
for ev in s.get("hooks", {}).values():
    for m in ev:
        for h in m["hooks"]:
            for ref in re.findall(r"~/\.claude/(scripts/[\w./-]+)", h.get("command", "")):
                if not Path(os.path.expanduser("~/.claude"), ref).exists():
                    bad.append(f"훅 스크립트 없음: {ref}")
for rel in Path(sys.argv[2]).read_text().split():
    try:
        if "__HOME__" in (d / rel).read_text(errors="ignore"):
            bad.append(f"자리표시자 미치환: {rel}")
    except OSError as e:
        bad.append(f"읽기 실패: {rel} ({e})")
print("\n".join("  ✗ " + b for b in bad[:20]) or "  ✓ settings JSON 유효, 훅 스크립트 전부 존재, 경로 치환 완료")
sys.exit(1 if bad else 0)
PY

echo
[ "$WITH_MCP" = 1 ] || log "MCP 서버까지 넣으려면: ./install.sh --with-mcp --skip-plugins --skip-skills"
if [ "${#FAILED[@]}" -gt 0 ]; then
  warn "실패: ${FAILED[*]}"
  warn "자세한 출력: $LOG — 네트워크·인증 확인 후 다시 실행하면 된다(재실행해도 안전)."
  exit 1
fi
log "완료. Claude Code를 새로 시작하면 적용된다."
