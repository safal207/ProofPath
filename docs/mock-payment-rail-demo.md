# Mock Payment Rail Demo

> **ProofPath decides. Mock rail executes only after ACCEPT.**

This demo proves that ProofPath Agent Payment Guard is not just evaluating
payments — it controls whether execution reaches the payment rail.

## What the mock rail proves

- `ACCEPT` decisions result in a transaction recorded on the mock rail.
- `BLOCK` / `INTENT_REPLAYED` decisions never reach the mock rail.
- `HOLD` / `RECURRING_PAYMENT_REQUIRES_APPROVAL` decisions never reach the mock rail.

The mock rail has no real payment logic. It is a simulation-only HTTP server
that appends JSONL transaction records to `.proofpath/mock-rail-transactions.jsonl`.

All execution goes through `payment_guard_to_mock_rail_adapter.py` — the adapter
is the only component allowed to forward `ACCEPT` decisions to the mock rail.

## How to run

From the repository root:

```bash
bash examples/agent-payment-guard/run_mock_rail_demo.sh
```

## What the demo does

1. Cleans previous runtime files: audit log, replay store, mock rail transactions,
   evidence bundle.
2. Starts the ProofPath Guard Service in enforce mode (port 18790).
3. Starts the Mock Payment Rail HTTP server (port 18791).
4. Sends a valid signed-intent proposal.
   - Guard returns `ACCEPT` with `execution_allowed=true`.
   - Adapter forwards the transaction to the mock rail.
   - Mock rail records exactly 1 transaction.
5. Replays the same signed intent envelope.
   - Guard returns `BLOCK` / `INTENT_REPLAYED` with `execution_allowed=false`.
   - Adapter does **not** call the mock rail.
   - Mock rail transaction count remains 1.
6. Sends a recurring payment without approval.
   - Guard returns `HOLD` / `RECURRING_PAYMENT_REQUIRES_APPROVAL` with `execution_allowed=false`.
   - Adapter does **not** call the mock rail.
   - Mock rail transaction count remains 1.
7. Exports the portable evidence bundle.
8. Verifies the bundled audit log hash chain.

## Expected output

```
[mock-rail-demo] ========================================
[mock-rail-demo]  SUCCESS SUMMARY
[mock-rail-demo] ========================================
[mock-rail-demo]  ACCEPT reached mock rail via adapter
[mock-rail-demo]  BLOCK did not reach mock rail
[mock-rail-demo]  HOLD did not reach mock rail
[mock-rail-demo]  evidence bundle exported
[mock-rail-demo]  hash-chain verification passed
[mock-rail-demo] ========================================
```

## Mock rail transaction record shape

```json
{
  "ts": "2026-05-27T00:00:00Z",
  "surface": "mock-payment-rail",
  "status": "MOCK_EXECUTED",
  "agent_id": "agent_researcher_01",
  "asset": "USDC",
  "amount": "0.07",
  "recipient": "market-data-api.example",
  "proofpath_decision": "ACCEPT",
  "proofpath_audit_hash": "sha256:..."
}
```

## Files

| File | Purpose |
|---|---|
| `examples/agent-payment-guard/mock_payment_rail.py` | Mock payment rail HTTP server |
| `examples/agent-payment-guard/payment_guard_to_mock_rail_adapter.py` | Adapter: guard -> rail |
| `examples/agent-payment-guard/run_mock_rail_demo.sh` | Runnable demo script |

## Non-goals

No real wallet integration, no real USDC transfer, no custody, no private keys,
no payment SDKs, no RPC calls, no smart contracts, no KYC/AML,
no production compliance claims, no JWS implementation, no EIP-712 implementation.
