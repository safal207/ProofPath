# NLnet update draft — 2026-06-133

Subject: Update for proposal 2026-06-133 — ProofPath prototype

Dear NLnet team,

I am writing a short update regarding proposal `2026-06-133`:

**PythiaLabs: Open Evidence Gates for High-Risk AI-Agent Actions**

Since submitting the proposal, I created **ProofPath**, a concrete open-source prototype aligned with the proposal's evidence-gate direction.

Repository:

https://github.com/safal207/ProofPath

ProofPath is a causal gateway for high-risk AI-agent actions. It demonstrates the core idea in a smaller, runnable form:

> HTTPS protects the connection. ProofPath protects the meaning of the action.

Current prototype includes:

- a protocol draft for ProofPath HTTP headers;
- a Rust verifier for action context;
- an Axum gateway;
- upstream forwarding for accepted actions;
- blocking for unsafe irreversible actions without approval;
- hash-chained JSONL audit logs;
- a dangerous AI-agent action demo;
- a real-model-agent demo;
- community experiment levels for external feedback.

This does not change the submitted proposal scope. I am sharing it as additional evidence that the proposed evidence-gate layer is already being implemented and tested in public.

The mapping to the proposal is direct:

```text
Open evidence gate       -> ProofPath gateway
High-risk AI action      -> dangerous agent action demo
Pre-execution decision   -> ACCEPT / BLOCK / REJECT
Reviewer-facing artifact -> demo transcript + audit JSONL
Community engagement     -> ProofPath Lab experiment levels
```

Best regards,
Alexey Safonov
