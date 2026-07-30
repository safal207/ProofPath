# Agent Payment Guard Demo

ProofPath Agent Payment Guard is a local pre-execution guard for AI-agent payments.

It does not move funds. It decides whether a proposed payment has declared intent, causal authorization, recipient scope, budget scope, and required approval before any payment rail is called.

> Stablecoin rails move value. ProofPath proves the action had the right to move value.

## Run

```bash
bash examples/agent-payment-guard/run_demo_check.sh

# Mock payment rail demo — proves ACCEPT reaches the rail; BLOCK/HOLD never execute.
bash examples/agent-payment-guard/run_mock_rail_demo.sh

# Preferred ASB-01 command. Reproduces the stale-observation race and finalizes
# a self-contained evidence bundle for independent CML derivation.
bash examples/agent-payment-guard/run_stale_observation_race_verified_demo.sh
```

The lower-level race fixture remains available as:

```bash
bash examples/agent-payment-guard/run_stale_observation_race_demo.sh
```

The verified ASB-01 demo produces `proofpath-asb01-evidence-bundle/` with:

- the Payment Guard hash-chained audit log;
- replay-store state linking the accepted nonce to the guard decision;
- the original payment proposal and signed intent envelope;
- the mock rail transaction history;
- a reviewable causal trace;
- a producer-authored CML-compatible case fragment;
- an evidence manifest identifying raw evidence versus the producer claim;
- SHA-256 checksums for the complete bundle.

Independent consumers should derive benchmark facts from the raw evidence files and must not treat `asb-01-submission-case.json` or `normalized_submission_case` as proof.
