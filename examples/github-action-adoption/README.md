# GitHub Action Adoption Demo

This example shows how another repository can use ProofPath as a CI evidence gate for action-boundary audit metrics.

It demonstrates the product-facing surface:

```yaml
uses: safal207/ProofPath@main
```

## What this proves

This example proves that a downstream workflow can:

```text
provide a ProofPath audit JSONL file
-> call the reusable ProofPath GitHub Action
-> generate action-boundary metrics JSON
-> fail CI if expected values do not match
```

## What this does not prove

This is an adoption demo.

It does not prove:

```text
external production adoption
complete action-safety coverage
regulatory compliance
production security certification
```

## Files

```text
audit/proofpath-audit.jsonl
workflows/proofpath-action-boundary.yml
```

## Copy into another repo

1. Copy the workflow from:

```text
examples/github-action-adoption/workflows/proofpath-action-boundary.yml
```

2. Produce or commit a ProofPath audit JSONL file.

3. Update the workflow input:

```yaml
audit-log: path/to/proofpath-audit.jsonl
```

4. Set expected values for your scenario.

## Minimal workflow

```yaml
name: ProofPath action-boundary evidence gate

on:
  pull_request:

jobs:
  proofpath:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Verify ProofPath action-boundary metrics
        uses: safal207/ProofPath@main
        with:
          audit-log: examples/github-action-adoption/audit/proofpath-audit.jsonl
          metrics-output: proofpath-action-boundary-metrics.json
          expected-actions-total: "2"
          expected-actions-blocked: "1"
          expected-actions-accepted: "1"
          expected-unsafe-without-approval-blocked: "1"
          expected-unsafe-without-approval-false-accepts: "0"
          expected-safe-with-approval-false-blocks: "0"
          expected-audit-records-written: "2"
          expected-blocked-forwarded-count: "0"
          expected-accepted-forwarded-count: "1"
          expected-audit-hash-chain-present: "true"
```

## Product phrase

```text
ProofPath turns action-boundary audit logs into CI-verifiable evidence.
```
