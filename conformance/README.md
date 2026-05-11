# ProofPath Conformance Fixtures

These fixtures document the expected behavior of the current ProofPath v0.1 verifier.

They are intended for reviewers, implementers, and contributors who want to inspect the behavioral contract without reading Rust unit tests.

## Scope

The fixtures cover the minimal v0.1 action-context profile:

```text
x-proofpath-intent-id
x-proofpath-causal-parent
x-proofpath-scope
x-proofpath-reversibility
x-proofpath-human-approval optional
```

They describe expected decisions and reason codes for valid and invalid request contexts.

## Important limitations

These fixtures are not a full interoperability suite yet.

They do not currently cover:

- HTTP Message Signatures;
- W3C Trace Context propagation;
- policy configuration;
- multi-step causal chains;
- replay protection;
- external key management;
- audit-log verification.

They are a small behavioral contract for the current verifier rules.

## Fixture layout

```text
conformance/
  README.md
  manifest.json
  valid/
    reversible-accept.json
    irreversible-with-approval-accept.json
  invalid/
    missing-intent-reject.json
    missing-causal-parent-reject.json
    missing-scope-reject.json
    missing-reversibility-reject.json
    invalid-reversibility-reject.json
    irreversible-without-approval-block.json
```

## Decision expectations

| Fixture | Expected decision | Expected reason |
| --- | --- | --- |
| `valid/reversible-accept.json` | `ACCEPT` | `null` |
| `valid/irreversible-with-approval-accept.json` | `ACCEPT` | `null` |
| `invalid/missing-intent-reject.json` | `REJECT` | `MISSING_INTENT` |
| `invalid/missing-causal-parent-reject.json` | `REJECT` | `MISSING_CAUSAL_PARENT` |
| `invalid/missing-scope-reject.json` | `REJECT` | `MISSING_SCOPE` |
| `invalid/missing-reversibility-reject.json` | `REJECT` | `MISSING_REVERSIBILITY` |
| `invalid/invalid-reversibility-reject.json` | `REJECT` | `INVALID_REVERSIBILITY` |
| `invalid/irreversible-without-approval-block.json` | `BLOCK` | `IRREVERSIBLE_ACTION_REQUIRES_APPROVAL` |

## Why this matters

Demos show the story.

Conformance fixtures show the contract.

A reviewer should be able to verify that ProofPath does not only have a narrative, but also has explicit behavioral expectations for both safe and unsafe request contexts.

## Implementation note

The Rust verifier unit tests in `crates/proofpath-verifier/src/lib.rs` should remain the executable source of truth for the current implementation.

These JSON fixtures make the same behavior easier to inspect and port to other implementations.
