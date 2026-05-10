# ProofPath

**Verifiable intent for every critical action.**

> **HTTPS protects the connection. ProofPath protects the meaning of the action.**
>
> HTTPS secures the channel. ProofPath secures the intent.

ProofPath is an open protocol and gateway layer for adding verifiable intent, causal authorization, and auditable action chains to HTTPS APIs and AI-agent systems.

HTTPS proves that a connection is secure. ProofPath proves that an action was authorized, causally grounded, and accountable.

> HTTPS proves the channel. ProofPath proves the action.

## Quick demo

Run the one-minute AI agent dangerous action demo:

```bash
python3 examples/upstream/demo_server.py
cargo run -p proofpath-gateway
bash examples/agent-dangerous-action/agent_delete_without_approval.sh
bash examples/agent-dangerous-action/agent_delete_with_approval.sh
cat proofpath-audit.jsonl
```

Demo story:

```text
AI agent attempts irreversible delete without approval
  -> ProofPath BLOCKS before protected API
AI agent repeats with explicit human approval
  -> ProofPath ACCEPTS and forwards
Every decision
  -> hash-chained audit trail
```

See:

- `examples/agent-dangerous-action/README.md`
- `docs/demo-transcript.md`
- `docs/launch-post.md`

## Why

Modern systems increasingly allow AI agents, services, and automated workflows to perform critical actions:

- send emails
- execute payments
- deploy code
- modify infrastructure
- access private data
- call external APIs
- trigger irreversible operations

HTTPS secures the transport layer, but it does not answer:

- Why did this action happen?
- Who or what authorized it?
- Was there a valid human or system intention?
- Was the action reversible or irreversible?
- Can we prove the causal chain after the fact?

ProofPath adds this missing layer.

## Core idea

Every critical request should carry a verifiable action context:

```http
POST /payments/transfer HTTP/1.1
Host: api.example.com
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-00
x-proofpath-intent-id: intent_9f21
x-proofpath-causal-parent: decision_71ab
x-proofpath-scope: payments.transfer.once
x-proofpath-reversibility: irreversible
x-proofpath-decision: ACCEPT
signature-input: proofpath=("@method" "@target-uri" "x-proofpath-intent-id" "x-proofpath-causal-parent" "x-proofpath-scope" "x-proofpath-reversibility");created=1778430000;keyid="agent-key-1"
signature: proofpath=:BASE64_SIGNATURE:
```

The request is not only checked for identity and transport security. It is checked for causal validity.

## Decision model

A ProofPath-compatible gateway can return:

```json
{
  "decision": "ACCEPT",
  "intent_id": "intent_9f21",
  "causal_valid": true,
  "scope_valid": true,
  "reversibility": "irreversible",
  "audit_hash": "sha256:..."
}
```

or:

```json
{
  "decision": "BLOCK",
  "reason": "MISSING_CAUSAL_AUTHORIZATION"
}
```

## Project goals

- Define a minimal ProofPath HTTP header profile.
- Build a Rust gateway for validating ProofPath-aware requests.
- Support signed request context using HTTP Message Signatures.
- Integrate with W3C Trace Context where possible.
- Provide conformance fixtures for valid and invalid request chains.
- Build tools for inspecting, replaying, and auditing action traces.

## Non-goals

ProofPath does not replace HTTPS, TLS, OAuth, OpenTelemetry, or existing API gateways.

ProofPath complements them by adding causal authorization and verifiable intent.

## Architecture

```text
Client / Agent
    |
    | HTTPS request + ProofPath headers
    v
ProofPath Gateway
    |
    | validates intent, causal parent, scope, reversibility, signature
    v
Protected API
    |
    v
Append-only audit log
```

## Planned components

```text
proofpath/
  specs/
    proofpath-http-profile-v0.1.md
    headers.md
    threat-model.md
    signature-profile.md
  crates/
    proofpath-gateway/
    proofpath-verifier/
    proofpath-policy/
  examples/
    payments-api/
    ai-agent-actions/
    ci-deploy-gate/
  conformance/
    valid/
    invalid/
  docs/
    philosophy.md
    why-https-is-not-enough.md
```

## Standards alignment

ProofPath aims to build on existing web infrastructure:

- HTTPS / TLS for secure transport
- W3C Trace Context for distributed trace propagation
- HTTP Message Signatures for signing request components
- OpenTelemetry-style observability for operational traces

## Status

Early protocol design. Expect breaking changes.

## License

MIT
