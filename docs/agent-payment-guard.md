# ProofPath Agent Payment Guard (Simulation-Only)

ProofPath Agent Payment Guard is a **local simulation-only action-authorization demo** for AI-agent payment proposals. It evaluates whether a proposed payment is in declared scope **before** any payment rail would be called in a future integration.

> **Claim boundary:** This demo does not execute payments, custody funds, secure wallets, detect fraud, or provide compliance certification.

## Threat context

Payment-capable agents create a high-impact action boundary: a model can generate plausible but unauthorized payment intents. The risk is not only prompt injection, but also guardrail bypass attempts where an agent proposes an action that is missing authorization lineage or exceeds approved scope.

This demo focuses on validating the **authorization envelope** attached to a payment proposal:

- declared user intent (`human_intent_id`, `purpose`);
- causal linkage (`causal_parent`);
- budget scope (`approved_budget`);
- recipient and asset scope (`approved_recipient`, policy allow-lists);
- recurring-payment escalation path (`HOLD` when approval is missing).

See also the broader threat framing in `docs/threats/model_guardrail_bypass.md`.

## Action-boundary flow

```text
AI agent proposes payment
  -> ProofPath checks declared intent
  -> ProofPath checks causal parent
  -> ProofPath checks budget and recipient scope
  -> ProofPath returns ACCEPT / HOLD / BLOCK
  -> only ACCEPT would be eligible to reach a payment rail in a future integration
  -> audit record is appended and hash-chain verified locally
```

## Decision table

| Condition | Decision | Reason |
|---|---|---|
| In-scope one-time payment | ACCEPT | `PAYMENT_WITHIN_SCOPE_AND_BUDGET` |
| Amount exceeds approved budget | BLOCK | `OVER_BUDGET` |
| Missing `purpose`, `human_intent_id`, or `causal_parent` | BLOCK | `MISSING_PAYMENT_INTENT` |
| Approved recipient mismatch | BLOCK | `RECIPIENT_MISMATCH` |
| Recipient not allow-listed by policy | BLOCK | `RECIPIENT_NOT_ALLOWED` |
| Asset not allow-listed by policy | BLOCK | `ASSET_NOT_ALLOWED` |
| Amount is not parseable numeric value | BLOCK | `INVALID_AMOUNT` |
| Recurring payment without required approval | HOLD | `RECURRING_PAYMENT_REQUIRES_APPROVAL` |

## Local quickstart

From repository root:

```bash
bash examples/agent-payment-guard/run_demo_check.sh
```

The script runs scenario fixtures, validates compact decision output, checks exit codes (`0` ACCEPT, `2` BLOCK, `3` HOLD), writes `.proofpath/audit.jsonl`, and verifies the hash chain using:

```bash
python3 scripts/verify_audit_log.py .proofpath/audit.jsonl
```

## Expected outputs

CLI decision output contract remains compact JSON:

```json
{"decision":"ACCEPT|BLOCK|HOLD","reason":"..."}
```

Exit code contract:

- `0` = ACCEPT
- `2` = BLOCK
- `3` = HOLD

## Audit record example

Each record in `.proofpath/audit.jsonl` includes decision metadata and hash-chain fields:

```json
{
  "ts":"2026-01-01T00:00:00Z",
  "surface":"agent-payment-guard",
  "decision":"BLOCK",
  "reason":"OVER_BUDGET",
  "agent_id":"agent_researcher_01",
  "asset":"USDC",
  "amount":"12.50",
  "approved_budget":"5.00",
  "recipient":"market-data-api.example",
  "causal_parent":"task_market_report_001",
  "previous_hash":"GENESIS",
  "hash":"sha256:..."
}
```

Hash-chain rules:

- first record uses `previous_hash = "GENESIS"`;
- each `hash` is SHA-256 over canonical JSON for the record excluding `hash`;
- each following record points to the prior record's `hash`.

## Non-claims

This is a local simulation-only action-authorization demo.
It does **not**:

- execute real payments;
- custody funds or keys;
- integrate wallets, payment provider SDKs, or RPC rails;
- provide fraud detection, KYC/AML enforcement, or compliance certification;
- provide complete agent security by itself.

## Relationship to related docs and future exports

- `docs/threats/model_guardrail_bypass.md`: describes guardrail-bypass style threats this boundary helps constrain.
- Future CML / T-Trace / LTP exports: this demo keeps local evidence compact and deterministic so it can be mapped into richer evidence packages later, without changing the core ACCEPT/HOLD/BLOCK boundary behavior.
