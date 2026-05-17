# Reports

This directory contains reviewer-facing measured and planned evidence reports for ProofPath and the connected evidence-gate stack.

## Current reports

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

This baseline is not a domain benchmark.

It does not yet report:

```text
ProofPath action-boundary false accept / false block rates
ProofPath decision latency
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
