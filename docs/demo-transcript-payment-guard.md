# Agent Payment Guard — E2E Demo Transcript

Expected output from `bash examples/agent-payment-guard/run_e2e_evidence_demo.sh`.

## Story

```text
AI agents will need payment rails.
Payment rails need authorization.
Authorization needs evidence.
ProofPath provides that evidence.
```

Core principle:

```text
Model output is a proposal, not authorization.
```

## Expected output

```
[e2e] ProofPath Agent Payment Guard — end-to-end evidence demo
[e2e] starting guard service (enforce mode, signed intent required)...
[e2e] service ready.

[e2e] step 1 — valid signed intent: ACCEPT
  decision: ACCEPT
  execution_allowed: true
  audit_hash: sha256:...

[e2e] step 2 — replay same envelope: BLOCK / INTENT_REPLAYED
  decision: BLOCK
  reason: INTENT_REPLAYED
  execution_allowed: false

[e2e] step 3 — stopping service and exporting evidence bundle
[export] hash chain: chain valid (2 records)
[export] copied  .proofpath/audit.jsonl  ->  proofpath-evidence-bundle/audit.jsonl
[export] copied  examples/agent-payment-guard/payment_guard_service_config.json  ->  proofpath-evidence-bundle/payment_guard_service_config.json
[export] copied  examples/agent-payment-guard/payment_policy.json  ->  proofpath-evidence-bundle/payment_policy.json
[export] copied  .proofpath/replay-store.json  ->  proofpath-evidence-bundle/replay-store.json
[export] wrote   proofpath-evidence-bundle/verification_report.json

[export] bundle ready: proofpath-evidence-bundle/
         records : 2
         nonces  : 1
         chain   : OK

[e2e] step 4 — verifying bundled audit log hash chain
  audit log: OK (2 records, chain valid)

[e2e] ✓ ProofPath Agent Payment Guard demo complete.

Bundle contents:
  proofpath-evidence-bundle/
    audit.jsonl                        (2 records)
    replay-store.json                  (1 spent nonce)
    payment_guard_service_config.json
    payment_policy.json
    verification_report.json

What was demonstrated:
  ACCEPT   valid signed intent envelope
  BLOCK    replayed intent (INTENT_REPLAYED)
  EXPORT   portable evidence bundle
  VERIFY   hash-chain integrity confirmed
```

## Decisions

| Step | Proposal | Envelope | Decision | Reason |
|---|---|---|---|---|
| 1 | valid_micro_payment | intent.valid.json | ACCEPT | PAYMENT_WITHIN_SIGNED_INTENT_ENVELOPE |
| 2 | valid_micro_payment | intent.valid.json (same) | BLOCK | INTENT_REPLAYED |

## What this proves

- The guard enforces signed human intent before payment execution.
- A spent nonce cannot be reused — replay protection is persistent across restarts.
- Every decision is hash-chained in `audit.jsonl` — the chain is verifiable offline.
- The evidence bundle is portable: any reviewer can re-run `verify_audit_log.py` without access to the live service.
