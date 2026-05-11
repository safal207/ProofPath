# ProofPath Internet Action Layer

## Summary

The internet is very good at proving that a connection is protected, that an identity is authenticated, or that a credential is valid.

It is weaker at proving whether a specific high-risk action should happen now.

ProofPath focuses on that missing execution boundary.

```text
valid connection
  + valid identity
  + valid credential
  != valid action
```

ProofPath is not a replacement for TCP/IP, TLS, DNS, IAM, OAuth, API keys, firewalls, brokers, databases, CI/CD systems, or application security.

ProofPath is an additional pre-execution decision layer for critical actions.

## From transport security to action security

Traditional internet infrastructure answers questions such as:

- Is the connection encrypted?
- Is the certificate valid?
- Is the user or service authenticated?
- Does the credential have broad permission?
- Did the request reach the expected endpoint?

Those questions are necessary.

But high-risk automated systems and AI agents also need a different question:

> Should this specific action be allowed to execute now?

That action-level question includes:

- What is the declared intent?
- What is the causal parent or prior authorization context?
- What scope is being used?
- Is the action reversible, compensatable, or irreversible?
- Does the action require human approval?
- Should the action be accepted, held, rejected, blocked, or audited?
- Can the decision be reviewed later?

ProofPath adds this action-level boundary.

## Internet layer map

| Internet layer | Existing controls | Missing action question | ProofPath gate example |
| --- | --- | --- | --- |
| DNS / domain | registrar auth, DNSSEC, account security | Should this production DNS record change now? | Block DNS change without approved intent. |
| CDN / edge | CDN tokens, WAF rules, edge config ACLs | Should this cache/security rule change now? | Hold or block production edge rule changes without approval. |
| TLS / certificate | TLS, certificate managers, ACME, CA policies | Should this certificate or trust configuration change now? | Block unapproved certificate rotation or trust change. |
| Network / routing | VPN, firewalls, routing ACLs, network automation | Should this route, firewall, or ACL change execute now? | Block high-risk production network changes without approval. |
| API gateway | API keys, OAuth, IAM, rate limits | Should this specific API action execute now? | Block irreversible API action without causal authorization. |
| Message broker | broker ACLs, credentials, TLS, cluster policy | Should this broker policy/topic/queue action execute now? | Block high-risk broker policy change without approval. |
| Database | DB roles, IAM, network ACLs, migrations | Should this schema or data change execute now? | Block schema/data change without approval. |
| CI/CD | GitHub tokens, deploy keys, protected branches | Should this production deploy happen now? | Block production deploy without approved intent. |
| Website / app | deploy credentials, app auth, CI controls | Should this website change publish now? | Block destructive website asset change without approval. |
| Secrets / environment | vaults, repo permissions, secret managers | Should this secret or environment change happen now? | Block production secret/env change without approval. |
| Email / CRM | OAuth, workspace permissions, CRM roles | Should this outbound message or customer data export happen now? | Hold or block mass send/export without approval. |
| AI agent tools | tool permissions, sandboxing, provider controls | Should this tool call be executed in this context? | Block unsafe tool call before side effects. |
| Memory / state | storage ACLs, vector DB access, app policy | Should this memory/state update become durable? | Block destructive or ungrounded memory update. |

## What ProofPath does not replace

ProofPath does not replace:

- TCP/IP;
- TLS or HTTPS;
- DNSSEC;
- OAuth;
- IAM;
- API keys;
- network firewalls;
- broker ACLs;
- database permissions;
- CI/CD controls;
- secret managers;
- sandboxing;
- secure software development practices;
- human review processes.

Those controls remain necessary.

ProofPath complements them by asking whether the proposed action is valid in context.

## What ProofPath adds

ProofPath adds a standard action context:

```text
declared intent
causal parent
scope
reversibility
approval when required
decision
audit hash
```

This lets a gateway or verifier make an explicit decision before a high-risk action reaches the protected system.

A simplified action flow:

```text
agent or service proposes action
  -> ProofPath receives request context
  -> verifier checks intent, causal parent, scope, reversibility, approval
  -> safe action is forwarded
  -> high-risk unapproved action is blocked or held
  -> decision is written to hash-chained audit log
```

## Why this matters for AI agents

AI agents increase the importance of action-level security because they can combine:

- valid credentials;
- tool access;
- multi-step planning;
- ambiguous user intent;
- automated execution;
- irreversible side effects.

A model can produce a tool call that is syntactically valid and authenticated while still being unsafe in context.

ProofPath does not claim to fully understand human intent. Instead, it treats declared intent, causal context, scope, reversibility, and approval as security-relevant evidence that must be checked and logged.

## Relationship to current demos

The current demos are examples of the same internet action-layer pattern:

| Demo | Boundary |
| --- | --- |
| `examples/agent-dangerous-action` | Valid agent/API access is not the same as valid irreversible action. |
| `examples/website-builder-gate` | Valid deploy access is not the same as valid website change. |
| `examples/network-broker-gate` | Valid infra access is not the same as valid network or broker action. |
| `examples/database-migration-gate` | Valid DB credentials are not the same as valid schema or data change. |

Each demo follows the same rule:

```text
safe / reversible / scoped action -> ACCEPT
high-risk irreversible action without approval -> BLOCK
```

## Reviewer takeaway

ProofPath is best understood as an execution-boundary security layer.

It starts from a simple claim:

> The internet can prove that a connection is valid. ProofPath helps prove that an action is valid.

Or shorter:

```text
TLS secures the channel.
IAM secures the identity.
ProofPath secures the decision to act.
```
