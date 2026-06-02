# NGI TALER Reviewer Path

## Project

**ProofPath Agent Payment Guard**

Repository: https://github.com/safal207/ProofPath

## One-sentence summary

ProofPath Agent Payment Guard is an open-source pre-execution authorization and evidence layer for AI-agent payment proposals.

It treats model output as a proposal, not as payment authorization.

## Why this matters

AI agents are starting to interact with tools that can trigger payments, purchases, subscriptions, invoices, refunds, reimbursements, and treasury operations.

Traditional payment infrastructure can verify credentials, channels, merchants, and settlement flows.

It does not answer a new agentic-systems question:

> Was this specific AI-proposed payment action authorized by a human intent, within policy, fresh, non-replayed, and auditable before execution?

ProofPath focuses on this gap.

## Fit with NGI TALER

NGI TALER supports free and open-source work around privacy-preserving digital payments.

ProofPath aligns with that goal by adding a small reusable guard layer around payment proposals:

- signed human intent before execution;
- policy checks before a payment is allowed;
- replay protection;
- privacy-aware audit evidence;
- portable evidence bundles;
- open-source implementation and documentation.

ProofPath does not replace GNU Taler.

It is designed as an auxiliary authorization and evidence component that can later integrate with GNU Taler-style payment flows and other privacy-preserving payment rails.

## Reviewer quick path

Start here:

1. Read `docs/TALER_ALIGNMENT.md`.
2. Run or inspect `examples/agent-payment-guard/run_e2e_evidence_demo.sh`.
3. Read `docs/AGENT_PAYMENT_GUARD_DEMO.md`.
4. Inspect the API contract in `openapi/proofpath-guard-service-v0.1.yaml`.
5. Read `docs/BUDGET_AND_MILESTONES.md`.

## Current project status

The current prototype demonstrates:

- payment proposal evaluation;
- signed intent envelope checks;
- asset and recipient policy checks;
- budget and scope checks;
- replay detection through persistent nonce state;
- hash-chained audit logging;
- evidence export;
- offline evidence verification;
- mock payment rail execution only after `ACCEPT`.

Current non-claims:

- no real wallet custody;
- no private key management;
- no production GNU Taler integration yet;
- no regulatory compliance claim;
- no certified security audit;
- no production-grade cryptography claim unless explicitly implemented and reviewed.

## Target outcome of the grant

The grant will turn the current prototype into a cleaner open-source payment guard component with:

- a stable proposal schema;
- a stable signed intent envelope format;
- a policy engine suitable for AI-agent payment workflows;
- portable evidence bundles;
- a command-line verifier;
- integration documentation for privacy-preserving payment systems;
- a reference path toward GNU Taler-compatible integration;
- public test fixtures and reproducible demos.

## Success criteria

A reviewer or developer should be able to:

- run a deterministic demo locally;
- observe `ACCEPT`, `HOLD`, and `BLOCK` decisions;
- verify that a replayed payment intent is blocked;
- export an evidence bundle;
- verify that evidence offline;
- understand how the design could integrate with GNU Taler-style flows;
- reuse the schemas and guard logic in another open-source payment application.

## Suggested reviewer command path

```bash
git clone https://github.com/safal207/ProofPath.git
cd ProofPath

bash examples/agent-payment-guard/run_demo_check.sh
bash examples/agent-payment-guard/run_service_check.sh
bash examples/agent-payment-guard/run_e2e_evidence_demo.sh
bash examples/agent-payment-guard/run_mock_rail_demo.sh
```

Expected high-level story:

```text
valid signed intent        -> ACCEPT
same signed intent replay  -> BLOCK / INTENT_REPLAYED
policy violation           -> HOLD or BLOCK
accepted proposal          -> reaches mock rail
blocked proposal           -> never reaches mock rail
evidence export            -> portable bundle
offline verification       -> OK
```

## Grant proposal reference

Submitted application:

```text
Application 2026-08-00b — ProofPath Agent Payment Guard
Fund: NGI TALER
Requested amount: EUR 50,000
Correct repository: https://github.com/safal207/ProofPath
```
