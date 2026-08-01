# ProofPath Sigstore Admission Verifier v0.1

This layer closes the gap between a client saying “my certificate has provenance”
and Control Cloud independently verifying that provenance before admission.

```text
Assured Action certificate bytes
        ↓
gh attestation verify
        ↓
GitHub/Sigstore certificate and transparency checks
        ↓
strict admission result
        ↓
server-side result directory
        ↓
admission-gated tenant ingestion
```

## What is cryptographically verified

The verifier executes `gh attestation verify` as an argument vector, never through a
shell. The policy pins:

- the repository associated with the attestation;
- the exact signer workflow identity, which also binds its repository;
- the source repository commit digest;
- the signer workflow commit digest;
- the exact GitHub Actions OIDC issuer;
- SLSA provenance v1;
- denial of self-hosted runners;
- presence of at least one verified transparency-log or timestamp-authority entry.

The verified subject is the exact certificate file. Its SHA-256 digest is different
from the canonical semantic digest of the parsed certificate; the result records both.

GitHub documents that the certificate identity and verified timestamps are the parts
of `gh attestation verify --format json` that originate from cryptographically protected
material. Workflow-controlled predicate fields are therefore not used as independent
authority.

## Verification command

```bash
python3 control-cloud/admission/verify_sigstore.py verify \
  --subject clearance-certificate.json \
  --policy admission-policy.json \
  --verified-at 2026-08-02T00:00:00Z \
  --output admission-result.json
```

The runtime invokes the equivalent of:

```bash
gh attestation verify clearance-certificate.json \
  --repo OWNER/REPOSITORY \
  --signer-workflow OWNER/REPOSITORY/.github/workflows/TRUSTED.yml \
  --source-digest SOURCE_SHA \
  --signer-digest SIGNER_SHA \
  --cert-oidc-issuer https://token.actions.githubusercontent.com \
  --predicate-type https://slsa.dev/provenance/v1 \
  --deny-self-hosted-runners \
  --format json
```

A successful result has:

```text
decision: ACCEPT
verified: true
verification_mode: GH_ATTESTATION_VERIFY
runner_environment: github-hosted
github_attestation_verified: true
transparency_timestamp_verified: true
authority_granted: false
deployment_performed: false
payments_executed: false
```

The result itself has a domain-separated `result_root`.

## Admission-gated ingestion

`admitted_ingest.py` is a separate reference API runtime. It does not trust an
admission result embedded by the client.

The signed tenant request contains an existing `EXTERNAL_RESULT_BOUND`
`provenance_binding`. The server derives a result filename solely from the bound
subject digest:

```text
{admissions_dir}/{subject_sha256_hex}.json
```

The result file must already exist in the server-controlled admission directory.
The runtime validates the result root and binds all of the following to the signed
request certificate:

- exact subject digest;
- canonical certificate digest;
- clearance root;
- repository;
- source commit SHA;
- deploy artifact digest;
- verifier identity;
- verification time;
- GitHub-hosted runner policy;
- exact GitHub OIDC issuer;
- successful attestation and transparency verification.

Only then can the receipt contain:

```text
provenance_cryptographically_verified_by_api: true
```

## HTTP service

```bash
python3 control-cloud/ingestion/admitted_ingest.py serve \
  --registry tenant-registry.json \
  --store ./control-cloud-store \
  --admissions-dir ./trusted-admissions \
  --host 127.0.0.1 \
  --port 8080
```

Endpoint:

```text
POST /v1/tenants/{tenant_id}/assured-actions
```

Authentication remains the HMAC request contract from ingestion v0.1. Admission-gated
events are stored separately:

```text
{store}/tenants/{tenant_id}/admitted-events.jsonl
{store}/tenants/{tenant_id}/.admitted-ingest.lock
```

The store uses exclusive locking, append, `fsync`, `O_NOFOLLOW` where available,
symlink rejection, chained event roots, idempotency, and nonce replay protection.

## Honest boundaries

This layer verifies provenance of the supplied certificate. It does not grant authority, and it does **not**:

- re-run Deploy Guard;
- prove the model’s internal reasoning;
- grant deployment, financial, IAM, or repository authority;
- perform the deployment;
- execute a payment;
- provide insurance or financial coverage;
- prove beneficial-owner or organizational independence;
- guarantee that a compromised trusted workflow produced semantically correct evidence.

Every admitted receipt remains:

```text
financial_status: RECORDED_NOT_PAYABLE
payments_executed: false
insurance_provided: false
deployment_performed: false
authority_granted: false
```

Production still requires TLS termination, authentication rate limits, durable
transactional storage, managed secrets, key rotation, admission-result retention,
monitoring, backups, tenant administration, workflow governance, and security review.
