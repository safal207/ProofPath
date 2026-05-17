# ProofPath GitHub Action Quickstart

ProofPath can be used as a reusable GitHub Action to verify action-boundary metrics from a ProofPath audit JSONL file.

This is the first productized ProofPath surface.

## What it does

The action reads an audit log, produces a metrics JSON file, and fails CI when expected metrics do not match.

```text
ProofPath audit JSONL
-> action-boundary metrics JSON
-> expected-value assertions
-> pass / fail CI
```

## Basic usage

```yaml
name: ProofPath action-boundary check

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
          audit-log: proofpath-audit.jsonl
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

## Inputs

| Input | Required | Meaning |
| --- | --- | --- |
| `audit-log` | yes | Path to ProofPath audit JSONL file. |
| `metrics-output` | no | Path where metrics JSON should be written. |
| `run-id` | no | Identifier included in generated metrics. |
| `expected-actions-total` | no | Expected total actions. |
| `expected-actions-blocked` | no | Expected blocked actions. |
| `expected-actions-accepted` | no | Expected accepted actions. |
| `expected-unsafe-without-approval-blocked` | no | Expected no-approval guarded actions blocked. |
| `expected-unsafe-without-approval-false-accepts` | no | Expected false accepts for no-approval guarded actions. |
| `expected-safe-with-approval-false-blocks` | no | Expected false blocks for approved actions. |
| `expected-audit-records-written` | no | Expected audit records. |
| `expected-blocked-forwarded-count` | no | Expected blocked actions forwarded upstream. |
| `expected-accepted-forwarded-count` | no | Expected accepted actions forwarded upstream. |
| `expected-audit-hash-chain-present` | no | Expected hash-chain presence value. |

## Output

| Output | Meaning |
| --- | --- |
| `metrics-json` | Path to generated metrics JSON. |

## Claim boundary

This action verifies action-boundary audit metrics.

It does not by itself prove:

```text
production security
complete prevention of unsafe actions
regulatory compliance
large-scenario benchmark coverage
```

It is a CI evidence gate.

## Product phrase

```text
ProofPath turns action-boundary audit logs into CI-verifiable evidence.
```
