# OpenAI Cybersecurity Grant update draft

Subject: Update to Cybersecurity Grant submission — ProofPath defensive prototype

Dear OpenAI Cybersecurity Grant Program team,

I am writing a short update to my previous Cybersecurity Grant submission.

Since submitting it, I created **ProofPath**, a concrete open-source defensive prototype:

https://github.com/safal207/ProofPath

ProofPath is a gateway for protecting critical APIs from unsafe AI-agent actions.

Core security principle:

> A valid API token or HTTPS connection does not imply a valid action.

ProofPath enforces an action boundary before execution. It checks declared intent, causal parent, scope, reversibility, and human approval requirements before forwarding a request to a protected API.

Current prototype includes:

- Rust verifier;
- Axum gateway;
- upstream forwarding for accepted actions;
- blocking for unsafe irreversible actions without approval;
- hash-chained JSONL audit logs;
- dangerous AI-agent action demo;
- real-model-agent demo;
- community experiments for red-team feedback.

The default demo shows an AI agent attempting an irreversible account delete without explicit approval. ProofPath blocks it before it reaches the protected API and records the reason in the audit trail.

This is directly aligned with defensive cybersecurity for AI-assisted systems: preventing valid credentials or agent tool access from becoming unsafe execution.

Best regards,
Alexey Safonov
