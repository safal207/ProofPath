# NGI TALER Reviewer Path

## Project

**ProofPath Agent Payment Guard**

Application: `2026-08-00b`

Fund: NGI TALER

Requested amount: EUR 50,000

Canonical repository: https://github.com/safal207/ProofPath

> Repository correction: the submitted application may reference `https://github.com/ProofPath/AgentPaymentGuard`, which may return `404`. The canonical applicant-controlled repository is `https://github.com/safal207/ProofPath`. This changes discoverability only, not project scope.

## One-sentence summary

ProofPath Agent Payment Guard is an open-source pre-execution authorization and evidence layer for AI-agent payment proposals.

```text
Model output is a proposal, not authorization.
```

## Why this matters

AI agents are starting to interact with tools that can trigger payments, purchases, subscriptions, invoices, refunds, reimbursements, and treasury operations.

Traditional payment infrastructure can verify credentials, channels, merchants, and settlement flows.

It does not answer a new agentic-systems question:

> Was this specific AI-proposed payment action authorized by human intent, within policy, fresh, non-replayed, and auditable before execution?

ProofPath focuses on this gap.

## Fit with NGI TALER

NGI TALER supports free and open-source work around privacy-preserving digital payments.

ProofPath contributes an auxiliary guard layer around payment proposals:

- signed human intent before execution;
- policy checks before a payment is allowed;
- freshness and replay protection;
- privacy-aware audit evidence;
- portable evidence bundles;
- open-source implementation and documentation.

ProofPath does not replace GNU Taler and does not currently claim a production GNU Taler integration.

The intended boundary is:

```text
AI agent proposes payment
  -> ProofPath validates intent, scope, policy, freshness, and replay state
  -> ProofPath emits ACCEPT / HOLD / BLOCK
  -> ACCEPT may be passed to a GNU Taler adapter or another payment rail
```

## Reviewer quick path

1. Read [`GRANT_EVIDENCE_INDEX.md`](GRANT_EVIDENCE_INDEX.md).
2. Read this file.
3. Read [`TALER_ALIGNMENT.md`](TALER_ALIGNMENT.md).
4. Run the end-to-end and mock-rail demos.
5. Inspect the API contract in [`../openapi/proofpath-guard-service-v0.1.yaml`](../openapi/proofpath-guard-service-v0.1.yaml).
6. Read [`BUDGET_AND_MILESTONES.md`](BUDGET_AND_MILESTONES.md).

## Current project status

The current prototype demonstrates:

- payment proposal evaluation;
- signed intent envelope checks;
- recipient, asset, budget, purpose, and scope policy checks;
- freshness and expiry checks;
- persistent nonce replay protection;
- deterministic `ACCEPT`, `HOLD`, and `BLOCK` decisions;
- hash-chained audit logging;
- evidence export;
- offline evidence verification;
- mock payment rail execution only after `ACCEPT`.

Current non-claims:

- no real wallet custody;
- no private-key management;
- no production GNU Taler integration;
- no regulatory compliance claim;
- no certified security audit;
- no claim that audit evidence proves external real-world truth.

## Reviewer command path

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
blocked or held proposal   -> never reaches mock rail
evidence export            -> portable bundle
offline verification       -> OK
tampered evidence          -> verification failure
```

## Target outcome of the grant

The grant will turn the reviewer-grade prototype into a cleaner open-source payment guard component with:

- stable payment proposal schemas;
- stable signed-intent envelope profiles;
- hardened policy and replay semantics;
- privacy-minimised evidence bundles;
- command-line evaluation, export, and verification;
- deterministic GNU Taler-oriented adapter fixtures and integration notes;
- public test fixtures, threat model, and reproducible demos;
- external security and ecosystem feedback.

## Success criteria

A reviewer or developer should be able to:

- run a deterministic demo locally;
- observe `ACCEPT`, `HOLD`, and `BLOCK` decisions;
- verify that a replayed intent is blocked, including after restart;
- prove that blocked and held proposals never reach the mock rail;
- export an evidence bundle;
- verify the evidence offline;
- detect tampered evidence;
- identify the exact integration boundary for a GNU Taler adapter;
- understand what the guard proves and what it does not prove.

## Grant proposal reference

```text
Application: 2026-08-00b
Fund: NGI TALER
Requested amount: EUR 50,000
Canonical repository: https://github.com/safal207/ProofPath
```
