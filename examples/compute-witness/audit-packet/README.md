# Compute Witness Audit Packet Example

Status: Draft v0.1

## Purpose

This directory shows what a small buyer/reviewer-facing Compute Witness audit packet can look like.

The packet is not a new proof system. It is a compact index over existing evidence:

```text
job manifest
-> compute receipt
-> audit log entry
-> computed audit hash
-> validator command
-> validator output
-> non-claims
```

## Why this exists

A reviewer may not want to inspect every fixture file one by one. An audit packet gives them a single object that says:

- which workflow was evaluated;
- which evidence files belong together;
- which verifier decision was produced;
- which audit hash was checked;
- whether a causal parent receipt was involved;
- how to reproduce validation.

## Files

```text
examples/compute-witness/audit-packet/
  README.md
  packet.accept.json
  packet.chain.json
```

## Packet types

### `packet.accept.json`

A minimal packet for one accepted compute job.

It points to:

- `job_manifest.accept.json`
- `compute_receipt.accept.json`
- `audit_log.accept.json`

### `packet.chain.json`

A packet for a parent-to-child compute chain.

It points to:

- parent job manifest, receipt, and audit entry;
- child job manifest, receipt, and audit entry;
- parent receipt id used by the child;
- parent output hash consumed as the child input hash.

## Validation

From the repository root:

```bash
python3 scripts/validate_compute_witness.py
```

Expected output:

```text
PASS accepted demo inference job
PASS blocked unbounded gpu job
PASS causal chain parent job
PASS causal chain child job
PASS compute witness conformance (4 fixtures)
```

## What this packet proves

The packet proves a narrow, inspectable evidence contract:

- referenced evidence files exist in the repository;
- receipt identity matches manifest identity;
- receipt decision matches the expected conformance decision;
- receipt audit hash can be recomputed from the audit log entry;
- child compute can point to a prior accepted parent receipt;
- child input commitment can match parent output commitment.

## What this packet does not prove

This packet does not prove:

- GPU hardware identity;
- trusted execution environment state;
- zkML execution correctness;
- distributed settlement;
- model output truth;
- production-grade key management;
- complete regulatory compliance.

## Buyer-facing phrase

```text
This packet makes compute authorization and continuity reviewable without asking the reviewer to trust the model or a hidden service.
```
