# Contributing to ProofPath

Thank you for your interest in ProofPath.

ProofPath is an early-stage open-source project exploring verifiable intent and causal authorization for HTTPS APIs and AI-agent actions.

## What we are building

We are building a small, practical layer that helps systems answer:

- Why did this action happen?
- Which intent authorized it?
- Which prior decision is its causal parent?
- Is the action reversible, compensatable, or irreversible?
- Can the action be audited after the fact?

## Good first contribution areas

- Improve examples in the HTTP profile.
- Add valid and invalid conformance fixtures.
- Expand the threat model.
- Implement simple Rust parser types.
- Add CLI output examples.
- Improve documentation clarity.

## Design rules

1. Do not replace HTTPS.
2. Do not replace OAuth/OIDC.
3. Keep v0.1 minimal.
4. Prefer explicit reason codes over vague errors.
5. Make every critical action auditable.
6. Treat irreversible actions as special.

## Commit style

Use short, clear commit messages:

```text
Add ProofPath HTTP profile
Add initial threat model
Implement header parser
Add invalid missing-intent fixture
```

## Pull requests

A useful PR should include:

- What changed.
- Why it matters.
- Any open questions.
- Tests or examples when applicable.

## Community tone

ProofPath discusses security and accountability. Keep discussions precise, respectful, and evidence-driven.
