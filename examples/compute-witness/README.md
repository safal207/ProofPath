# Compute Witness Demo

This demo documents the first ProofPath compute-boundary proof environment.

It shows two minimal cases:

1. `job_manifest.accept.json` -> a bounded compute request with declared intent and causal authorization.
2. `job_manifest.block.json` -> an unbounded compute request missing causal authorization.

Each manifest has a corresponding receipt:

- `compute_receipt.accept.json`
- `compute_receipt.block.json`

## Demo story

```text
Agent proposes compute job
  -> job manifest records intent, scope, causal parent, and commitments
  -> ProofPath verifier decides ACCEPT or BLOCK
  -> compute receipt records the decision and evidence hash
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
PASS compute witness conformance (2 fixtures)
```

You can also pass an explicit conformance manifest path:

```bash
python3 scripts/validate_compute_witness.py conformance/compute-witness/manifest.json
```

## What this proves in v0.1

This demo proves a narrow but useful contract:

- the compute request has a stable job id;
- the request declares intent;
- the request carries a causal parent when accepted;
- the scope is bounded for accepted jobs;
- model, runtime, input, and output commitments are recorded;
- blocked jobs explain why they were not accepted;
- every receipt can point to audit evidence;
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
  compute_receipt.accept.json
  compute_receipt.block.json

conformance/compute-witness/
  manifest.json

scripts/
  validate_compute_witness.py
```

## Review phrase

```text
ProofPath Compute Witness proves that a compute/action result was requested, scoped, causally authorized, decided, and recorded before it is trusted.
```
