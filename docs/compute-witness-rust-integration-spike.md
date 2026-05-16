# Compute Witness Rust Integration Spike

Status: Draft v0.1

## Purpose

This document maps the Compute Witness JSON fixture contract to the existing Rust `proofpath-verifier` crate.

The goal is not to rewrite the verifier in one step. The goal is to identify a small adapter path that moves Compute Witness from Python-only conformance into the production-facing Rust core without destabilizing the v0.1 JSON fixtures.

## Current Rust baseline

The repository is already a Rust workspace with:

```text
crates/proofpath-verifier
crates/proofpath-gateway
```

The verifier crate currently exposes:

```text
RequestContext
Decision
ReasonCode
VerificationResult
verify(ctx: &RequestContext) -> VerificationResult
```

It validates the first ProofPath HTTP action context profile:

```text
x-proofpath-intent-id
x-proofpath-causal-parent
x-proofpath-scope
x-proofpath-reversibility
x-proofpath-human-approval
```

The existing CLI is:

```bash
cargo run -p proofpath-verifier --bin proofpath-verify -- <request.http>
```

It parses HTTP headers, calls `verify()`, and prints a JSON `VerificationResult`.

## Current Compute Witness baseline

Compute Witness currently lives as a fixture-level evidence contract:

```text
job manifest
-> compute receipt
-> audit log entry
-> canonical SHA-256 verification
-> optional causal parent receipt verification
-> challenge fixtures with expected failures
```

Current executable validator:

```bash
python3 scripts/validate_compute_witness.py
python3 scripts/validate_compute_witness.py conformance/compute-witness/challenge_manifest.json
```

The Python validator is intentionally reviewable and dependency-free. It should remain the canonical conformance harness until the Rust adapter reaches parity.

## Integration principle

Do not merge Compute Witness directly into the action verifier rules.

Instead, add a narrow adapter layer:

```text
ComputeWitnessJobManifest JSON
  -> RequestContext projection
  -> proofpath_verifier::verify()
  -> ComputeWitnessReceipt draft
  -> audit/conformance validation
```

This keeps the existing verifier focused on action-context policy while letting Compute Witness reuse the same decision vocabulary.

## Field mapping

### Manifest to RequestContext

```text
job_manifest.intent_id       -> x-proofpath-intent-id
job_manifest.causal_parent   -> x-proofpath-causal-parent
job_manifest.scope           -> x-proofpath-scope
job_manifest.reversibility   -> x-proofpath-reversibility
job_manifest.human_approval  -> x-proofpath-human-approval, optional
```

### VerificationResult to receipt

```text
VerificationResult.decision       -> compute_receipt.decision
VerificationResult.reason         -> compute_receipt.reason
VerificationResult.intent_id      -> compute_receipt.intent_id
VerificationResult.causal_parent  -> compute_receipt.causal_parent
VerificationResult.scope          -> compute_receipt.scope
```

### Manifest fields that remain Compute Witness specific

These fields should stay outside the minimal action verifier at first:

```text
job_id
agent_id
model_hash
runtime_hash
input_hash
expected_output_kind
output_hash
audit_hash
verified_at
```

They belong to the Compute Witness adapter/receipt layer, not the generic HTTP action-context verifier.

## Proposed Rust types

Add these types in a future PR, likely under `crates/proofpath-verifier/src/compute_witness.rs` or a small sibling crate if the boundary grows.

```rust
pub struct ComputeWitnessJobManifest {
    pub profile: String,
    pub job_id: String,
    pub agent_id: String,
    pub intent_id: String,
    pub causal_parent: Option<String>,
    pub scope: String,
    pub reversibility: Reversibility,
    pub human_approval: Option<String>,
    pub model_hash: String,
    pub runtime_hash: String,
    pub input_hash: String,
    pub expected_output_kind: String,
    pub requested_at: Option<String>,
}

pub struct ComputeWitnessReceiptDraft {
    pub job_id: String,
    pub agent_id: String,
    pub intent_id: Option<String>,
    pub causal_parent: Option<String>,
    pub scope: Option<String>,
    pub model_hash: String,
    pub runtime_hash: String,
    pub input_hash: String,
    pub output_hash: Option<String>,
    pub decision: Decision,
    pub reason: Option<ReasonCode>,
}
```

The first Rust adapter should not generate final `audit_hash`. That should remain part of the audit/conformance layer until canonical JSON hashing is implemented and tested in Rust.

## Proposed functions

```rust
pub fn manifest_to_request_context(manifest: &ComputeWitnessJobManifest) -> RequestContext;

pub fn verify_compute_manifest(manifest: &ComputeWitnessJobManifest) -> ComputeWitnessReceiptDraft;
```

Expected behavior:

```text
1. Parse manifest JSON.
2. Project manifest into RequestContext.
3. Call existing verify().
4. Return a receipt draft with verifier decision fields plus compute commitment fields.
```

## Proposed CLI

A future minimal CLI could be:

```bash
cargo run -p proofpath-verifier --bin proofpath-compute-witness -- examples/compute-witness/job_manifest.accept.json
```

Expected output:

```json
{
  "job_id": "job_demo_accept_001",
  "decision": "ACCEPT",
  "reason": null,
  "intent_id": "intent_demo_inference",
  "causal_parent": "decision_compute_budget_approved_001",
  "scope": "compute.inference.demo.once"
}
```

This output should be a draft receipt, not a final audit-anchored receipt.

## Recommended first implementation PR

Keep the first Rust PR intentionally small:

```text
1. Add ComputeWitnessJobManifest serde type.
2. Add manifest_to_request_context().
3. Add verify_compute_manifest().
4. Add tests using existing accepted and blocked job manifests.
5. Add CLI only if the library adapter is clean.
```

Do not implement audit packets, challenge fixtures, or canonical audit hashing in the first Rust PR.

## Acceptance tests

Minimum tests:

```text
accepted manifest -> Decision::Accept
blocked manifest with missing causal_parent -> Decision::Reject or Block, depending on final mapping
manifest projection preserves intent_id
manifest projection preserves scope
manifest projection preserves reversibility
manifest projection preserves optional human_approval
```

Important note:

The current action verifier treats missing causal parent as `Reject`. Some Compute Witness fixtures use `BLOCK` for structurally valid but unsafe compute cases. The first Rust integration must explicitly decide whether Compute Witness keeps its own decision mapping layer or aligns directly with the current action verifier output.

## Open design question

### Reject vs Block mapping

The existing verifier returns:

```text
Missing causal parent -> REJECT
Irreversible without approval -> BLOCK
```

The current Compute Witness blocked fixture uses:

```text
MISSING_CAUSAL_PARENT -> BLOCK
```

This is the main integration mismatch.

Recommended resolution:

```text
Keep the generic action verifier semantics unchanged.
Add a Compute Witness policy adapter that can map verifier outcomes into compute-domain receipt outcomes when needed.
```

That keeps the Rust core stable while allowing Compute Witness to express compute-market policy.

## Non-goals for the Rust spike

This spike does not implement:

- final Rust code;
- canonical JSON hashing in Rust;
- audit packet verification in Rust;
- challenge fixture execution in Rust;
- GPU hardware attestation;
- zkML verification;
- TEE integration;
- production key management.

## Why this matters

The Python validator is good for reviewer trust because it is small and readable.

The Rust adapter path is good for production credibility because ProofPath's core execution boundary already lives in Rust.

Together, the intended maturity ladder is:

```text
Python conformance validator
-> Rust manifest adapter
-> Rust receipt draft generation
-> Rust audit hash verification
-> Rust challenge verification
-> optional provider/TEE/zkML attestations
```

## Next recommended issue

Create a follow-up implementation issue:

```text
Compute Witness: implement Rust manifest adapter
```

Scope it narrowly to manifest parsing, projection to `RequestContext`, and receipt draft generation.
