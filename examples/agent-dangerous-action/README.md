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

```json
{
  "forwarded": false,
  "proofpath": {
    "decision": "BLOCK",
    "reason": "IRREVERSIBLE_ACTION_REQUIRES_APPROVAL"
  }
}
```

Now run the approved action:

```bash
bash examples/agent-dangerous-action/agent_delete_with_approval.sh
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

Finally inspect the audit trail:

```bash
cat proofpath-audit.jsonl
```

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
