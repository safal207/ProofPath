# ProofPath Reviewer Identity & Separation of Duties v0.1

Trusted Workflow Governance proves that a workflow version is allowed. It does not
prove that the named reviewers are real, active, distinct from the author, or
independent from one another.

This layer adds a second human-governance boundary before Control Cloud append:

```text
workflow governance ACCEPT
        ↓
server-controlled reviewer identity registry
        ↓
exact approval bundle bound to governance decision
        ↓
identity status + evidence + role + author separation
        ↓
organization + control-cluster + payment-cluster separation
        ↓
ACCEPT / HOLD / BLOCK / CHALLENGE
        ↓
server-controlled reviewer decision
        ↓
separated ingestion
```

## Identity registry

Each reviewer record pins:

- a stable reviewer ID and GitHub login;
- an identity provider and exact identity subject;
- organization, control-cluster, and payment-cluster IDs;
- allowed roles;
- effective and expiry times;
- an identity-evidence digest;
- an explicit independence attestation;
- `authority_granted: false`.

A suspension is a separate append-oriented record. An effective suspension blocks
the reviewer even when the original reviewer record remains ACTIVE.

The reference registry uses synthetic reviewer identities. It is illustrative only.

## Approval bundle

Each approval binds:

```text
governance_decision_root
workflow
signer_sha
reviewer_id
reviewer_identity_subject
identity_evidence_digest
statement_digest
approved_at
conflict_of_interest_declared
```

The evaluator rejects duplicate reviewer approvals, REJECT votes, stale or
future-dated approvals, mismatched identity evidence, and approvals that do not bind
the exact workflow-governance decision.

## Separation policy

The server-controlled policy can require:

- a minimum approval count;
- a minimum number of distinct organizations;
- an exact reviewer role;
- allowed identity providers;
- no reviewer from the author's organization;
- distinct control clusters;
- distinct payment clusters;
- bounded approval age.

Decision semantics:

- `ACCEPT`: all identity and separation gates pass;
- `HOLD`: evidence may become sufficient later, such as missing quorum or expired identity window;
- `BLOCK`: a concrete conflict exists, such as self-approval, suspension, shared control, or evidence mismatch;
- `CHALLENGE`: identity mapping is ambiguous and requires resolution.

## Separation-gated ingestion

`control-cloud/ingestion/separated_ingest.py` requires all four boundaries:

```text
authenticated tenant request
provenance_cryptographically_verified_by_api: true
governance_trust_verified_by_api: true
reviewer_identity_verified_by_api: true
separation_of_duties_verified_by_api: true
```

The server derives the only accepted reviewer decision path from the exact workflow
governance decision root:

```text
{separation_dir}/{governance_decision_root_without_sha256_prefix}.json
```

The client cannot provide a trusted decision path or set a reviewer-verification
boolean. Missing, symlinked, escaped, stale, non-ACCEPT, or mismatched decisions fail
before append.

## Identity change proposals

`check-identity-change` emits read-only `PROPOSE_SUSPEND` when an observed reviewer
identity differs from the registry in any of these fields:

- identity subject;
- organization;
- control cluster;
- payment cluster;
- identity-evidence digest.

It does not edit the registry, revoke credentials, remove a GitHub reviewer, change
branch protection, or perform a repository write.

## Honest boundaries

This reference implementation does not prove that the named reviewers are independent humans.
An `independence_attested: true` field is a machine-readable claim, not external proof.

It does not perform KYC, KYB, sanctions screening, or beneficial-owner verification.
It does not verify employment, corporate control, payment-account ownership, device
ownership, or whether two accounts are secretly controlled by one person.

The reference conformance workflow uses synthetic reviewer identities from synthetic
organizations. It demonstrates enforcement logic only.

Every separated receipt remains:

```text
financial_status: RECORDED_NOT_PAYABLE
payments_executed: false
insurance_provided: false
deployment_performed: false
authority_granted: false
repository_write_performed: false
```

Production still requires verified identity providers, authenticated approval
statements, immutable registry administration, beneficial-owner and control-cluster
evidence, payment-account verification, separation of duties for registry changes,
monitoring, backups, incident response, privacy controls, and independent security
review.
