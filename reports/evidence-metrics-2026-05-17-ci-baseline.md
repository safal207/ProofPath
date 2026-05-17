# Evidence Metrics CI Baseline — 2026-05-17

This report is the first measured baseline for Evidence Metrics v0.1.

It records only what has actually been measured from the successful GitHub Actions validation run.

It does not invent benchmark numbers.

## Source

```text
workflow: Rust
run_number: 126
run_id: 25989064156
job: test
job_id: 76391780251
source_commit: 96fea1d5afbb3bd6d540a257bdf03662c6be6b15
conclusion: success
```

## Measured values

| Area | Metric | Value | Source |
| --- | --- | --- | --- |
| CI | workflow_success | true | Rust workflow run 126 |
| CI | formatting_pass | true | Check formatting step |
| CI | clippy_pass | true | Run clippy step |
| CI | tests_pass | true | Run tests step |
| Compute Witness | compute_witness_cli_fixture_pass | true | Verify Compute Witness Rust CLI fixture step |
| CI | ci_runs_total | 1 | GitHub Actions workflow run 25989064156 |
| CI | ci_success_count | 1 | GitHub Actions workflow run 25989064156 |
| CI | ci_failure_count | 0 | GitHub Actions workflow run 25989064156 |
| Reviewer artifacts | metrics_template_present | true | `reports/evidence-metrics-template-v0.1.json` |
| Reviewer artifacts | measured_baseline_present | true | `reports/evidence-metrics-2026-05-17-ci-baseline.json` |

## Interpretation

This baseline shows that the current repository evidence path is reproducible at the CI level:

```text
formatting -> success
clippy -> success
tests -> success
Compute Witness Rust CLI fixture -> success
workflow -> success
```

This is a real measured baseline.

It is not yet a domain benchmark.

## What remains planned

The following metrics remain planned until future evidence runs generate values:

```text
ProofPath action-boundary false accept / false block rates
ProofPath decision latency p50 / p95
ProofPath audit hash-chain validation count
Compute Witness valid / invalid packet counts
Compute Witness audit-hash mismatch detection count
CML causal-validity measured fixture results
LTP trace / replay measured fixture results
PythiaLabs ALLOW / BLOCK / ESCALATE measured gate distribution
```

## Reviewer-safe claim

Safe claim:

```text
The repository currently passes its CI evidence path, including formatting, clippy, Rust tests, and the Compute Witness Rust CLI fixture.
```

Do not overstate this as:

```text
The system has been benchmarked across all action-boundary domains.
```

That has not been measured yet.

## Next measured milestone

The next milestone should be:

```text
Evidence Metrics v0.2
-> run ProofPath dangerous-action demo
-> parse audit log
-> emit action-boundary metrics JSON
-> summarize false accept / false block / audit record counts
```

That would turn this baseline from CI reproducibility into domain-level evidence.
