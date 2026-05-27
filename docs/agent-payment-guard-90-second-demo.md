# ProofPath Agent Payment Guard — 90-second demo script

## Command

Run from the repository root:

```bash
bash examples/agent-payment-guard/run_mock_rail_demo.sh
```

## Spoken script

**Opening — 10 seconds**

ProofPath is the authorization and evidence layer for AI-agent payments.

The key idea is simple: model output is a proposal, not authorization.

An agent can propose a payment, but an external boundary should decide whether that payment is allowed to execute.

**Step 1 — valid proposal — 15 seconds**

Here the agent proposes a small USDC API payment.

ProofPath checks the signed human intent envelope, policy, approved asset, budget, recipient, causal parent, payment mode, and nonce.

This proposal is valid, so ProofPath returns:

```text
ACCEPT
execution_allowed=true
```

The adapter receives that decision and forwards the payment to the mock rail. The mock rail records exactly one transaction.

**Step 2 — replay attack — 15 seconds**

Now we replay the same signed intent envelope.

The payment still looks syntactically valid, but the nonce has already been used.

ProofPath returns:

```text
BLOCK / INTENT_REPLAYED
execution_allowed=false
```

The adapter does not call the mock rail. The mock rail transaction count stays at one.

**Step 3 — recurring payment without approval — 15 seconds**

Next, the agent proposes a recurring payment without required approval.

ProofPath returns:

```text
HOLD / RECURRING_PAYMENT_REQUIRES_APPROVAL
execution_allowed=false
```

Again, the adapter does not call the mock rail. The transaction count still stays at one.

**Step 4 — evidence — 20 seconds**

After the decisions, ProofPath exports a portable evidence bundle.

The bundle includes:

```text
audit.jsonl
replay-store.json
payment_guard_service_config.json
payment_policy.json
verification_report.json
```

Then we verify the bundled audit log hash chain.

The result is not just “the demo worked.” The result is a reviewable evidence trail showing:

```text
ACCEPT reached the rail.
BLOCK did not reach the rail.
HOLD did not reach the rail.
The audit chain verifies.
```

**Close — 15 seconds**

ProofPath does not move money.

ProofPath proves whether an agent was allowed to move money.

The product path is:

```text
proposal -> guard -> adapter -> rail/no rail -> audit -> evidence
```

That is the core authorization boundary for AI-agent payments.

## Expected success summary

```text
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

## What to point out while demoing

- The model never directly executes a payment.
- The adapter forwards only `ACCEPT` decisions.
- `BLOCK / INTENT_REPLAYED` proves replay protection.
- `HOLD / RECURRING_PAYMENT_REQUIRES_APPROVAL` proves approval gating.
- The evidence bundle lets someone review the path without trusting the live service.

## One-sentence takeaway

```text
ProofPath turns agent payment proposals into verifiable authorization decisions before execution.
```
