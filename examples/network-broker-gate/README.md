# Network and Message Broker Gate Demo

This demo shows ProofPath as a mandatory pre-execution gate for network operations and message broker administration.

It makes ProofPath useful for infrastructure teams, SREs, platform engineers, network engineers, and teams operating Kafka/RabbitMQ/NATS-like systems.

```text
AI/SRE assistant proposes infra action
  -> network or broker action context is declared
  -> ProofPath checks intent, causal parent, scope, reversibility, and approval
  -> safe diagnostic actions continue
  -> risky config/admin actions are blocked before execution
  -> every decision is written to the audit log
```

## Core line

**Valid infra access should not automatically mean valid network or broker action.**

An infra assistant may have a valid admin token, broker credential, VPN access, or network automation key. That does not mean every proposed infrastructure action should execute.

ProofPath does not replace IAM, broker ACLs, network ACLs, VPN, TLS, or existing infrastructure controls. It adds an action-level decision boundary before high-risk infrastructure actions execute.

## Scenario

An infra assistant is allowed to help with diagnostics.

The assistant attempts three actions:

1. a safe network diagnostic;
2. a production network policy change without explicit human approval;
3. a high-risk message broker policy change without explicit human approval.

ProofPath separates these cases:

```text
safe network diagnostic                 -> ACCEPT
production network change without approval -> BLOCK
broker policy change without approval      -> BLOCK
```

## Run

Terminal 1: start the demo protected API.

```bash
python3 examples/upstream/demo_server.py
```

Terminal 2: start the ProofPath gateway.

```bash
cargo run -p proofpath-gateway
```

Terminal 3: run the network/broker scenarios.

### 1. Safe network diagnostic

```bash
bash examples/network-broker-gate/network_read_status.sh
```

Expected result:

```text
HTTP/1.1 200 OK
```

```json
{
  "forwarded": true,
  "proofpath": {
    "decision": "ACCEPT"
  }
}
```

Meaning:

```text
The action is read-only, scoped as diagnostic, and reversible.
ProofPath accepts it and forwards it to the protected API.
```

### 2. Production network change without approval

```bash
bash examples/network-broker-gate/network_change_production_without_approval.sh
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
The assistant may have valid infra credentials.
The proposed production network change is high-risk and lacks explicit human approval.
ProofPath blocks it before the protected API sees it.
```

### 3. Broker policy change without approval

```bash
bash examples/network-broker-gate/broker_policy_change_without_approval.sh
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
The assistant attempts a high-risk broker policy change without explicit approval.
ProofPath blocks the action before execution.
```

## Inspect the audit trail

```bash
cat proofpath-audit.jsonl
```

Expected audit shape:

```jsonl
{"audit_id":"...","previous_hash":"GENESIS","intent_id":"intent_read_network_status_001","causal_parent":"decision_user_requested_network_diagnostic","scope":"network.diagnostic.read","decision":"ACCEPT","reason":null,"forwarded":true,"upstream_status":200,"hash":"sha256:..."}
{"audit_id":"...","previous_hash":"sha256:...","intent_id":"intent_change_production_network_policy_001","causal_parent":"decision_agent_detected_network_issue","scope":"network.firewall.change","decision":"BLOCK","reason":"IRREVERSIBLE_ACTION_REQUIRES_APPROVAL","forwarded":false,"upstream_status":null,"hash":"sha256:..."}
{"audit_id":"...","previous_hash":"sha256:...","intent_id":"intent_change_broker_policy_001","causal_parent":"decision_agent_reduce_message_lag","scope":"broker.policy.change","decision":"BLOCK","reason":"IRREVERSIBLE_ACTION_REQUIRES_APPROVAL","forwarded":false,"upstream_status":null,"hash":"sha256:..."}
```

## Reviewer quick check

```text
1. Safe network diagnostic returns ACCEPT.
2. Safe diagnostic is forwarded upstream.
3. Production network policy change without approval returns BLOCK.
4. Broker policy change without approval returns BLOCK.
5. Blocked actions are not forwarded upstream.
6. All decisions appear in the audit log.
7. Audit entries form a hash-linked chain.
```

## Suggested network and broker action scopes

```text
network.diagnostic.read
network.firewall.change
network.route.change
network.acl.change
network.dns.change
broker.message.publish.staging
broker.topic.create
broker.policy.change
broker.retention.change
broker.binding.change
broker.queue.purge
broker.consumer.rebalance
```

## Suggested approval policy

Require explicit human approval for:

- production firewall changes;
- production route changes;
- ACL/security policy changes;
- DNS changes affecting production traffic;
- broker policy changes affecting production streams;
- broker retention changes;
- queue/topic purge or replacement;
- dead-letter path changes;
- production exchange/topic/queue binding changes;
- disabling observability or retry paths.

## What this proves

ProofPath can protect infrastructure workflows, not only generic API calls.

The important boundary is not whether the agent has credentials. The boundary is whether the proposed network or broker action is valid in context.

## Takeaway

A valid admin token, broker credential, VPN session, or automation key is not the same as a valid infrastructure action.

ProofPath makes AI-assisted infrastructure changes reviewable before execution.
