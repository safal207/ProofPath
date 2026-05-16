# Compute Witness Grant Reviewer Path

This document gives grant reviewers a short path for evaluating the ProofPath Compute Witness workstream.

Compute Witness is a narrow proof environment for making AI/agent compute results reviewable before they are trusted. It focuses on the boundary between a proposed compute job and the downstream action or result that may depend on it.

## Core hypothesis

A compute result should not be trusted only because an agent produced it or because a service returned it.

For high-risk agentic systems, a compute job should carry reviewable evidence:

```text
intent
-> scope
-> causal authorization
-> model/runtime/input commitments
-> decision
-> audit evidence
-> optional causal continuity with prior accepted evidence
```

The current repository tests whether this contract can be expressed through committed fixtures, conformance checks, audit packets, challenge cases, and a Rust verifier path.

## 5-minute reviewer path

From the repository root:

```bash
python3 scripts/validate_compute_witness.py
```

Then run the Rust receipt-draft path:

```bash
cargo run -q -p proofpath-verifier --bin proofpath-compute-witness -- examples/compute-witness/job_manifest.accept.json
```

To compare the Rust CLI output against the committed fixture:

```bash
cargo run -q -p proofpath-verifier --bin proofpath-compute-witness -- examples/compute-witness/job_manifest.accept.json > /tmp/rust_receipt_draft.accept.json
diff -u examples/compute-witness/rust_receipt_draft.accept.json /tmp/rust_receipt_draft.accept.json
```

## Key artifacts

| Artifact | Purpose |
| --- | --- |
| [`examples/compute-witness/README.md`](../examples/compute-witness/README.md) | Main demo and reviewer quickstart. |
| [`examples/compute-witness/job_manifest.accept.json`](../examples/compute-witness/job_manifest.accept.json) | Accepted compute job input fixture. |
| [`examples/compute-witness/compute_receipt.accept.json`](../examples/compute-witness/compute_receipt.accept.json) | Expected accepted compute receipt fixture. |
| [`examples/compute-witness/audit_log.accept.json`](../examples/compute-witness/audit_log.accept.json) | Audit evidence fixture for accepted job. |
| [`examples/compute-witness/audit-packet/README.md`](../examples/compute-witness/audit-packet/README.md) | Buyer/reviewer-facing audit packet explanation. |
| [`examples/compute-witness/challenge/README.md`](../examples/compute-witness/challenge/README.md) | Broken-evidence challenge cases. |
| [`examples/compute-witness/rust_receipt_draft.accept.json`](../examples/compute-witness/rust_receipt_draft.accept.json) | Expected output from the Rust CLI receipt-draft path. |
| [`scripts/validate_compute_witness.py`](../scripts/validate_compute_witness.py) | Python conformance validator. |
| [`.github/workflows/compute-witness.yml`](../.github/workflows/compute-witness.yml) | Compute Witness conformance CI. |
| [`.github/workflows/rust.yml`](../.github/workflows/rust.yml) | Rust CI, including CLI output fixture regression check. |

## Evidence chain

The current evidence chain is:

```text
job manifest
  -> compute receipt
  -> audit log entry
  -> canonical SHA-256 verification
  -> optional causal parent receipt verification
  -> challenge fixtures for broken evidence
  -> Rust verifier adapter
  -> Rust CLI receipt-draft output
  -> committed expected output fixture
  -> CI regression check
```

This makes the workstream inspectable in three ways:

1. **Fixture-level review**: reviewers can inspect committed JSON inputs, receipts, audit logs, and expected outputs.
2. **Executable conformance**: reviewers can run the Python validator and Rust CLI locally.
3. **Regression enforcement**: CI checks that the conformance fixtures and Rust CLI output do not silently drift.

## What this proves today

This workstream currently proves a narrow but useful contract:

- compute jobs can declare intent, scope, causal parent, and commitments;
- accepted jobs require causal authorization;
- blocked jobs explain why they were not accepted;
- receipts can be anchored to audit evidence;
- audit evidence can be verified through canonical SHA-256 hashing;
- child jobs can be checked against prior accepted evidence;
- deliberately broken audit hashes and broken causal chains are rejected by challenge fixtures;
- the Rust verifier can project a Compute Witness manifest into a receipt draft;
- the Rust CLI output is compared against a committed fixture in CI.

## What this does not prove yet

This is not yet a full compute attestation system.

It does not currently prove:

- GPU hardware identity;
- trusted execution environment state;
- zkML execution correctness;
- model truthfulness;
- distributed settlement;
- full replay or dispute resolution;
- production key management;
- final Rust audit-hash generation for all packet types.

Those are future layers. The current milestone is intentionally smaller: make the first proof contract inspectable, executable, challengeable, and regression-tested.

## Why this is grant-relevant

Compute Witness addresses a practical safety and governance gap in agentic AI systems:

```text
A model output can look valid while the compute/action lineage behind it is not reviewable.
```

The project turns that concern into concrete infrastructure artifacts:

- committed evidence formats;
- deterministic validators;
- broken-evidence challenge cases;
- Rust implementation path;
- CI checks that enforce the expected behavior.

This is grant-relevant because it converts a broad AI safety claim into something funders can inspect, run, and challenge.

## Next evidence artifacts

The highest-value next steps are:

1. **Rust audit-hash verifier**: move more of the Python conformance logic into Rust without removing the reviewer-friendly Python harness.
2. **More challenge cases**: add missing scope, invalid reversibility, mismatched model/runtime/input commitment cases.
3. **Replay packet**: produce a single compressed reviewer packet containing manifest, receipt, audit log, validator command, and validator output.
4. **Policy boundary mapping**: define when compute-domain `REJECT` should remain `REJECT` versus become `BLOCK`.
5. **Pilot scenario**: connect Compute Witness to a toy agent workflow where an accepted or blocked compute result controls a downstream action.

## Review phrase

```text
Compute Witness is not just a concept: it has committed inputs, expected outputs, conformance checks, challenge cases, and a Rust execution path verified in CI.
```
