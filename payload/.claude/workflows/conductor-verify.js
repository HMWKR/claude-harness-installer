export const meta = {
  name: 'conductor-verify',
  description: '지휘-검증-승인 오케스트레이션(견고판): 계획→Claude 적대 계획검수→병렬 실행→Claude 적대 1차검수→종합→Claude 독립 사전검증→main 승인용 번들. 교차벤더 codex 최종 게이트는 반환 후 main이 직접 수행(nested codex는 stall-prone이라 제외). 승인권=main, 검증증거=밖.',
  whenToUse: '멀티에이전트 실작업의 표준 파이프라인. "울트라워크"·"팀으로/병렬로"·"다관점 검증"·"종합 감사"·고위험 비가역 다단계 신호에 발동(CLAUDE.md 레이어서열 정합). args.task로 작업을 준다. 사소·단일스레드·단순질문은 제외. 고위험은 args.highStakes=true로 관점분산 검증. 반환 후 main이 codex MCP로 교차벤더 최종검증 필수.',
  phases: [
    { title: 'Plan', detail: 'main 지휘: 분해 + DoD(템플릿에서 선택)' },
    { title: 'PlanReview', detail: 'Claude 적대 계획·DoD 검수(재계획 1회)' },
    { title: 'Execute', detail: '병렬 teammates (이미지 서브태스크는 main 후처리 플래그: 생성=codex·시각 판정=main의 codex+critic)' },
    { title: 'Review1', detail: 'Claude 적대 1차검수(산출물별)' },
    { title: 'Synthesize', detail: 'main 종합·충돌 해소·불확실성 보존' },
    { title: 'Verify', detail: 'Claude 독립 사전검증(고위험=관점분산) — 최종 교차벤더 게이트는 main' },
    { title: 'Approve', detail: 'main 승인용 증거 번들 반환(codexGate=PENDING)' },
  ],
}

// ===== schemas =====
const PLAN = { type: 'object', additionalProperties: false, required: ['subtasks', 'dod', 'topology'], properties: {
  subtasks: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['id', 'brief', 'kind', 'parallelizable'], properties: {
    id: { type: 'string' }, brief: { type: 'string' },
    kind: { type: 'string', enum: ['code', 'analysis', 'image', 'image-analysis', 'research', 'doc'] },
    parallelizable: { type: 'boolean' } } } },
  dod: { type: 'array', items: { type: 'string' } },
  verifyCmd: { type: ['string', 'null'] },
  topology: { type: 'string', enum: ['pipeline', 'parallel', 'expert-pool', 'producer-reviewer'] },
  notes: { type: 'string' } } }

const VERDICT = { type: 'object', additionalProperties: false, required: ['approved', 'severity', 'issues'], properties: {
  approved: { type: 'boolean' }, severity: { type: 'string', enum: ['ok', 'warn', 'block'] },
  issues: { type: 'array', items: { type: 'string' } }, suggestions: { type: 'array', items: { type: 'string' } } } }

const REVIEW = { type: 'object', additionalProperties: false, required: ['verdict', 'issues'], properties: {
  verdict: { type: 'string', enum: ['pass', 'revise', 'fail'] },
  issues: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['summary', 'severity'], properties: {
    summary: { type: 'string' }, severity: { type: 'string', enum: ['low', 'med', 'high'] } } } } } }

const SYNTH = { type: 'object', additionalProperties: false, required: ['deliverable', 'decisions'], properties: {
  deliverable: { type: 'string' }, decisions: { type: 'array', items: { type: 'string' } },
  residualUncertainty: { type: 'array', items: { type: 'string' } } } }

const FINAL = { type: 'object', additionalProperties: false, required: ['verdict', 'dodResults'], properties: {
  verdict: { type: 'string', enum: ['go', 'no-go', 'go-with-caveats'] },
  dodResults: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['item', 'pass'], properties: {
    item: { type: 'string' }, pass: { type: 'boolean' }, evidence: { type: 'string' } } } },
  canaryDetected: { type: ['boolean', 'null'] }, caveats: { type: 'array', items: { type: 'string' } } } }

// ===== 적대 검수 프롬프트(독립 컨텍스트 Claude — nested MCP 없음, stall/지연 회피) =====
// ADV 워커(계획검수·1차검수·검증)는 전부 agentType: 'critic'으로 스폰한다 — 쓰기·크론·발송 도구가 없는
// 읽기전용 워커라서 "검증자는 외부에 직접 쓰지 않는다"가 도구 목록으로 집행된다(rules/agent-teams-boundaries.md)
const ADV = (role, what) => `당신은 ${role}다. 생성자와 독립된 회의적 시각으로 아래를 반박하라 — 동의 편향 배제, 진짜 결함만. 확신 없으면 보수적으로(revise/block) 판정. 검증주권(실행자가 자기 시험지 저작)·누락·과확장·엣지케이스를 특히 본다.\n\n대상:\n${what}`

// ===== 입력 =====
const task = (args && typeof args === 'object' && args.task) || (typeof args === 'string' ? args : null)
if (!task) { log('args.task 없음 — 중단'); return { error: 'no task (args.task 필요)' } }
const highStakes = !!(args && typeof args === 'object' && args.highStakes)
const constraints = (args && typeof args === 'object' && args.constraints) || ''
log(`conductor-verify(견고판) 시작 · highStakes=${highStakes}`)

// ===== 1. PLAN (main 지휘) =====
phase('Plan')
let plan = await agent(
  `당신은 오케스트레이터의 계획 노드다. 작업을 검증 가능한 서브태스크로 분해하고, DoD(완료기준)를 ~/.claude/verification-templates/ 유형(feature-impl·bugfix·refactor·review-qa)에서 골라 구체화하라(자유저작 최소화). 이미지 생성/편집은 kind='image'(반환 후 main이 codex로 생성), 이미지/스크린샷 시각·실사 판정은 kind='image-analysis'(반환 후 main이 codex·Claude critic 판정단으로 판정)로 표시. 독립 병렬 가능은 parallelizable=true.\n\n작업: ${task}\n제약: ${constraints || '(없음)'}`,
  { schema: PLAN, phase: 'Plan', label: 'plan' })
if (!plan) return { error: 'plan 실패' }

// ===== 2. PLAN REVIEW (Claude 적대, 재계획 1회) =====
phase('PlanReview')
let planOK = false
for (let k = 0; k < 2 && !planOK; k++) {
  const pv = await agent(ADV('계획 검수자', `계획+DoD를 반박:\n${JSON.stringify(plan)}`),
    { schema: VERDICT, phase: 'PlanReview', label: `plan-review#${k + 1}`, agentType: 'critic' })
  if (pv && pv.approved && pv.severity !== 'block') { planOK = true; break }
  if (k === 0) {
    log('계획 검수 미승인 — 접근 바꿔 재계획(1회)')
    const nextPlan = await agent(
      `이전 계획이 검수에서 반려됨. 지적을 반영해 접근을 바꿔 재계획하라. 지적: ${pv ? JSON.stringify(pv.issues) : '검수 실패'}\n원작업: ${task}`,
      { schema: PLAN, phase: 'PlanReview', label: 'replan' })
    if (nextPlan) plan = nextPlan
  }
}
if (!planOK) log('⚠ 계획 검수 미통과 — 증거 번들에 표기(main 재검토)')

// ===== 3. EXECUTE (병렬 teammates) =====
phase('Execute')
const subs = plan.subtasks || []
const execResults = await parallel(subs.map((st) => () => {
  const img = st.kind === 'image'
    ? '\n\n[이미지] 이 서브태스크는 이미지 자산이다. 가능한 산출물(SVG 코드 초안)을 직접 작성하되, **최종 이미지 생성은 반환 후 main이 codex MCP로 수행**(벡터·래스터 모두)하도록 필요한 사양(모티프·치수·제약)을 명확히 기술해 반환하라(cross-vendor-routing 규칙).'
    : st.kind === 'image-analysis'
      ? '\n\n[이미지 분석] 이 서브태스크는 이미지/스크린샷 판정이다. 분석 초안을 작성하되, **최종 시각·실사 판정은 반환 후 main이 codex·Claude critic 판정단으로 수행**하도록 판정 대상·기준을 명확히 기술해 반환하라(cross-vendor-routing 규칙).'
      : ''
  return agent(
    `서브태스크를 수행하고 산출물을 반환하라. result 원문 보존, 외부 파일 직접쓰기 금지(산출은 반환만).\n\n[${st.id}] ${st.brief}${img}`,
    { phase: 'Execute', label: `exec:${st.id}` })
}))

// ===== 4. REVIEW1 (Claude 적대 1차검수, 산출물별) =====
phase('Review1')
const reviews = await parallel(execResults.map((r, i) => () => {
  if (!r) return null
  const id = subs[i] ? subs[i].id : String(i)
  return agent(ADV('교차 검수자', `서브태스크 [${id}] 산출물을 실제 관점에서 반박(진짜 결함만):\n${String(r).slice(0, 6000)}`),
    { schema: REVIEW, phase: 'Review1', label: `review:${id}`, agentType: 'critic' })
}))

// ===== 5. SYNTHESIZE (main 종합·충돌 해소·불확실성 보존) =====
phase('Synthesize')
const execText = execResults.map((r, i) => `[${subs[i] ? subs[i].id : i}] ${String(r || '(null)').slice(0, 3000)}`).join('\n---\n')
const synth = await agent(
  `당신은 종합 노드다. 서브태스크 결과와 1차 검수를 통합해 최종 산출물을 만들어라. 충돌은 지우지 말고 [DECISION]으로 해소, 검수 지적 반영, 미해결 불확실은 residualUncertainty에 보존.\n\n결과:\n${execText}\n\n1차검수:\n${JSON.stringify(reviews)}`,
  { schema: SYNTH, phase: 'Synthesize', label: 'synthesize' })

// ===== 6. VERIFY (Claude 독립 사전검증; 고위험=관점분산) — 최종 교차벤더 게이트는 main =====
phase('Verify')
const deliverable = String((synth && synth.deliverable) || '')
let preVerify
if (highStakes) {
  const lenses = ['정확성', '보안·안전', '재현성·엣지케이스']
  const panel = (await parallel(lenses.map((L) => () =>
    agent(ADV(`${L} 렌즈 독립 검증자`, `통합 산출물을 DoD 대비 검증(각 DoD pass/evidence, 심은 함정=카나리 탐지).\nDoD: ${JSON.stringify(plan.dod)}\n산출물: ${deliverable.slice(0, 6000)}`),
      { schema: FINAL, phase: 'Verify', label: `verify:${L}`, agentType: 'critic' })))).filter(Boolean)
  const go = panel.filter((v) => v.verdict === 'go').length
  preVerify = {
    verdict: panel.length && go === panel.length ? 'go' : (go >= 2 ? 'go-with-caveats' : 'no-go'),
    dodResults: panel[0] ? panel[0].dodResults : [],
    canaryDetected: panel.some((v) => v.canaryDetected === true) ? true : null,
    caveats: panel.flatMap((v) => v.caveats || []),
    panelVerdicts: panel.map((v) => v.verdict),
  }
} else {
  preVerify = await agent(ADV('독립 검증자', `통합 산출물을 DoD 대비 검증(각 DoD pass/evidence, 심은 함정=카나리 탐지).\nDoD: ${JSON.stringify(plan.dod)}\n산출물: ${deliverable.slice(0, 7000)}`),
    { schema: FINAL, phase: 'Verify', label: 'pre-verify', agentType: 'critic' })
}

// ===== 7. APPROVE (main 승인용 번들; 교차벤더 codex 게이트는 main이 직접) =====
phase('Approve')
const hasImage = subs.some((s) => s.kind === 'image' || s.kind === 'image-analysis')
return {
  task,
  plan,
  deliverable: synth ? synth.deliverable : null,
  decisions: synth ? synth.decisions : [],
  residualUncertainty: synth ? synth.residualUncertainty : [],
  firstPassReviews: reviews,
  claudePreVerify: preVerify,
  planApproved: planOK,
  codexGate: 'PENDING',
  imageRoutingNeeded: hasImage,
  recommendation: preVerify ? preVerify.verdict : 'no-go',
  note: '이 번들은 Claude 사전검증까지다. **교차벤더 최종 게이트는 main이 직접 호출**한다(중첩 호출은 stall-prone — 2026-07-07 codex 스모크): codexGate = mcp__codex__codex(sandbox:"read-only")로 DoD 대비 독립 검증(고위험·시각/실사 판정은 관점이 다른 critic 판정단을 더한다 — grok 퇴역 2026-10-02). imageRoutingNeeded=true면 main이 kind=image는 codex 생성(벡터·래스터), kind=image-analysis는 codex·critic 판정으로 라우팅(영상은 로컬 Remotion — rules/cross-vendor-routing.md). 승인권=main, 검증증거=밖.',
}
