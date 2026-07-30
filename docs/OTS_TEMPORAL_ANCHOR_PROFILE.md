# OpenTimestamps temporal-anchor profile

Status: **experimental sidecar profile**  
Schema identifier: `proofpath.temporal-anchor.ots.v0.1`

## Purpose

`issued_at` inside a signed or hashed decision is tamper-evident after issuance,
but the issuer can still choose a favorable value before hashing. This sidecar
can establish an external upper bound:

> the exact subject bytes existed no later than the Bitcoin block attested by
> the verified OpenTimestamps proof.

OpenTimestamps describes this as proving that data existed prior to a point in
time. The official client validates `.ots` proofs against the Bitcoin
blockchain.

## Non-goals

A verified OTS proof does **not** prove:

- who authored or approved the subject;
- that the subject was correct, authorized, or current;
- the exact creation time;
- that the issuer did not possess different unpublished content;
- freshness of a knowledge source after the anchor.

It only anchors the exact committed bytes before a Bitcoin block time.

## Sidecar shape

```json
{
  "schema": "proofpath.temporal-anchor.ots.v0.1",
  "subject": {
    "path": "decision.json",
    "content_hash": "sha256:..."
  },
  "proof": {
    "path": "decision.json.ots",
    "media_type": "application/vnd.opentimestamps.ots",
    "content_hash": "sha256:..."
  },
  "verification": {
    "status": "TEMPORALLY_ANCHORED",
    "reason": "BITCOIN_ATTESTATION_VERIFIED",
    "bitcoin_block_height": 358391,
    "attested_before": "2015-05-28 CEST"
  },
  "temporal_precedence_proven": true,
  "verifier": {
    "binary": "/usr/local/bin/ots",
    "executed": true,
    "returncode": 0,
    "output_sha256": "sha256:..."
  }
}
```

## Promotion rule

A sidecar may set `temporal_precedence_proven: true` only when all of the
following hold:

1. the exact target bytes were supplied to the verifier;
2. the exact `.ots` proof bytes were supplied;
3. the official verifier process completed successfully;
4. the output contains exactly one Bitcoin block attestation;
5. the output contains no pending or unknown attestation;
6. the verifier result is preserved as evidence.

A URL, proof filename, claimed block height, self-declared timestamp, or exit
code by itself is insufficient.

## Runtime trust boundary

This profile delegates cryptographic validation to the installed official
OpenTimestamps client and its Bitcoin data source. The host, executable, PATH,
Bitcoin node, and captured output remain part of the trusted computing base.

A hardened deployment should additionally pin the verifier package/binary by
version or digest, record the Bitcoin node configuration class without storing
credentials, and run inside a reproducible environment.

## Pending proofs

Fresh timestamps commonly remain pending until calendar data reaches a Bitcoin
block. `PENDING` is not failure and is not proof of temporal precedence. The
proof can later be upgraded and reverified.

## GuardrailDecision integration

The base decision should carry only a frozen reference to the sidecar:

```json
{
  "temporal_anchor": {
    "profile": "proofpath.temporal-anchor.ots.v0.1",
    "result_ref": "temporal-anchor-result.json",
    "result_hash": "sha256:..."
  }
}
```

Consumers must verify the sidecar hash and require
`verification.status == "TEMPORALLY_ANCHORED"` before using the anchor for
ordering or “what was knowable at decision time.”
