# ProofPath Threat Model

Status: Draft

## Purpose

This document describes the first threat model for ProofPath.

ProofPath assumes that HTTPS, TLS, identity providers, and API gateways may already exist. The project focuses on threats where the channel is secure but the action is still causally unsafe, unauthorized in context, or impossible to explain after the fact.

## Core assumption

A technically valid request can still be causally invalid.

Examples:

- The token is valid, but the action was never approved.
- The request is over HTTPS, but the agent invented the user intent.
- The workflow has permission to read data, but suddenly attempts to delete data.
- The deployment request is authenticated, but not connected to an approved change.

## Assets to protect

- Human intent
- Authorization decisions
- Critical API operations
- Irreversible actions
- Agent tool calls
- Audit trails
- Policy decisions
- Causal chain integrity

## Threat scenarios

### 1. Stolen token performs valid HTTPS request

An attacker obtains a valid bearer token and sends a syntactically correct HTTPS request.

ProofPath mitigation:

- Require `x-proofpath-intent-id`.
- Require `x-proofpath-causal-parent`.
- Require signed ProofPath context.
- Reject or block requests without a valid causal chain.

### 2. Confused deputy agent

An AI agent with broad tool access is manipulated into performing an action that the user did not actually intend.

ProofPath mitigation:

- Bind tool calls to declared intent.
- Require scoped permissions.
- Require human approval for irreversible actions.
- Audit the chain from user instruction to final API call.

### 3. Irreversible action without approval

A service or agent deletes data, transfers money, or deploys code without explicit approval.

ProofPath mitigation:

- Mark actions as `irreversible`.
- Require `x-proofpath-human-approval` for configured scopes.
- Return `HOLD` or `BLOCK` if approval is missing.

### 4. Replay attack

A previously valid request is replayed.

ProofPath mitigation:

- Include timestamp, nonce, or request digest in the signed context.
- Maintain replay cache for critical scopes.
- Return `REPLAY_DETECTED`.

### 5. Scope escalation

A client authorized for one scope attempts another scope.

ProofPath mitigation:

- Evaluate `x-proofpath-scope` against policy.
- Bind scope to intent and causal parent.
- Return `INVALID_SCOPE` or `POLICY_DENIED`.

### 6. Causal chain forgery

A client supplies a fake causal parent identifier.

ProofPath mitigation:

- Verify causal parent exists in trusted audit storage.
- Verify parent status and policy outcome.
- Verify parent hash/signature when applicable.

### 7. Audit trail tampering

An attacker modifies or deletes audit logs after the action.

ProofPath mitigation:

- Use append-only JSONL logs.
- Chain audit records with hashes.
- Periodically anchor log heads to external storage where possible.

## Out of scope for v0.1

- Replacing TLS or HTTPS
- Replacing OAuth/OIDC
- Full formal verification of policy language
- Universal identity management
- Network-level intrusion detection

## Initial security invariant

A critical action SHOULD NOT execute unless it has:

1. a declared intent,
2. a valid causal parent,
3. a valid scope,
4. a reversibility classification,
5. a policy decision,
6. an auditable record.
