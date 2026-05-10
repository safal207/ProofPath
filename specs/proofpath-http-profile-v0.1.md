# ProofPath HTTP Profile v0.1

Status: Draft

## 1. Purpose

ProofPath adds verifiable intent and causal authorization metadata to HTTPS requests.

The profile is designed for APIs, AI-agent actions, workflow automation, and critical operations where secure transport is necessary but not sufficient.

ProofPath does not replace HTTPS, TLS, OAuth, OpenTelemetry, or existing API gateways. It adds an action accountability layer.

## 2. Design principle

A request is not considered fully admissible only because it is authenticated or transported over HTTPS.

A critical request SHOULD be evaluated across four dimensions:

1. Identity: who or what is making the request.
2. Intent: what intended outcome the request claims to serve.
3. Causality: which prior decision or state authorizes this action.
4. Consequence: whether the action is reversible, compensatable, or irreversible.

## 3. Required headers

### `x-proofpath-intent-id`

A stable identifier for the declared intention behind the action.

Example:

```http
x-proofpath-intent-id: intent_9f21
```

### `x-proofpath-causal-parent`

A stable identifier for the prior decision, approval, policy result, or trace event that causally authorizes the request.

Example:

```http
x-proofpath-causal-parent: decision_71ab
```

### `x-proofpath-scope`

A minimal permission scope for the action.

Example:

```http
x-proofpath-scope: payments.transfer.once
```

### `x-proofpath-reversibility`

The reversibility class of the action.

Allowed values:

- `reversible`
- `compensatable`
- `irreversible`

Example:

```http
x-proofpath-reversibility: irreversible
```

## 4. Optional headers

### `x-proofpath-agent-id`

Identifier for the agent, service, workflow, or human-operated client performing the action.

### `x-proofpath-human-approval`

Reference to a human approval record when required by policy.

### `x-proofpath-policy-id`

Identifier of the policy profile used to evaluate the request.

### `x-proofpath-decision`

Decision produced by a ProofPath-compatible verifier or gateway.

Allowed values:

- `ACCEPT`
- `HOLD`
- `REJECT`
- `BLOCK`
- `AUDIT`

### `x-proofpath-audit-hash`

Hash of the audit record or append-only log entry associated with the request.

## 5. Decision outcomes

### ACCEPT

The request is causally valid and can proceed.

### HOLD

The request is not rejected, but needs more information, preconditions, or human confirmation.

### REJECT

The request is invalid and should not proceed. Rejection is normally caused by malformed or missing ProofPath context.

### BLOCK

The request is structurally valid but policy-denied or unsafe.

### AUDIT

The request may proceed, but a policy has marked it for additional review.

## 6. Failure reasons

Suggested reason codes:

- `MISSING_INTENT`
- `MISSING_CAUSAL_PARENT`
- `INVALID_SCOPE`
- `INVALID_REVERSIBILITY`
- `INVALID_SIGNATURE`
- `REPLAY_DETECTED`
- `IRREVERSIBLE_ACTION_REQUIRES_APPROVAL`
- `POLICY_DENIED`
- `CAUSAL_CHAIN_BROKEN`
- `UNSUPPORTED_PROFILE_VERSION`

## 7. Example: accepted request

```http
POST /payments/transfer HTTP/1.1
Host: api.example.com
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-00
x-proofpath-intent-id: intent_9f21
x-proofpath-causal-parent: decision_71ab
x-proofpath-scope: payments.transfer.once
x-proofpath-reversibility: irreversible
x-proofpath-human-approval: approval_11fa
signature-input: proofpath=("@method" "@target-uri" "x-proofpath-intent-id" "x-proofpath-causal-parent" "x-proofpath-scope" "x-proofpath-reversibility" "x-proofpath-human-approval");created=1778430000;keyid="agent-key-1"
signature: proofpath=:BASE64_SIGNATURE:
```

Expected verifier result:

```json
{
  "decision": "ACCEPT",
  "reason": null,
  "intent_id": "intent_9f21",
  "causal_parent": "decision_71ab",
  "scope_valid": true,
  "causal_valid": true,
  "signature_valid": true
}
```

## 8. Example: blocked request

```http
DELETE /accounts/123 HTTP/1.1
Host: api.example.com
x-proofpath-intent-id: intent_9012
x-proofpath-scope: accounts.delete
x-proofpath-reversibility: irreversible
```

Expected verifier result:

```json
{
  "decision": "BLOCK",
  "reason": "MISSING_CAUSAL_PARENT"
}
```

## 9. Signature profile

Critical ProofPath headers SHOULD be signed using HTTP Message Signatures or an equivalent request-signing mechanism.

At minimum, signatures SHOULD cover:

- HTTP method
- target URI
- `x-proofpath-intent-id`
- `x-proofpath-causal-parent`
- `x-proofpath-scope`
- `x-proofpath-reversibility`
- body digest when applicable

## 10. Compatibility with trace context

ProofPath MAY use W3C Trace Context headers such as `traceparent` and `tracestate` for distributed trace correlation.

Trace context identifies where a request traveled. ProofPath identifies why the action was admissible.

## 11. Open questions

- Should ProofPath define a canonical JSON envelope in addition to HTTP headers?
- Should causal parent references be URI-like, UUID-like, or content-addressed?
- What is the minimum viable policy language for v0.1?
- Should irreversible actions always require explicit human approval?
- How should gateways handle partial ProofPath adoption in legacy systems?
