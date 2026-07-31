# PoCI External Witness SDK v0.1

This kit lets a repository controlled by another GitHub owner or organization answer the ProofPath organizational-independence challenge without receiving write, merge, secret, or execution access to ProofPath.

## Child-sized model

ProofPath solved a problem and two computers checked it. The SDK gives the same problem to a person from another family. That person checks the work in their own house and signs the answer with their own identity.

## Kit contents

- `sdk/proofpath_external_witness.py` — one dependency-free Python file;
- `examples/poci-witness/external-operator/challenge.json` — deterministic challenge;
- `examples/poci-witness/external-operator/reference-workflow.yml` — workflow to copy;
- `schemas/poci-external-operator-response-v0.1.schema.json` — response contract;
- `tests/test_external_witness_sdk.py` — conformance and mutation corpus.

## Minimal onboarding

In a repository whose owner is **not** `safal207`:

1. Create `proofpath-witness/`.
2. Copy the SDK as `proofpath-witness/proofpath_external_witness.py`.
3. Copy the challenge as `proofpath-witness/challenge.json`.
4. Copy the reference workflow to `.github/workflows/proofpath-external-witness.yml`.
5. Review every pinned repository, SHA, workflow, and command.
6. Commit the files and run **ProofPath External Witness** manually.
7. Return the resulting artifact or a link to the successful workflow run in issue #203.

No repository secrets are required. The workflow needs only GitHub's short-lived OIDC identity and the permissions declared in the template.

## Three stages

### 1. Verify the challenge

The SDK recomputes `challenge_root` and validates the six required graph roots and owner boundary.

### 2. Create the response subject

The external workflow:

- verifies the ProofPath producer attestation;
- checks out the exact pinned ProofPath code;
- rebuilds the graph space;
- recomputes source, graph, transition-cell, and multi-graph roots;
- emits `proofpath.poci.external-operator-response.v0.1`.

The response itself is still pending attestation. It cannot truthfully contain the verification result for a signature that does not exist yet.

### 3. Attest and finalize

After `actions/attest@v4` signs the exact response bytes, the workflow independently verifies that attestation and emits `proofpath.poci.external-operator-submission.v0.1`, binding:

- the exact response subject digest;
- the attestation-verification result digest;
- the response root;
- the external repository, owner, and workflow identity.

ProofPath must verify the attestation again during admission. A claimed verification inside the submission is evidence to inspect, not self-authenticating truth.

## Decisions

- `ACCEPT` — different owner, valid producer attestation, exact six-graph agreement;
- `HOLD` — technically correct run, but repository owner is still `safal207`;
- `BLOCK` — malformed identity, workflow, report, or missing attestation;
- `CHALLENGE` — challenge, source, graph, transition-cell, or product-root mismatch.

Every output preserves:

```json
{
  "authority_granted": false
}
```

An external witness never receives merge or execution authority.

## Trust boundary

This reference kit proves owner-diverse repository/workflow execution and keyless provenance when used by another owner. It does not yet prove:

- independent human review;
- different cloud infrastructure;
- an independently implemented graph algorithm;
- freedom from coordinated owners;
- correctness of real-world facts represented by the graph.

The reference workflow reuses a pinned ProofPath builder so that first adopters can reproduce the protocol deterministically. A later implementation-diversity profile should require at least one independently written builder.

## Current pinned producer

```text
repository: safal207/ProofPath
organizational-gate head: 646f5c63795fc7338c3206db1d40aceec4c8a1de
producer attestation provenance SHA: 3a5dde912c44e0957204d3df733e712c596455f1
challenge root: sha256:02f8118f2f5ff7465409ec513da5d0474e26ec8d7c469c5e06ed181f02a82c20
```

Changing any pinned value creates a new challenge round and requires fresh evidence.
