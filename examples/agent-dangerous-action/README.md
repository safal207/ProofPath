# AI Agent Dangerous Action Demo

This demo shows the core ProofPath story in one minute.

## Scenario

An AI agent has a valid HTTPS connection and can call an API.

The user asked the agent to inspect an account.

The agent attempts an irreversible delete action without human approval.

A traditional API boundary may see a valid request. ProofPath sees a missing causal authorization for an irreversible action and blocks it.

## Core line

**HTTPS protects the connection. ProofPath protects the meaning of the action.**

## Run

Terminal 1: start the demo protected API.

```bash
python3 examples/upstream/demo_server.py
```

Terminal 2: start the ProofPath gateway.

```bash
cargo run -p proofpath-gateway
```

Terminal 3: run the dangerous agent action.

```bash
bash examples/agent-dangerous-action/agent_delete_without_approval.sh
```

Expected result:

```text
HTTP/1.1 403 Forbidden
```

```json
{
  "forwarded": false,
  "proofpath": {
    "decision": "BLOCK",
    "reason": "IRREVERSIBLE_ACTION_REQUIRES_APPROVAL"
  }
}
```

Meaning:

```text
The connection may be valid.
The action is not valid.
ProofPath blocks it before the protected API sees it.
```

Now run the approved action:

```bash
bash examples/agent-dangerous-action/agent_delete_with_approval.sh
```

Expected result:

```text
HTTP/1.1 200 OK
```

```json
{
  "forwarded": true,
  "upstream_status": 200,
  "proofpath": {
    "decision": "ACCEPT"
  }
}
```

Meaning:

```text
The action has intent, causal parent, scope, reversibility classification, and explicit human approval.
ProofPath accepts it and forwards it to the protected API.
```

Finally inspect the audit trail:

```bash
cat proofpath-audit.jsonl
```

Expected audit shape:

```jsonl
{"audit_id":"...","previous_hash":"GENESIS","intent_id":"intent_inspect_account_001","causal_parent":"decision_user_requested_inspection","scope":"account.delete","decision":"BLOCK","reason":"IRREVERSIBLE_ACTION_REQUIRES_APPROVAL","forwarded":false,"upstream_status":null,"hash":"sha256:..."}
{"audit_id":"...","previous_hash":"sha256:...","intent_id":"intent_delete_account_approved_001","causal_parent":"decision_human_approved_delete","scope":"account.delete","decision":"ACCEPT","reason":null,"forwarded":true,"upstream_status":200,"hash":"sha256:..."}
```

Reviewer quick check:

```text
1. The unsafe irreversible action returns BLOCK.
2. The blocked action is not forwarded upstream.
3. The approved irreversible action returns ACCEPT.
4. The approved action is forwarded upstream.
5. Both decisions appear in the audit log.
6. The second audit entry links to the previous hash.
```

## Full transcript

For a fuller expected terminal transcript, see:

- `docs/demo-transcript.md`

## What this proves

ProofPath does not replace HTTPS.

ProofPath adds a causal action boundary:

```text
agent action
  -> declared intent
  -> causal parent
  -> scope
  -> reversibility
  -> human approval when required
  -> ACCEPT/BLOCK/REJECT
  -> audit hash trail
```

## Takeaway

A valid connection is not the same as a valid action.

ProofPath makes critical actions accountable.
