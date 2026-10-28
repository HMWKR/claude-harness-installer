---
name: cross-vendor
description: |
  이종 벤더(codex)를 실작업에 동원하는 방법. Use when the user explicitly asks for a code review / "리뷰해줘" / PR review / second opinion, when a hard-to-reverse architecture or design decision is on the table, after 2+ failed fix attempts (root-cause pass), for security or algorithm edge-case review, when generating raster/photo images, or when a verdict needs an independent non-Claude vendor. An explicit review request applies regardless of file count. Covers which vendor to call and the exact invocation templates. NOT for routine self-checking after an ordinary edit, trivial questions, or Claude-only work where a second vendor adds no value.
---

# Cross-Vendor 동원 (codex)

Claude가 이미 가진 두 이종 벤더를 **적절한 지점에 스스로** 동원한다. 규범 SSoT는 `~/.claude/rules/cross-vendor-routing.md` — 이 스킬은 발동 진입점이자 호출 템플릿이다.

## 언제 무엇을 (트리거 → 벤더)

| 신호 | 벤더 | 이유 |
|---|---|---|
| 코드 리뷰·2차 의견 요청 | codex read-only | 이종 벤더 교차검증이 동종 다수결 상관오류를 깬다 |
| 되돌리기 비싼 아키텍처·설계 결정 | codex read-only | 비가역 결정에 독립 관점 |
| 2회 수정 실패 후 근본원인 | codex read-only | 같은 모델이 못 본 것을 다른 모델이 봄 |
| 보안·알고리즘 엣지케이스 검증 | codex read-only | 적대적 관점 |
| 래스터/사진 이미지 생성 | codex MCP (`image_gen__imagegen`, sandbox workspace-write + 산출 전용 cwd) | 2026-09-28 사용자 지시. 호출 규약: rules/cross-vendor-routing.md "이미지 생성 호출" |
| 영상 | 코드형은 로컬 Remotion, 생성형은 fal.ai(+Blender 기준 프레임) | 2026-10-22 사용자 지시. rules/cross-vendor-routing.md 표 |
| 시각/실사 판정·고위험(비가역+영향 큼) | codex + Claude critic 판정단 | 관점 분산(동종 다수결만으로 닫지 않는다) |

네이밍·스타일·사소한 수정에는 부르지 않는다(비용 > 이득).

## 호출 템플릿

**codex 2차 의견/리뷰** (main 직접 — 서브에이전트 경로는 동원 매트릭스상 [미검증]이라 카나리 승격 전에는 쓰지 않는다):
```
mcp__codex__codex(prompt="<대상+DoD+판정 형식 GO/NO-GO>", sandbox="read-only", cwd="<repo>")
```
`sandbox` 생략 시 codex-sandbox-guard 훅이 차단한다(반드시 명시). `danger-full-access`, `config`의 sandbox 키, `workspace-write`의 넓은 cwd(홈·`~/.claude`·`~/.codex`·소스 루트 등)도 차단된다 — 쓰기 호출은 산출 전용 하위 폴더를 cwd로 준다. `/codex:review`·`/codex:adversarial-review`는 사용자 슬래시 전용(disable-model-invocation)이라 모델은 위 MCP를 직접 쓴다.

**codex MCP 토큰 오류**("access token could not be refreshed") 시: MCP 서버가 낡은 인증을 들고 있는 것 — 사용자가 `/mcp`로 재연결할 때까지 같은 판정을 CLI로 한다: `codex exec --skip-git-repo-check -s read-only "<프롬프트>"`(2026-10-02 실측). CLI도 가드가 검사한다 — `-s` 필수, workspace-write는 `--cd <좁은 산출 폴더>` 필수. if·for·`{}`·`$()`·백틱 안의 codex exec는 판정 불가로 막히니 단순한 한 줄로 쓴다(출력용 `echo codex exec`도 막힘 — 안전 쪽 오탐). 백그라운드로 돌릴 때는 `< /dev/null`을 붙인다 — 표준 입력이 열려 있으면 "Reading additional input from stdin"에서 멈춘다(2026-10-02 실측).

## 경로별 규율

경로별 실측·규율의 SSoT는 `rules/cross-vendor-routing.md`의 동원 매트릭스다. 요지: 결정적 교차벤더 게이트는 **main 직접**이 규범이고, 팀메이트는 교차벤더를 직접 부르지 말고 리드(main)에 요청한다. 판정·검토 산출물은 오케스트레이터가 회수해 반영(워커 외부 직접 쓰기 금지).

## 답변 처리 (Kinney 3부)

교차벤더 답을 받으면: ① 무엇을 물었나 ② 벤더 답변 **원문** ③ 어느 쪽을 더 신뢰하는지 판단. 조언자의 확신을 그대로 행동으로 세탁하지 않는다.
