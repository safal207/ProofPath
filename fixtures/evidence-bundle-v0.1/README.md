# ProofPath Evidence Bundle v0.1 Fixtures

This fixture directory defines the first reviewable contract for the ProofPath
offline evidence bundle described in issue #161.

It is intentionally small. The goal is to make the reviewer path boring and
repeatable before adding more export surface area.

## Bundle Shape

A v0.1 evidence bundle should use this layout:

```text
proofpath-evidence/
  manifest.json
  decisions.jsonl
  hash-chain.json
  verifier-result.json
  privacy-report.json
  README.md
```

## Reviewer Flow

The reviewer flow should stay linear:

```text
export bundle
-> run offline verifier
-> inspect verifier-result.json
-> confirm privacy-report.json
-> decide whether the bundle is acceptable
```

The reviewer should not need to trust a live ProofPath service to answer the
basic v0.1 questions.

## Verifier Questions

For v0.1, the offline verifier should answer only these questions:

1. Is every file declared in `manifest.json` present and hash-matching?
2. Is the decision chain complete from the genesis/null marker to the chain
   head?
3. Does changing a decision field break verification?
4. Does deleting a middle record break continuity?
5. Does `privacy-report.json` confirm that unnecessary personal or payment
   data was omitted, redacted, hashed, or explicitly justified?

## Planned Fixture Matrix

| Fixture | Expected result | Purpose |
| --- | --- | --- |
| `valid-bundle/` | verifier passes | Shows the smallest acceptable offline evidence bundle. |
| `invalid-modified-decision/` | verifier fails hash-chain verification | Proves decision-field tampering is detected. |
| `invalid-deleted-middle-record/` | verifier fails continuity | Proves missing records break the chain. |
| `invalid-privacy-leak/` | verifier fails privacy-boundary check | Proves unnecessary personal/payment fields can fail even when hashes are otherwise valid. |

## Suggested Result Codes

The verifier output should keep stable reason codes so CI, CLI output, and
grant-reviewer docs can all refer to the same failure classes:

```text
manifest_file_missing
manifest_hash_mismatch
hash_chain_broken
decision_record_tampered
decision_record_missing
privacy_boundary_failed
unsupported_bundle_schema
```

Human-readable explanations can change, but these reason codes should be
treated as part of the fixture contract once implemented.

## Non-Claims

This fixture contract does not claim:

- production-grade immutable storage;
- trusted timestamping;
- cryptographic signing;
- full payment compliance;
- prevention of all privacy leaks.

It only defines a small offline-review contract for a portable, tamper-evident,
privacy-minimized evidence bundle.
