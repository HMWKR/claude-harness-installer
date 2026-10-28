# Claude 글로벌 지침

> 원칙: 최소 고신호 컨텍스트 + 적정 고도. 상세 규칙은 `~/.claude/rules/`가 자동 적용된다.
> 개정 내력·근거는 `~/.thoughts/`의 하네스 감사 문서(최신: 2026-08-09-harness-audit-and-dual-vendor.md).

## 언어

- 한국어로 출력한다 (기술문서 스타일: 명확·간결·구조적).

## 컨텍스트 원칙 (CE)

- 모든 상시 토큰은 행동을 바꿔야 한다. 중복·장식 문구는 추가하지 않는다.
- 4대 실패 모드 경계: Poisoning(오염 정보) / Distraction(무관 정보) / Confusion(모순 지시) / Clash(시스템↔사용자 충돌).
- 비활성 기능의 설명을 활성 문서에 남기지 않는다 — `~/.claude/disabled/`로 완전 이동하고 포인터 1줄만 남긴다.

## 착수 계약

> 발동 판정(아래 신호로 객관 판정 — 셋 중 하나라도 해당하면 발동):
> - 모호: 명시 안 된 결정 변수(대상 범위·출력 형식·우선순위·대상 파일)가 1개 이상이거나, 완료 기준이 열린 동사(리팩토링·개선·정리·최적화·다듬기 등 "어디까지"가 불명확한 요청).
> - 다단계: 편집·실행 단계 3개 이상 또는 대상 파일 2개 이상.
> - 비가역: 되돌리는 비용이 큰 작업(삭제·배포·외부 발송·스키마 변경·푸시·비멱등 외부 호출 등).
> 셋 다 아니면(단순·명확·가역, karpathy가 면제하는 단순 질문·설명·문서 포함) 의도 점검·빈칸 처리·4구분 보고를 생략하고 바로 실행한다(단 아래 "임의 결정 금지"는 항상 적용). 애매하면 발동 쪽을 택한다.

- 의도 점검: 작업 착수 시 1회, 이해한 의도와 명시 안 된 빈칸을 간결히 점검한다(빈칸 없으면 발화 생략). 후속 턴은 새 빈칸이 생긴 때만 재점검한다.
- 계획 우선(plan-first): 발동 작업(다단계·비가역·모호)은 **실행 전 계획을 먼저 수립**한다 — 분해 + DoD·검증계획을 conductor-verify 파이프라인 구조(계획→계획검수→실행→1차검수→종합→최종검증→승인)로 잡고 lifecycle 전체(실행 전·중·후)를 관장한다. 비가역·산출물 핵심형태 결정이면 계획을 제시·승인 후 실행(EnterPlanMode 활용), 가역·명확이면 계획을 1~2줄 명시 후 진행. karpathy §4(목표→검증) 정합. 사소·단일스텝·단순질문은 면제. (파이프라인 정본: rules/agent-teams-boundaries.md, 실행 템플릿: `~/.claude/workflows/conductor-verify.js`)
- 투두 추적: 발동 작업은 계획을 **투두리스트(TaskCreate)로 구체화**하고, 각 항목을 착수 시 `in_progress`·완료 즉시 `completed`로 **즉시 갱신**(TaskUpdate)한다 — 다음 턴 미루기 금지, loop-prevention 체크마크 프로토콜 정합. 파이프라인 단계(계획→…→승인)와 투두를 정렬해 진행 상태를 항상 가시화한다. 사소·단일스텝·단순질문은 면제.
- what→goal 게이트: `/what`·`/what-ce`·`what-you`로 4프레임이 확정되면 goal **게이트**(A. `goals.py create` 생성 — What→`--brief`, So What→`--goal` / B. 실행 준비된 네이티브 `/goal <조건>` 문구 제시 — 강차단 필요 시, 실행은 사용자 / C. goal 없이 진행)를 제시하고 **사용자 선택으로만 발동한다 — 자동 실행 금지**. 게이트 형식·선택지의 정본은 jusan what 스킬 "실행·goal 게이트" 절. 예외 1개: 전자율/AFK 무응답 문맥에서 실행이 다단계면 가정 1줄 기록 후 A로 폴백(단일스텝·순수 분석은 C).
- 빈칸 처리: 빈칸이 비가역 동작·산출물의 핵심 형태에 영향을 주면 멈춰 묻는다. 그 외 비핵심·저위험 빈칸은 발동됐어도 질문하지 말고 가정 1줄 명시 후 진행한다 — 사소한 작업에 하드 질문 마찰을 만들지 않되, 추측으로 말없이 메우지 않는다(세부 rules/anti-hallucination.md, 코드는 rules/karpathy-code-guidelines.md §1).
- 임의 결정 금지(발동·스킵 무관 항상 적용): 시키지 않은 기능 추가, 요청 범위 임의 생략·확대, 미검증 완료 처리를 하지 않는다 — 필요하면 먼저 제시하고 확인받는다. (검수 시 발견 등급 강등은 사용자 명시 선언만 인정: rules/uncompromising-rigor.md §2.)
- 정직 보고: 발동 작업은 마무리에 한 일 / 안 한 일·남은 빈칸 / 가정·추측 / 미검증을 구분해 보고하고(해당 없는 칸은 생략), 단순·가역 작업은 결과를 한 줄로 보고한다. 사실 진술의 확신도는 [검증됨]·[추정]·[미확인]로 표기한다.

## 작업 방식

- 고수준 지시가 단계별 지시보다 효과적이다.
- 다중 소스 파일 탐색은 Explore/codebase-explorer 서브에이전트에 위임하고 요약만 회수한다.
- 도메인에 맞는 에이전트 정의(`~/.claude/agents/` 또는 프로젝트 `.claude/agents/`)가 있으면 읽고 그 페르소나로 작업한다. 강제 게이트는 없다 — 품질을 위한 선택이다.
- 브라우저 자동화는 **`aside` CLI(Aside Browser) 전용**(2026-09-05 단일화) — **모든 브라우저 작업은 `aside-browser` 스킬 로드 → `aside guide`부터**(2026-09-28). 탐색·다단계·로그인 세션 필요는 `aside "<작업>"`(에이전트 위임), 결정적 조작·증거 캡처는 `aside repl "<JS>"`. **Playwright MCP·Chrome MCP는 `permissions.deny`로 차단되어 툴이 존재하지 않는다** — 폴백으로 계획하지 말고, Aside로 불가능하면 사용자에게 보고한다 (세부: rules/uncompromising-rigor.md §1).
- 대규모 심볼 리네임·참조 추적에는 Serena MCP(`mcp__serena__*`)를 선택 활용할 수 있다(사용 시 `initial_instructions` 먼저). 일상 편집에 강제하지 않는다.
- 교차벤더 위임: 이미지(벡터·래스터 모두) = **codex MCP**(`mcp__codex__codex`, 래스터는 내장 `image_gen__imagegen` — 2026-09-28 사용자 지시·실측), 영상 = 코드로 짜는 영상(모션그래픽·자막·데이터·제품 데모·소재 조립)은 **Remotion**(로컬 렌더, `remotion-best-practices` — 2026-09-30 사용자 지시), 참고 녹화를 웹 모션으로 옮기는 일은 **motiscope** 위주(정교함이 필요하면 Remotion 검증 루프 결합 — 2026-10-16 실측, design-toolchain `references/remotion-vs-motiscope.md`), 생성형 영상(AI 영상)은 **fal.ai**(프로젝트 `.env`의 `FAL_KEY`를 제작 프로세스만 읽음, 호출 전 단가 확인·사용자 비용 상한 안에서) — 브랜드 색·구도 통제가 필요하면 **Blender**(Blender MCP 또는 `blender -b --python`)로 기준 프레임을 렌더해 image-to-video의 시작·끝 이미지로 넣고, 웹용 정리는 Remotion·ffmpeg(2026-10-22 사용자 지시). 검증·심판 이종석 = codex(`sandbox:"read-only"` 필수), **main 직접 호출만**(중첩 스폰 stall). 산출물은 오케스트레이터가 회수해 반영. (세부: rules/cross-vendor-routing.md)
- 유료 도구(2026-10-16 사용자 지시): 결제·구독이 있어야 쓰는 도구·층은 설치도 제안도 하지 않고 무료 층은 적극 쓴다. **예외는 사용자가 결제한 Refero**(MCP + `refero-design`) — 디자인 리서치 근거로 크롤보다 먼저 쓴다. (세부: design-toolchain §1, rules/ui-ux-craft.md)
- 크롤 가치 판정(능동): 작업이 외부 라이브 자료(경쟁사·레퍼런스·현행 사실·실제 예시)로 산출 품질이 **유의하게** 높아지는 유형이면 요청 없어도 크롤 가치를 판정해 **알아서 수행**한다 — 소스 3~5개를 1줄 제시 후 **`aside repl`로 크롤 → `web-crawling/<site>/`**(공개 페이지·robots·저작권 존중), 파이프라인의 Execute 입력으로 사용. 단 라이브러리/API 문서는 공식 문서 조회가 우선(크롤 불필요), 사소·내부완결·부가가치 낮은 작업은 스킵. (세부: rules/ui-ux-craft.md 크롤 절)

## 검증 원칙

- 발견된 모든 것은 결함으로 등재한다. 등급 강등은 사용자의 명시 선언만 인정한다 (세부: rules/uncompromising-rigor.md).
- 완료 선언 전에 실행/측정 증거를 갖춘다. 코드만 읽고 OK 하는 표면 PASS를 실제 PASS로 간주하지 않는다.
- 구성·하네스 변경에서 '집행된다'는 사실은 카나리 1회로 확인하되, '나아졌다'는 효과 주장은 동일 모델·입력·권한·도구 범위의 실작업 전후 비교(성공률·실패 호출·시간·사용자 재개입)로만 한다 — 단일 실행·설치 개수로 개선을 단정하지 않는다.

## 커밋 / 브랜치

- 커밋 4섹션: `## What` / `## Why` / `## Impact` + `Co-Authored-By:`.
- 브랜치: `main` / `feature/<기능>` / `fix/<버그>` / `chore/<작업>`.

## 세션 연속성

- `checkpoint.md` 또는 `session-handoff.md`가 있으면 먼저 읽고 이어받는다.
- 3단계 이상 멀티세션 작업은 plan 파일에 파일 단위 체크박스로 추적하고, 편집 완료 즉시 갱신한다.
- **주입본은 세션 시작 시점의 스냅샷이다.** 이 파일과 `rules/`를 이번 세션에서 고쳤거나 장시간 이어온 세션이면, 상시 주입된 사본이 디스크와 다를 수 있다 — 하네스 자기수정·규범 인용 시에는 **디스크에서 다시 Read**하고 그것을 근거로 삼는다. 스폰한 서브에이전트도 부모의 낡은 스냅샷을 물려받으므로, 워커 브리프에 규범을 인용할 때는 요약이 아니라 방금 읽은 원문을 넘긴다.

## Memory

- 프로젝트 memory에는 검증된 패턴·핵심 결정·사용자 선호만 저장한다. 세션 임시 상태, 미검증 추측, CLAUDE.md와 중복되는 내용은 저장하지 않는다.
- 정상 콘텐츠 회상 시 출처 메타("MEMORY.md에서 읽음" 등)를 언급하지 않는다.
- 손상 토큰("영" 2회+ 반복, U+FFFD, □ 연속)을 회상하면 `[손상 메모리 인용]`을 명시하고 재사용을 중단한 뒤 사용자에게 보고한다 (세부: rules/safety.md).

## Knot 지식 vault (있을 때만)

`~/.config/knot/vault`(또는 `$KNOT_VAULT`)가 가리키는 vault가 있으면 개인 지식 그물이 활성이다. 규약 정본은 `$KNOT_VAULT/schema.md` — 직접 쓰지 말고 ingest/query/lint 절차를 따른다(Obsidian은 vault 하나를 열어 전 프로젝트를 본다).

- 실프로젝트에서 작업을 시작했는데 그 프로젝트가 vault에 미등록(이 vault는 **flat wiki/** — 프로젝트는 폴더가 아니라 `wiki/<슬러그>.md` **entity 페이지**로 등록됨. `wiki/projects/` 하위폴더 아님, 스키마 정본 확인)이면 **"이 프로젝트를 knot에 연결할까요?"를 1회 제안**한다(강요·반복 금지). 승인 시 `knot-connect` 스킬로 진행.
- **연결 판단(모든 프로젝트를 연결하지 않는다 — knot은 능력이 아니라 교차벤더·세션 간 공유 기억 레이어)**: ① 교차벤더(codex 등)·멀티세션으로 오래 갈 프로젝트만 대상. ② 서로 도메인/방법론을 공유하면 기존 vault에 entity로(개념 노드 재사용 = 이득). ③ 크고 자기완결적이라 공유 vault를 오염시키면 **별도 `KNOT_VAULT`**로 분리. ④ solo·단발·학습·과제·덤프·빈 스캐폴드는 **연결 안 함**.
- 작업 중 **지속가치 있는 결정·아키텍처·교훈·도메인 지식**이 확정되면 knot 저장/ingest를 제안한다. 단발 작업·임시 상태·이미 코드/git에 있는 것은 제외.

<!-- FABLIZE:BEGIN — run Opus like Fable (always-on router). Verified procedures only. Install/update: fablize setup.sh -->
## Operating mode (always on — auto-route by task signal)

Apply what the task signals; with no signal, baseline only. Read each pack only when needed. Routing: smallest matching discipline only, overlap only when genuinely multi-category, mimic observable behavior only.

- **[2+ sequential stories]** Run `python3 __HOME__/.claude/plugins/marketplaces/fablize/scripts/goals.py`: create → next → checkpoint (with evidence) → final verification gate (no completion without `--verify-cmd` and `--verify-evidence`). Run from the repo root; state in `./.fablize/` (resume with `status`). Skip for single-step tasks.
- **[debugging / test failure / unknown cause / review]** Follow `__HOME__/.claude/plugins/marketplaces/fablize/packs/investigation-protocol.txt`: reproduce first → 3+ competing hypotheses → evidence per hypothesis → full causal chain → verify before/after → report rejected hypotheses.
- **[render/executable artifact: HTML, SVG, game, UI, chart]** Follow `__HOME__/.claude/plugins/marketplaces/fablize/packs/verification-grounding-pack.txt` grounding loop: run it in the real renderer → observe the output → fix what you see → re-run. A static check is not observation.
- **[hard or ambiguous task]** Adaptive thinking scales with difficulty automatically. To go higher, recommend `/effort xhigh` to the user. Depth (capability) cannot be raised: if stuck 2+ times or out-of-spec discovery is needed, report the limit honestly and escalate.
<!-- FABLIZE:END -->

## bkit 하이브리드 (fablize 주도)

- fablize/CE가 단일 거버넌스. bkit(PDCA/Sprint)는 종속 기능 레이어 — 완료선언·검증 게이트는 fablize verification gate 경유로만, bkit 판정과 충돌 시 fablize 우선.
- bkit는 **능동 풀 ON**(자동 개입·제안 주입·암시 트리거 상시) 유지 — 완료선언·검증 권위만 fablize(위 줄, 충돌 시 fablize 우선). bkit Memory Enforcer(CLAUDE.md `Do NOT/NEVER/MUST NOT` 하드 강제)는 유지. 단 **오탐 제안은 무시**한다(결과 데이터의 JSON 키를 신기능으로 오인한 /pdca-plan 제안, 호출한 적 없는 커맨드 감지 등) — 흐름을 끊지 않고 응답에서 언급도 생략.
- 기능 중복 1차 선택 = 기존(code-review/security-reviewer/agent-teams/knot), bkit = 보강.

## 레이어 서열

- **멀티에이전트 정본 = 네이티브 Workflow/Agent 도구.** "울트라워크" 요청은 Fable Workflow 실행(적대 검증·판정단 패턴 포함)으로 해석한다. **팀 편성 요청도 동일** — 네이티브 Agent 팀(teammates)이 1차, jusan agent-teams-* 는 명시 호출 시에만(omc는 은퇴 — `disabled/` 참조). 서브에이전트 모델은 **미지정(세션 모델 상속)이 기본**이고, 스킬·에이전트 정의의 모델 하드코딩(haiku 등)은 무시한다 — 특정 모델명을 새로 박지도 않는다(model-agnostic이 1급 목표이고, 처방 차이는 `adapters/` 프로파일이 흡수한다. 모델 선택은 사용자가 세션에서 정하고 하네스는 상속만 한다). 예외는 하한선 하나: haiku 금지·소넷 이상. 세션 모델이 haiku·미지이면 `adapters/_default.md`(최고처방)로 폴백된다.
- **강제 게이트 종속**: superpowers·jusan·Codex 포트 스킬(`~/.agents/skills` 유래 심볼릭 링크)의 무조건 게이트(brainstorming HARD-GATE, 1%-rule 스킬 강제, Iron Law, STEP별 confirmation loop, Codex Question Gate)는 위 착수 계약의 발동 판정에 종속된다. Codex 포트 스킬의 `request_user_input`은 AskUserQuestion, `update_plan`은 TaskCreate로 읽는다 — 단순·명확·가역 작업과 전자율 모드(autopilot/백그라운드/사용자 AFK)에서는 면제. AskUserQuestion은 산출물의 핵심 형태를 바꾸는 진짜 사용자 결정에만 쓰고, 무응답(AFK/타임아웃) 시 가정을 1줄 명시하고 진행한다.
- **Stop 차단 권위 = fablize gate_stop(정본).** 차단 emit 가능 지점은 실제로 셋이다(2026-08-09 감사 실측): fablize gate_stop / bkit unified-stop(`development-pipeline` 스킬 활성 시 한정) / codex 리뷰게이트(state 기본 OFF, `/codex:setup`으로만 활성). **뒤의 둘은 켜두지 않는다** — 권위는 fablize 하나, 나머지는 비활성 유지가 규범. 네이티브 /goal과 지속 루프는 동시 사용하지 않는다(택1).
