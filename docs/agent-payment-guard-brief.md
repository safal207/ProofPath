# ProofPath Agent Payment Guard

## One-line

ProofPath is the authorization and evidence layer for AI-agent payments.

Shorter:

```text
We do not move money.
We prove whether an agent was allowed to move money.
```

## Problem

AI agents can propose payments, but model output is not authorization.

A model can generate a payment request that looks syntactically valid while still being causally unsafe: wrong recipient, wrong budget, replayed intent, missing approval, stale mandate, or action outside the user's actual scope.

Traditional payment rails answer:

```text
Can this credential move money?
```

ProofPath asks the missing question:

```text
Was this specific agent payment allowed to execute now — and can we prove why?
```

## Solution

ProofPath inserts an external decision boundary before execution.

The agent may propose a payment, but ProofPath decides whether that proposal becomes an executable action.

```text
proposal -> guard -> adapter -> rail/no rail -> audit -> evidence
```

## Demo path

The current Agent Payment Guard demo runs this path locally:

```text
AI agent payment proposal
  -> ProofPath Guard Service
  -> signed intent + policy + replay checks
  -> adapter
  -> mock rail only if ACCEPT
  -> hash-chained audit log
  -> replay store
  -> portable evidence bundle
```

Run it:

```bash
bash examples/agent-payment-guard/run_mock_rail_demo.sh
```

## What it proves

```text
ACCEPT reaches mock rail.
BLOCK / INTENT_REPLAYED never reaches mock rail.
HOLD / RECURRING_PAYMENT_REQUIRES_APPROVAL never reaches mock rail.
Evidence bundle proves the path.
```

The important boundary is not the mock rail. The important boundary is the adapter:

```text
ProofPath decides.
Adapter enforces.
Mock rail executes only after ACCEPT.
Evidence proves the path.
```

## Current surfaces

| Surface | What it provides |
|---|---|
| Guard Service | Local HTTP authorization endpoint for payment proposals. |
| Adapter | Execution boundary between ProofPath decisions and a payment rail. |
| Mock Rail Demo | Demonstrates ACCEPT reaches rail while BLOCK/HOLD do not. |
| Replay Store | Persistent nonce protection for signed intent envelopes. |
| Hash-Chained Audit Log | Tamper-evident record of ACCEPT, BLOCK, and HOLD decisions. |
| Evidence Export Bundle | Portable proof packet containing audit, replay store, config, policy, and verification report. |
| OpenAPI Contract | Integration-ready API description for external agents and adapters. |

## Integration targets

### x402-style pay-per-request flow

```text
Agent wants to call paid API
  -> prepares payment proposal
  -> ProofPath evaluates signed intent, policy, budget, recipient, nonce
  -> only ACCEPT reaches payment rail
  -> audit/evidence packet records why
```

ProofPath does not replace x402-style payment rails. It sits before execution as authorization and evidence.

### LangGraph / agent runtime flow

```text
Agent runtime emits payment tool call
  -> tool call routed through ProofPath adapter
  -> ACCEPT forwards to rail/tool
  -> BLOCK/HOLD returns structured reason to runtime
  -> audit/evidence remains outside model memory
```

The model can propose. The external boundary decides.

### Generic agent-wallet SDK mock

```text
agent-wallet SDK call
  -> ProofPath preflight decision
  -> ACCEPT invokes SDK
  -> BLOCK/HOLD never invoke SDK
  -> evidence bundle can be reviewed offline
```

This lets wallet builders keep their rails while delegating decision proof to ProofPath.

## Why now

AI agents are moving from text generation to action execution. Payments are one of the highest-risk action classes because a mistaken or manipulated request can move real value.

As agent payments grow, teams will need more than model guardrails. They will need external authorization, replay protection, auditability, and portable evidence.

## Non-goals

ProofPath Agent Payment Guard is not a wallet and not a payment processor.

No real wallets, token transfers, custody, private keys, payment SDKs, RPC calls, smart contracts, KYC/AML, production compliance claims, JWS, or EIP-712 are included in this local demo.

## Positioning

```text
AI agents will need payment rails.
Payment rails need authorization.
Authorization needs evidence.
ProofPath provides that evidence.
```
