# Security grant revision: ProofPath update

Date: 2026-05-11

This document records that a revised full proposal was submitted through a public cybersecurity grant form.

## Purpose of the revision

The revision added ProofPath as a concrete public implementation update.

Repository:

https://github.com/safal207/ProofPath

## Core framing

ProofPath prevents valid API credentials or AI-agent tool access from becoming unsafe, unaudited, or irreversible actions.

The project focuses on a narrow execution-boundary problem:

> Valid credentials should not automatically mean valid action.

## What changed since the original proposal

Since the original submission, a runnable public prototype was created.

The prototype demonstrates:

- declared intent checks;
- causal parent checks;
- scope checks;
- reversibility classification;
- human approval requirements for irreversible actions;
- a Rust verifier crate;
- an Axum gateway;
- upstream forwarding only after a ProofPath decision;
- blocking unsafe irreversible actions before they reach the protected API;
- hash-chained JSONL audit logs;
- dangerous-action and real-model-agent demos;
- community experiment levels for external feedback.

## Important non-claims

This document is only an internal project record of a revised submission.

ProofPath does not replace HTTPS, OAuth, IAM, API keys, or ordinary infrastructure security.

ProofPath is an additional action-level security and audit layer for high-risk AI-agent/API actions.

## Supporting links

- ProofPath repository: https://github.com/safal207/ProofPath
- GitHub profile: https://github.com/safal207
- X profile: https://x.com/lim746048
