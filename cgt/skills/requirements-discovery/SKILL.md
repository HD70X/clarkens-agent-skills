---
name: requirements-discovery
description: Uncover the real problem behind a vague idea, complaint, product concept, or solution-shaped request and turn it into clear, evidence-aware, testable requirements. Use for problem discovery, discovery interviews, 需求挖掘、需求澄清、需求细化, product or feature clarification, PRD gap analysis, scope clarification, assumption checking, or acceptance-criteria definition. Do not use for straightforward implementation when requirements and validators are already clear, or for a general architecture or plan risk review that does not need requirements discovery.
---

# Requirements Discovery

Turn uncertainty into a decision-ready problem definition and requirements set. Keep evidence, assumptions, unknowns, risks, and candidate solutions visibly separate. Questioning is a means to improve the decision, not an end in itself.

## Choose the working mode

- **Interactive discovery:** Interview the user when the input is an idea, complaint, or incomplete request.
- **Artifact review:** Inspect an existing brief, PRD, ticket, transcript, or design and identify gaps, contradictions, hidden assumptions, and unverifiable claims.
- **Synthesis:** Consolidate prior discussion or evidence into a requirements brief.

Infer the mode from the request. Do not ask the user to choose a mode unless the intended deliverable genuinely changes the work.

Load references progressively:

- For interactive discovery or a deep artifact review, read [discovery-lenses.md](references/discovery-lenses.md).
- For a product, feature, PRD, user-experience, adoption, or product-metric request, also read [product-lens.md](references/product-lens.md). Infer whether the product is at concept, prototype, or live-iteration stage when the evidence makes that clear.
- When producing a structured deliverable, read [output-templates.md](references/output-templates.md).

Do not create a separate product workflow. Apply the product lens to the shared discovery process.

## Maintain the discovery map

Track five categories throughout the work:

1. **Confirmed evidence:** Explicit user statements or evidence supported by an available source.
2. **Assumptions to validate:** Inferences or causal claims that the decision depends on; include a validation approach when useful.
3. **Unresolved unknowns:** Missing information whose answer could change the decision.
4. **Risks and counter-scenarios:** Ways the problem framing, requirement, or intended outcome could fail or create harm.
5. **Candidate solutions:** Proposed answers kept separate from confirmed problems and requirements.

Update this map after meaningful new information. Show a compact snapshot when it helps the user correct the model, before changing direction, or at convergence. Keep it in the conversation by default; do not create working-note files unless the user requests an artifact or durable record.

## Discovery workflow

1. Establish the decision to be enabled: what the user needs to decide, approve, build, test, or learn. If unclear, state a provisional frame and begin discovery.
2. Build the current model from available evidence: affected people, triggering situation, current behavior or workaround, observed pain or cost, desired outcome, constraints, and known dependencies. Initialize the discovery map.
3. Identify the uncertainty most likely to change scope, priority, design, or acceptance criteria. Ask the highest-information question next.
4. Test the emerging problem definition against a recent real example, plausible competing explanation, counterexample, boundary condition, and the consequence of doing nothing. Use adversarial lenses selectively; do not run a generic checklist.
5. When an important answer cannot be known through discussion, record a testable assumption and propose the smallest evidence-gathering step capable of changing the decision. Do not execute external research, experiments, or user-facing changes without authorization.
6. Cover only relevant requirement dimensions: actors and permissions, scenarios and state transitions, data, integrations, failure and recovery, performance, security and privacy, accessibility, operations, rollout, and compliance.
7. Synthesize when the user asks, when the next decision is supportable, or when further questioning has low value. Preserve unresolved questions instead of inventing precision.

## Interview behavior

- Prefer the last real occurrence and its timeline over hypothetical opinions.
- Ask one primary question per turn. Batch up to three tightly related questions only when the answers jointly determine the next direction; explain the grouping when it is not obvious.
- Make questions neutral and concrete. Avoid suggesting the desired answer or treating the proposed solution as a fixed requirement.
- Do not mechanically apply “five whys.” Probe causes only while each answer changes the model or exposes a testable assumption.
- Summarize the evolving understanding after several meaningful answers or before changing topic; do not repeat a full summary after every turn.
- Inspect user-provided artifacts and available local context before asking for information already present there.
- Mark a question as blocking only when the next decision genuinely cannot proceed without it. Explain why a challenge matters when it is not self-evident.
- Be direct about contradictions and risks without becoming adversarial toward the user. Do not make the decision on the user's behalf.
- Use the user's language and level of technical detail.

## Stop and converge deliberately

Filter each possible follow-up:

- **Decision invariance:** Do not ask if every plausible answer leads to the same decision.
- **Resolvability:** If discussion cannot establish the answer, convert it to a hypothesis with a validation method instead of repeatedly asking.
- **Goal boundary:** Accept an explicit value judgment as a premise. If it appears to contradict the user's deeper stated outcome, challenge it once with a reason; accept the user's confirmed choice after that.
- **Materiality:** Record low-impact issues as secondary rather than expanding them into new question lines.

Offer convergence when no new high-leverage question emerges, the next decision can be made at the stated confidence, or the user asks to stop. Treat “set this aside,” “converge,” “produce the report,” “deep-dive X,” and equivalent language as controls; exact commands are not required.

## Quality bar

A useful result makes the following clear:

- whose problem is being addressed and in what situation
- what happens today, including workarounds and measurable impact where known
- what outcome matters and how success could be observed
- what is in scope and explicitly out of scope
- which claims and requirements are confirmed versus assumed
- relevant constraints, edge cases, dependencies, and risks
- acceptance criteria that can be verified
- which high-risk assumptions need validation and what evidence could resolve them
- open questions whose answers could materially change the decision

Do not present a feature list as evidence that the underlying problem is understood. Do not silently turn assumptions into requirements. Do not force quantitative metrics or cost estimates when no honest measurement method exists; use a binary, qualitative, or reviewable validator instead.
