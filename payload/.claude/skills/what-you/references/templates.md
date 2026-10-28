# What-You Templates

## Contents

1. Canonical artifact
2. Progressive stage output
3. Handoff Object
4. Decision ledger
5. Risk register
6. Quality gate
7. Change log
8. Question gates

## 1. Canonical Artifact

Use one file such as:

```text
docs/what-you/<task-slug>.md
```

Adapt to the project documentation convention when one exists.

```markdown
# <Task> · What-You Program

> Status:
> Updated:
> Scope:
> Last approved gate:

## 0. Current State

## 1. Request Frame

## 2. Evidence Ledger

## 3. Conflict Map

## 4. Why Ladder

## 5. What Architecture

## 6. How Architecture

## 7. So What and Success System

## 8. Decision Ledger

## 9. Risk Register

## 10. Context and Artifact Architecture

## 11. Sequential Execution Plan

## 12. Quality Gates

## 13. Definition of Done

## 14. Current Decision State

## 15. Change Log
```

Keep the file a decision index. Link to large supporting artifacts rather than embedding them.

## 2. Progressive Stage Output

```markdown
## Stage <N> · <Name>

| Frame | Approved/proposed content |
|---|---|
| Evidence | ... |
| Why | ... |
| What | ... |
| How | ... |
| So What | ... |

### Derivation Record

- Evidence used:
- Observed conflicts:
- Interpretation:
- Alternatives considered:
- Proposed decision:
- Why this option:
- Confidence:
- Open issues:
- Artifact impact:
```

Include only frames reached at the current stage.

## 3. Handoff Object

```markdown
## What-You Handoff Object

| Field | Approved content |
|---|---|
| Purpose Frame | ... |
| Goal | ... |
| Outputs | ... |
| Inputs | ... |
| Constraints | ... |
| Evaluation | ... |
| Risks | ... |
| Context Architecture | ... |
| Artifact Plan | ... |
| Next Safe Action | ... |

### Evidence Boundaries

- Fact:
- Promise:
- Hypothesis:
- Legacy:
- Conflict:

### Decision Trace

- Approved:
- Rejected:
- Open:
- Invalidated:
```

## 4. Decision Ledger

```markdown
| ID | Decision | Evidence | Alternatives | Reason | Confidence | Status | Downstream impact |
|---|---|---|---|---|---|---|---|
```

Statuses:

- `proposed`
- `approved`
- `rejected`
- `invalidated`
- `superseded`

## 5. Risk Register

```markdown
| Risk | Cause | Probability | Impact | Detection | Mitigation | Owner/status |
|---|---|---:|---:|---|---|---|
```

Always include:

- evidence poisoning;
- scope distraction;
- terminology confusion;
- constraint clash;
- execution/production risk when applicable.

## 6. Quality Gate

```markdown
### Gate <ID> · <Name>

Entry:
- ...

Checks:
- [ ] ...

Pass:
- ...

Immediate fail:
- ...

Evidence:
- ...

Decision:
- pending
```

## 7. Change Log

```markdown
| Date | Stage | Change | Reason/evidence | Approved by | Downstream reset |
|---|---|---|---|---|---|
```

Do not delete old decisions. Mark them invalidated or superseded.

## 8. Question Gates

> Delivery rule (Claude Code): the Text Gate below is the DEFAULT gate form. It must appear at
> the END of the turn's final text message, after the full stage output, with no tool calls
> after it — text emitted before a tool call in the same turn may not render to the user.
> Add the line `Question tool unavailable; text fallback explicitly allowed.` only when
> falling back because a question tool genuinely failed, not when the Text Gate is the default.

### Stage confirmation (Text Gate)

```text
게이트: <gate-id> — <Stage> (번호로 답해주세요)

1. Confirm and continue (Recommended)
   Locks this stage and opens the next one.

2. Revise current stage
   Keeps downstream stages blocked.

3. Backtrack
   Invalidates affected downstream decisions.

4. Stop and export
   Preserves the current artifact without execution.
```

### Execution handoff

```text
1. Execute sequentially with tracked artifacts (Recommended)
2. Hand off to what-ce for prompt optimization
3. Export the Handoff Object only
4. Backtrack to a named stage

goal 게이트 — goal을 설정할까요, 하지 말까요? (So What 성공 기준을 goal로 잠금)
A. Create via goals.py (What → --brief, So What → --goal; completion requires verification evidence)
B. Ready-to-run native /goal <condition> line (user executes it)
C. No goal

Answer format: "1-A", "3-C"
```

### Q4 safety

Name the exact action, target, external effect, rollback/recovery path, and safest alternative. Do not bundle multiple risky actions into one approval.
