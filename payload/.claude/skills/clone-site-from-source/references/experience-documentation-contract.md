# Deep Experience Documentation Contract

Read this before writing the UX analysis and before declaring the crawl complete.

## Default outcome

Every run produces an evidence-backed explanation of how the service works, why users may choose it, where the experience succeeds or fails, and how to verify or improve it. A route inventory or visual clone alone is not completion.

Create and complete these mandatory documents:

| File | Required outcome |
| --- | --- |
| `14-UX-전략-인기-성공요인.md` | Product/UX strategy, verified popularity or growth signals, success drivers, counter-evidence, tradeoffs, and limits of the claims |
| `15-역할-JTBD-사용자-여정.md` | User and operator roles, context, jobs, desired outcomes, end-to-end journeys, emotional trajectory, service blueprint, and success signals |
| `16-서비스-퍼널-성장-루프.md` | North-star value, acquisition-to-retention funnel, activation and conversion points, growth loops, loop breaks, events, metric tree, and guardrails |
| `17-상세-유저플로우-상태-복구.md` | Each primary flow with entry, prerequisites, steps, decisions, completion, abandonment, loading/empty/error states, auth or external boundaries, recovery, and evidence |
| `18-디자인-UX-원리-평가.md` | Design rationale, information architecture, visual hierarchy, cognitive load, content design, persuasion, dark-pattern risk, accessibility, heuristics, and reuse cautions |
| `19-서비스-경험-감사-리스크-개선.md` | Cross-surface audit, role and touchpoint coverage, findings, friction, operator experience, missing capabilities, cross-risks, prioritized roadmap, and handoff needs |
| `20-기능-상태-테스트-매트릭스.md` | Feature-by-state test matrix, failure/recovery coverage, accessibility, responsive behavior, performance, release checklist, and regression suite |
| `21-UX-근거-출처-레지스터.md` | Evidence hierarchy, route/screenshot/DOM/asset evidence, dated external sources, conflicts, claim limits, unresolved questions, and document-to-source mapping |

## Evidence language

Prefix material claims with one of these labels:

- `[확인]`: directly observed in the current public product, repository artifact, screenshot, DOM, response, or authoritative dated source.
- `[강한 추론]`: multiple observations support the conclusion, but the product or operator did not state it directly.
- `[검증 필요]`: plausible and decision-relevant, but it needs analytics, authenticated access, user research, or an additional source.
- `[확인 불가]`: the required authenticated, private, historical, backend, commercial, or operator evidence was unavailable.

Do not convert an inference into a confirmed fact through repetition. Every `[확인]` statement must point to a route, QA artifact, DOM/asset observation, manifest field, or dated source entry. Record source date and access date for external popularity, funding, usage, conversion, or market claims. When sources disagree, preserve both values and explain the difference instead of averaging them.

## Required analysis lenses

Cover each applicable lens even when the result is “not observable”:

1. Public visitor, first-time user, returning creator, power user, team or business buyer, developer/integrator, and operator/moderator/support roles.
2. Discovery, value comprehension, onboarding, first-value activation, creation or core task, iteration, completion, export/share, return, upgrade, cancellation, and recovery.
3. Desktop, mobile, keyboard, reduced-motion, slow/loading, empty, validation, permission, rate-limit, credit/quota, failure, retry, and destructive-action states.
4. Global navigation, route hierarchy, terminology, visual hierarchy, density, disclosure, feedback, status visibility, control affordance, trust, pricing, privacy, safety, moderation, copyright, and support.
5. Acquisition, activation, retention, referral, revenue, creator/community loops, content loops, template or remix loops, and ecosystem/integration loops.
6. User-facing, operator-facing, and system-facing steps in the service blueprint, including evidence that cannot be inspected safely.

## Flow contract

For every primary flow record:

- actor, context, goal, trigger, entry point, and prerequisites;
- ordered screens, controls, decisions, branches, and backtracking;
- visible system feedback and state transitions;
- completion and success signal;
- abandonment, error, empty, permission, quota, and authentication boundaries;
- recovery path, support path, and irreversible-risk warning;
- desktop/mobile/accessibility differences;
- source route and evidence paths;
- confidence label and the next verification method.

Include a Mermaid diagram when a flow has three or more dependent steps or two or more meaningful branches.

## Evaluation and improvement contract

- Explain both what works and the mechanism by which it helps the user.
- Separate business success from interface quality; do not claim causality without evidence.
- Include counter-evidence, tradeoffs, manipulation or dark-pattern risk, and groups who may be disadvantaged.
- Prioritize improvements as `P0`, `P1`, `P2`, or `P3`, with user impact, evidence, proposed change, owner, dependency, success metric, and verification method.
- Define events and metrics without inventing current analytics values.
- State non-goals and unavailable evidence, especially authenticated flows, backend orchestration, billing, moderation, support tooling, and historical experiments.

## Completion gate

The deep-experience set is complete only when:

- every required heading is present and substantively filled;
- each file contains evidence labels and evidence paths or dated source references;
- all four evidence labels are represented across the set;
- no placeholder or unresolved `TODO`/`pending` marker remains;
- primary flows include state, failure, recovery, accessibility, and boundary coverage;
- the source registry maps material claims to evidence and records conflicts;
- prioritized improvements and a regression-ready test matrix are present;
- unavailable authenticated/backend/operator evidence is explicit rather than guessed.
