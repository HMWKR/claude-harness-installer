# claude-harness-installer

Claude Code 개인 하네스(전역 지침·규칙·훅·스킬·에이전트·워크플로·플러그인 구성)를 다른 머신에 그대로 설치하는 배포판입니다.

## AI 에이전트용 설치 지침

이 레포 주소를 받고 "하네스 설치"를 요청받았다면 아래를 그대로 실행하세요.

```bash
git clone https://github.com/HMWKR/claude-harness-installer.git ~/claude-harness-installer
cd ~/claude-harness-installer
./install.sh            # 파일 + 플러그인 31개 + 외부 스킬 36개
# MCP 서버까지:  ./install.sh --with-mcp
```

- 종료 코드 0이면 성공입니다. 0이 아니면 마지막의 `실패:` 줄과 로그 경로를 그대로 사용자에게 보고하세요.
- 끝나면 Claude Code를 새로 시작해야 적용된다고 사용자에게 알리세요.
- 다시 실행해도 안전합니다. 네트워크·인증 문제로 실패한 단계는 다시 돌리면 됩니다.
- 플러그인 설치에 사람 확인이 필요한 경우(마켓플레이스가 명령 실행을 선언한 경우) 설치기는 자동 수락하지 않고 실패로 보고합니다. 사용자에게 `claude plugin install <이름>`을 직접 실행하도록 안내하세요.

한 줄 설치도 됩니다.

```bash
curl -fsSL https://raw.githubusercontent.com/HMWKR/claude-harness-installer/main/bootstrap.sh | bash
```

## 설치기가 바꾸는 것

- `~/.claude/` 아래 하네스 파일. **기존 `settings.json`은 병합하지 않고 교체합니다**(모델·권한·훅 포함). 바뀌는 파일은 모두 먼저 `~/.claude/backups/harness-install-<시각>/`에 복사하고, 되돌리는 명령을 출력합니다.
- `~/.claude/skills/<이름>`이 심볼릭 링크이면 링크 너머 원본을 건드리지 않고 링크를 실폴더로 바꿉니다. 링크 정보는 백업 폴더 `links/`에 남습니다.
- `~/bkit.config.json` — 없을 때만 만듭니다.
- 플러그인·외부 스킬·(선택) MCP 서버 등록. 자세한 출력은 백업 폴더의 `install.log`.
- `CLAUDE_CONFIG_DIR`로 설정 폴더를 바꿔 쓰는 환경은 지원하지 않습니다(훅 경로가 `~/.claude`로 고정). 설정돼 있으면 설치기가 멈춥니다.

## 요구 사항

| 필요 | 용도 | 없으면 |
|---|---|---|
| `python3`, `git` | 설치기·훅 | 설치 중단 |
| `claude` CLI | 플러그인·MCP 등록 | 해당 단계 건너뜀 |
| Node.js (`npx`) | 외부 스킬 설치 | 해당 단계 건너뜀 |
| `jq` | 스킬 라우터·harness-lint·verify-lock 훅 | 그 훅들이 조용히 꺼짐 |

하네스 규칙이 전제하는 선택 도구입니다. 없어도 설치는 되지만 해당 기능은 동작하지 않습니다.

- **Aside 브라우저 + `aside` CLI**: 모든 브라우저 작업의 단일 경로(`rules/uncompromising-rigor.md` §1). Playwright·Chrome MCP는 `permissions.deny`로 막혀 있습니다.
- **codex CLI**: 교차벤더 검증·이미지 생성(`rules/cross-vendor-routing.md`)
- **uv**(serena·blender MCP), Obsidian vault(`KNOT_VAULT`, 기본 `~/knot-vault`)
- impeccable 자동 감지 훅(`scripts/design-detect-hook.py`)은 macOS arm64 엔진 해시에 고정돼 있어 다른 플랫폼에서는 실행을 거부합니다.

## 옵션

```
./install.sh --with-mcp        MCP 서버 등록 (manifest/mcp.sh)
./install.sh --skip-plugins    플러그인 단계 생략
./install.sh --skip-skills     외부 스킬 단계 생략
./install.sh --dry-run         아무것도 바꾸지 않고 할 일만 출력
```

MCP 비밀값은 환경변수로 넘깁니다. 셸 기록에 남지 않게 `read -rs REFERO_TOKEN && export REFERO_TOKEN` 후 `./install.sh --with-mcp`. 등록된 토큰은 `~/.claude.json`에 평문으로 저장됩니다. Figma·Motion 같은 HTTP 서버는 등록 후 Claude Code 안에서 `/mcp`로 로그인하세요.

## 구성

```
payload/.claude/        ~/.claude 로 복사되는 파일 (홈 경로는 __HOME__ 로 저장, 설치 때 치환)
  CLAUDE.md             전역 지침
  settings.json         훅·권한·플러그인·모델 설정 (anti-loop·checkpoint 훅 포함)
  rules/ scripts/ agents/ commands/ workflows/ adapters/ verification-templates/
  skills/               직접 만든 스킬 + 원본 레포가 없는 스킬 (20개)
  patches/              플러그인 캐시 패치 재적용 레시피 (자동 적용하지 않음)
manifest/
  plugins.json          마켓플레이스 10곳(공식 포함) + 플러그인 31개
  skills.json           원본 레포에서 받는 외부 스킬 36개
  mcp.sh                MCP 서버 등록 템플릿
tools/export.py         ~/.claude 에서 payload/ 를 다시 만드는 스크립트 (관리자용)
```

플러그인과 외부 스킬은 각 원본의 **최신본**이 설치됩니다. 원본 하네스에서 플러그인 캐시에 손으로 적용한 수정은 `patches/`에 레시피로만 있고, 자동 적용하지 않습니다.

## 원본 하네스와 다른 점

- 들어 있지 않은 것: 세션 기록, 메모리(`projects/*/memory`), 캐시, 자격 증명, 플러그인 캐시, 퇴역 구성(`disabled/`), `~/.thoughts/` 감사 문서(규칙 본문이 근거로 인용만 함)
- `~/.agents/skills`에만 있고 원본 레포가 없는 로컬 스킬 8개는 빠졌습니다(`manifest/skills.json`의 `excluded_local_links`)
- 특정 회사 환경 설명(`autoMode.environment`), Orca 앱이 주입한 훅·상태줄, 홈 경로 기반 권한, 개인 열람 사이트 WebFetch 허용은 뺐습니다
- 원본의 `settings.local.json`은 홈 폴더에서 실행할 때만 읽히는 파일입니다. 그 안의 훅(anti-loop·checkpoint·세션 시작 안내)은 `settings.json`에 합쳐 어느 폴더에서든 동작하게 했고, 넓은 Bash 자동 허용(curl·python3·rm 등)은 싣지 않았습니다
- `gptaku-plugins` 마켓플레이스(insane-search)는 새 환경에서 설치가 실패해 뺐습니다

## 업데이트 (관리자용)

```bash
python3 tools/export.py      # ~/.claude → payload/ 재생성 + 개인 정보 스캔
git add -A && git commit && git push
```

치환표 `~/.config/harness-export/redact.json`(레포 밖, `HARNESS_REDACT`로 변경)에 `{"원문": "치환"}`을 넣으면 내보낼 때 바꿉니다. 스캔(홈 경로·사용자명·이메일·토큰·claude.ai 아티팩트 URL·UUID·치환표 원문)에 걸리는 것이 남으면 exit 1로 멈춥니다.

제3자 스킬의 출처와 라이선스는 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)에 있습니다.
