# Audit Log Verification

ProofPath gateway demos write JSONL audit entries so reviewers can inspect what happened at the action boundary.

This note explains the current local demo audit format, how the hash chain works, and what the current checker can and cannot prove.

## Current audit record shape

A gateway audit record currently includes fields like:

```json
{
  "audit_id": "...",
  "previous_hash": "GENESIS",
  "intent_id": "intent_inspect_account_001",
  "causal_parent": "decision_user_requested_inspection",
  "scope": "account.delete",
  "decision": "BLOCK",
  "reason": "IRREVERSIBLE_ACTION_REQUIRES_APPROVAL",
  "forwarded": false,
  "upstream_url": "http://127.0.0.1:9797/protected",
  "upstream_status": null,
  "hash": "sha256:..."
}
```

The key fields for integrity inspection are:

| Field | Meaning |
| --- | --- |
| `audit_id` | Unique identifier for this audit record. |
| `previous_hash` | `GENESIS` for the first record, otherwise the previous record's `hash`. |
| `decision` | ProofPath verifier decision, such as `ACCEPT`, `REJECT`, or `BLOCK`. |
| `reason` | Structured reason code when the action is rejected or blocked. |
| `forwarded` | Whether the gateway forwarded the request upstream. |
| `upstream_status` | HTTP status returned by the upstream service when forwarded. |
| `hash` | SHA-256 digest over the record payload excluding the `hash` field. |

## Hash-chain semantics

For the first record:

```text
previous_hash = GENESIS
hash = sha256(record_without_hash)
```

For each following record:

```text
previous_hash = previous_record.hash
hash = sha256(record_without_hash)
```

This creates a local hash-linked chain:

```text
GENESIS
  -> record_1.hash
  -> record_2.hash
  -> record_3.hash
```

If an old record is modified, its recomputed hash changes. If a record is removed or reordered, a later `previous_hash` no longer points to the prior record's `hash`.

## Verify a local audit log

After running a demo that writes `proofpath-audit.jsonl`, run:

```bash
python3 scripts/verify_audit_log.py proofpath-audit.jsonl
```

Expected result for a valid chain:

```text
ProofPath audit log verification passed: 2 records
first_previous_hash=GENESIS
last_hash=sha256:...
```

A broken chain exits non-zero and reports the failing record, for example:

```text
ProofPath audit log verification failed:
- record 2: previous_hash expected 'sha256:...', got 'sha256:tampered'
```

## Example valid chain

```jsonl
{"audit_id":"a1","previous_hash":"GENESIS","intent_id":"intent_1","causal_parent":"decision_1","scope":"profile.update","decision":"ACCEPT","reason":null,"forwarded":true,"upstream_url":"http://127.0.0.1:9797/protected","upstream_status":200,"hash":"sha256:..."}
{"audit_id":"a2","previous_hash":"sha256:...","intent_id":"intent_2","causal_parent":"decision_2","scope":"account.delete","decision":"BLOCK","reason":"IRREVERSIBLE_ACTION_REQUIRES_APPROVAL","forwarded":false,"upstream_url":"http://127.0.0.1:9797/protected","upstream_status":null,"hash":"sha256:..."}
```

The second record is linked to the first because:

```text
record_2.previous_hash == record_1.hash
```

## Example broken chain

```jsonl
{"audit_id":"a1","previous_hash":"GENESIS","intent_id":"intent_1","causal_parent":"decision_1","scope":"profile.update","decision":"ACCEPT","reason":null,"forwarded":true,"upstream_url":"http://127.0.0.1:9797/protected","upstream_status":200,"hash":"sha256:..."}
{"audit_id":"a2","previous_hash":"sha256:wrong","intent_id":"intent_2","causal_parent":"decision_2","scope":"account.delete","decision":"BLOCK","reason":"IRREVERSIBLE_ACTION_REQUIRES_APPROVAL","forwarded":false,"upstream_url":"http://127.0.0.1:9797/protected","upstream_status":null,"hash":"sha256:..."}
```

This is broken because:

```text
record_2.previous_hash != record_1.hash
```

## What this proves

The local checker can verify that:

1. the JSONL file is parseable;
2. the first record starts from `GENESIS`;
3. every later record points to the previous record's `hash`;
4. each record's `hash` matches the current record payload excluding the `hash` field.

## What this does not prove

The current JSONL hash chain is an inspectable local integrity mechanism. It does not replace:

- secure append-only storage;
- digital signatures;
- external timestamping;
- key management;
- trusted execution environments;
- immutable object storage;
- regulatory-grade audit infrastructure.

A local hash chain can detect many accidental or naive modifications. It is not, by itself, a tamper-proof storage system if an attacker can rewrite the entire file and recompute all hashes.

## Reviewer phrase

```text
ProofPath does not only log decisions; it makes the local audit trail structurally inspectable.
```
