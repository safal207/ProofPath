# Reports

This directory contains reviewer-facing measured and planned evidence reports for ProofPath and the connected evidence-gate stack.

## Current reports

### Action-Boundary Fixture Metrics — 2026-05-17

Human-readable summary:

```text
reports/action-boundary-fixture-2026-05-17.md
```

Machine-readable JSON:

```text
reports/action-boundary-fixture-2026-05-17.json
```

Source fixture:

```text
fixtures/action-boundary/dangerous-action-audit.jsonl
```

Collector script:

```text
scripts/collect_action_boundary_metrics.py
```

Measured fixture values:

```text
actions_total -> 2
actions_blocked -> 1
actions_accepted -> 1
unsafe_without_approval_blocked -> 1
unsafe_without_approval_false_accepts -> 0
safe_with_approval_false_blocks -> 0
audit_records_written -> 2
blocked_forwarded_count -> 0
accepted_forwarded_count -> 1
audit_hash_chain_present -> true
```

Claim boundary:

```text
fixture baseline only; not production benchmark; no latency measurement yet
```

### Evidence Metrics CI Baseline — 2026-05-17

Human-readable summary:

```text
reports/evidence-metrics-2026-05-17-ci-baseline.md
```

Machine-readable JSON:

```text
reports/evidence-metrics-2026-05-17-ci-baseline.json
```

This is the first measured Evidence Metrics baseline.

It records only real CI and Compute Witness fixture measurements from GitHub Actions workflow run 126:

```text
workflow: Rust
run_number: 126
run_id: 25989064156
job: test
job_id: 76391780251
source_commit: 96fea1d5afbb3bd6d540a257bdf03662c6be6b15
conclusion: success
```

Measured values:

```text
formatting_pass -> true
clippy_pass -> true
tests_pass -> true
Compute Witness Rust CLI fixture -> true
workflow_success -> true
ci_failure_count -> 0
```

## Claim boundary

The current reports are not full domain benchmarks.

They do not yet report:

```text
live-run ProofPath latency
large scenario false accept / false block rates
CML causal-validity measured results
LTP trace / replay measured results
PythiaLabs ALLOW / BLOCK / ESCALATE measured distribution
```

Those should be produced by future evidence runs.

## Related docs

```text
docs/EVIDENCE_METRICS_V0_1.md
docs/EVIDENCE_PACKET_V0_1.md
reports/evidence-metrics-template-v0.1.json
```
