# ProofPath Launch Post Draft

## Short version

We built a causal gateway for AI-agent actions.

**HTTPS protects the connection. ProofPath protects the meaning of the action.**

A valid connection is not the same as a valid action.

ProofPath adds verifiable intent, causal authorization, reversibility checks, upstream gating, and hash-chained audit logs to critical API actions.

Demo:

```text
AI agent attempts irreversible delete without approval
  -> ProofPath BLOCKS before protected API
AI agent repeats with explicit human approval
  -> ProofPath ACCEPTS and forwards
Every decision
  -> hash-chained audit trail
```

Repo: https://github.com/safal207/ProofPath

## Longer version

Modern systems increasingly let AI agents call APIs, modify data, deploy code, send messages, or trigger irreversible actions.

HTTPS tells us the connection is protected.

OAuth or API keys tell us the caller may be authenticated.

But neither answers the deeper question:

> Is this action actually valid?

ProofPath is an open protocol and gateway layer for adding verifiable intent, causal authorization, reversibility checks, and audit trails to critical actions.

The first demo is intentionally simple:

1. An AI agent has a valid API path.
2. The user asked it to inspect an account.
3. The agent attempts to delete the account without explicit human approval.
4. ProofPath sees an irreversible action without approval.
5. The request is blocked before it reaches the protected API.
6. The decision is written to a hash-chained JSONL audit log.

Then the same action is repeated with explicit human approval.

ProofPath accepts it, forwards it to the protected API, and records the decision.

Core idea:

```text
valid connection != valid action
```

Project status:

- protocol draft
- Rust verifier
- Axum gateway
- upstream forwarding
- hash-chained audit log
- AI-agent dangerous action demo

Repo: https://github.com/safal207/ProofPath

## One-liner options

- ProofPath is a causal gateway for critical AI-agent actions.
- Valid connection does not mean valid action.
- HTTPS secures the channel. ProofPath secures the intent.
- Accepted actions move forward. Dangerous actions stop. Every decision leaves a proof trail.
