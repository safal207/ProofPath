# proofpath-verifier

Minimal Rust verifier for ProofPath HTTP action context.

## What it checks

The v0.1 verifier checks:

- `x-proofpath-intent-id`
- `x-proofpath-causal-parent`
- `x-proofpath-scope`
- `x-proofpath-reversibility`
- `x-proofpath-human-approval` for irreversible actions

## Decisions

The verifier can currently return:

- `ACCEPT`
- `REJECT`
- `BLOCK`

`HOLD` and `AUDIT` are part of the public decision model but are not used by the minimal verifier yet.

## Run tests

```bash
cargo test --workspace --all-targets
```

## CLI example

```bash
cargo run -p proofpath-verifier --bin proofpath-verify -- conformance/valid/payment-transfer-approved.http
```

Expected output:

```json
{
  "decision": "ACCEPT",
  "reason": null,
  "intent_id": "intent_9f21",
  "causal_parent": "decision_71ab",
  "scope": "payments.transfer.once",
  "reversibility": "irreversible",
  "human_approval": "approval_11fa",
  "causal_valid": true,
  "scope_valid": true
}
```
