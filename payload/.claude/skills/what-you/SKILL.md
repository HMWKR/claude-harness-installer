---
name: what-you
description: |
  근거 기반으로 요청의 목적과 실행 구조를 깊게 도출하고, 최종 답뿐 아니라 중간의 증거·충돌·가정·대안·선택 이유·파이프라인·성공 기준·산출물까지 감사 가능한 Decision Trace로 남기는 심층 What 프레임워크. Use when the user invokes "$what-you" or "what-you", when a request matches the `what` skill triggers and additionally asks for "매우 깊게", "전체 과정", "사고 방식", "중간 도출", "파이프라인", "근거와 산출물", "왜 이렇게 결정했는지", or when a complex multi-document/project task needs a canonical MD and reproducible purpose-to-execution architecture. Prefer `what` for lightweight Why-What-How-So What framing and `what-ce` when the main need is CE prompt optimization. Not for requester personality profiling, simple knowledge questions, or verbatim private chain-of-thought disclosure.
---

# What-You

## Core Purpose

Turn an ambiguous or complex request into an evidence-backed, reviewable path from reality to purpose, execution, artifacts, and verified value.

`what-you` extends `what`; it does not profile the requester. Its distinctive output is the observable derivation process:

```text
Evidence
  → Interpretation
    → Alternatives
      → Decision
        → Execution architecture
          → Artifacts
            → Verification
```

Do not reveal hidden/private chain-of-thought. Externalize only useful, auditable reasoning: cited evidence, assumptions, concise rationale, rejected alternatives, confidence, risks, and decision history.

## Relationship to Other Skills

| Need | Skill |
|---|---|
| Lightweight purpose framing | `what` |
| Deep purpose-to-artifact derivation | `what-you` |
| Finalized purpose to CE prompt optimization | `what-ce` |
| Standalone context-engineering advice | `ce-advisor` |

Invocation priority:

1. Explicit `$what-you` or `what-you` always selects this skill.
2. A `what`-style request plus deep process, evidence, pipeline, or artifact requirements selects this skill.
3. An ordinary `what` trigger without those depth signals stays with `what`.
4. If the user wants prompt optimization after this workflow, produce the Handoff Object and bridge to `what-ce`; do not duplicate its CE phases.

## Announce

At the start, say:

> "What-You 심층 도출을 시작합니다. Evidence → Why → What → How → So What → Decision Trace → Artifact/Handoff 순서로 진행하며, 결과뿐 아니라 근거·대안·선택 이유를 검증 가능한 형태로 남기겠습니다. 각 주요 단계에서 확인을 받겠습니다."

If resuming:

> "기존 What-You 기준 문서를 읽고 마지막 승인 게이트부터 이어갑니다. 확정 내용은 유지하고 새 근거로 바뀌는 부분만 변경 로그에 기록하겠습니다."

## Question Gate Runtime

Use a Question Gate at every proposal, confirmation, approval, mode choice, scope choice, step transition, artifact-write choice, execution choice, tool choice, safety boundary, or external-write decision.

### Stage Output Delivery — MUST, before any gate

**Every stage's output must reach the user's screen before its gate asks for a decision.**

Claude Code display rule (2026-08-09, verified in session): text emitted before a tool call in the same turn may not render, and a question dialog occupies the screen. So stage output followed by `AskUserQuestion` in one turn makes the user answer blind — they see options for an analysis they never saw.

Therefore, in Claude Code:

1. Each stage's output MUST be the final text of its turn — **no tool calls after it**.
2. Present the gate as a **Text Gate**: numbered options at the end of that same final message. The user's chat reply is the gate selection.
3. `AskUserQuestion` is allowed ONLY for short, self-contained gates whose full context fits inside the question text itself (e.g., a one-line safety confirmation). Never call it in the same turn as substantial stage output.

### Gate form by runtime

| Runtime | Default gate form |
|---|---|
| Claude Code (CLI/desktop) | Text Gate (above) — dialog only for short self-contained gates |
| Codex (`request_user_input` available) | Question tool dialog |
| No user available (AFK/autonomous) | Autonomous exception below |

### Gate mechanics (all forms)

- Put the recommended option first and label it `(Recommended)`.
- Give every option one short impact sentence.
- Do not continue until the user selects an option; a chat reply (number or words) counts for Text Gates.
- If the user's reply answers a different question or reports a problem, treat it as gate feedback — resolve it first; never consume it as a selection.
- If neither a question tool nor chat interaction is possible, stop with `Question Gate cannot be satisfied`.
- Q4 always overrides auto-run or prior broad approval.
- Autonomous/AFK exception (Claude harness alignment): if the user is unavailable and the gate is Q3 (not Q4), state the assumption in one line, record it as `proposed` in the Decision Ledger, and continue. Q4 gates never auto-pass — stop and report instead.

### Skill-Specific Gates

| Gate | Level | When | Recommended path |
|---|---:|---|---|
| `what-you-evidence` | Q3 | Evidence/Conflict Map complete | Confirm evidence and continue |
| `what-you-why` | Q3 | Why Ladder complete | Confirm Why |
| `what-you-what` | Q3 | What Architecture complete | Confirm What |
| `what-you-how` | Q3 | How Architecture complete | Confirm How |
| `what-you-so-what` | Q3 | Value and success system complete | Confirm So What |
| `what-you-artifact` | Q3 | Before creating/updating a canonical local artifact | Write one canonical MD |
| `what-you-handoff` | Q3 | Before execution or another skill handoff | Execute with tracked stages |
| `what-you-safety` | Q4 | Before destructive action, production change, credential use, external write, deploy, or real sub-agent execution | Use the safest scoped action |

**Iron Law:** Never silently advance a major stage or overwrite a previously approved decision.

## Modes

### Deep — Default

Use for multi-document, multi-stakeholder, strategic, brand, architecture, or cross-channel tasks.

- Build a complete Evidence Ledger.
- Trace Why at least three meaningful levels when supported.
- Compare at least two viable alternatives.
- Produce execution dependencies, gates, risks, artifacts, and success metrics.
- Recommend a canonical MD for work spanning three or more stages.

### Standard

Use when evidence is limited and the task is bounded.

- Preserve the complete workflow.
- Keep each Derivation Record short.
- Produce one alternative comparison and a compact Handoff Object.

### Resume

Trigger with `--resume <path>` or a referenced prior What-You artifact.

1. Read the whole current-state, decisions, open issues, and change log.
2. Identify the last approved gate.
3. Revalidate only facts likely to have changed.
4. Continue from the next unapproved stage.

If the user asks for a fast purpose frame, recommend `what`; do not degrade `what-you` into an untraceable shortcut.

## Required Reading

- For Deep mode, read [methodology.md](references/methodology.md) before Stage 0.
- Before creating a canonical artifact or Handoff Object, read [templates.md](references/templates.md).
- Do not load either reference for a simple routing decision.

## Core Invariants

1. **Reality before purpose** — inspect current state before deriving goals.
2. **Evidence before inference** — cite the source of every material conclusion.
3. **Fact and aspiration separation** — never merge current truth with future promise.
4. **Conflict visibility** — surface contradictions instead of averaging them away.
5. **Alternatives before commitment** — compare credible paths at decision points.
6. **Purpose hierarchy** — cultural/strategic Why outranks temporary visual or technical fashion.
7. **Sequential reversibility** — isolate stages so rejected work does not contaminate later work.
8. **Artifact continuity** — persist approved decisions for long or multi-session work.
9. **Verification before completion** — compare outputs to So What and Definition of Done.
10. **No fabricated certainty** — label confidence and unresolved questions.

## Information Pipeline

Collect information in this order:

| Priority | Source | Rule |
|---:|---|---|
| 1 | Current conversation | Capture explicit intent, approvals, corrections, and vocabulary |
| 2 | Project state | Read AGENTS.md, handoffs, manifests, actual files, code, logs, and artifacts |
| 3 | Primary/official sources | Use standards, first-party docs, research, or live verification when needed |
| 4 | User question | Ask only when remaining uncertainty would materially change the result |

For large source sets, do not keep everything active. Build stage-specific Context Packs and retain only source pointers plus approved conclusions in the canonical document.

## Output Contract: Derivation Record

Every major stage must include:

```text
Stage:
Decision sought:
Evidence used:
Observed conflicts:
Interpretation:
Alternatives considered:
Proposed decision:
Why this option:
Confidence:
Open issues:
Artifact impact:
Next gate:
```

Keep `Interpretation` and `Why this option` concise and decision-relevant. Do not simulate an unrestricted internal monologue.

## Workflow

### Stage 0 — Intake and Reality Boundary

1. Restate the objective in one sentence.
2. Identify the requested output, actual decision to be made, stakeholders, scope, and non-goals.
3. Inspect project instructions and session continuity files.
4. Determine complexity, reversibility, evidence volume, and external-action risk.
5. Choose Deep, Standard, or Resume mode.
6. Propose whether a canonical MD is needed; use `what-you-artifact` before writing it.

Output:

- Request Frame
- Scope and Non-goals
- Source Plan
- Mode
- Safety Boundary

### Stage 1 — Evidence and Conflict Map

1. Inspect real files, code, logs, prototypes, and existing artifacts before naming conclusions.
2. Record material evidence using:
   - `Fact`
   - `Promise`
   - `Hypothesis`
   - `Legacy`
   - `Conflict`
3. Rank source authority and recency.
4. Separate current state, target state, and historical state.
5. Build a conflict map and state which conflicts must be resolved before design or execution.
6. Produce the Derivation Record.
7. Stop at `what-you-evidence`.

Do not solve the task while evidence boundaries are still unstable.

### Stage 2 — Why Ladder

Derive purpose in layers:

```text
Surface request
  → Functional reason
    → User/organizational outcome
      → Strategic reason
        → Cultural or identity-level belief, when genuinely supported
```

For each layer:

- Tie it to evidence.
- Mark inference strength.
- Stop when another “why” would become speculative or tautological.
- Test the deepest Why against observed product/project behavior.
- Include a short phrase and a full statement.
- Stop at `what-you-why`.

### Stage 3 — What Architecture

Translate the approved Why into a target system:

- Core outcome
- Workstreams
- Required artifacts
- In-scope and out-of-scope
- Current-to-target delta
- User-visible and organizational outcomes
- Non-goals
- Definition of the target state

Avoid defining What as a list of disconnected deliverables. Show how the parts form one system.

Compare at least two scope architectures when the boundary is consequential. Stop at `what-you-what`.

### Stage 4 — How Architecture

Design an executable and verifiable pipeline:

1. Identify relevant real-world methodologies or official standards before assigning expert roles.
2. State methodology sources, applied method, non-goals/limits, and verification standard.
3. Break work into phases with dependencies and reversible gates.
4. Separate exploration, selection, refinement, implementation, and verification.
5. Define Context Packs for each phase.
6. Define tools, inputs, outputs, write set, and validation.
7. Compare at least two execution paths.
8. Document failure conditions and rollback/backtrack routes.
9. Stop at `what-you-how`.

If agents or teams are proposed, do not spawn them without explicit user intent and the Q4 safety gate.

### Stage 5 — So What and Success System

Define what changes if the work succeeds:

- User value
- Product/project value
- Organizational value
- Business or cultural value
- Leading indicators
- Lagging indicators
- Quantitative acceptance targets where defensible
- Qualitative tests
- Immediate rejection conditions
- Non-success examples
- Definition of Done

Trace each value back to the approved Why. Flag any success metric that can be achieved while violating the Why. Stop at `what-you-so-what`.

### Stage 6 — Decision Trace and Artifact Architecture

Compile the approved stages into:

- Decision Ledger
- Rejected Alternatives
- Risk Register
- Context Architecture
- Artifact Tree
- Quality Gates
- Change Log
- Current Decision State

For work spanning three or more stages, recommend one canonical MD rather than scattered notes. Use the template reference and stop at `what-you-artifact` before the first write unless the user already explicitly requested that local artifact.

### Stage 7 — Handoff and Execution Choice

Produce:

```text
What-You Handoff Object
├── Purpose Frame
├── Evidence Boundaries
├── Goal
├── Outputs
├── Inputs
├── Constraints
├── Evaluation
├── Risks
├── Context Architecture
├── Decision Trace
├── Artifact Plan
└── Next Safe Action
```

Offer:

1. Execute with tracked sequential stages.
2. Hand off to `what-ce` for CE prompt optimization.
3. Export the Handoff Object only.
4. Backtrack to a named stage.

In the same final message, also present the **goal gate** (never skipped; ask it plainly — "goal을 설정할까요, 하지 말까요?"):

- A. Create a goal via fablize `goals.py create` — What becomes `--brief`, the So What success criteria become `--goal`; completion then requires verification evidence.
- B. Present a ready-to-run native `/goal <condition>` line — for a hard Stop-hook block; the user runs it themselves.
- C. Proceed without a goal — mark `(Recommended)` when the work is single-step or pure analysis.

Answer format: `"1-A"`, `"3-C"`. On A, run `goals.py create` before execution starts. Autonomous/AFK exception: multi-step work falls back to A with a one-line recorded assumption; single-step or pure analysis falls back to C.

Stop at `what-you-handoff`.

### Stage 8 — Post-Execution Audit

After execution:

1. Compare actual artifacts against So What, rejection conditions, and Definition of Done.
2. Record passed, partial, failed, and unverified criteria.
3. Update the Decision Ledger and Change Log.
4. Report residual risks and the smallest next action.
5. Never declare completion with required unverified criteria.

## Backtrack Protocol

When later evidence invalidates an approved stage:

1. Name the exact conflict.
2. Identify the earliest affected stage.
3. Present:
   - Backtrack and reset downstream decisions `(Recommended when material)`
   - Preserve the decision with an explicit exception
   - Stop and export current state
4. If backtracking, mark downstream decisions `invalidated`; do not silently rewrite history.
5. Re-run only affected stages and append the change reason.

After two material backtracks, propose a root reframing instead of continuing incremental patches.

## Anti-Failure Controls

### Poisoning

- Isolate Legacy and low-authority evidence.
- Preserve provenance for every approved claim.
- Never allow a polished draft to become evidence for its own correctness.

### Distraction

- Use one Context Pack per stage.
- Keep the canonical MD as the decision index, not a dump of all source content.
- Move detailed supporting material to referenced artifacts.

### Confusion

- Maintain a glossary for overloaded terms.
- Separate facts, desired outcomes, execution methods, and artifacts.
- Keep one active decision per gate.

### Clash

- Apply this precedence:

```text
Explicit user decision
  > Safety and project instructions
    > Verified current reality
      > Approved Why and success system
        > Methodology and channel needs
          > stylistic preference or temporary trend
```

When two higher-priority constraints conflict, stop and ask; do not average them.

## Completion Criteria

The skill is complete only when:

- Evidence boundaries are explicit.
- Why, What, How, and So What are individually approved.
- The intermediate Decision Trace is usable without private chain-of-thought.
- Alternatives and rejection reasons are recorded.
- The execution pipeline has dependencies, gates, and verification.
- The artifact set and current state are discoverable.
- Actual results are audited against the approved success system.

## Never

- Never use `what-you` to infer personality, identity, health, politics, or other sensitive traits.
- Never invent evidence to make a purpose frame feel complete.
- Never hide conflicts to preserve narrative neatness.
- Never expose or claim to expose verbatim hidden chain-of-thought.
- Never continue past a required gate without the user's selection.
- Never perform destructive, production, credential, external-write, deploy, or real sub-agent actions without Q4 approval.
- Never let the canonical artifact and chat state diverge after a material approved change.
