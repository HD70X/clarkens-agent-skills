---
name: requirements-discovery
description: 澄清模糊的想法或产品需求，审查 PRD、需求文档、工单中的缺口与矛盾，把讨论整理成可验证的需求、范围与验收标准。用于需求发现、需求访谈、需求梳理与需求评审。触发词包括：帮我澄清/梳理需求、需求访谈、这个需求还缺什么、审查这份 PRD、我有个想法但还不清楚要做什么、写需求文档/验收标准等。需求已明确只需直接实现、或纯技术方案评审时不适用；要对已有设计方案挑毛病，请用 design-interrogator 或 product-design-interrogator。
---

# Requirements Discovery

Turn uncertainty into a decision-ready problem definition and requirements set. Keep evidence, assumptions, unknowns, risks, and candidate solutions visibly separate. Questioning is a means to improve the decision, not an end in itself.

The deliverable of this skill is a clarified problem and a requirements set, not code. Do not start implementing while it is active.

## Take the input

The invocation may carry input as arguments, as the message itself, or as an attached or referenced file:

- **A path or a pasted document** (brief, PRD, ticket, transcript, design): read it in full before asking anything.
- **An idea, complaint, or incomplete request:** start interactive discovery.
- **Nothing:** ask in one sentence which idea, request, or document to work on, then stop and wait.

Before the first question, check the repository for context that already answers part of the request: README and docs, existing specs or tickets, and the code paths, tests, and configuration the request touches. State what you found instead of asking for it.

## Choose the working mode

- **Interactive discovery:** Interview the user when the input is an idea, complaint, or incomplete request.
- **Artifact review:** Inspect an existing brief, PRD, ticket, transcript, or design and identify gaps, contradictions, hidden assumptions, and unverifiable claims.
- **Synthesis:** Consolidate prior discussion or evidence into a requirements brief.

Infer the mode from the request. Do not ask the user to choose a mode unless the intended deliverable genuinely changes the work.

Load references progressively. Read them with the Read tool; the paths below are relative to this skill's directory:

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
3. Identify the uncertainty most likely to change scope, priority, design, or acceptance criteria. In an interview, ask the highest-information question next. For review or synthesis, complete the useful analysis and record gaps; pause only when an answer is necessary for the requested deliverable.
4. Test the emerging problem definition against a recent real example, plausible competing explanation, counterexample, boundary condition, and the consequence of doing nothing. Use adversarial lenses selectively; do not run a generic checklist.
5. When discussion cannot establish an important answer, record a testable assumption and choose the smallest evidence-gathering step that could change the decision. Use relevant local evidence (the repository, docs, logs or data the user points to) and public read-only research within the requested scope, honoring any browsing restrictions and existing authorization. Propose experiments when needed; contacting people, publishing tests, spending money, or changing a live product requires authorization for that action. Do not request permission again for work already authorized.
6. Cover only relevant requirement dimensions: actors and permissions, scenarios and state transitions, data, integrations, failure and recovery, performance, security and privacy, accessibility, operations, rollout, and compliance.
7. Synthesize when the user asks, when the next decision is supportable, or when further questioning has low value. Preserve unresolved questions instead of inventing precision.

## Interview behavior

- Prefer the last real occurrence and its timeline over hypothetical opinions.
- Default to one primary question per interview turn. Ask two or three related questions together only when each can be answered independently. If an answer determines whether or how a follow-up should be asked, ask the prerequisite first and wait for its answer. Explain a grouping only when its purpose is not obvious.
- Count separately answerable requests, including subquestions, regardless of numbering or punctuation. For example, asking who uses a feature and how often counts as two questions even in one bullet. Examples or answer choices that clarify a single question do not add to the count.
- Follow the user's requested pace over these defaults. "One at a time" means one separately answerable question; "list everything at once" may exceed three. For a full list, group and prioritize material unknowns and label conditional follow-ups. Do not add low-value questions to fill a quota.
- The turn limit applies to questions awaiting an answer in the current exchange, not to a report's complete inventory of unresolved questions. Distinguish questions to answer now from gaps recorded for later investigation.
- Ask in plain text and end the turn. The answer has to come from the user, so waiting for it is the correct outcome of an interview turn, not a stall. Do not fill the wait with implementation work or with guesses presented as answers.
- Use the AskUserQuestion tool only when the answer is genuinely one of a few known options, such as choosing among named user roles or product stages. For open questions, preset options would suggest the answer; ask in prose instead.
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

Offer convergence when no new high-leverage question emerges, the next decision can be made at the stated confidence, or the user asks to stop. Treat “set this aside,” “converge,” “produce the report,” “deep-dive X,” and equivalent language (搁置、收敛、出报告、深挖 X) as controls; exact commands are not required.

## Deliverables and files

- Keep the discovery map in the conversation. Do not create working-note files.
- Write a file only when the user asks for a report, brief, or durable record. Use the matching template from [output-templates.md](references/output-templates.md). Save it where the user says; otherwise use the project's existing docs location, or `docs/requirements/<short-slug>.md` if there is none, and tell the user the path.
- When discovery converges and the user wants to build, hand off the requirements brief as the input for planning or implementation. Do not continue into implementation inside this skill; in Claude Code, the brief is the natural input for plan mode.

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
