# proofpath-gateway

Minimal Axum gateway for ProofPath-protected HTTP actions.

The gateway accepts HTTP requests, extracts ProofPath headers, calls `proofpath-verifier`, and returns a structured decision.

## Run

```bash
cargo run -p proofpath-gateway
```

The gateway listens on:

```text
http://127.0.0.1:8787
```

## Health check

```bash
curl http://127.0.0.1:8787/health
```

## Accepted request

```bash
curl -i -X POST http://127.0.0.1:8787/demo/protected \
  -H 'x-proofpath-intent-id: intent_9f21' \
  -H 'x-proofpath-causal-parent: decision_71ab' \
  -H 'x-proofpath-scope: payments.transfer.once' \
  -H 'x-proofpath-reversibility: irreversible' \
  -H 'x-proofpath-human-approval: approval_11fa'
```

Expected result:

```json
{
  "forwarded": true,
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

## Current limitation

This MVP does not yet proxy accepted requests to a real upstream service. It returns `forwarded: true` to show that the request would pass the ProofPath gate.
