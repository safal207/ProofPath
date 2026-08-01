# ProofPath Control Cloud Authenticated Ingestion v0.1

This directory contains a dependency-free reference service for accepting
tenant-scoped ProofPath Assured Action records and turning them into the
append-only input used by Control Cloud.

It is a **reference service, not a hosted production SaaS**.

```text
Deploy Guard certificate
+ commercial metadata
+ operator assignments
        ↓ exact request bytes
tenant HMAC authentication
        ↓
idempotency + nonce + timestamp checks
        ↓
append-only chained event
        ↓
ingestion receipt
        ↓
Control Cloud dataset export
        ↓
deterministic dashboard snapshot
```

## HTTP endpoint

```text
POST /v1/tenants/{tenant_id}/assured-actions
```

Required headers:

```text
X-ProofPath-Key-Id
X-ProofPath-Timestamp
X-ProofPath-Nonce
X-ProofPath-Idempotency-Key
X-ProofPath-Content-SHA256
X-ProofPath-Signature
```

The signature is HMAC-SHA256 over:

```text
proofpath.control-cloud.ingest-signing.v0.1
POST
/v1/tenants/{tenant_id}/assured-actions
{tenant_id}
{key_id}
{timestamp}
{nonce}
{idempotency_key}
{sha256_of_exact_body_bytes}
```

Secrets are not stored in the tenant registry. Each key refers to a
`secret_env` environment variable. Production deployment should resolve that
variable from a dedicated secret manager.

## Authentication properties

The reference implementation checks:

- tenant and key are active;
- key belongs to the tenant;
- exact request body SHA-256;
- constant-time HMAC comparison;
- signed timestamp within the configured clock-skew window;
- request `submitted_at` bound to the signed timestamp;
- nonce replay;
- idempotency conflicts;
- repository belongs to one of the tenant's configured prefixes;
- paths remain inside the configured store root.

An identical retry with the same idempotency key and exact body returns the
original receipt and does not append another event.

Using the same idempotency key with different content is rejected. Reusing a
nonce under a different idempotency key is also rejected.

## Event store

Each tenant has:

```text
{store}/tenants/{tenant_id}/events.jsonl
{store}/tenants/{tenant_id}/.ingest.lock
```

Events are appended while an exclusive file lock is held, flushed with
`fsync`, and connected through `previous_event_root → event_root`. The full
chain is revalidated before export or another append.

This is append-only event semantics for the reference implementation. A
production Control Cloud should use a transactional database or immutable
object/event store with backups, retention controls, concurrency tests,
monitoring, and disaster recovery.

## Commands

Create authentication headers for exact request bytes:

```bash
export PROOFPATH_INGEST_DEMO_SECRET='replace-with-at-least-32-bytes'

python3 control-cloud/ingestion/ingest.py sign \
  --body examples/control-cloud/ingestion/request.accept.json \
  --tenant acme-demo \
  --key-id demo-key-1 \
  --secret-env PROOFPATH_INGEST_DEMO_SECRET \
  --timestamp 2026-08-02T00:00:00Z \
  --nonce nonce-demo-00000001 \
  --idempotency-key idem-demo-00000001 \
  --headers-out /tmp/headers.json
```

Ingest once:

```bash
python3 control-cloud/ingestion/ingest.py ingest \
  --body examples/control-cloud/ingestion/request.accept.json \
  --headers /tmp/headers.json \
  --registry examples/control-cloud/ingestion/tenant-registry.json \
  --store /tmp/proofpath-control-cloud \
  --tenant acme-demo \
  --now 2026-08-02T00:00:00Z \
  --receipt /tmp/receipt.json
```

Export accepted records to the existing Control Cloud dataset profile:

```bash
python3 control-cloud/ingestion/ingest.py export \
  --store /tmp/proofpath-control-cloud \
  --tenant acme-demo \
  --generated-at 2026-08-02T00:05:00Z \
  --output /tmp/assured-actions.json
```

Run the local reference HTTP service:

```bash
python3 control-cloud/ingestion/ingest.py serve \
  --registry examples/control-cloud/ingestion/tenant-registry.json \
  --store /tmp/proofpath-control-cloud
```

The server binds to `127.0.0.1` by default. A production deployment needs TLS
termination, rate limiting, tenant quotas, observability, key rotation,
revocation, a secret manager, durable transactional storage, availability
controls, and an independent security review.

## Honest assurance boundary

The ingestion API authenticates the tenant request and validates the supplied
certificate's internal boundary. It:

- does not independently verify Sigstore or GitHub attestation cryptography;
- does not re-run Deploy Guard;
- does not determine that a reviewer owns a business role;
- does not execute a deployment;
- does not grant authority;
- does not send a payment;
- does not create an insurance policy;
- does not claim an external quorum.

A provenance result may be recorded as `EXTERNAL_RESULT_BOUND`, but the API
only binds the result fields to the request. It still emits:

```text
provenance_cryptographically_verified_by_api: false
financial_status: RECORDED_NOT_PAYABLE
payments_executed: false
insurance_provided: false
deployment_performed: false
authority_granted: false
```

Real cryptographic verification should be performed by a separately pinned
verifier, with its output admitted under a dedicated verification contract.

## Production path

```text
v0.1 reference HMAC ingress
        ↓
managed tenant/key service
        ↓
database-backed idempotency and event ledger
        ↓
pinned Sigstore admission verifier
        ↓
tenant-authenticated query API
        ↓
billing provider in simulation/shadow mode
        ↓
reviewed payout orchestration
```

Payment and coverage integrations remain intentionally outside this slice.
