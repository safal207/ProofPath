# ProofPath Compute Witness Environment

Status: Draft v0.1

## Purpose

The ProofPath Compute Witness Environment is a minimal proof environment for AI compute and agent actions.

It extends ProofPath from action-boundary verification into compute-boundary accountability: a system should be able to show that a compute request had declared intent, bounded scope, causal authorization, recorded input/output commitments, and a verifier decision before the result becomes trusted evidence.

This document does not claim to cryptographically prove arbitrary large-model execution. The first version is intentionally narrower and reviewable.

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

## Example flow

```text
1. Agent proposes compute job.
2. Client creates job manifest.
3. ProofPath evaluates intent, causal parent, scope, reversibility, and commitments.
4. Safe job receives ACCEPT.
5. Unsafe or unauthorized job receives REJECT/BLOCK/HOLD.
6. Result is recorded as a compute receipt.
7. Receipt can be attached to audit evidence, replay, or future dispute flows.
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
- a credible next step toward challenge/replay and audit-log verification.

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
It proves that a compute/action result was requested, scoped, causally authorized, committed, decided, and recorded in a way that can be inspected later.
```
