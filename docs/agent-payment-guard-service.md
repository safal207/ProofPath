# Agent Payment Guard Service (Local HTTP)

This service exposes ProofPath Agent Payment Guard over local HTTP so an external AI agent runtime can request an authorization decision before execution.

## Start service

### With JSON config (recommended)

```bash
python3 examples/agent-payment-guard/payment_guard_service.py \
  --config examples/agent-payment-guard/payment_guard_service_config.json
```

### With CLI flags (legacy)

```bash
python3 examples/agent-payment-guard/payment_guard_service.py --host 127.0.0.1 --port 8787
```

CLI flags (`--host`, `--port`, `--policy`, `--audit-path`, `--replay-store-path`) override the corresponding config file values when both are provided.

## Config file reference

`examples/agent-payment-guard/payment_guard_service_config.json`:

```json
{
  "mode": "enforce",
  "require_signed_intent": true,
  "policy_path": "examples/agent-payment-guard/payment_policy.json",
  "audit_path": ".proofpath/audit.jsonl",
  "replay_store_path": ".proofpath/replay-store.json",
  "service": {
    "host": "127.0.0.1",
    "port": 8787
  },
  "audit": {
    "hash_chain": true,
    "recent_records_default_limit": 20,
    "recent_records_max_limit": 100
  }
}
```

| Field | Description |
|---|---|
| `mode` | Default evaluation mode: `enforce` (blocks on non-ACCEPT) or `shadow` (observes only). Request body `mode` overrides this per-request. |
| `require_signed_intent` | If `true`, requests without an `intent_envelope` are treated as strict and return `BLOCK / MISSING_INTENT_ENVELOPE`. Merged with per-request strictness; strictest wins. |
| `policy_path` | Path to the payment policy JSON file. |
| `audit_path` | Path to the JSONL audit log. |
| `replay_store_path` | Path to the local JSON replay store used for signed intent nonce replay protection. |
| `service.host` | Bind address. |
| `service.port` | Bind port. |
| `audit.hash_chain` | Enables hash-chained audit records (always on in current implementation). |
| `audit.recent_records_default_limit` | Default number of records returned by `GET /v1/audit/records` when no `limit` query param is given. |
| `audit.recent_records_max_limit` | Maximum allowed value for the `limit` query param; requests above this are clamped. |

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

## Replay protection

Accepted signed intent envelopes persist their nonce into the local replay store:

```text
.proofpath/replay-store.json
```

A second attempt to use the same nonce returns:

```text
BLOCK / INTENT_REPLAYED
```

This replay state survives service restart because it is stored separately from process memory. The audit log still records both the original `ACCEPT` decision and the later replay `BLOCK` decision.

## Read replay store diagnostics

```bash
curl -sS http://127.0.0.1:8787/v1/replay-store | python3 -m json.tool
```

Example response:

```json
{
  "nonces": 1,
  "entries": {
    "nonce_market_research_001": {
      "nonce": "nonce_market_research_001",
      "human_intent_id": "intent_market_research_001",
      "agent_id": "agent_researcher_01",
      "used_at": "2026-05-26T00:00:00Z",
      "decision_hash": "sha256:...",
      "status": "used"
    }
  }
}
```

This endpoint is local demo diagnostics only. It is not an authorization API.

## Read recent audit records

```bash
curl -sS 'http://127.0.0.1:8787/v1/audit/records?limit=20' | python3 -m json.tool
```

Behavior:
- No `limit` param → uses `audit.recent_records_default_limit` from config
- `limit` > `audit.recent_records_max_limit` → clamped to max
- Non-integer `limit` → `400 Bad Request` with JSON error

Records come from `.proofpath/audit.jsonl` and include hash chaining (`previous_hash`, `hash`).

## Local validation

```bash
bash examples/agent-payment-guard/run_demo_check.sh
bash examples/agent-payment-guard/run_service_check.sh
python3 scripts/verify_audit_log.py .proofpath/audit.jsonl
```
