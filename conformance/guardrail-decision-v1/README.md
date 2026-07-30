# GuardrailDecisionV1 source-provenance conformance vectors

This corpus tests a narrow question raised in `crewAIInc/crewAI#4877`:

> What can an independent verifier actually prove from `knowledge_source_ref`,
> `source_content_hash`, and optional provenance sidecars?

It is provider-neutral and stdlib-only. The checker imports neither ProofPath,
CrewAI, CKG, nor any guardrail vendor implementation.

## Run

```bash
python3 scripts/check_guardrail_provenance_vectors.py \
  conformance/guardrail-decision-v1/manifest.json
```

Expected result: ten passing vectors.

## Proof levels

| Level | Mechanical meaning |
| --- | --- |
| `COMMITTED` | A syntactically valid SHA-256 commitment and source reference exist. The original bytes are not independently recoverable from the record. |
| `REPRODUCIBLE` | An immutable snapshot is present and its bytes recompute to `source_content_hash`. |
| `FRESH` | The historical snapshot recomputes and a supplied current representation still matches the same hash. |
| `INVALID` | A required invariant fails; the checker fails closed. |

A stale live source does **not** erase historical reproducibility. It produces
`SOURCE_STALE` while retaining `REPRODUCIBLE` when the frozen snapshot still
matches.

## Retrieval representation

A URL alone does not identify one byte stream. Redirects, compression, content
negotiation, and normalization can produce different bodies for the same URL.
Vectors that carry bytes therefore require a retrieval profile with a supported
representation:

- `response-body-raw`
- `response-body-decompressed`

This first corpus deliberately rejects ambiguous labels such as
`whatever-curl-returned`.

## Temporal precedence

`issued_at` inside a hashed record is tamper-evident, but it does not prove that
the issuer did not choose a favorable timestamp before hashing. The checker
therefore emits `TEMPORAL_PRECEDENCE_UNPROVEN` when no external anchor is
provided.

Likewise, merely adding `temporal_anchor_ref` does not make the anchor valid.
This corpus emits `EXTERNAL_ANCHOR_UNVERIFIED` until a profile-specific verifier
checks the referenced Bitcoin OpenTimestamps or RFC 3161 proof.

That distinction is intentional: a reference is a fetch hint, not evidence that
verification succeeded.

## Covered cases

- hash-only commitment;
- valid frozen snapshot;
- matching current source;
- changed current source;
- tampered snapshot;
- missing snapshot;
- ambiguous byte representation;
- self-declared `issued_at` without an anchor;
- declared but unverified external anchor;
- malformed source hash.

## Scope boundary

This is not a complete GuardrailDecision schema and does not define policy
semantics, signatures, decision canonicalization, or provider behavior. It is a
small conformance layer for the source-origin portion of the audit chain and is
intended to cross-check cleanly with independent decision-vector suites such as
Vaara's `governance_decision_v0` corpus.
