# P3 Verification Addendum

This addendum extends the clean-checkout reviewer path with two command-level checks:

1. conformance fixture execution;
2. audit JSONL hash-chain verification.

## 1. Run conformance fixtures

From the repository root:

```bash
python3 scripts/check_conformance_fixtures.py conformance/manifest.json
```

Expected result:

```text
PASS valid/reversible-accept.json -> ACCEPT
PASS valid/irreversible-with-approval-accept.json -> ACCEPT
PASS invalid/missing-intent-reject.json -> REJECT MISSING_INTENT
PASS invalid/missing-causal-parent-reject.json -> REJECT MISSING_CAUSAL_PARENT
PASS invalid/missing-scope-reject.json -> REJECT MISSING_SCOPE
PASS invalid/missing-reversibility-reject.json -> REJECT MISSING_REVERSIBILITY
PASS invalid/invalid-reversibility-reject.json -> REJECT INVALID_REVERSIBILITY
PASS invalid/irreversible-without-approval-block.json -> BLOCK IRREVERSIBLE_ACTION_REQUIRES_APPROVAL

ProofPath conformance fixtures passed: 8
```

Meaning:

```text
The JSON fixture contract matches the current minimal verifier behavior.
```

## 2. Verify an audit log after running a demo

After a demo writes `proofpath-audit.jsonl`, run:

```bash
python3 scripts/verify_audit_log.py proofpath-audit.jsonl
```

Expected result for the two-record dangerous-action demo:

```text
ProofPath audit log verification passed: 2 records
first_previous_hash=GENESIS
last_hash=sha256:...
```

Expected result for the three-record CI/CD demo:

```text
ProofPath audit log verification passed: 3 records
first_previous_hash=GENESIS
last_hash=sha256:...
```

## What this adds to the reviewer path

The original runbook shows manual reproduction:

```text
clone -> run gateway -> run demo -> inspect audit log
```

This addendum adds executable verification:

```text
conformance manifest -> expected verifier decisions
proofpath-audit.jsonl -> hash-chain verification
```

## Claim boundary

This verifies local fixture behavior and local JSONL hash-chain structure.

It does not prove production security, regulatory compliance, secure append-only storage, external timestamping, key management, or complete unsafe-action coverage.
