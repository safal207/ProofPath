# ProofPath Alignment with NGI TALER

## Summary

ProofPath Agent Payment Guard is an auxiliary open-source layer for privacy-preserving digital payment ecosystems.

It does not try to become a payment rail.

It provides a pre-execution guard around AI-agent payment proposals so that payment-capable agents cannot turn model output into irreversible payment execution without explicit, verifiable, auditable authorization.

## Core alignment

NGI TALER is focused on privacy-preserving digital payments and technology commons.

ProofPath contributes to this direction by addressing an emerging payment risk:

> AI agents may soon be able to propose, initiate, or route payments. Payment systems need a way to verify intent, scope, replay status, and evidence before execution.

ProofPath adds this missing layer.

## How ProofPath complements GNU Taler

GNU Taler focuses on privacy-preserving electronic payments.

ProofPath focuses on intent and evidence before a payment attempt reaches a payment rail.

A future integration can look like this:

```text
AI agent proposes payment
  -> ProofPath validates signed human intent
  -> ProofPath checks policy, budget, asset, recipient, freshness, nonce
  -> ProofPath emits ACCEPT / HOLD / BLOCK
  -> ACCEPT can be passed to GNU Taler or another payment rail
  -> evidence bundle remains verifiable later
```

ProofPath does not need access to private payment data beyond what is required for authorization.

It can be designed so that evidence is privacy-aware:

- record decision metadata;
- avoid storing unnecessary personal data;
- use hashes and commitments where possible;
- export only what is needed for verification;
- separate authorization evidence from payment settlement data.

## Specific contributions

### 1. Signed human intent

AI model output is not authorization.

ProofPath requires a signed intent envelope before payment execution is allowed.

### 2. Policy checks

Payment proposals can be checked against:

- allowed assets;
- allowed recipients;
- budget limits;
- time windows;
- recurring approval scope;
- maximum amount;
- agent identity;
- purpose or invoice reference.

### 3. Replay protection

A payment intent should not be reusable indefinitely.

ProofPath persists nonces and blocks repeated envelopes.

### 4. Evidence bundles

Each decision can be exported as evidence.

The evidence should be portable and verifiable without relying on a live hosted service.

### 5. Auditability without surveillance

ProofPath aims to preserve the distinction between:

- payer privacy;
- merchant accountability;
- proof that an agent was authorized to propose or execute an action.

This direction fits the broader TALER principle that privacy should be technical, not merely policy-based.

## What this grant will improve

The grant will fund:

- stable payment proposal schemas;
- improved signed-intent envelope design;
- better verification tooling;
- GNU Taler integration notes;
- privacy-preserving evidence format;
- documentation and examples;
- reproducible test fixtures;
- threat model for AI-agent payment authorization.

## Non-goals

This project will not:

- implement a replacement for GNU Taler;
- handle real custody of funds;
- store private keys for users;
- claim banking compliance;
- claim production-grade security without audit;
- process real payments during the grant period unless explicitly scoped and reviewed.

## Why this is timely

Payment-capable AI agents create a new boundary problem.

Credentials and transport security can show that a request came from a valid system.

They do not prove that the payment was aligned with a signed human intent, non-replayed, within policy, and reviewable.

ProofPath addresses that boundary.
