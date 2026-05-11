# PR: docs: improve ProofPath reviewer positioning

## What changed

- Updated `README.md` with a reviewer-facing 60-second summary.
- Added `docs/reviewer-summary.md`.
- Added `docs/grant-updates/security-grant-revision-proofpath-update.md`.

## Why it matters

ProofPath is being used as a public implementation artifact in grant-review and cybersecurity-review contexts. The repository needs to communicate the core security value quickly to reviewers, cybersecurity researchers, and open-source contributors.

The new documentation emphasizes:

- ProofPath as a defensive pre-execution gateway;
- the distinction between valid credentials and valid actions;
- the fact that ProofPath complements rather than replaces HTTPS/OAuth/IAM/API-key security;
- the current runnable implementation;
- current limitations and near-term roadmap.

## How to review

1. Open `README.md` and check whether the project is understandable within 60 seconds.
2. Read `docs/reviewer-summary.md` for a 1–2 page reviewer-facing overview.
3. Read `docs/grant-updates/security-grant-revision-proofpath-update.md` for the revised grant-submission record.
4. Verify that there are no funder endorsement claims and no claim that ProofPath replaces HTTPS.

## Test / CI status

Documentation-only change.

Recommended checks:

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
```

Report the actual CI status honestly after the PR runs.
