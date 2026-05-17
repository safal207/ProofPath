# ProofPath v0.1 Product Milestone

ProofPath v0.1 is the first product milestone for a CI-verifiable action-boundary evidence gate.

It turns ProofPath audit logs into machine-checkable CI evidence.

## One-sentence summary

```text
ProofPath v0.1 verifies whether high-risk AI-agent/API actions produced the expected BLOCK / ACCEPT / audit metrics before CI passes.
```

## Product phrase

```text
ProofPath turns action-boundary audit logs into CI-verifiable evidence.
```

## What is included in v0.1

v0.1 includes the first complete product slice:

```text
live demo
-> audit log
-> metrics collector
-> CI verification
-> reusable GitHub Action
-> downstream-style adoption example
```

## Core artifacts

| Artifact | Purpose |
| --- | --- |
| `crates/proofpath-gateway/` | Rust gateway that evaluates and forwards or blocks actions. |
| `scripts/collect_action_boundary_metrics.py` | Converts audit JSONL into metrics JSON. |
| `scripts/assert_action_boundary_metrics.py` | Asserts expected metrics for CI. |
| `action.yml` | Reusable composite GitHub Action. |
| `docs/GITHUB_ACTION_QUICKSTART.md` | Product quickstart for GitHub Action users. |
| `examples/github-action-adoption/` | Downstream-style adoption example. |
| `scripts/run_live_action_boundary_check.sh` | Live CI demo runner. |
| `reports/action-boundary-fixture-2026-05-17.json` | First fixture metrics baseline. |
| `reports/evidence-metrics-2026-05-17-ci-baseline.json` | First CI reproducibility baseline. |

## CI-validated evidence

The current CI validates:

```text
formatting
clippy
Rust tests
Compute Witness Rust CLI fixture
live action-boundary metrics
reusable ProofPath GitHub Action self-test
```

The important product-level check is:

```text
ProofPath audit JSONL
-> action-boundary metrics JSON
-> expected-value assertions
-> CI pass / fail
```

## GitHub Action usage

A downstream repository can use ProofPath as a CI evidence gate:

```yaml
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

## Demo story

The canonical action-boundary demo checks two actions:

```text
1. no-approval irreversible action -> BLOCK
2. approved irreversible action -> ACCEPT
```

Expected v0.1 metrics:

```text
actions_total = 2
actions_blocked = 1
actions_accepted = 1
unsafe_without_approval_blocked = 1
unsafe_without_approval_false_accepts = 0
safe_with_approval_false_blocks = 0
audit_records_written = 2
blocked_forwarded_count = 0
accepted_forwarded_count = 1
audit_hash_chain_present = true
```

## Reviewer interpretation

Safe claim:

```text
ProofPath v0.1 demonstrates a CI-verifiable evidence gate for action-boundary audit metrics.
```

Stronger but still bounded claim:

```text
ProofPath v0.1 shows that an AI-agent/API action boundary can be expressed as audit logs, measured as metrics, and enforced as CI pass/fail evidence.
```

Do not overstate this as:

```text
ProofPath proves complete AI-agent safety.
```

That is not claimed.

## Non-claims

v0.1 does not claim:

```text
production security certification
complete prevention of unsafe actions
formal verification
regulatory compliance
external production adoption
large-scenario benchmark coverage
latency benchmark coverage
```

## What v0.1 proves

v0.1 proves that the first product surface exists:

```text
an audit log can be checked by a reusable CI action
```

That is the minimum useful product slice.

## Next milestones

### v0.2

```text
publish versioned GitHub release/tag
add larger action-boundary scenario suite
emit artifact uploads from CI
add latency measurement
```

### v0.3

```text
add policy configuration file
support multiple action profiles
add richer report summaries
add third-party/downstream repo demo
```

## Bottom line

ProofPath v0.1 is no longer only a protocol idea or local demo.

It is a reusable CI evidence gate for action-boundary audit metrics.
