# NGI TALER Grant Evidence Index

Application: `2026-08-00b`

Project: ProofPath Agent Payment Guard

Fund: NGI TALER

Requested amount: EUR 50,000

Canonical repository: https://github.com/safal207/ProofPath

Review state: application acknowledged; first-round eligibility review pending.

## Repository correction

The submitted application may contain the repository URL:

```text
https://github.com/ProofPath/AgentPaymentGuard
```

That URL is not the canonical repository and may return `404`.

The canonical, applicant-controlled repository is:

```text
https://github.com/safal207/ProofPath
```

This correction changes only repository discoverability. It does not change project scope, requested amount, or deliverables.

## Reviewer thesis

```text
Model output is a payment proposal, not payment authorization.
```

ProofPath Agent Payment Guard is a pre-execution authorization and evidence layer. It checks signed human intent, policy scope, freshness, replay state, and audit requirements before a proposed payment is allowed to reach a payment rail.

## Causal and temporal transition graph

```text
AI agent proposes payment
  -> proposal is untrusted
  -> signed human intent is resolved
  -> recipient / asset / amount / purpose / time scope is checked
  -> nonce and replay state is checked
  -> ACCEPT / HOLD / BLOCK is recorded
  -> only ACCEPT may reach the mock rail
  -> portable evidence is exported
  -> offline verifier checks the decision chain
```

Current verified transition:

```text
proposal
  -> signed-intent and policy evaluation
  -> replay-safe decision
  -> hash-chained audit
  -> mock rail boundary
  -> offline-verifiable evidence bundle
```

Grant-funded transition:

```text
reviewer-grade prototype
  -> stable schemas and signature profiles
  -> privacy-minimised evidence format
  -> documented GNU Taler adapter boundary
  -> reproducible integration fixtures
  -> external security and ecosystem feedback
```

## Claim-to-evidence matrix

| Claim | Current evidence | Status | Grant-funded delta | Acceptance test |
| --- | --- | --- | --- | --- |
| Model output is not authorization | Guard service and reviewer documentation separate proposal from signed intent | Implemented | Stabilise normative contract | Missing intent can never produce `ACCEPT` |
| Payment policy is enforced before execution | Asset, recipient, budget, purpose, and scope checks | Implemented baseline | Harden policy schema and reason codes | Invalid policy yields deterministic `HOLD` or `BLOCK` |
| Replays are blocked | Persistent nonce/replay store | Implemented baseline | Expand fixtures and recovery checks | Reusing the same intent returns `BLOCK / INTENT_REPLAYED`, including after restart |
| Decisions are auditable | Hash-chained `audit.jsonl` | Implemented | Strengthen portable manifest and privacy report | Tampering breaks verification |
| Evidence can be verified offline | Evidence bundle export and verifier | Implemented baseline | Stabilise bundle format and CLI | Bundle verifies without the live service |
| Blocked proposals never execute | Mock payment rail demo | Implemented | Expand adapter contract | `BLOCK` and `HOLD` produce zero downstream executions |
| Accepted proposals reach a rail boundary | Mock rail receives accepted proposals | Implemented | Document GNU Taler connection point | `ACCEPT` links decision hash to mock execution ID |
| GNU Taler fit is explicit | `TALER_ALIGNMENT.md` and reviewer path | Documentary / planned | Build deterministic Taler-oriented adapter fixtures and integration notes | Reviewer can identify exact pre-payment integration boundary |
| Privacy is preserved | Data-minimisation direction and non-claims | Partial | Define privacy-aware evidence schema | Evidence omits unnecessary payer/payment data and documents retained fields |
| External review exists | Public issues and community paths | Pending | Engage Taler/payment and security reviewers | At least one external technical review is captured publicly |

## Reviewer commands

```bash
git clone https://github.com/safal207/ProofPath.git
cd ProofPath
bash examples/agent-payment-guard/run_demo_check.sh
bash examples/agent-payment-guard/run_service_check.sh
bash examples/agent-payment-guard/run_e2e_evidence_demo.sh
bash examples/agent-payment-guard/run_mock_rail_demo.sh
```

Expected story:

```text
valid signed intent        -> ACCEPT
same intent replay         -> BLOCK / INTENT_REPLAYED
policy violation           -> HOLD or BLOCK
ACCEPT                      -> reaches mock rail
HOLD / BLOCK                -> never reaches mock rail
evidence export             -> portable bundle
offline verification       -> OK
tampered evidence           -> verification failure
```

## GNU Taler boundary

ProofPath does not replace GNU Taler and does not currently claim a production GNU Taler integration.

The intended boundary is:

```text
AI payment proposal
  -> ProofPath authorization decision
  -> ACCEPT only
  -> GNU Taler adapter or another privacy-preserving rail
```

The grant-funded work should make this boundary concrete through schemas, fixtures, integration notes, and deterministic tests without handling real custody or private keys.

## Current boundaries

ProofPath Agent Payment Guard currently does not claim:

- real wallet custody;
- real token or bank transfer execution;
- production private-key management;
- production GNU Taler integration;
- regulatory compliance certification;
- production-grade cryptography without independent review;
- that audit evidence proves external real-world truth.

## Decision rule

A payment transition may return `ACCEPT` only when:

1. signed intent is present and valid;
2. the proposal is within recipient, asset, amount, purpose, and time scope;
3. freshness and replay checks pass;
4. the decision and evidence are durably recorded;
5. downstream execution is linked to the accepted decision.

Missing or contradictory evidence must fail closed as `HOLD`, `BLOCK`, or `CHALLENGE`.
