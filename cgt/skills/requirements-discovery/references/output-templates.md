# Output Templates

Choose the smallest artifact that enables the user's next decision. Omit empty sections; never fill gaps with invented details.

For live interview questions, follow [Interview behavior](../SKILL.md#interview-behavior). Report templates may list all material unresolved questions; their example list lengths are not limits. If also asking for a reply now, identify that subset separately so the full inventory is not presented as an immediate questionnaire.

Use confidence labels where ambiguity matters:

- **Confirmed:** directly stated or supported by available evidence
- **Assumption:** a claim or interpretation awaiting validation
- **Unknown:** material information not yet established
- **Risk:** a failure mode or counter-scenario that could change the decision
- **Candidate:** a possible solution kept separate from the established problem

## Discovery snapshot

Use during an ongoing interview:

```markdown
## Current understanding

- Target user / stakeholder:
- Triggering situation:
- Current behavior or workaround:
- Observed problem and impact:
- Desired outcome:

## What is established

- [Confirmed] ...

## Assumptions to test

- [Assumption] Claim — decision affected — possible validation

## Unresolved unknowns

- [Unknown] ...

## Risks and counter-scenarios

- [Risk] ...

## Candidate solutions

- [Candidate] ...

## Next question

...
```

## Requirements brief

Use when the user needs a reviewable product or engineering input:

```markdown
# Requirements brief: [working title]

## Decision and objective

What decision or outcome this brief supports.

## Problem statement

[User or stakeholder] encounters [problem] when [situation], causing [observable impact]. Current workarounds are [workaround and limitation].

## Evidence and confidence

- [Confirmed] Evidence, source, or example
- [Assumption] Claim, why it is plausible, and what depends on it
- [Unknown] Evidence gap and how it could be resolved

## Users and scenarios

- Primary actors and goals
- Main scenario and relevant variations

## Desired outcomes and success signals

- Outcome
- Observable metric, binary validator, or review criterion

## Scope

### In scope

- ...

### Out of scope

- ...

## Requirements

- R1. Verifiable behavior or constraint
- R2. ...

## Edge cases and failure handling

- ...

## Dependencies, risks, and constraints

- ...

## Hypothesis-validation plan

| Hypothesis | Decision impact | Current evidence | Validation method | Change criterion | Effort / time |
|---|---|---|---|---|---|
| ... | ... | ... | ... | ... | ... |

## Acceptance criteria

- Given [starting state], when [event or action], then [observable result].

## Open questions

- Question — why the answer matters — owner or evidence source if known

## Candidate solutions

- Candidate idea, clearly separated from confirmed requirements
```

Include the validation table only for assumptions important enough to change scope, priority, design, or the decision to proceed. Use qualitative effort when a numeric estimate would be fabricated.

## Product discovery brief

Use for a product or feature decision when product-stage and adoption evidence matter more than a full implementation specification:

```markdown
# Product discovery brief: [working title]

## Stage and decision

- Stage: Concept / Prototype / Live iteration
- Decision to make:

## Target and non-target users

- Primary user and situation:
- Other affected roles:
- Explicitly not optimized for:

## Problem evidence and current alternatives

- Confirmed observations:
- Current workaround or competitor:
- Frequency, severity, and consequence of inaction:

## Desired outcome and success signals

- User outcome:
- Primary signal:
- Guardrails:
- Expected time-to-signal:

## Critical product assumptions

- Behavior or adoption:
- Value and switching:
- Discovery or distribution:
- Operational feasibility:

## Risks and second-order effects

- Misuse or gaming:
- Cannibalization or workflow displacement:
- Trust, privacy, safety, support, or maintenance:

## Hypothesis-validation plan

| Priority | Hypothesis | Evidence needed | Method | Change criterion | Effort / time |
|---|---|---|---|---|---|
| High | ... | ... | ... | ... | ... |

## Recommendation boundary

- What the evidence currently supports:
- What remains conditional:
- Next reversible step:
```

## Artifact gap review

Use when reviewing a PRD, ticket, brief, or design:

```markdown
## Executive finding

Whether the artifact is decision-ready or implementation-ready, and the main reason.

## Material gaps

| Priority | Gap or ambiguity | Why it matters | Recommended clarification |
|---|---|---|---|
| High | ... | Changes scope/design/validation | ... |

## Contradictions and hidden assumptions

- ...

## Missing acceptance coverage

- Main path:
- Boundary or permissions:
- Failure and recovery:
- Non-functional constraint:
- Product adoption, discovery, misuse, or guardrails when relevant:

## Questions to resolve next

1. Highest-information question
2. Next most consequential question
```

Rank gaps by their effect on the decision, not by how easy they are to document.
