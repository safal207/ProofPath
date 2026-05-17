# Changelog

## v0.1 — Product Milestone

ProofPath v0.1 is the first product milestone for a CI-verifiable action-boundary evidence gate.

### Added

- Live action-boundary CI check.
- Action-boundary metrics collector.
- Action-boundary metrics assertion helper.
- Reusable composite GitHub Action in `action.yml`.
- GitHub Action quickstart documentation.
- Downstream-style adoption example.
- Fixture and CI baseline reports.
- v0.1 product milestone note.

### Validated in CI

```text
formatting
clippy
Rust tests
Compute Witness Rust CLI fixture
live action-boundary metrics
reusable ProofPath GitHub Action self-test
```

### Product phrase

```text
ProofPath turns action-boundary audit logs into CI-verifiable evidence.
```

### Claim boundary

v0.1 is not a production-security certification, formal verification result, or complete prevention guarantee.

It is the first reusable product slice:

```text
ProofPath audit JSONL
-> metrics JSON
-> expected-value assertions
-> CI pass / fail
```
