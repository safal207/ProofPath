# ProofPath Grant Positioning

This note explains how ProofPath supports existing and future grant applications.

Core line:

> HTTPS protects the connection. ProofPath protects the meaning of the action.

## Strategic role

ProofPath should not be positioned as a replacement for PythiaLabs, LTP, or CML.

It is the minimal, runnable reference implementation of an action-level evidence gate for AI-agent systems.

```text
LTP / CML     -> deeper research infrastructure for traces and causal memory
PythiaLabs    -> evidence-gate product/research framing
ProofPath     -> concrete protocol + gateway + demo + community lab
```

## Why ProofPath matters for funders

Modern AI agents may hold valid credentials and use valid HTTPS connections while still performing invalid or unsafe actions.

ProofPath studies and implements a pre-execution boundary that checks:

- declared intent;
- causal parent;
- action scope;
- reversibility;
- human approval when required;
- gateway decision;
- auditability after the decision.

The project now includes:

- protocol draft;
- Rust verifier;
- Axum gateway;
- upstream forwarding;
- hash-chained JSONL audit logs;
- dangerous AI-agent action demo;
- real-model-agent demo;
- community experiment levels L0-L5.

## NLnet NGI Zero Commons — proposal 2026-06-133

Submitted proposal:

```text
PythiaLabs: Open Evidence Gates for High-Risk AI-Agent Actions
Code: 2026-06-133
Requested amount: €30,000
```

ProofPath is directly aligned with this proposal.

Mapping:

```text
Open evidence gate                 -> ProofPath gateway
High-risk AI-agent action           -> dangerous agent action demo
Pre-execution decision              -> ACCEPT / BLOCK / REJECT
Reviewer-facing artifact            -> demo transcript + audit JSONL
Tamper-checkable output             -> hash-chained audit trail
Community engagement                -> ProofPath Lab experiment levels
```

Recommended use:

Send NLnet a short clarification/update before the deadline if appropriate.

Do not rewrite the proposal radically. Frame ProofPath as a concrete prototype created after submission that strengthens the original deliverables.

Suggested phrase:

> Since submitting proposal 2026-06-133, I built ProofPath as a concrete open-source prototype aligned with the proposal: a causal gateway for high-risk AI-agent actions with a Rust verifier, Axum gateway, real-model-agent demo, hash-chained audit logs, and community experiment levels.

## Schmidt Sciences — Science of Trustworthy AI

ProofPath fits as an empirical workstream for action-level oversight.

Recommended framing:

```text
ProofPath Lab: action-level oversight experiments for AI agents under tool-use and irreversible-action settings.
```

Strong research questions:

- When does valid tool access become invalid action execution?
- Can action context checks reduce unsafe irreversible actions?
- Which causal/action fields are necessary for reliable pre-execution oversight?
- How do real models fail when asked to propose action plans under pressure?

ProofPath deliverables that support the application:

- reproducible local demo;
- real-model-agent experiment;
- red-team issue track;
- structured reason codes;
- audit trail for post-hoc analysis;
- community feedback loop.

## Schmidt Sciences — Interpretability RFP

ProofPath is not a pure interpretability project.

Use it carefully as a supporting artifact, not the central claim.

Possible fit:

- detecting unsafe action proposals;
- studying mismatch between natural-language instruction and proposed tool action;
- generating structured traces of model action intent;
- comparing model-proposed action context against policy/verifier decisions.

Avoid overclaiming that ProofPath explains model internals.

## OpenAI Cybersecurity Grant Program

ProofPath is a strong defensive cybersecurity fit.

Recommended framing:

```text
A defensive gateway for AI-assisted systems that prevents valid credentials from becoming unsafe actions.
```

Strong lines:

- Valid API token does not imply valid action.
- ProofPath protects critical APIs from unsafe AI-agent actions.
- The gateway enforces intent, scope, reversibility, approval, and audit before execution.

Suggested update angle:

> Since my original submission, I built a runnable ProofPath prototype that demonstrates the defensive boundary: unsafe irreversible agent actions are blocked before reaching a protected API, while approved actions are forwarded and recorded in a hash-chained audit log.

## LTFF / EA Funds

Do not create another near-duplicate application immediately.

Use ProofPath as an update to the existing application.

Reason:

There was already confusion around two similar EA Funds submissions. A short update is safer than a new duplicate.

Recommended framing:

```text
ProofPath is a concrete prototype demonstrating the action-level oversight boundary described in the existing AI safety tooling application.
```

Attach:

- repo link;
- dangerous action demo;
- real-model-agent demo;
- community experiments;
- audit trail.

## Rust Foundation / Rust Innovation Lab

The Rust Foundation response indicated that the project was too early and should return with traction.

ProofPath helps build that traction:

- Rust verifier;
- Rust/Axum gateway;
- community experiment issues;
- external feedback path;
- future integration work.

Recommended action:

Do not re-approach immediately.

First gather:

- 3-5 external feedback issues;
- 1-2 external integrations;
- evidence of usage or stars;
- CI passing consistently;
- short technical roadmap.

Then write a concise follow-up.

## Google.org Impact Challenge: AI for Science

ProofPath may support the broader LTP/CML proposal as an applied demonstration of action-level oversight.

Use it as evidence of execution velocity, not as a replacement for the submitted research scope.

Recommended phrase:

> ProofPath is a smaller reference implementation created after submission to demonstrate the same oversight principle in a runnable AI-agent action setting.

## Foresight AI Nodes / OpenAI Safety Fellowship / CIP

ProofPath strengthens the personal research profile:

- shows rapid prototype capability;
- shows concrete AI-agent safety boundary;
- shows community experiment design;
- shows practical QA/security instincts;
- makes the research direction easier to understand.

Use ProofPath in follow-ups or interviews as:

```text
A minimal lab environment for studying accountable AI-agent actions.
```

## Recommended immediate actions

1. Keep ProofPath independent but explain its relationship to PythiaLabs clearly.
2. Send short update emails to NLnet, LTFF/EA Funds, and OpenAI Cybersecurity Grant.
3. Do not spam every funder.
4. Gather community feedback before approaching Rust Foundation again.
5. Use ProofPath as the public demo layer for future Schmidt / AI safety conversations.

## One-sentence positioning

ProofPath is the runnable protocol/gateway layer that turns the PythiaLabs evidence-gate idea into a concrete AI-agent action boundary.
