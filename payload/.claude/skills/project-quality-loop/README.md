# Project Quality Loop — Claude Code Skill

어떤 프로젝트든 **발견 → 기준 정의 → 구현/검수 → 증거 수집 → 수정 → 재검수 → 독립 검수 → GO/NO-GO 판정**을 적용하는 범용 Claude Code 스킬이다.

## 지원 범위

- Web UI와 브라우저 자동화
- Backend/API, Database
- Mobile, Desktop
- CLI/TUI, Library/SDK
- Data/ETL, ML·생성형 AI
- AI Agent, Automation, MCP
- Infrastructure, DevOps
- Document, Content, Design, Image, Video, Audio
- 위 유형이 결합된 Mixed Product

## 설치

### 모든 로컬 프로젝트에서 사용

macOS/Linux:

```bash
mkdir -p ~/.claude/skills
cp -R project-quality-loop ~/.claude/skills/project-quality-loop
```

Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force "$HOME/.claude/skills" | Out-Null
Copy-Item -Recurse -Force project-quality-loop "$HOME/.claude/skills/project-quality-loop"
```

또는 포함된 설치 스크립트를 사용한다.

```bash
./install.sh
```

```powershell
./install.ps1
```

### 현재 저장소에만 적용

```bash
mkdir -p .claude/skills
cp -R /path/to/project-quality-loop .claude/skills/project-quality-loop
```

또는:

```bash
./install.sh --project /path/to/repository
```

프로젝트 스킬로 커밋하면 팀원과 Claude Code 클라우드 세션에서도 동일한 절차를 공유하기 쉽다.

## 실행

```text
/project-quality-loop full "현재 프로젝트 전체를 출시 가능한 수준까지 검수하고 수정"
```

```text
/project-quality-loop audit "로그인·회원가입·결제 플로우, 모바일 포함"
```

```text
/project-quality-loop fix "기존 findings의 Blocker와 Critical을 수정하고 전체 회귀 검증"
```

```text
/project-quality-loop release "v1.0 출시 게이트"
```

```text
/project-quality-loop plan "문서 산출물과 웹 대시보드를 함께 검수할 계획 수립"
```

## 모드

| 모드 | 동작 |
|---|---|
| `plan` | 조사, 분류, 완료 조건, 검수 계획만 작성 |
| `audit` | 소스 수정 없이 검사·증거·보고서 작성 |
| `fix` | 알려진 문제 수정과 재검수 |
| `full` | 요구사항 보완, 구현, 종합 검수, 수정, 재검수 |
| `release` | 실제 배포 없이 출시 가능 여부 판정 |

## 생성되는 품질 SSoT

```text
.claude/quality/
├── manifest.md
├── test-matrix.md
├── findings.jsonl
├── decision-log.md
├── final-report.md
├── project-detection.json
└── evidence/<run-id>/
```

기존 품질 체계가 있으면 새 폴더를 강요하지 않고 기존 구조를 우선 사용한다.

## 자동 프로젝트 감지

감지 스크립트는 명령을 실행하지 않고 파일과 manifest만 읽는다.

```bash
python ~/.claude/skills/project-quality-loop/scripts/detect_project.py --root . --pretty
```

품질 작업공간 초기화:

```bash
python ~/.claude/skills/project-quality-loop/scripts/bootstrap_quality.py --root . --mode full
```

스크립트가 실행되지 않는 환경에서는 Claude가 저장소를 직접 조사해 같은 절차를 수행한다.

## 핵심 안전 규칙

- 운영 배포, 실제 결제·전송, 데이터 삭제, 권한 변경은 승인 없이 실행하지 않는다.
- 미해결 Blocker·Critical이 있으면 평균 점수와 무관하게 GO를 금지한다.
- `FIXED_UNVERIFIED`, `NOT_RUN`, `UNKNOWN`을 PASS로 처리하지 않는다.
- 동일 실패가 두 차례 반복되고 새 증거나 개선이 없으면 무한 반복 대신 BLOCKED로 전환한다.
- 사용자의 기존 변경과 관련 없는 파일을 되돌리지 않는다.

## 파일 구조

```text
project-quality-loop/
├── SKILL.md
├── README.md
├── references/
│   ├── project-classification.md
│   ├── audit-matrix.md
│   ├── quality-gates.md
│   ├── reporting-schema.md
│   └── independent-review.md
├── templates/
│   ├── PROJECT_QUALITY_MANIFEST.md
│   ├── TEST_MATRIX.md
│   ├── DECISION_LOG.md
│   ├── FINAL_VERIFICATION_REPORT.md
│   └── ISSUE_RECORD.json
├── scripts/
│   ├── detect_project.py
│   └── bootstrap_quality.py
└── evals/
    ├── README.md
    └── test-prompts.json
```

## 권장 사용 패턴

작은 변경마다 이 스킬을 자동 호출하기보다, 기능 묶음 완료·전면 검수·출시 전 검증 시 사용한다. 스킬은 수동 실행형이므로 Claude가 임의로 긴 검수와 수정 작업을 시작하지 않는다.
