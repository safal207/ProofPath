# ProofPath Signed Human Intent Envelope v0.1 (Demo First)

This profile adds a **local demo-only** signed envelope for the Agent Payment Guard.

## Non-production warning

`demo-sha256-v0` is intentionally non-production. It is **not** wallet signing, JWS, key management, custody, or payment rail integration.

## Demo signature profile

- `signature_alg = demo-sha256-v0`
- `signature = sha256(canonical_json(envelope_without_signature) + demo_secret)`

## Guard verification checks

- MISSING_INTENT_ENVELOPE
- INVALID_INTENT_SIGNATURE
- INTENT_EXPIRED
- INTENT_REPLAYED
- INTENT_AGENT_MISMATCH
- INTENT_PURPOSE_MISMATCH
- INTENT_CAUSAL_PARENT_MISMATCH
- INTENT_ASSET_MISMATCH
- INTENT_RECIPIENT_MISMATCH
- INTENT_AMOUNT_EXCEEDED
- INTENT_BUDGET_SCOPE_MISMATCH

Accepted payments with a verified envelope return `PAYMENT_WITHIN_SIGNED_INTENT_ENVELOPE`.
