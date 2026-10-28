# What-You Methodology

## Contents

1. Complexity calibration
2. Evidence ledger
3. Conflict resolution
4. Why depth
5. What architecture
6. How architecture
7. Success system
8. Decision trace
9. Context packs
10. Transparency boundary

## 1. Complexity Calibration

Score each dimension from 0 to 2.

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Source volume | Conversation only | Several files | Multi-system or large corpus |
| Conflict | None | Some ambiguity | Competing truths or eras |
| Stakeholders | One | Several aligned | Several with different incentives |
| Channels | One output | Several related | Product/business/brand cross-channel |
| Reversibility | Easy | Moderate | Expensive, public, or structural |
| Uncertainty | Low | Medium | Core goal/category unresolved |

- `0–3`: route to `what` unless the user explicitly invoked `what-you`.
- `4–7`: Standard What-You.
- `8–12`: Deep What-You with canonical artifact and complete gates.

The score selects depth; it does not replace user preference.

## 2. Evidence Ledger

Use a table:

| ID | Type | Claim | Source | Authority | Recency | Confidence | Affected decision |
|---|---|---|---|---|---|---|---|

Types:

- `Fact`: directly observed current state.
- `Promise`: approved but not yet realized target.
- `Hypothesis`: plausible and testable, not confirmed.
- `Legacy`: historical decision or artifact.
- `Conflict`: two sources cannot both govern the same decision.

Rules:

- Cite actual paths, symbols, pages, logs, or official URLs.
- Summarize sources; do not paste large documents into the ledger.
- A generated proposal is never a Fact.
- Mark stale evidence rather than deleting it.

## 3. Conflict Resolution

Resolve conflicts using:

1. Explicit recent user decision
2. Applicable safety/project instruction
3. Observed current behavior
4. Approved current specification
5. Recent business intent
6. Historical artifact
7. External analogy or trend

For each conflict, record:

```text
Conflict:
Competing evidence:
Decision affected:
Precedence rule:
Resolution:
Residual risk:
```

Do not resolve value conflicts only by source recency. A recent artifact may still contradict the approved Why.

## 4. Why Depth

Use a Why Ladder, not a fixed number of “why” questions.

### Layer tests

- **Surface**: What was requested?
- **Functional**: What immediate problem changes?
- **Outcome**: Who can act differently?
- **Strategic**: What durable advantage or capability appears?
- **Cultural/identity**: What belief about how the world should work is expressed?

Stop when:

- the next layer has no evidence;
- the answer becomes generic (“to succeed”, “to be better”);
- the answer merely repeats the prior layer;
- a different stakeholder would give a materially different answer.

When stakeholders differ, create parallel Why branches and identify the governing branch.

## 5. What Architecture

Use a system map:

```text
Core outcome
├── Capability/workstream A
│   ├── artifact
│   └── acceptance condition
├── Capability/workstream B
└── Shared operating layer
```

Check:

- Does every workstream serve the Why?
- Is an artifact mistaken for an outcome?
- Does the scope contain mutually incompatible target states?
- What must explicitly remain unchanged?
- What is deliberately postponed?

Compare scope options using impact, risk, dependency, cost, and reversibility.

## 6. How Architecture

Separate:

1. Discovery and evidence
2. Strategy and decisions
3. Exploration
4. Selection
5. Refinement
6. Implementation
7. Verification
8. Operation and governance

For each phase:

| Field | Required content |
|---|---|
| Input | Approved evidence/context pack |
| Method | Real methodology or standard |
| Action | Bounded work |
| Output | Reviewable artifact |
| Gate | User or evaluator decision |
| Failure | Observable fail condition |
| Recovery | Backtrack or rollback |

### Expert methodology hook

Before naming an expert or agent:

1. Identify the actual professional problem.
2. Find internal, official, standard, or authoritative methodology sources.
3. State `Methodology sources`, `Applied methodology`, `Non-goals/limits`, and `Verification standard`.
4. Only then map a role or execution agent.

## 7. Success System

Build a value chain:

```text
Artifact quality
  → comprehension/behavior change
    → operational adoption
      → business or cultural outcome
```

Separate:

- Leading metrics: immediate comprehension, quality, adoption signals.
- Lagging metrics: revenue, retention, cycle time, organizational learning.
- Acceptance tests: binary or threshold-based.
- Rejection conditions: immediate failures even if aggregate score is high.
- Non-success: attractive outcomes that do not satisfy the Why.

Label proposed thresholds as proposed until a baseline exists.

## 8. Decision Trace

A Decision Trace is not a transcript of internal thought. It is the minimum record required for another reviewer to reproduce or challenge a decision.

Use:

| ID | Decision | Evidence | Alternatives | Reason | Confidence | Approver | Date | Downstream impact |
|---|---|---|---|---|---|---|---|---|

Record a rejected alternative when it was credible enough to change scope, cost, risk, or meaning.

Do not record:

- token-by-token deliberation;
- speculative associations with no decision impact;
- sensitive inferred user traits;
- redundant narration of obvious actions.

## 9. Context Packs

For large tasks, create logical packs:

```text
Evidence Pack
Strategy Pack
Exploration Pack A/B/C
Selected System Pack
Channel/Implementation Packs
Verification Pack
```

Each pack contains:

- governing approved decisions;
- required source pointers;
- current task;
- exclusions;
- expected output;
- evaluation and stop condition.

Avoid passing discarded alternatives into selection/refinement unless explicitly testing them.

## 10. Transparency Boundary

Provide:

- evidence;
- assumptions;
- concise inference;
- alternatives;
- decision rationale;
- uncertainty;
- verification.

Do not claim to provide:

- hidden/private chain-of-thought;
- exhaustive internal deliberation;
- certainty beyond the evidence.

If the user asks for “the whole thought process,” translate it into a deeper Decision Trace and explain this boundary briefly.
