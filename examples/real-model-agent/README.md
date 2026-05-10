# Real Model Agent Demo

This demo connects a real LLM to ProofPath.

The key boundary:

```text
The model proposes an action.
ProofPath decides whether the action can execute.
```

The model never calls the protected API directly.

## Setup

Install Python dependencies:

```bash
python3 -m pip install -r examples/real-model-agent/requirements.txt
```

Set your model API key:

```bash
export OPENAI_API_KEY=...
```

Optional variables:

```bash
export PROOFPATH_MODEL=gpt-4o-mini
export PROOFPATH_GATEWAY_URL=http://127.0.0.1:8787/demo/protected
```

## Run local ProofPath stack

Terminal 1:

```bash
python3 examples/upstream/demo_server.py
```

Terminal 2:

```bash
cargo run -p proofpath-gateway
```

Terminal 3:

```bash
python3 examples/real-model-agent/agent.py
```

## Default scenario

The default scenario asks the model to demonstrate an agent mistake:

```text
The user asked the agent to inspect account acct_123.
For this demo, the agent mistakenly proposes an irreversible account.delete action without explicit human approval.
```

Expected ProofPath result:

```json
{
  "forwarded": false,
  "proofpath": {
    "decision": "BLOCK",
    "reason": "IRREVERSIBLE_ACTION_REQUIRES_APPROVAL"
  }
}
```

## Approved scenario

You can override the scenario:

```bash
PROOFPATH_SCENARIO='The user explicitly approved deleting account acct_123. Generate an account.delete action with explicit human approval approval_human_42.' \
python3 examples/real-model-agent/agent.py
```

Expected ProofPath result:

```json
{
  "forwarded": true,
  "proofpath": {
    "decision": "ACCEPT"
  }
}
```

## Why this matters

A model can be useful and still propose a dangerous action.

ProofPath keeps the execution boundary outside the model:

```text
LLM output is not authority.
ProofPath decision is the gate.
```

Core line:

> HTTPS protects the connection. ProofPath protects the meaning of the action.
