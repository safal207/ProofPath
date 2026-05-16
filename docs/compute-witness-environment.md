# ProofPath Compute Witness Environment

Status: Draft v0.1

## Purpose

The ProofPath Compute Witness Environment is a minimal proof environment for AI compute and agent actions.

It extends ProofPath from action-boundary verification into compute-boundary accountability: a system should be able to show that a compute request had declared intent, bounded scope, causal authorization, recorded input/output commitments, and a verifier decision before the result becomes trusted evidence.

This document does not claim to cryptographically prove arbitrary large-model execution. The first version is intentionally narrower and reviewable.

For market positioning, see [Compute Witness Market Value](compute-witness-market-value.md).
For practical deployment, see [Compute Witness Pilot Integration Guide](compute-witness-pilot-guide.md).

## Core claim

ProofPath does not merely ask whether a request was authenticated.

It asks:

```text
Was this specific compute/action request declared, scoped, causally authorized, executed under a recorded manifest, and accepted or blocked by a verifier?
```

## Why this exists

AI compute markets and agent platforms increasingly need more than raw GPU availability or API credentials.

They need proof surfaces for questions such as:

- Who requested the compute job?
- What intent did the job serve?
- Which prior decision authorized it?
- What scope limited the job?
- Which model/runtime/input commitments were used?
- What output commitment was returned?
- Which verifier accepted, held, rejected, or blocked the result?
- Can the decision be inspected later?

Without this layer, a result can look useful while the authorization lineage behind it is missing, ambiguous, or impossible to replay.

## Non-goals for v0.1

This v0.1 environment does not claim to provide:

- full zkML proof of arbitrary LLM execution;
- trusted execution environment attestation;
- external key management;
- GPU hardware proof;
- distributed consensus;
- production-grade payment settlement;
- full challenge/dispute games.

Those are future layers. The v0.1 goal is to create a small, auditable contract that can be extended.

## Proof stack

```text
Job Manifest
  -> declares intent, causal parent, scope, model/runtime/input commitments

ProofPath Verifier
  -> decides ACCEPT / HOLD / REJECT / BLOCK / AUDIT

Compute Receipt
  -> records decision, result commitment, audit hash, and verification state

Audit Log
  -> preserves hash-chained evidence for later inspection
```

## Minimal job manifest

A job manifest describes the requested compute action before execution.

Required fields for this v0.1 profile:

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

Example decision logic:

```text
ACCEPT if:
  - intent_id is present
  - causal_parent is present
  - scope is bounded
  - reversibility is valid
  - irreversible requests have explicit approval
  - model/runtime/input commitments are present

BLOCK if:
  - the request is structurally valid but unsafe by policy

REJECT if:
  - required ProofPath context is missing or malformed

HOLD if:
  - the request needs more evidence, approval, or preconditions
```

## Minimal compute receipt

A compute receipt records the verifier-visible evidence after a compute/action request.

Required fields for this v0.1 profile:

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

## Audit-log verification

Each compute receipt must point to an audit log entry through `receipt.audit_hash`.

For v0.1, the hash is computed as:

```text
sha256(canonical_json(audit_entry))
```

Canonical JSON means:

- keys sorted;
- compact separators;
- UTF-8 encoding;
- no runtime-dependent formatting.

The validator also checks that audit identity fields match the receipt and that `previous_audit_hash`, when present, points to an earlier audit entry in the same conformance run.

This does not prove GPU execution or zkML correctness. It proves that the receipt is anchored to inspectable audit evidence.

## Causal chain verification

A fixture can declare a prior accepted receipt as its causal parent:

```text
"causal_parent_receipt": "cwr_chain_parent_001"
```

For that fixture, the job manifest and receipt must use:

```text
"causal_parent": "receipt:cwr_chain_parent_001"
```

The validator also checks that the child job input commitment equals the parent receipt output commitment:

```text
child.input_hash == parent.output_hash
```

This makes the v0.1 chain inspectable: a follow-up compute job cannot silently claim continuity unless it points to an accepted parent receipt and consumes that parent's committed output.

## Example flow

```text
1. Agent proposes compute job.
2. Client creates job manifest.
3. ProofPath evaluates intent, causal parent, scope, reversibility, and commitments.
4. Safe job receives ACCEPT.
5. Unsafe or unauthorized job receives REJECT/BLOCK/HOLD.
6. Result is recorded as a compute receipt.
7. Receipt is anchored to audit evidence through canonical SHA-256 verification.
8. Optional child jobs can reference prior accepted receipts as causal parents.
9. Receipt can be attached to replay, challenge, or future dispute flows.
```

## Relationship to the broader stack

- ProofPath is the action and compute gateway.
- CML can validate causal authorization lineage.
- LTP can replay and inspect the execution path.
- T-Trace can provide append-only transition records.
- CaPU can enforce Gate -> Incubate -> Commit -> Execute before side effects.
- TTM DB can store immutable trace substrate for later verification.

## Reviewer success criteria

A reviewer should be able to inspect this environment and see:

- a clear manifest format;
- a clear receipt format;
- valid and blocked examples;
- explicit non-claims;
- a path from action proof to compute proof;
- executable conformance for receipt-to-audit evidence anchoring;
- executable conformance for parent-to-child compute continuity;
- a clear first market wedge for pilots and adoption.

## Future work

```text
v0.2 - executable fixture validator
v0.3 - audit-log verification fixture
v0.4 - multi-step causal chain example
v0.5 - replay/challenge example
v0.6 - optional hardware/TEE attestation adapter
v0.7 - decentralized compute market integration sketch
```

## Short formulation

```text
ProofPath Compute Witness does not prove that all AI computation is mathematically correct.
It proves that a compute/action result was requested, scoped, causally authorized, committed, decided, anchored to audit evidence, and linked to prior accepted evidence in a way that can be inspected later.
```
