# ProofPath Control Cloud v0.1

ProofPath Control Cloud turns a set of Assured Action clearance certificates into a deterministic operational snapshot, an operator-earnings preview, and a canonical audit export.

```text
Assured Action certificates
+ risk tier
+ operator assignments
+ settlement policy
        ↓
Control Cloud snapshot builder
        ↓
deterministic signed-build snapshot
+ JSONL audit export
+ static dashboard
```

## What this slice does

- validates the observable fields of ProofPath Deploy Guard clearance certificates;
- rejects duplicate action IDs and clearance roots;
- aggregates `ACCEPT`, `HOLD`, `BLOCK`, and `CHALLENGE` decisions;
- calculates risk-adjusted price previews using integer minor units and basis points;
- deterministically allocates an operator pool by explicit weights;
- proves conservation of gross value, platform share, operator pool, infrastructure share, and dispute reserve;
- emits a domain-separated `snapshot_root`;
- emits one canonical JSONL audit event per action;
- packages a dependency-free browser dashboard;
- publishes the snapshot and audit export as signed build artifacts in CI.

## Financial boundary

This reference implementation **does not move money**. It calls no payment processor, bank, wallet, exchange, or blockchain.

Every output is marked:

```text
financial_mode: SIMULATION_ONLY
financial_status: SIMULATION_ONLY_NOT_PAYABLE
payments_executed: false
```

The generated operator earnings are previews, not balances or debts. The snapshot is **not an invoice**, not a payout instruction, not a bank ledger, and **not insurance**. The `dispute_reserve` field is an allocation preview, not regulated insurance capital or customer funds.

## Assurance boundary

Control Cloud summarizes supplied certificates. It **does not re-run Deploy Guard**, independently verify the underlying GitHub evidence, execute a deployment, grant authority, or claim an external quorum.

The snapshot always states:

```text
deployment_performed: false
authority_granted: false
external_quorum_claimed: false
```

A production service must verify certificate provenance and authorization before ingestion, authenticate tenants, enforce access control, provide durable storage, and integrate an appropriately licensed payment or coverage partner before presenting payable balances or covered actions.

## Deterministic settlement preview

All money values use integer minor units. All allocation and risk inputs use basis points.

```text
gross preview
= base price
× risk multiplier
× decision multiplier

operator pool + dispute reserve + infrastructure + platform
= gross preview exactly
```

Operator pool rounding is deterministic. Each operator first receives the integer floor of its weighted share. Remaining minor units are assigned in stable operator order. No value is created or lost.

## Build a snapshot

```bash
python3 control-cloud/build_snapshot.py \
  --dataset examples/control-cloud/assured-actions.json \
  --policy examples/control-cloud/settlement-policy.json \
  --output artifacts/control-cloud/control-cloud-snapshot.json \
  --audit-export artifacts/control-cloud/audit-export.jsonl
```

Reference output:

```text
actions:        4
ACCEPT:         1
HOLD:           1
BLOCK:          1
CHALLENGE:      1
gross preview:  25500 USD minor units
operator pool:  14024 USD minor units
snapshot root:  sha256:a782f7a1b8fc5d7a6a11815066191a304a32231d969381637902a75f55467deb
```

## Dashboard

The CI artifact places these files together:

```text
index.html
control-cloud-snapshot.json
audit-export.jsonl
```

Serve the directory with any static HTTP server or open the page and select a snapshot manually. The page has no third-party scripts, fonts, analytics, payment SDKs, or cloud credentials. Data values are rendered through DOM `textContent`.

## Signed build artifact

The GitHub workflow keyless-attests the exact snapshot bytes and the exact JSONL audit export as a **signed build artifact**. That attestation proves which repository workflow produced those bytes; it does not transform a simulation into a payable settlement or an insured obligation.

## Future production layers

```text
v0.1 deterministic snapshot and dashboard
  ↓
tenant-authenticated ingestion API
  ↓
verified certificate provenance and retention
  ↓
operator identity / KYB / payout accounts
  ↓
disputes and bonded witness accounting
  ↓
licensed payment and coverage partners
```
