# ProofPath Trusted Workflow Governance v0.1

Sigstore Admission proves that exact certificate bytes were signed under a pinned
GitHub workflow identity. That is necessary but not sufficient: a correctly signed
artifact can still come from a workflow version that is expired, revoked, changed
without review, or allowed only for a different event or ref.

This layer adds a server-controlled governance decision before Control Cloud append:

```text
cryptographically verified admission result
        ↓
server-controlled governance registry
        ↓
workflow + signer SHA + file digest + event/ref + time + reviewers + revocations
        ↓
ACCEPT / HOLD / BLOCK / CHALLENGE
        ↓
server-controlled decision directory
        ↓
governed ingestion
```

## Trust record

An ACTIVE record pins all of the following:

- repository and owner scope;
- exact workflow identity;
- exact signer commit SHA;
- SHA-256 digest of the workflow file bytes;
- allowed GitHub event types;
- allowed ref prefixes;
- effective and expiry timestamps;
- reviewer roster, approvals, and required quorum;
- an external review ticket identifier;
- `authority_granted: false`.

The reference registry in `examples/control-cloud/trusted-workflow-governance-registry.json`
is illustrative only. Its reviewer names, approvals, SHA, digest, and review ticket do
**not** represent independent production approval.

## Decision semantics

`verify_workflow_governance.py evaluate` returns one machine-readable decision:

- `ACCEPT`: one exact ACTIVE record matches and all gates pass;
- `HOLD`: evidence may become sufficient later, such as missing quorum or inactive window;
- `BLOCK`: a concrete prohibition exists, such as revocation, mutation, wrong event, or unpinned signer SHA;
- `CHALLENGE`: the registry is ambiguous and requires human resolution.

Example:

```bash
python3 control-cloud/governance/verify_workflow_governance.py evaluate \
  --admission-result admission-result.json \
  --registry trusted-workflow-registry.json \
  --observed-at 2026-08-02T00:01:00Z \
  --workflow-file-digest sha256:... \
  --event-type pull_request \
  --ref refs/pull/214/merge \
  --output governance-decision.json
```

An ACCEPT decision includes a domain-separated `decision_root` and binds:

```text
admission_result_root
subject_digest
repository
signer_repository
signer_workflow
signer_sha
workflow_file_digest
event_type
ref
trust_record_id
trust_record_root
```

## Revocation records

Revocations are append-oriented records separate from trust records. A revocation
that is effective at evaluation time forces `BLOCK`, even when the original record
still says ACTIVE.

`check-change` produces a read-only revocation proposal when:

- the trusted workflow path appears in the changed-path set;
- the observed signer SHA differs from the pinned SHA;
- the observed workflow file digest differs from the pinned digest;
- the registry has no unique ACTIVE record for that workflow.

```bash
python3 control-cloud/governance/verify_workflow_governance.py check-change \
  --registry trusted-workflow-registry.json \
  --workflow OWNER/REPO/.github/workflows/trusted.yml \
  --observed-signer-sha COMMIT_SHA \
  --observed-file-digest sha256:... \
  --changed-paths changed-paths.json \
  --observed-at 2026-08-02T00:02:00Z \
  --output revocation-proposal.json
```

The command does not write to GitHub, edit the registry, revoke credentials, change
branch protection, or grant authority. It only emits `PROPOSE_REVOKE` or `NO_CHANGE`.
A production control plane must require authenticated reviewers and append an actual
revocation record through a separately authorized process.

## Governance-gated ingestion

`governed_ingest.py` is the high-assurance entrypoint layered over the authenticated
and Sigstore-admitted ingestion runtimes.

The server derives the only accepted governance decision path from the exact
admission result root:

```text
{governance_dir}/{admission_result_root_without_sha256_prefix}.json
```

The client cannot provide a decision path or set a trusted flag. Before any append,
the server requires:

```text
provenance_cryptographically_verified_by_api: true
governance_trust_verified_by_api: true
```

It also re-binds the governance decision to the admission result, rejects symlinks
and path escapes, and rejects decisions that are future-dated or older than fifteen
minutes.

```bash
python3 control-cloud/ingestion/governed_ingest.py \
  --body ingest-request.json \
  --headers authenticated-headers.json \
  --registry tenant-registry.json \
  --store ./control-cloud-store \
  --admissions-dir ./trusted-admissions \
  --governance-dir ./trusted-governance-decisions \
  --tenant proofpath-demo \
  --now 2026-08-02T00:02:00Z \
  --receipt governed-receipt.json
```

## Honest boundaries

This layer does **not** prove that named reviewers are independent humans, that their
accounts were uncompromised, or that an external organization approved the workflow.
The reference conformance run uses synthetic reviewer identities and an honest
reference ACTIVE record.

It also does not:

- alter GitHub settings or branch protection;
- perform repository writes from the runtime path;
- revoke a workflow automatically;
- re-run the workflow's business logic;
- prove model reasoning;
- deploy software;
- execute payments;
- provide insurance;
- grant IAM, deployment, repository, or financial authority.

Every governed receipt remains:

```text
financial_status: RECORDED_NOT_PAYABLE
payments_executed: false
insurance_provided: false
deployment_performed: false
authority_granted: false
repository_write_performed: false
```

Production still requires authenticated governance administration, immutable registry
storage, reviewer identity verification, separation of duties, approval freshness,
key and account lifecycle management, monitoring, backups, incident response, and
independent security review.
