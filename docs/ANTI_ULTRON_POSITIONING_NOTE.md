# Anti-Ultron Positioning Note

This note captures an informal metaphor for explaining ProofPath and the connected evidence-gate stack to non-technical audiences.

It is not the official project name.

The official framing remains:

```text
Evidence gates before high-risk agentic actions.
```

## The metaphor

"Anti-Ultron" is a narrative shorthand for a simple safety boundary:

```text
No high-risk AI/agent action should proceed without evidence,
authorization, context, traceability, and a reviewable boundary decision.
```

The point is not to build a more powerful agent that defeats a dangerous agent.

The point is to make the transition from intent to action inspectable and interruptible.

## What this means technically

A risky agentic action should not be trusted only because:

- a model produced it;
- a tool call is available;
- credentials exist;
- a prompt says it is allowed;
- a workflow can technically execute.

Instead, the action should pass through an evidence boundary:

```text
proposed action
+ scope
+ authorization
+ evidence
+ context freshness
+ recovery assumptions
+ trace continuity
-> ALLOW / BLOCK / ESCALATE
```

## Mapping to the current stack

```text
ProofPath
  -> action-boundary and verifier layer before high-risk execution

Compute Witness
  -> reviewable evidence for AI/agent compute results

PythiaLabs
  -> deterministic evidence-gate application surface

CML
  -> causal-validity / why-allowed layer

LTP / L-THREAD
  -> trace, replay, continuity, and admissibility layer

LS / Liminal Stack
  -> broader grant reviewer and governance surface
```

## Plain-language explanation

The dangerous pattern is:

```text
AI understands a goal
-> expands the goal
-> acts through tools
-> changes the world
-> nobody can reconstruct why it was allowed
```

The ProofPath / evidence-gate pattern is:

```text
AI proposes an action
-> evidence is checked
-> authorization is checked
-> trace continuity is checked
-> causal validity is checked
-> the boundary decides ALLOW / BLOCK / ESCALATE
-> the decision is reviewable later
```

## Public storytelling version

Use this only as a metaphor:

```text
Anti-Ultron infrastructure for AI agents:
not a smarter super-agent, but a boundary layer that stops high-risk actions
unless evidence, authorization, context, and traceability are present.
```

Safer grant/reviewer wording:

```text
An open-source evidence-gate layer for high-risk AI/agent actions.
```

Even safer technical wording:

```text
A deterministic action-boundary and evidence-verification layer for agentic workflows.
```

## Why this helps

The metaphor helps explain the work quickly to founders, journalists, civil-society technologists, and non-specialist reviewers.

It translates the technical point:

```text
agentic AI needs action boundaries, not only better prompts
```

into a human-readable story:

```text
AI should not be able to move from reasoning to dangerous action without a checkable gate.
```

## Non-claims

This project does not claim to:

- solve AGI alignment;
- prevent all autonomous AI harm;
- prove a model is truthful;
- certify production security;
- replace human governance;
- replace legal, compliance, or safety review;
- create a full AI immune system;
- guarantee that no dangerous action can occur;
- be affiliated with or endorsed by any fictional franchise or rights holder.

The narrow claim is:

```text
High-risk AI/agent actions should have inspectable evidence gates and replayable decision artifacts before execution.
```

## Recommended usage

Use "Anti-Ultron" only in:

- founder storytelling;
- informal demos;
- social posts;
- non-technical explanations;
- internal positioning discussions.

Do not use it as the primary headline for:

- grant applications;
- formal academic writing;
- security claims;
- compliance claims;
- official protocol specifications.

## Bottom line

"Anti-Ultron" is a useful metaphor.

The actual project is narrower and stronger:

```text
ProofPath builds reviewable action boundaries for high-risk agentic AI workflows.
```