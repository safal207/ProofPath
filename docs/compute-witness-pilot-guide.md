# Compute Witness Pilot Integration Guide

Status: Draft v0.1

## Purpose

This guide shows how a team can run a narrow ProofPath Compute Witness pilot on one AI compute or agent workflow.

The goal is not to replace a production governance platform. The goal is to produce a small, inspectable audit packet showing that a compute result was:

```text
requested
-> scoped
-> causally authorized
-> decided
-> anchored to audit evidence
-> optionally linked to prior accepted evidence
```

## Who this pilot is for

This pilot is designed for teams that need evidence around high-risk AI compute actions:

- AI compute marketplaces;
- agent platforms;
- regulated AI product teams;
- AI safety and evaluation teams;
- internal platform teams testing agentic workflows.

## What the pilot proves

A successful pilot proves a narrow contract:

- every compute job has a manifest;
- every verifier decision has a compute receipt;
- every receipt is anchored to an audit log entry;
- `receipt.audit_hash` equals the canonical SHA-256 hash of the audit entry;
- blocked jobs explain the reason they were not accepted;
- child jobs can prove continuity by referencing a prior accepted parent receipt;
- CI can detect broken audit hashes or broken parent-to-child commitments.

## What the pilot does not prove

This pilot does not prove:

- GPU hardware identity;
- trusted execution environment state;
- zkML execution correctness;
- distributed settlement;
- model truthfulness;
- complete compliance readiness;
- production-grade key management.

The first pilot is intentionally smaller:

```text
Make compute authorization and continuity inspectable.
```

## Pilot deliverable

At the end of the pilot, the team should have:

- one accepted compute job fixture;
- one blocked compute job fixture;
- one parent-to-child compute chain fixture;
- one validator output;
- one audit packet or packet draft;
- one short risk note describing what passed, what failed, and what is still not proven.

For concrete packet examples, see [`examples/compute-witness/audit-packet/`](../examples/compute-witness/audit-packet/).

## Required artifacts

Each compute step should produce three artifacts.

### 1. Job manifest

The job manifest records the proposed compute action before it is trusted.

Required v0.1 fields:

```text
job_id
agent_id
intent_id
causal_parent
scope
reversibility
model_hash
runtime_hash
input_hash
expected_output_kind
```

### 2. Compute receipt

The compute receipt records the verifier-visible decision.

Required v0.1 fields:

```text
receipt_id
job_id
agent_id
intent_id
causal_parent
scope
model_hash
runtime_hash
input_hash
output_hash
decision
reason
audit_hash
verified_at
```

### 3. Audit log entry

The audit log entry is the inspectable evidence anchor for the receipt.

The receipt must point to it through:

```text
receipt.audit_hash == sha256(canonical_json(audit_entry))
```

Canonical JSON means sorted keys, compact separators, UTF-8 encoding, and no runtime-dependent formatting.

## Minimal architecture

```text
AI workflow / compute requester
  -> emits job manifest
  -> verifier returns ACCEPT / HOLD / REJECT / BLOCK / AUDIT
  -> emits compute receipt
  -> emits audit log entry
  -> conformance validator checks receipt and audit evidence
  -> CI stores or reports validator output
```

## Example pilot workflow

Start with one workflow that has two steps.

```text
Step 1: run a bounded compute task
  -> accepted parent receipt

Step 2: run a follow-up compute task
  -> child causal_parent = receipt:<parent_receipt_id>
  -> child.input_hash == parent.output_hash
```

The child step should not be treated as causally valid unless it references the accepted parent receipt and consumes the parent's committed output.

## Local validation

From the repository root:

```bash
python3 scripts/validate_compute_witness.py
```

Expected output for the current v0.1 fixture set:

```text
PASS accepted demo inference job
PASS blocked unbounded gpu job
PASS causal chain parent job
PASS causal chain child job
PASS compute witness conformance (4 fixtures)
```

## CI validation

The repository includes a GitHub Actions workflow:

```text
.github/workflows/compute-witness.yml
```

It runs:

```bash
python3 scripts/validate_compute_witness.py
```

A pilot integration should add the same command to the buyer's CI or demo repository.

## Success criteria

The pilot is successful when:

- accepted jobs produce valid receipts;
- blocked jobs produce explicit reasons;
- audit hashes are reproducible;
- child jobs cannot claim continuity without an accepted parent receipt;
- broken hashes or broken parent-child commitments fail validation;
- reviewers can inspect the artifact set without trusting a hidden service.

## Pilot packet outline

A buyer-facing audit packet can be as small as:

```text
workflow_id
job_manifest_path
compute_receipt_path
audit_log_path
computed_audit_hash
verifier_decision
causal_parent_receipt
validator_command
validator_output
non_claims
```

The packet does not need to be a production format in v0.1. It only needs to make evidence reviewable.

## Recommended first pilot

Use this first pilot shape:

```text
Case A: accepted compute job
Case B: blocked compute job
Case C: accepted parent job
Case D: accepted child job linked to parent receipt
```

This is enough to show the core value:

```text
valid evidence passes
unsafe or unauthorized compute is blocked
child compute continuity is checked
```

## Buyer-facing demo script

Use this five-minute script:

```text
1. Show the job manifest.
2. Show the compute receipt.
3. Show the audit log entry.
4. Run the validator.
5. Show the parent-to-child chain.
6. Show the audit packet.
7. Explain what is proven.
8. Explain what is not proven yet.
```

## Adoption ladder

```text
Level 0: Read the Compute Witness docs.
Level 1: Run the fixture validator locally.
Level 2: Add CI conformance to one demo repository.
Level 3: Emit receipts from one real workflow.
Level 4: Store audit packets for review.
Level 5: Add replay/challenge fixtures.
Level 6: Add Rust verifier integration.
Level 7: Add optional TEE, zkML, or provider-specific attestation.
```

For the proposed Rust integration path, see [Compute Witness Rust Integration Spike](compute-witness-rust-integration-spike.md).

## Links

- [Compute Witness Environment](compute-witness-environment.md)
- [Compute Witness Market Value](compute-witness-market-value.md)
- [Compute Witness Rust Integration Spike](compute-witness-rust-integration-spike.md)
- [Compute Witness Demo](../examples/compute-witness/README.md)
- [Compute Witness Audit Packet Example](../examples/compute-witness/audit-packet/README.md)

## Short formulation

```text
ProofPath Compute Witness is pilot-ready when one workflow can emit manifests, receipts, audit logs, audit packets, and validator output that a reviewer can inspect without trusting the model or a hidden service.
```
