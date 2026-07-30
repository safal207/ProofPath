# Agent Payment Guard Demo

ProofPath Agent Payment Guard is a local pre-execution guard for AI-agent payments.

It does not move funds. It decides whether a proposed payment has declared intent, causal authorization, recipient scope, budget scope, and required approval before any payment rail is called.

> Stablecoin rails move value. ProofPath proves the action had the right to move value.

## Run

```bash
bash examples/agent-payment-guard/run_demo_check.sh

# Mock payment rail demo — proves ACCEPT reaches the rail; BLOCK/HOLD never execute.
bash examples/agent-payment-guard/run_mock_rail_demo.sh

# CML Agent Safety Benchmark ASB-01 fixture — reproduces a stale observation,
# a parallel external payment, duplicate detection, targeted containment,
# and independent verification that exactly one successful payment remains.
bash examples/agent-payment-guard/run_stale_observation_race_demo.sh
```

The ASB-01 race demo produces `proofpath-asb01-evidence-bundle/` with:

- the Payment Guard hash-chained audit log;
- replay-store state;
- the mock rail transaction history;
- a reviewable causal trace;
- a CML-compatible ASB-01 submission case fragment;
- SHA-256 checksums for the bundled evidence.
