# Dahl/Gonka Live Three-Replica Evidence — 2026-08-03

## Scope

A non-sensitive Android/Linux pilot ran the same bounded request three times through the Dahl OpenAI-compatible endpoint using `MiniMaxAI/MiniMax-M2.7`.

No API key, prompt body beyond the fixed test phrase, or reasoning text is stored in this evidence note.

## Observed result

```json
{
  "claim_id": "dahl-live-pilot-20260803T203620Z",
  "verdict": "CONSENSUS",
  "requested_replicas": 3,
  "successful_replicas": 3,
  "agreement_score": 1.0,
  "provider_request_ids": [
    "devshard-44246-1001",
    "devshard-44246-1001",
    "devshard-44246-1001"
  ],
  "reasoning_markup": [
    "closed",
    "closed",
    "closed"
  ],
  "endpoint_origins": [
    "https://inference.dahl.global"
  ],
  "receipt_hash": "sha256:35b9c3eb2e67e88bd20ecc620e49f8b718c080e213ef0973a3b6a9af756804eb"
}
```

The local receipt was written with owner-only permissions and contains hashes and metadata rather than the API key or reasoning text.

## What this proves

- API-key authentication succeeded.
- Three client-side execution attempts returned usable responses.
- All three safely extracted final answers agreed exactly.
- MiniMax reasoning markup was detected and excluded from final-answer agreement scoring.
- ProofPath produced a stable receipt hash for the observed execution metadata.

## What this does not prove

All three responses returned the same provider request ID: `devshard-44246-1001`.

That may indicate caching, request deduplication, a shared upstream execution, or simply provider-specific ID semantics. The evidence is insufficient to distinguish those possibilities.

Therefore:

```text
output consensus: observed
three successful client attempts: observed
independent provider routing: not observed and not proven
independent GPU execution: not proven
validator diversity: not proven
```

The output verdict remains `CONSENSUS` because it describes answer agreement. Routing evidence must be reported separately and must not be inferred from answer agreement.

## Follow-up control

The live-pilot summarizer classifies provider request IDs separately:

- `DUPLICATE_PROVIDER_REQUEST_IDS`
- `MISSING_PROVIDER_REQUEST_IDS`
- `DISTINCT_PROVIDER_REQUEST_IDS_NOT_INDEPENDENCE_PROOF`
- `INSUFFICIENT_SUCCESSFUL_EXECUTIONS`

Duplicate or missing IDs make the strict live pilot exit non-zero. Even distinct IDs remain only inconclusive routing evidence; they do not prove independent machines, validators, or GPUs.
