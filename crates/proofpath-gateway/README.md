# proofpath-gateway

Minimal Axum gateway for ProofPath-protected HTTP actions.

The gateway accepts HTTP requests, extracts ProofPath headers, calls `proofpath-verifier`, writes a hash-chained JSONL audit record, and forwards accepted requests to a protected upstream API.

## Run local demo

Terminal 1: start demo protected API.

```bash
python3 examples/upstream/demo_server.py
```

Terminal 2: start ProofPath gateway.

```bash
cargo run -p proofpath-gateway
```

The gateway listens on:

```text
http://127.0.0.1:8787
```

Default upstream:

```text
http://127.0.0.1:9797/protected
```

Default audit log:

```text
proofpath-audit.jsonl
```

You can override both:

```bash
PROOFPATH_UPSTREAM_URL=http://127.0.0.1:9797/protected \
PROOFPATH_AUDIT_LOG=proofpath-audit.jsonl \
cargo run -p proofpath-gateway
```

## Health check

```bash
curl http://127.0.0.1:8787/health
```

## Accepted and forwarded request

```bash
curl -i -X POST http://127.0.0.1:8787/demo/protected \
  -H 'x-proofpath-intent-id: intent_9f21' \
  -H 'x-proofpath-causal-parent: decision_71ab' \
  -H 'x-proofpath-scope: payments.transfer.once' \
  -H 'x-proofpath-reversibility: irreversible' \
  -H 'x-proofpath-human-approval: approval_11fa' \
  -d '{"amount":"100.00","currency":"USD"}'
```

Expected result:

```json
{
  "forwarded": true,
  "upstream_status": 200,
  "proofpath": {
    "decision": "ACCEPT"
  }
}
```

## Blocked irreversible request

```bash
curl -i -X POST http://127.0.0.1:8787/demo/protected \
  -H 'x-proofpath-intent-id: intent_9f21' \
  -H 'x-proofpath-causal-parent: decision_71ab' \
  -H 'x-proofpath-scope: payments.transfer.once' \
  -H 'x-proofpath-reversibility: irreversible'
```

Expected result:

```json
{
  "forwarded": false,
  "proofpath": {
    "decision": "BLOCK",
    "reason": "IRREVERSIBLE_ACTION_REQUIRES_APPROVAL"
  }
}
```

## Rejected malformed request

```bash
curl -i -X POST http://127.0.0.1:8787/demo/protected
```

Expected result:

```json
{
  "forwarded": false,
  "proofpath": {
    "decision": "REJECT",
    "reason": "MISSING_INTENT"
  }
}
```

## Inspect audit log

```bash
cat proofpath-audit.jsonl
```

Each record includes:

- audit id
- previous hash
- intent id
- causal parent
- scope
- decision
- reason
- forwarded flag
- upstream URL
- upstream status
- record hash

This makes the gateway a small causal boundary: accepted actions move forward, blocked actions stop, and every decision leaves a verifiable trail.
