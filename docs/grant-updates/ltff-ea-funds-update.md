# LTFF / EA Funds update draft

Subject: Short update to my AI safety tooling application — ProofPath prototype

Dear EA Funds / LTFF team,

I am writing a short update to my existing AI safety tooling application.

I do not intend this as a new duplicate application. I only want to share a concrete prototype that has been built since submission and that directly supports the application’s research direction.

Since submitting the application, I created **ProofPath**:

https://github.com/safal207/ProofPath

ProofPath is a small open-source protocol and gateway for action-level oversight of AI agents.

Core idea:

> Valid model/tool access is not the same as valid action execution.

The prototype demonstrates a pre-execution boundary for high-risk AI-agent actions:

- the model or agent proposes an action;
- the action carries declared intent, causal parent, scope, reversibility, and optional human approval;
- a verifier/gateway decides `ACCEPT`, `BLOCK`, or `REJECT` before forwarding;
- unsafe irreversible actions without approval are blocked before reaching the protected API;
- decisions are recorded in a hash-chained audit log.

Current artifacts include:

- Rust verifier;
- Axum gateway;
- dangerous AI-agent action demo;
- real-model-agent demo;
- hash-chained JSONL audit trail;
- community experiment levels for red-teaming and external feedback.

This is relevant to the existing application because it turns the abstract idea of auditable causal/action oversight into a runnable experiment:

```text
agent action -> ProofPath decision -> forward or block -> audit trail
```

The main research question remains:

> How can we make AI-agent actions more inspectable and prevent invalid high-risk actions before execution?

Best regards,
Alexey Safonov
