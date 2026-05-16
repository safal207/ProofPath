# Compute Witness Demo

This demo documents the first ProofPath compute-boundary proof environment.

It shows four minimal cases:

1. `job_manifest.accept.json` -> a bounded compute request with declared intent and causal authorization.
2. `job_manifest.block.json` -> an unbounded compute request missing causal authorization.
3. `job_manifest.chain.parent.json` -> the first accepted job in a causal compute chain.
4. `job_manifest.chain.child.json` -> a follow-up job that depends on the parent receipt output.

Each manifest has a corresponding receipt and audit log entry.

For market positioning and pilot packaging, see [`docs/compute-witness-market-value.md`](../../docs/compute-witness-market-value.md).
For buyer/reviewer-facing evidence bundles, see [`audit-packet/`](audit-packet/).

## Demo story

```text
Agent proposes compute job
  -> job manifest records intent, scope, causal parent, and commitments
  -> ProofPath verifier decides ACCEPT or BLOCK
  -> compute receipt records the decision and audit hash
  -> audit log entry is verified through canonical SHA-256 hashing
  -> optional child jobs prove continuity by referencing parent receipts
```

## Run validation

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

You can also pass an explicit conformance manifest path:

```bash
python3 scripts/validate_compute_witness.py conformance/compute-witness/manifest.json
```

## Run the Rust receipt-draft CLI

The Rust verifier can also project a Compute Witness job manifest into a receipt draft:

```bash
cargo run -p proofpath-verifier --bin proofpath-compute-witness -- examples/compute-witness/job_manifest.accept.json
```

This command emits a `ComputeWitnessReceiptDraft` JSON object.

Expected output fixture:

```text
examples/compute-witness/rust_receipt_draft.accept.json
```

You can compare the command output against the fixture:

```bash
cargo run -q -p proofpath-verifier --bin proofpath-compute-witness -- examples/compute-witness/job_manifest.accept.json > /tmp/rust_receipt_draft.accept.json
diff -u examples/compute-witness/rust_receipt_draft.accept.json /tmp/rust_receipt_draft.accept.json
```

It does not emit a final audit-anchored receipt yet. Audit hashes, audit packets, and challenge execution remain in the conformance layer for v0.1.

## What this proves in v0.1

This demo proves a narrow but useful contract:

- the compute request has a stable job id;
- the request declares intent;
- the request carries a causal parent when accepted;
- the scope is bounded for accepted jobs;
- model, runtime, input, and output commitments are recorded;
- blocked jobs explain why they were not accepted;
- every receipt is anchored to audit evidence;
- audit evidence is verified through canonical SHA-256 hashing;
- optional `previous_audit_hash` links to an earlier audit entry;
- child jobs can reference a prior accepted receipt as their causal parent;
- child job input commitments can be checked against parent receipt output commitments;
- the fixture contract is executable through `scripts/validate_compute_witness.py`.

## What it does not prove yet

This demo does not yet prove:

- GPU hardware identity;
- trusted execution environment state;
- zkML execution correctness;
- distributed settlement;
- full replay or dispute resolution.

Those are future layers. This fixture exists to make the first proof contract inspectable.

## Files

```text
examples/compute-witness/
  README.md
  job_manifest.accept.json
  job_manifest.block.json
  job_manifest.chain.parent.json
  job_manifest.chain.child.json
  compute_receipt.accept.json
  compute_receipt.block.json
  compute_receipt.chain.parent.json
  compute_receipt.chain.child.json
  rust_receipt_draft.accept.json
  audit_log.accept.json
  audit_log.block.json
  audit_log.chain.parent.json
  audit_log.chain.child.json
  audit-packet/
    README.md
    packet.accept.json
    packet.chain.json

conformance/compute-witness/
  manifest.json

scripts/
  validate_compute_witness.py
```

## Contract path

```text
job manifest
  -> compute receipt
  -> audit log entry
  -> canonical SHA-256 verification
  -> optional causal parent receipt verification
  -> CI conformance check
```

## Review phrase

```text
ProofPath Compute Witness proves that a compute/action result was requested, scoped, causally authorized, decided, anchored to audit evidence, and linked to prior accepted evidence before it is trusted.
```
