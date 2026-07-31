# PoCI cross-repository federation v0.1

Status: executable experimental profile  
Profile: `proofpath.poci.cross-repo-federation.v0.1`

## Purpose

A three-runner quorum inside ProofPath proves process and runner separation. An
Ibex consumer receipt proves that a second repository can verify the producer
attestation and independently reproduce the six-graph transition space. The
federation profile closes the loop by verifying both keyless identities and
binding their common consensus into one federation root.

```text
ProofPath three-runner quorum
        ↓ ProofPath Sigstore identity
Ibex external recomputation
        ↓ Ibex Sigstore identity
ProofPath federation verifier
        ↓
two-domain federation root
```

## Required domains

Version 0.1 requires exactly two distinct repository/workflow domains:

1. **Producer domain** — the attested ProofPath quorum report.
2. **External-consumer domain** — the attested Ibex consumer receipt.

Different jobs inside one workflow do not count as different federation
domains. The repository and signer-workflow identities must both differ.

## Verified bindings

The federation verifier checks:

- exact SHA-256 bytes of the producer report and consumer receipt;
- successful keyless attestation verification for both subjects;
- pinned repository, signer workflow, source SHA, signer SHA, GitHub OIDC issuer,
  and GitHub-hosted runner boundary;
- accepted producer quorum with three verified witness attestations;
- accepted external consumer receipt;
- the external receipt's own domain-separated integrity root;
- the external receipt's binding back to the exact ProofPath producer report;
- equality of round, consensus root, source digest, graph set, envelope,
  six graph roots, transition-cell root, and multi-graph root.

## Decision semantics

```text
CHALLENGE > BLOCK > ACCEPT
```

- `ACCEPT` — both domains are attested and agree exactly.
- `BLOCK` — a required domain, attestation, identity, profile, or verification
  flag is absent or invalid.
- `CHALLENGE` — committed bytes, roots, or consensus fields contradict each
  other or the pinned policy.

Representative reason codes:

- `FEDERATION_POLICY_INVALID`
- `FEDERATION_DOMAIN_NOT_DISTINCT`
- `FEDERATION_PRODUCER_ATTESTATION_MISSING`
- `FEDERATION_CONSUMER_ATTESTATION_MISSING`
- `FEDERATION_PRODUCER_SUBJECT_MISMATCH`
- `FEDERATION_CONSUMER_SUBJECT_MISMATCH`
- `FEDERATION_PRODUCER_REPORT_INVALID`
- `FEDERATION_CONSUMER_RECEIPT_INVALID`
- `FEDERATION_CONSUMER_RECEIPT_ROOT_MISMATCH`
- `FEDERATION_PRODUCER_CONSENSUS_MISMATCH`
- `FEDERATION_CONSUMER_CONSENSUS_MISMATCH`
- `FEDERATION_CROSS_DOMAIN_MISMATCH`

## Canonical federation root

The complete federation report is copied, `federation_root` is set to `null`,
canonical JSON is encoded, and SHA-256 is computed with domain prefix:

```text
proofpath:poci:cross-repo-federation:v0.1:root\n
```

The root includes digests of the actual `gh attestation verify` result objects,
so it commits to the two provenance-verification executions as well as their
subjects.

## Mutation coverage

The focused corpus covers:

- producer subject substitution;
- external-consumer subject substitution;
- missing producer or consumer attestation;
- same-repository pseudo-federation;
- graph-root substitution;
- external receipt-root tampering;
- external workflow substitution;
- deterministic federation roots.

## Reviewer command

After obtaining both `gh attestation verify --format json` result files:

```bash
python3 scripts/verify_poci_cross_repo_federation.py \
  examples/poci-witness/federation/policy.json \
  --producer-report \
    examples/poci-witness/federation/proofpath-attested-quorum-report.json \
  --consumer-receipt \
    examples/poci-witness/federation/ibex-external-consumer-receipt.json \
  --producer-attestation-result producer-attestation.json \
  --consumer-attestation-result consumer-attestation.json \
  --pretty
```

## Honest boundary

ProofPath and Ibex now provide different repositories, commits, workflows,
runners, artifacts, and Sigstore identities. Both repositories are currently
controlled by the same GitHub account owner. This proves repository/workflow
federation and independent recomputation, not independent organizational
governance. The federation proves committed evidence consistency, not objective
real-world truth.
