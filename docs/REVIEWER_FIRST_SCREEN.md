# Reviewer First Screen

Status: shortest entry point for grant, fellowship, and external reviewers.

## One sentence

ProofPath is a verifiable intent and action-boundary audit layer for AI-agent and API actions.

## Core thesis

```text
valid credential != valid action != valid scope != valid reversibility != valid approval
```

A request can be authenticated and still be unsafe. ProofPath adds a separate action-level check before a high-risk action reaches the protected system.

## Review in five minutes

1. Read `docs/START_HERE_V0_1.md`.
2. Review the CI evidence gate path.
3. Review the Personal Agent Guard path.
4. Review Agent Payment Guard if payment authorization is relevant.
5. Read `AI_SAFETY_PORTFOLIO.md` for the broader research map.

## What ProofPath is

ProofPath is an experimental action-boundary evidence layer. It focuses on declared intent, causal authorization, scope, reversibility, approval, and auditability.

It currently demonstrates:

- pre-execution action-boundary checks;
- explicit ACCEPT / HOLD / BLOCK-style decisions;
- hash-chained audit logs;
- CI-verifiable evidence metrics;
- local approval rails for coding agents;
- payment-guard evidence demos;
- portable evidence export patterns.

## What ProofPath is not

ProofPath is not:

- a replacement for HTTPS;
- a replacement for OAuth, IAM, or API keys;
- production security certification;
- regulatory compliance;
- complete prevention coverage;
- formal verification;
- a replacement for human review.

## Best current funding framing

```text
Fund ProofPath to expand reusable action-boundary evidence gates for AI-agent/API workflows.
```

Near-term work:

- expand scenario coverage;
- harden evidence metrics;
- improve local guard policies;
- add latency and artifact reporting;
- publish clearer reviewer runbooks;
- connect ProofPath with PythiaLabs evidence-gate workflows.

## Bottom line

ProofPath makes one missing layer inspectable:

```text
Was this specific action authorized, scoped, reversible or approved, and auditable before execution?
```
