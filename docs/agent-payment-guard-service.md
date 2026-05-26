# Agent Payment Guard Service (Local HTTP)

This service exposes ProofPath Agent Payment Guard over local HTTP so an external AI agent runtime can request an authorization decision before execution.

## Start service

```bash
python3 examples/agent-payment-guard/payment_guard_service.py --host 127.0.0.1 --port 8787
```

## Health check

```bash
curl -sS http://127.0.0.1:8787/v1/health | python3 -m json.tool
```

Expected response:

```json
{
  "status": "ok",
  "surface": "agent-payment-guard-service",
  "version": "0.1"
}
```

## Evaluate a proposal (enforce mode)

```bash
curl -sS -X POST http://127.0.0.1:8787/v1/payment-proposals/evaluate \
  -H 'content-type: application/json' \
  -d "$(python3 - <<'PY'
import json
proposal = json.load(open('examples/agent-payment-guard/payment_proposal.valid_micro_payment.json', encoding='utf-8'))
envelope = json.load(open('examples/agent-payment-guard/intent_envelopes/intent.valid.json', encoding='utf-8'))
print(json.dumps({'mode':'enforce','proposal':proposal,'intent_envelope':envelope}))
PY
)" | python3 -m json.tool
```

Enforce semantics:
- `ACCEPT` => `execution_allowed=true`, `would_block=false`
- `HOLD` / `BLOCK` => `execution_allowed=false`, `would_block=true`

## Evaluate a proposal (shadow mode)

```bash
curl -sS -X POST http://127.0.0.1:8787/v1/payment-proposals/evaluate \
  -H 'content-type: application/json' \
  -d "$(python3 - <<'PY'
import json
proposal = json.load(open('examples/agent-payment-guard/payment_proposal.asset_not_allowed.json', encoding='utf-8'))
print(json.dumps({'mode':'shadow','proposal':proposal,'intent_envelope':None}))
PY
)" | python3 -m json.tool
```

Shadow semantics:
- `ACCEPT` => `execution_allowed=true`, `would_block=false`
- `HOLD` / `BLOCK` => `execution_allowed=true`, `would_block=true`

Shadow mode always writes an audit record with actual decision and reason.

## Read recent audit records

```bash
curl -sS 'http://127.0.0.1:8787/v1/audit/records?limit=20' | python3 -m json.tool
```

Records come from `.proofpath/audit.jsonl` and include hash chaining (`previous_hash`, `hash`).

## Local validation

```bash
bash examples/agent-payment-guard/run_demo_check.sh
bash examples/agent-payment-guard/run_service_check.sh
python3 scripts/verify_audit_log.py .proofpath/audit.jsonl
```
