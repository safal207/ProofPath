# Submitted Application Reviewer Bridge

This page routes reviewers from already-submitted grant materials to the correct current repository, implementation surface, and evidence path.

## NGI TALER application 2026-08-00b

Project: **ProofPath Agent Payment Guard**

Fund: NGI TALER

Requested amount: EUR 50,000

Canonical repository:

```text
https://github.com/safal207/ProofPath
```

The submitted application may contain this earlier or incorrect URL:

```text
https://github.com/ProofPath/AgentPaymentGuard
```

That URL may return `404`. The canonical applicant-controlled repository is `safal207/ProofPath`.

This is a discoverability correction only. It does not change the project scope, budget, or submitted deliverables.

## Fast NGI TALER reviewer route

1. Read [`GRANT_EVIDENCE_INDEX.md`](GRANT_EVIDENCE_INDEX.md).
2. Read [`NGI_TALER_REVIEWER_PATH.md`](NGI_TALER_REVIEWER_PATH.md).
3. Read [`TALER_ALIGNMENT.md`](TALER_ALIGNMENT.md).
4. Run the Agent Payment Guard demos.
5. Inspect [`BUDGET_AND_MILESTONES.md`](BUDGET_AND_MILESTONES.md).

Reviewer commands:

```bash
git clone https://github.com/safal207/ProofPath.git
cd ProofPath
bash examples/agent-payment-guard/run_demo_check.sh
bash examples/agent-payment-guard/run_service_check.sh
bash examples/agent-payment-guard/run_e2e_evidence_demo.sh
bash examples/agent-payment-guard/run_mock_rail_demo.sh
```

Expected transition evidence:

```text
valid signed intent        -> ACCEPT
replayed intent             -> BLOCK / INTENT_REPLAYED
policy violation            -> HOLD or BLOCK
ACCEPT                      -> reaches mock rail
HOLD / BLOCK                -> never reaches mock rail
evidence export             -> portable bundle
offline verification        -> OK
tampered evidence           -> verification failure
```

## Current implementation focus

ProofPath Agent Payment Guard treats model-generated payment instructions as proposals rather than authorization.

The current repository demonstrates:

- signed intent envelope checks;
- recipient, asset, budget, purpose, and scope policy checks;
- freshness and expiry checks;
- persistent nonce replay protection;
- deterministic `ACCEPT`, `HOLD`, and `BLOCK` decisions;
- hash-chained audit records;
- portable evidence export;
- offline evidence verification;
- mock payment rail execution only after `ACCEPT`.

## GNU Taler relationship

ProofPath does not replace GNU Taler.

The intended relationship is:

```text
AI agent proposes payment
  -> ProofPath validates human intent and policy
  -> ProofPath emits ACCEPT / HOLD / BLOCK
  -> ACCEPT may be passed to a GNU Taler adapter or another payment rail
```

A production GNU Taler integration is not currently claimed. The grant-funded transition is to stabilise schemas, privacy-aware evidence, adapter boundaries, fixtures, and integration documentation.

## Other historical project names

Some prior materials may have used names or descriptions such as:

- PythiaLabs / open evidence gates;
- Liminal Stack / deterministic oversight;
- LTP + CML / causal trace oversight;
- Compute Witness;
- agentic AI evidence gates;
- verifiable intent for high-risk AI-agent actions.

These names should not be treated as exact aliases. They are related research or implementation surfaces around one broader direction: high-risk agent actions should be reviewable before execution and auditable afterward.

For application `2026-08-00b`, the relevant implementation surface is specifically **Agent Payment Guard**, not the broader ProofPath research portfolio.

## Claim boundary

This bridge does not claim that ProofPath currently provides:

- real wallet custody;
- real token or bank transfers;
- private-key management;
- production GNU Taler integration;
- regulatory certification;
- model truthfulness;
- production security certification;
- proof of external real-world outcomes.

## Reviewer phrase

```text
ProofPath Agent Payment Guard is the current executable implementation for application 2026-08-00b: a pre-execution authorization and evidence layer that treats AI-generated payment instructions as proposals, not authorization.
```
