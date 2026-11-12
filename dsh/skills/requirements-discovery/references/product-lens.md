# Product Lens

Read this reference only for products, features, PRDs, user experiences, adoption questions, or product metrics. Apply it to the shared requirements-discovery workflow; do not create a separate product-interrogation process.

Select only the dimensions likely to change the product decision. Do not turn this reference into a fixed questionnaire.

## Determine the product stage

Infer the stage from the available artifact or context. Ask only if the distinction changes the work.

- **Concept:** The solution is still an idea. Prioritize problem evidence, target users, value, alternatives, and the smallest validation of the riskiest assumption.
- **Prototype:** A flow or design exists but behavior is not established. Prioritize comprehension, motivation, workflow completeness, discoverability, failure paths, and prototype evidence.
- **Live iteration:** The product or feature is in use. Prioritize behavioral data quality, segmentation, causal interpretation, unintended effects, opportunity cost, maintenance, and rollout or rollback evidence.

## Product decision lenses

### Problem evidence

- Who experiences the problem, in what triggering situation, and how often?
- Is the problem observed in behavior or inferred from requests and opinions?
- What workaround is used today, and what does it cost?
- What happens if the product does nothing?

### Target and non-target users

- Who is the primary user, buyer, administrator, operator, or affected third party?
- Who appears adjacent but is explicitly not being optimized for?
- Are early adopters representative of the intended mainstream users?
- Do roles have conflicting success criteria or permissions?

### Behavioral assumptions and adoption

- What new action or habit must the user adopt?
- What evidence shows sufficient motivation, ability, and a timely trigger?
- What switching, learning, trust, or coordination cost stands in the way?
- Could stated interest diverge from actual use or retention?

### Value and alternatives

- Why choose this instead of the current workaround, a competitor, an adjacent feature, or doing nothing?
- Is the improvement large enough to overcome switching and operating costs?
- Does the proposed feature address the cause of the problem or only expose another interface for it?

### Scenario, frequency, and discovery

- What exact event makes the user need the feature?
- How frequently does that event occur, and does the interface prominence match the frequency?
- How will the intended user discover or remember the capability at the right time?
- Does the experience depend on cold start, network effects, data availability, or another party acting first?

### Success signals and guardrails

- Which observable behavior shows the user's outcome improved?
- What time-to-signal is realistic?
- Which vanity or proxy metric could improve while the outcome worsens?
- Which guardrail metrics protect retention, trust, quality, cost, or an existing core workflow?

### Misuse, gaming, and trust

- What happens if users ignore, misunderstand, automate, game, or maliciously exploit the feature?
- Could incentives optimize the measured action while undermining the real goal?
- What new privacy, safety, fairness, abuse, or brand risk appears?
- What detection, rate limit, review, recovery, or appeal path may be needed?

### Cost and minimum validation

- What product, engineering, design, operations, support, compliance, and maintenance costs are introduced?
- Which assumption combines high uncertainty with high downside if false?
- What is the least costly evidence that could justify continuing, changing direction, or stopping?
- Could a prototype, manual service, observation, limited cohort, or reversible rollout answer the question before full implementation?

### Second-order effects

- Does the feature cannibalize, clutter, or weaken an existing workflow?
- How will users, competitors, operators, or bad actors adapt after launch?
- Could short-term metric gains create long-term trust, quality, or support costs?
- What becomes difficult to remove or reverse once users depend on it?

## Prioritize product hypotheses

Rank hypotheses using judgment across:

- decision impact if false
- current uncertainty
- cost and irreversibility of acting before validation
- availability and strength of obtainable evidence

For high-priority hypotheses, define:

| Hypothesis | Why it matters | Current evidence | Validation method | Change criterion | Effort / time |
|---|---|---|---|---|---|
| ... | ... | ... | ... | ... | Low/Medium/High or grounded estimate |

Possible methods include existing analytics or logs, direct observation, targeted interviews, usability testing, a manual or concierge workflow, a clearly disclosed interest test, limited rollout, cohort comparison, or an experiment. Choose based on the claim being tested; do not default to an A/B test. Recommend methods without contacting users, publishing tests, or changing a live product unless the user explicitly authorizes those actions.

## Product-specific convergence

A product discovery result should make clear:

- stage and decision being supported
- target and non-target users
- problem evidence and current alternatives
- critical behavioral and value assumptions
- success signals and guardrails
- discovery, distribution, misuse, and second-order risks when relevant
- the smallest validation plan for the riskiest unresolved assumptions

Do not treat feature detail, stakeholder enthusiasm, clicks, or survey intent alone as proof of durable user value.
