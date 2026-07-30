# PoCI Witness Contract Example

This directory contains the first schema-valid Action Proof Envelope for the `proofpath.poci.v0.1` profile.

Files:

- `action-proof-envelope.valid.json` — bounded compute-purchase example expected to verify as `ACCEPT`.
- `fixtures/` — external manifest plus control and adversarial envelopes.
- `../../schemas/action-proof-envelope.v0.1.schema.json` — structural contract.
- `../../docs/POCI_SPEC_V0_1.md` — semantic contract.
- `../../docs/POCI_CANONICALIZATION_V0_1.md` — deterministic hashing profile.
- `../../scripts/verify_poci.py` — dependency-free offline reference verifier.

The example deliberately uses placeholder SHA-256 values and `envelope_root: null`. A verifier MUST treat `null` as “root not asserted yet,” not as a successfully verified digest.

## Verify one envelope

From the repository root:

```bash
python3 scripts/verify_poci.py examples/poci-witness/fixtures/valid-action.accept.json --pretty
```

`ACCEPT` exits with status `0`. `HOLD`, `BLOCK`, and `CHALLENGE` use distinct non-zero exit codes. Add `--allow-non-accept` when inspecting an expected negative fixture interactively.

The verifier uses `created_at` as the deterministic evaluation time unless `--at YYYY-MM-DDTHH:MM:SSZ` is supplied. It recomputes the verdict and does not trust the envelope's embedded `verification` object.

## Verify the complete fixture corpus

```bash
python3 scripts/verify_poci.py examples/poci-witness/fixtures/manifest.json --manifest --pretty
```

The command passes only when all 12 fixture decisions and primary reason codes match the external manifest.

## Run conformance tests

```bash
python3 -m unittest discover -s tests -p 'test_poci*.py' -v
```

The suite covers fixture outcomes, key-order invariance, byte-stable output, duplicate-key rejection, envelope-root mismatch, embedded-verdict tampering, and 20 security mutations that must never degrade to `ACCEPT`.

## Optional full JSON Schema check

With Python and `jsonschema` installed:

```bash
python3 - <<'PY'
import json
from jsonschema import Draft202012Validator, FormatChecker

schema = json.load(open('schemas/action-proof-envelope.v0.1.schema.json'))
envelope = json.load(open('examples/poci-witness/action-proof-envelope.valid.json'))
Draft202012Validator(schema, format_checker=FormatChecker()).validate(envelope)
print('PASS PoCI v0.1 schema example')
PY
```

Expected output:

```text
PASS PoCI v0.1 schema example
```
