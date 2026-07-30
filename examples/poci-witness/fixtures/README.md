# PoCI v0.1 Fixture Corpus

Twelve committed control and adversarial Action Proof Envelopes for #184 and #189.

`manifest.json` is the expected-outcome contract. Verifiers MUST recompute each result and MUST NOT trust the envelope's existing `verification` section.

Ten cases are schema-valid semantic cases. `missing-authority.block.json` and `unknown-profile.block.json` intentionally exercise fail-closed preflight behavior.

Fixture-only runtime context appears under `extensions["proofpath.fixture"]` and is authoritative only to the conformance runner.
