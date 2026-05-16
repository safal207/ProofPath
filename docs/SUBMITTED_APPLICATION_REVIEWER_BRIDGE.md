# Submitted Application Reviewer Bridge

This page is for reviewers who arrived here from an already-submitted grant application, email inquiry, or earlier project framing.

Some prior materials may have used names or descriptions such as:

- PythiaLabs / open evidence gates;
- Liminal Stack / deterministic oversight;
- LTP + CML / causal trace oversight;
- agentic AI evidence gates;
- verifiable intent for high-risk AI-agent actions.

Those names should not be treated as exact aliases. They were earlier surfaces of the same broader research direction: making high-risk AI-agent actions reviewable before execution and auditable after the fact.

ProofPath is the current implementation-focused repository for that direction.

## Current implementation focus

ProofPath focuses on the execution boundary:

```text
authenticated request
  != authorized action
  != valid scope
  != causal authorization
  != reviewable evidence
```

The repository now contains two connected implementation tracks:

1. **ProofPath gateway**: a pre-execution boundary for accepting or blocking high-risk actions.
2. **Compute Witness**: a proof environment for turning AI/agent compute into reviewable evidence.

## If your application referenced PythiaLabs

PythiaLabs framed the problem as open evidence gates for high-risk AI-agent actions.

The closest current continuation in this repository is:

- [Compute Witness grant reviewer path](COMPUTE_WITNESS_GRANT_REVIEWER_PATH.md)
- [Compute Witness reviewer quickstart](../examples/compute-witness/README.md#reviewer-quickstart)
- [Compute Witness audit packet](../examples/compute-witness/audit-packet/README.md)

The shared idea is:

```text
before trusting an AI-agent result or action,
there should be explicit evidence of intent, scope, authorization, commitments, and auditability.
```

## If your application referenced Liminal Stack, LTP, or CML

Those materials emphasized deterministic oversight, causal memory, traces, and replayable safety evidence.

The closest current continuation in this repository is:

- ProofPath's action-context model;
- hash-chained audit logs;
- Compute Witness causal parent checks;
- committed conformance fixtures;
- Rust verifier implementation work.

The shared idea is:

```text
a system can look functionally correct while still being causally or evidentially invalid.
```

ProofPath narrows that idea into an executable gateway/verifier surface.

## Fast reviewer route

Start here:

1. Read the [root README](../README.md) 60-second reviewer summary.
2. Open the [Compute Witness grant reviewer path](COMPUTE_WITNESS_GRANT_REVIEWER_PATH.md).
3. Run the [Compute Witness reviewer quickstart](../examples/compute-witness/README.md#reviewer-quickstart).
4. Inspect the [audit packet example](../examples/compute-witness/audit-packet/README.md).
5. Check the CI-backed Rust verifier path in `.github/workflows/rust.yml`.

The shortest local path is:

```bash
python3 scripts/validate_compute_witness.py
cargo run -q -p proofpath-verifier --bin proofpath-compute-witness -- examples/compute-witness/job_manifest.accept.json
```

## What changed since earlier applications

The current repository now includes more executable evidence than the earlier prose/application materials:

- reviewer-facing root positioning;
- Compute Witness grant reviewer path;
- grant evidence checklist;
- committed job manifests, receipts, and audit fixtures;
- Python conformance validator;
- audit packet examples;
- broken-evidence challenge fixtures;
- Rust verifier adapter;
- Rust CLI path;
- expected Rust output fixture;
- Rust audit-hash verifier primitive;
- CI regression checks.

In short:

```text
earlier applications: research direction and proposed evidence-gate work
current repository: executable evidence-chain implementation and verifier path
```

## What this does not claim

This bridge does not claim that every earlier project name is identical to ProofPath.

It also does not claim that ProofPath currently provides:

- GPU hardware identity;
- trusted execution environment attestation;
- zkML correctness;
- model truthfulness;
- production key management;
- distributed settlement;
- full replay/dispute resolution.

Those are future layers. The current work focuses on inspectable evidence contracts, verifier primitives, and regression-tested examples.

## Reviewer phrase

```text
If you arrived here from an earlier grant application, this repository is the current executable evidence layer for the same research direction: verifiable intent, causal authorization, and reviewable evidence for high-risk AI-agent actions.
```
