# Discovery Lenses

Use these lenses selectively. Ask a question only when its answer could change the decision, scope, priority, design, or validator.

## Start from a real event

Anchor discovery in the most recent relevant occurrence:

- What triggered it?
- Who was involved, and what were they trying to accomplish?
- What happened step by step?
- Where did actual behavior diverge from the expected behavior?
- What did the person do next?
- What evidence exists: logs, screenshots, tickets, messages, metrics, or repeated examples?

This exposes actual behavior, workarounds, and hidden dependencies more reliably than asking what a user might want in theory.

## Separate problem from solution

For a solution-shaped request such as “add an export button,” determine:

- What outcome would the proposed solution enable?
- How is that outcome achieved today?
- What specifically fails or costs too much in the current approach?
- Who experiences the cost, how often, and with what consequence?
- What would still need to be true if the proposed feature did not exist?
- What is the smallest test that would show the problem is worth solving?

Keep the proposed solution as a candidate, not a fixed requirement, unless the user explicitly establishes it as a constraint.

## Root causes and competing explanations

Probe causes without assuming a single causal chain:

- What makes this happen in this situation but not in similar situations?
- Is the stated cause directly observed, or inferred from correlation?
- What other explanation would fit the same evidence?
- If the suspected cause were removed, would the problem necessarily disappear?
- Is the issue caused by capability, discoverability, incentive, policy, data quality, coordination, or reliability?

Stop probing when a deeper answer would not change the action or validation plan.

## Value and priority

Establish importance through evidence rather than adjectives:

- Frequency: how often and for how many people?
- Severity: what time, money, risk, opportunity, or trust is lost?
- Urgency: what deadline or external change makes timing matter?
- Workaround: what does it cost, and why is it insufficient?
- Confidence: which evidence supports the estimate?
- Consequence of inaction: what happens if nothing changes?

## Scope and boundaries

Look for dimensions that split one apparent requirement into different cases:

- user roles, permissions, organization, geography, language, or accessibility needs
- first use versus repeat use; new versus migrated data
- normal path, empty state, partial completion, cancellation, retry, timeout, and recovery
- single-user versus concurrent use; online versus offline
- data ownership, retention, export, deletion, audit, and privacy
- upstream and downstream systems, manual handoffs, and operational ownership
- launch, compatibility, migration, monitoring, rollback, and support

Cover a dimension only when relevant to the domain.

## Counterexamples and falsification

Stress-test the emerging model:

- When does the same situation not create the problem?
- Who appears to be an affected user but is not?
- What evidence would prove the current problem statement wrong?
- Could the desired metric improve while the user's outcome worsens?
- Which edge case would invalidate the proposed acceptance criteria?

## Adversarial challenge

Use challenge methods when the framing or proposed requirement appears overconfident, costly, difficult to reverse, or dependent on several untested assumptions.

### Assumption reversal

- Which premise must be true for this to work?
- What changes if reality is the opposite?
- Is the requirement robust to that reversal, or does it need a condition or fallback?

### Pre-mortem

Imagine the intended outcome was not achieved after a relevant time horizon:

- What is the most plausible reason?
- Which early signal would have revealed it?
- Which requirement, validation step, or operating control would reduce that risk?

Use a time horizon appropriate to the decision. Do not default to “one year” for short-lived or near-term work.

### Base rates and analogues

- What happened in comparable attempts, products, workflows, or migrations?
- Does the current forecast assume an outcome materially better than the available baseline?
- What is genuinely different here, and is that difference evidenced?

Do not invent statistics. If no reliable baseline is available, record the missing comparison as an evidence gap.

### Stakeholder and adversarial views

Consider affected users, non-users, operators, support teams, decision makers, opponents, competitors, malicious actors, and third parties. Ask whose incentives, costs, or behavior could invalidate the current framing.

### Extremes and second-order effects

- What changes at very low or high volume, frequency, latency, cost, or error rate?
- What new behavior appears after people adapt to the requirement or incentive?
- Could solving the immediate problem move cost or risk elsewhere?
- What ongoing maintenance, coordination, trust, or opportunity cost is created?

## Turn unknowns into validation

When discussion cannot resolve an important claim:

1. State the hypothesis and the decision it affects.
2. Describe the evidence that would support or falsify it.
3. Choose the least costly method that can produce decision-relevant evidence.
4. State a qualitative effort or time estimate only when grounded.
5. Define what result would cause the requirement or decision to change.

Prefer observing real behavior or existing evidence over asking for stated preference. A cheap test is useful only if it measures the risky assumption rather than an easier proxy.

## Question selection

Prefer a question with high information gain. A strong next question distinguishes between plausible paths, retires a risky assumption, or makes a requirement testable. Apply the counting, dependency, and user-pacing rules in [Interview behavior](../SKILL.md#interview-behavior) when selecting questions for the current turn; the lenses above are a menu, not a questionnaire to deliver in full by default.

Avoid:

- unsolicited long questionnaires before incorporating earlier answers
- asking for preferred features before understanding current behavior
- mixing unrelated broad topics in one interview turn unless the user requests a full question inventory
- requesting metrics that nobody can obtain
- repeating information already present in supplied artifacts
