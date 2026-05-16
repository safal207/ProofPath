# Compute Witness Challenge Fixtures

Status: Draft v0.1

## Purpose

Challenge fixtures prove that the Compute Witness validator catches broken evidence, not only that valid evidence passes.

The intended reviewer story is:

```text
valid evidence passes
broken evidence fails
expected failure is itself checked by CI
```

## Challenge manifest

The challenge suite is defined in:

```text
conformance/compute-witness/challenge_manifest.json
```

It uses the same validator as the normal conformance manifest:

```bash
python3 scripts/validate_compute_witness.py conformance/compute-witness/challenge_manifest.json
```

## Current challenge cases

### 1. Bad audit hash

Fixture:

```text
examples/compute-witness/compute_receipt.challenge.bad_audit_hash.json
```

This receipt points to a valid audit log entry but uses the wrong `audit_hash`.

Expected validator behavior:

```text
audit_hash mismatch
```

### 2. Broken child input commitment

Fixture:

```text
examples/compute-witness/job_manifest.challenge.broken_child.json
```

This child manifest points to the accepted parent receipt but uses an input hash that does not match the parent output hash.

Expected validator behavior:

```text
manifest input_hash must equal parent output_hash
```

## What this proves

The challenge fixtures prove that the validator catches:

- forged or stale receipt-to-audit evidence;
- broken parent-to-child compute continuity;
- expected failure regressions in CI.

## What this does not prove

This challenge suite does not prove:

- GPU hardware identity;
- zkML execution correctness;
- trusted execution environment state;
- distributed settlement;
- model output truth.

## Buyer-facing phrase

```text
ProofPath Compute Witness does not only show valid evidence. It also demonstrates that broken evidence is rejected in a reproducible way.
```
