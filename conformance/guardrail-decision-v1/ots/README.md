# Bitcoin OpenTimestamps temporal-anchor vectors

This corpus tests the bounded adapter that turns official `ots verify` output
into a ProofPath temporal-anchor result.

It does **not** implement OpenTimestamps cryptography itself. Live verification
is delegated to the official OpenTimestamps client. The deterministic corpus
tests the fail-closed classification boundary around that client.

## Run the deterministic corpus

```bash
python3 scripts/check_ots_anchor_vectors.py \
  conformance/guardrail-decision-v1/ots/manifest.json
```

Expected result: eight passing vectors.

## Live verification

Install the official client and provide access to a Bitcoin Core node:

```bash
pip install opentimestamps-client

python3 scripts/verify_ots_anchor.py \
  decision.json \
  decision.json.ots \
  --bitcoin-node http://USER:PASS@127.0.0.1:8332 \
  --output temporal-anchor-result.json
```

The verifier copies the exact target and proof into a temporary directory as
`payload` and `payload.ots`, then invokes `ots verify payload.ots`. This prevents
the proof from being accidentally checked against a different neighboring file.

## Result states

| State | Meaning |
| --- | --- |
| `TEMPORALLY_ANCHORED` | The official client exited successfully and reported exactly one Bitcoin block attestation. |
| `PENDING` | The proof is waiting for Bitcoin confirmation or calendar completion. |
| `INVALID` | The proof/output is conflicting, malformed, or does not contain a Bitcoin attestation. |
| `UNAVAILABLE` | The client/node/runtime was unavailable, so no temporal claim is made. |

A `temporal_anchor_ref` URL alone never reaches `TEMPORALLY_ANCHORED`.
