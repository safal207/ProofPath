# AI Safety Portfolio Map

Status: reviewer-facing map for grant, fellowship, and collaboration reviewers.

This file explains how the related repositories fit together. The goal is to make the portfolio look like one research program, not a scattered set of unrelated prototypes.

## One-line research program

Deterministic evidence, intent, and causal accountability layers for high-risk AI-agent actions before they create real-world effects.

## ProofPath in the portfolio

### ProofPath

**Role:** verifiable intent and action-boundary audit.

ProofPath focuses on whether a critical action is causally authorized and auditable at the execution boundary.

```text
valid credential != valid action != valid scope != valid reversibility != valid approval
```

ProofPath is strongest when the reviewer cares about API boundaries, payment guards, CI evidence gates, or local approval rails for coding agents.

## Related layers

### PythiaLabs

**Role:** pre-execution evidence gates.

PythiaLabs evaluates whether a proposed high-risk AI-agent action has enough evidence, authorization, context, and recovery viability to proceed.

```text
AI agent proposes action -> evidence gate -> ALLOW / BLOCK / ESCALATE
```

PythiaLabs is the cleanest grant-facing entry point for the broader portfolio.

### CML — Causal Memory Layer

**Role:** causal permission and responsibility lineage.

CML records not only what happened, but why an action was allowed, blocked, or escalated. It is the causal accountability layer behind oversight decisions.

### LTP — Liminal Thread Protocol

**Role:** trace, replay, and admissibility path.

LTP structures multi-step agent traces so that decisions can be replayed, compared, and audited across sessions.

### LiminalQAengineer

**Role:** QA reliability substrate.

LiminalQAengineer applies causal and bi-temporal reasoning to CI/test workflows. It is not the main AI safety object, but it supports the engineering reliability background behind the portfolio.

## Recommended reviewer paths

### For AI safety / security reviewers

1. Start with `docs/START_HERE_V0_1.md`.
2. Review the CI evidence gate path.
3. Review the Personal Agent Guard path.
4. Review Agent Payment Guard if payment authorization is relevant.
5. Read PythiaLabs for the broader pre-execution evidence-gate framing.

### For grant reviewers

Use ProofPath as evidence that the portfolio is not only conceptual. It contains concrete action-boundary demos, audit logs, CI checks, and local guard patterns.

## What this portfolio is not

This portfolio does not claim:

- full AI alignment;
- complete agent safety;
- production security certification;
- regulatory compliance;
- replacement of human review;
- universal prevention of unsafe actions.

The current contribution is narrower:

```text
make high-risk AI-agent actions inspectable before execution.
```

## Bottom line

The portfolio should be read as a layered safety stack:

```text
PythiaLabs -> evidence gate
ProofPath -> intent and audit boundary
CML -> causal accountability
LTP -> trace and replay protocol
LiminalQAengineer -> reliability substrate
```

The shared thesis:

```text
AI-agent actions should be reviewable, replayable, and evidence-backed before execution.
```
