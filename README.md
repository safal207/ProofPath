# ProofPath

**Verifiable intent for every critical action.**

> **HTTPS protects the connection. ProofPath protects the meaning of the action.**
>
> HTTPS secures the channel. ProofPath secures the intent.

ProofPath is an open protocol and gateway layer for adding verifiable intent, causal authorization, and auditable action chains to HTTPS APIs and AI-agent systems.

HTTPS proves that a connection is secure. ProofPath proves that an action was authorized, causally grounded, and accountable.

> HTTPS proves the channel. ProofPath proves the action.

## 60-second reviewer summary

**ProofPath is a defensive pre-execution gateway that prevents valid AI-agent/API credentials from becoming unsafe, unaudited, or irreversible actions.**

ProofPath does **not** replace HTTPS, OAuth, IAM, API keys, or ordinary infrastructure security. Those layers remain necessary. ProofPath adds an action-level security and audit layer at the execution boundary: before a high-risk AI-agent or API action reaches the protected upstream system.

If you arrived here from an already-submitted grant application under an earlier name or framing, start with the [Submitted Application Reviewer Bridge](docs/SUBMITTED_APPLICATION_REVIEWER_BRIDGE.md). To understand how the related repositories fit together, see the [Ecosystem Graph](docs/ECOSYSTEM_GRAPH.md).

### Two ways to use ProofPath v0.1

ProofPath v0.1 now has two practical product surfaces:

| Surface | Path | What it gives you |
| --- | --- | --- |
| CI evidence gate | [`action.yml`](action.yml), [`docs/GITHUB_ACTION_QUICKSTART.md`](docs/GITHUB_ACTION_QUICKSTART.md) | Turn ProofPath audit logs into CI-verifiable metrics and pass/fail checks. |
| Personal Agent Guard | [`examples/personal-agent-guard/`](examples/personal-agent-guard/) | Add a local approval boundary and audit log around Claude Code / Codex-style AI coding tools. |

Product phrase:

```text
ProofPath turns action-boundary audit logs into CI-verifiable evidence.
```

Personal workflow phrase:

```text
ProofPath Personal Agent Guard is a local seatbelt for AI coding tools.
```

### Why HTTPS is not enough

HTTPS can protect the connection. API authentication can prove that a credential is valid. IAM can define broad permissions.

But high-risk AI-agent systems need an additional question:

> Should this specific action be allowed to execute now?

A request can be authenticated and still be unsafe. For example, an AI agent may have valid credentials while attempting to delete data, modify infrastructure, push unsafe code, trigger a financial workflow, or perform an irreversible administrative action outside the intended scope.

ProofPath focuses on that gap.

### What ProofPath does

ProofPath evaluates high-risk actions before execution and can produce explicit decisions such as `ACCEPT`, `HOLD`, `REJECT`, `BLOCK`, or `AUDIT`.

The current prototype demonstrates:

- declared intent checks;
- causal parent checks;
- scope checks;
- reversibility classification;
- human approval requirements for irreversible actions;
- a Rust verifier crate;
- an Axum gateway;
- upstream forwarding only after a ProofPath decision;
- blocking unsafe irreversible actions before they reach the protected API;
- hash-chained JSONL audit logs;
- dangerous-action and real-model-agent demos;
- reusable GitHub Action evidence gate;
- local Personal Agent Guard for Claude Code / Codex-style tools.

### ACCEPT vs BLOCK

Conceptually:

```text
ACCEPT:
  action has declared intent
  action has causal parent
  action is within scope
  action is reversible or approved
  gateway forwards upstream

BLOCK:
  action is irreversible
  action lacks required human approval
  gateway blocks before upstream execution
  decision is written to the audit log
```

### Why Compute Witness matters

Compute Witness turns AI/agent compute into reviewable evidence: a job manifest declares intent, scope, causal authorization, and commitments before a result is trusted.

The repository includes Python conformance, audit packet examples, challenge fixtures, a Rust verifier adapter, a Rust CLI, expected output fixtures, Rust audit-hash verification, and CI regression checks.

Reviewers can run the path locally without trusting a hidden service: start with the [Compute Witness grant reviewer path](docs/COMPUTE_WITNESS_GRANT_REVIEWER_PATH.md), the [Submitted Application Reviewer Bridge](docs/SUBMITTED_APPLICATION_REVIEWER_BRIDGE.md), the [Ecosystem Graph](docs/ECOSYSTEM_GRAPH.md), or the [Compute Witness reviewer quickstart](examples/compute-witness/README.md#reviewer-quickstart).

### Reviewer links

- [Start Here: ProofPath v0.1](docs/START_HERE_V0_1.md)
- [ProofPath v0.1 landing](docs/LANDING_V0_1.md)
- [Personal Agent Guard](examples/personal-agent-guard/)
- [Reviewer summary](docs/reviewer-summary.md)
- [ProofPath v0.1 Product Milestone](docs/RELEASE_V0_1.md)
- [Evidence Packet v0.1](docs/EVIDENCE_PACKET_V0_1.md)
- [Evidence Metrics v0.1](docs/EVIDENCE_METRICS_V0_1.md)
- [ProofPath GitHub Action quickstart](docs/GITHUB_ACTION_QUICKSTART.md)
- [Submitted Application Reviewer Bridge](docs/SUBMITTED_APPLICATION_REVIEWER_BRIDGE.md)
- [Ecosystem Graph](docs/ECOSYSTEM_GRAPH.md)
- [Compute Witness grant reviewer path](docs/COMPUTE_WITNESS_GRANT_REVIEWER_PATH.md)
- [TRC / TPU evidence plan](docs/TRC_TPU_EVIDENCE_PLAN.md)
- [Compute Witness reviewer quickstart](examples/compute-witness/README.md#reviewer-quickstart)
- [Internet Action Layer](docs/internet-action-layer.md)
- [Conformance fixtures](conformance/README.md)
- [Security grant revision note](docs/grant-updates/security-grant-revision-proofpath-update.md)
- [Threat model](specs/threat-model.md)
- [HTTP action-context profile](specs/proofpath-http-profile-v0.1.md)
- [Community experiments](COMMUNITY_EXPERIMENTS.md)

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

## Personal Agent Guard demo

Run the local AI coding tool guard demo:

```bash
bash examples/personal-agent-guard/run_demo_check.sh
```

Demo story:

```text
AI coding tool proposes a guarded command
  -> ProofPath Personal Agent Guard BLOCKS before approval
User creates a scoped time-limited approval
  -> the same command is ALLOWed
Every decision
  -> local .proofpath/audit.jsonl
```

See:

- `examples/personal-agent-guard/README.md`
- `examples/personal-agent-guard/demo-transcript.md`
- `examples/personal-agent-guard/claude-settings.example.json`
- `examples/personal-agent-guard/codex-config.example.toml`

## Execution-boundary demo matrix

ProofPath is intentionally demonstrated across multiple high-risk action boundaries. See also: [Internet Action Layer](docs/internet-action-layer.md).

| Demo | Core boundary | Expected decisions |
| --- | --- | --- |
| [AI agent dangerous action](examples/agent-dangerous-action/README.md) | Valid agent/API access is not the same as valid irreversible action. | `BLOCK` unsafe action, `ACCEPT` approved action |
| [Website builder gate](examples/website-builder-gate/README.md) | Valid deploy access is not the same as valid website change. | `ACCEPT` safe edit, `BLOCK` production/destructive changes without approval |
| [Network and broker gate](examples/network-broker-gate/README.md) | Valid infra access is not the same as valid network or broker action. | `ACCEPT` diagnostic, `BLOCK` high-risk infra changes without approval |
| [Database migration gate](examples/database-migration-gate/README.md) | Valid DB credentials are not the same as valid schema or data change. | `ACCEPT` inspection, `BLOCK` schema/data changes without approval |
| [CI/CD deploy gate](examples/cicd-deploy-gate/README.md) | Valid CI credentials are not the same as valid production deployment. | `ACCEPT` preview deploy, `BLOCK` production deploy without approval, `ACCEPT` approved rollback |
| [Personal Agent Guard](examples/personal-agent-guard/README.md) | Valid local AI-tool access is not the same as valid high-impact command execution. | `BLOCK` before approval, `ALLOW` after scoped time-limited approval |

Reviewer pattern:

```text
valid credential
  != valid action
  != valid scope
  != valid reversibility
  != valid approval
```

Each demo uses the same execution-boundary structure:

```text
agent proposes action
  -> ProofPath checks declared intent, causal parent, scope, reversibility, and approval
  -> safe action is forwarded
  -> high-risk action without approval is blocked
  -> decision is written to hash-chained audit log
```

## Join the Lab

ProofPath is open for community experiments.

We are not asking people to only confirm that it works. We want people to run it, break it, critique it, and tell us where the boundary is weak.

Pick an experiment level:

```text
L0 — Reader feedback: is the idea understandable?
L1 — Local demo: does the gateway work on your machine?
L2 — Real model: does the LLM boundary feel clear?
L3 — Red-team: can you break the model/action boundary?
L4 — Integration: can ProofPath protect another toy or real system?
L5 — Protocol critique: are the headers, reasons, and threat model right?
```

Start here:

- `COMMUNITY_EXPERIMENTS.md`
- #14 Reader feedback
- #15 Local gateway demo
- #16 Real model agent demo
- #17 Red-team the model boundary
- #18 Build an integration
- #19 Protocol and threat model critique

Lab principle:

> Do not only tell us what works. Tell us where ProofPath breaks, where it is confusing, and where the protocol is too weak.

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
