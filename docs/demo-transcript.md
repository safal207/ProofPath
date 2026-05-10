# ProofPath Demo Transcript

This transcript shows the core ProofPath loop:

```text
agent action -> ProofPath decision -> forward or block -> audit trail
```

## 1. Start the protected API

```bash
$ python3 examples/upstream/demo_server.py
Demo protected API listening on http://127.0.0.1:9797/protected
```

## 2. Start the ProofPath gateway

```bash
$ cargo run -p proofpath-gateway
ProofPath gateway listening on http://127.0.0.1:8787
```

## 3. Agent tries irreversible delete without approval

```bash
$ bash examples/agent-dangerous-action/agent_delete_without_approval.sh
HTTP/1.1 403 Forbidden
content-type: application/json

{
  "protected_api": "demo-protected-api",
  "upstream_url": "http://127.0.0.1:9797/protected",
  "proofpath": {
    "decision": "BLOCK",
    "reason": "IRREVERSIBLE_ACTION_REQUIRES_APPROVAL",
    "intent_id": "intent_inspect_account_001",
    "causal_parent": "decision_user_requested_inspection",
    "scope": "account.delete",
    "reversibility": "irreversible",
    "human_approval": null,
    "causal_valid": true,
    "scope_valid": true
  },
  "forwarded": false,
  "upstream_status": null,
  "audit_hash": "sha256:...",
  "message": "ProofPath rejected or blocked the action before it reached the protected API."
}
```

Meaning:

```text
The connection may be valid.
The action is not valid.
ProofPath blocks it before the protected API sees it.
```

## 4. Agent repeats with explicit human approval

```bash
$ bash examples/agent-dangerous-action/agent_delete_with_approval.sh
HTTP/1.1 200 OK
content-type: application/json

{
  "protected_api": "demo-protected-api",
  "upstream_url": "http://127.0.0.1:9797/protected",
  "proofpath": {
    "decision": "ACCEPT",
    "reason": null,
    "intent_id": "intent_delete_account_approved_001",
    "causal_parent": "decision_human_approved_delete",
    "scope": "account.delete",
    "reversibility": "irreversible",
    "human_approval": "approval_human_42",
    "causal_valid": true,
    "scope_valid": true
  },
  "forwarded": true,
  "upstream_status": 200,
  "audit_hash": "sha256:...",
  "message": "ProofPath accepted the action and forwarded it to the protected API."
}
```

Meaning:

```text
The action has intent, causal parent, scope, reversibility classification, and approval.
ProofPath accepts it and forwards it to the protected API.
```

## 5. Inspect the audit trail

```bash
$ cat proofpath-audit.jsonl
{"audit_id":"...","previous_hash":"GENESIS","intent_id":"intent_inspect_account_001","causal_parent":"decision_user_requested_inspection","scope":"account.delete","decision":"BLOCK","reason":"IRREVERSIBLE_ACTION_REQUIRES_APPROVAL","forwarded":false,"upstream_url":"http://127.0.0.1:9797/protected","upstream_status":null,"hash":"sha256:..."}
{"audit_id":"...","previous_hash":"sha256:...","intent_id":"intent_delete_account_approved_001","causal_parent":"decision_human_approved_delete","scope":"account.delete","decision":"ACCEPT","reason":null,"forwarded":true,"upstream_url":"http://127.0.0.1:9797/protected","upstream_status":200,"hash":"sha256:..."}
```

## Takeaway

**HTTPS protects the connection. ProofPath protects the meaning of the action.**

A valid connection is not the same as a valid action.

ProofPath makes critical actions accountable.
