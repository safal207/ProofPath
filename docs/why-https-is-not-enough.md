# Why HTTPS Is Not Enough for AI Agents

HTTPS is necessary infrastructure. It protects the transport channel and helps ensure that messages are exchanged securely between endpoints.

But agentic systems introduce a different problem.

The question is no longer only:

> Was the connection secure?

The question becomes:

> Was the action actually authorized by a valid intent and causal chain?

## The gap

An AI agent can perform actions across APIs, browsers, databases, CI/CD systems, email tools, payment systems, and cloud consoles.

Even when each API call happens over HTTPS, the system may still fail to answer:

- Did the user really ask for this?
- Did the agent infer too much?
- Was the tool call inside the allowed scope?
- Was this action reversible?
- Was human approval required?
- Can we audit the causal path afterward?

## Example

A request like this can be technically valid:

```http
DELETE /production/database/customer-records HTTP/1.1
Authorization: Bearer VALID_TOKEN
```

But that does not prove the action should happen.

ProofPath adds the missing context:

```http
x-proofpath-intent-id: intent_9f21
x-proofpath-causal-parent: decision_71ab
x-proofpath-scope: database.delete.once
x-proofpath-reversibility: irreversible
x-proofpath-human-approval: approval_11fa
```

Now the gateway can ask better questions:

- Does this intent exist?
- Does the causal parent exist?
- Is the scope valid?
- Is this irreversible action approved?
- Is the context signed?

## Principle

HTTPS proves the channel.

ProofPath proves the action.

## Target users

ProofPath is intended for teams building or securing:

- AI-agent platforms
- API gateways
- fintech systems
- CI/CD automation
- infrastructure automation
- healthcare workflows
- enterprise audit systems
- high-risk tool-calling systems

## The future

As systems become more automated, identity and encryption remain necessary but insufficient.

The next trust layer must include intent, causality, consequence, and auditability.
