# Action-Boundary Fixture Metrics — 2026-05-17

This report is the first measured action-boundary fixture baseline for the ProofPath dangerous-action demo.

It measures the canonical audit fixture:

```text
fixtures/action-boundary/dangerous-action-audit.jsonl
```

Metrics are also available as machine-readable JSON:

```text
reports/action-boundary-fixture-2026-05-17.json
```

## Scenario

The fixture contains two audit records:

```text
1. irreversible account.delete without human approval -> BLOCK
2. irreversible account.delete with explicit human approval -> ACCEPT
```

## Measured values

| Metric | Value | Meaning |
| --- | ---: | --- |
| `actions_total` | 2 | Two proposed actions are represented in the audit fixture. |
| `actions_blocked` | 1 | The unsafe irreversible action without approval is blocked. |
| `actions_accepted` | 1 | The approved irreversible action is accepted. |
| `unsafe_without_approval_blocked` | 1 | The expected unsafe case is blocked. |
| `unsafe_without_approval_false_accepts` | 0 | The unsafe fixture case is not accepted. |
| `safe_with_approval_false_blocks` | 0 | The approved fixture case is not blocked. |
| `audit_records_written` | 2 | Both decisions appear in the audit trail. |
| `blocked_forwarded_count` | 0 | The blocked action is not forwarded upstream. |
| `accepted_forwarded_count` | 1 | The accepted action is forwarded upstream. |
| `audit_hash_chain_present` | true | The second record links to the previous hash. |

## Interpretation

Safe interpretation:

```text
The dangerous-action fixture demonstrates one blocked irreversible action without approval and one accepted approved action, both captured as audit records.
```

This supports the core ProofPath claim:

```text
valid credential != valid action
```

A request can be structurally valid and still blocked if the action lacks approval or causal authorization.

## What this does not claim

This report does not claim:

```text
production benchmark coverage
latency measurement
large scenario coverage
complete prevention of unsafe actions
production security certification
regulatory compliance
```

It is a fixture baseline.

## Next measured step

The next measured step should run the live dangerous-action demo and emit the same metrics from the generated `proofpath-audit.jsonl` file:

```text
python3 examples/upstream/demo_server.py
cargo run -p proofpath-gateway
bash examples/agent-dangerous-action/agent_delete_without_approval.sh
bash examples/agent-dangerous-action/agent_delete_with_approval.sh
python3 scripts/collect_action_boundary_metrics.py \
  --input proofpath-audit.jsonl \
  --output reports/action-boundary-live-run.json
```

That would move from:

```text
fixture baseline
```

to:

```text
live demo run baseline
```
