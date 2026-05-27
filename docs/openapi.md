# ProofPath Guard Service OpenAPI

The Agent Payment Guard HTTP service has a formal OpenAPI contract:

```text
openapi/proofpath-guard-service-v0.1.yaml
```

## What it documents

```text
GET  /v1/health
POST /v1/payment-proposals/evaluate
GET  /v1/audit/records
GET  /v1/replay-store
```

The spec includes schemas for payment proposals, signed intent envelopes, evaluation responses, audit records, replay-store diagnostics, and error responses.

## Core semantics

```text
enforce + ACCEPT    -> execution_allowed=true,  would_block=false
enforce + HOLD/BLOCK -> execution_allowed=false, would_block=true
shadow  + ACCEPT    -> execution_allowed=true,  would_block=false
shadow  + HOLD/BLOCK -> execution_allowed=true,  would_block=true
```

Core principle:

```text
Model output is a proposal, not authorization.
```

## Smoke check

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('openapi/proofpath-guard-service-v0.1.yaml')
assert p.exists()
text = p.read_text(encoding='utf-8')
for s in ['/v1/health', '/v1/payment-proposals/evaluate', '/v1/audit/records', '/v1/replay-store']:
    assert s in text, s
for s in ['PaymentProposal', 'IntentEnvelope', 'EvaluationResponse', 'INTENT_REPLAYED']:
    assert s in text, s
print('OpenAPI spec smoke check passed')
PY
```

## Non-goals

This spec does not add generated SDKs, hosted API docs, real wallet integration, token transfers, custody, private keys, payment SDKs, RPC calls, JWS, or EIP-712.
