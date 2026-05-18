# Changelog

## Unreleased

### Fixed

- Gateway audit append no longer panics on `serde_json` errors; the error is
  propagated as `io::Error` (`crates/proofpath-gateway/src/main.rs`).
- Verifier `block()` now uses `!is_blank(...)` for `causal_valid` /
  `scope_valid` so future call sites without pre-validation stay correct.

### Performance

- `RequestContext::header` skips the lowercase allocation when the lookup
  name is already lowercase (true for all `HEADER_*` constants).
- `RequestContext::with_header` lowercases in place instead of allocating a
  second `String`.
- `Reversibility::parse` uses `eq_ignore_ascii_case` instead of allocating a
  lowercased copy.
- `audit::compute_audit_hash` writes canonical JSON into a single `String`
  buffer instead of building intermediate `Vec<String>` and concatenating
  via `format!`. Hash output is byte-identical (verified by the existing
  conformance test).

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
