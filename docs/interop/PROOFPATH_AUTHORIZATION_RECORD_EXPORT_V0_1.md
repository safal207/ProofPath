# ProofPath Authorization Record Export Profile v0.1

**Status:** Draft interoperability profile  
**Issue:** [ProofPath #166](https://github.com/safal207/ProofPath/issues/166)  
**Canonical ecosystem profile:** [Liminal #108](https://github.com/safal207/Liminal/issues/108)

## Purpose

ProofPath is a pre-execution authorization boundary. This profile defines how a
ProofPath decision can be exported as a provider-neutral `authorization_record`
without turning ProofPath into an observation source or post-response claim
verifier.

The exported record answers:

> Was this exact proposed action authorized, blocked, rejected, or held against
> the frozen context that existed at decision time?

It does not answer whether a downstream tool actually executed, whether a
captured result is truthful, or whether a model later described that result
faithfully.

## Files

- JSON Schema: [`schemas/proofpath-authorization-record-v0.1.schema.json`](../../schemas/proofpath-authorization-record-v0.1.schema.json)
- Fixture pack: [`conformance/authorization-record-export-v0.1.json`](../../conformance/authorization-record-export-v0.1.json)
- Report-time context: [`conformance/authorization-record-report-context-v0.1.json`](../../conformance/authorization-record-report-context-v0.1.json)
- Deterministic exporter: [`scripts/check_authorization_record_export.py`](../../scripts/check_authorization_record_export.py)
- Independent semantic verifier: [`scripts/verify_authorization_record_export.py`](../../scripts/verify_authorization_record_export.py)

Run:

```bash
python3 scripts/check_authorization_record_export.py
python3 scripts/verify_authorization_record_export.py
```

## Record shape

A portable record contains:

```text
schema
profile
transition_id
subject_id
action_identity_profile
action_identity_digest
binding_profile
binding_digest
decision
reason_codes
issued_at
expires_at
consumption_state
continuation_state
current_state
policy_ref
proofpath_evidence_refs
claim_boundary
```

`current_state` is intrinsic to the exported authorization record. Its portable
values are `ACTIVE`, `PENDING_APPROVAL`, `EXPIRED`, `CONSUMED`, `BLOCKED`,
`REJECTED`, and `INVALID`. Report-derived values such as `EXPIRED_AT_REPORT`
are not serialized into the canonical authorization record.

The fixture wraps each record with canonical bytes and a SHA-256 reference:

```text
record_ref = "sha256:" + SHA256(RFC8785-JCS(record))
```

The current fixture contains no floating-point values, so standard-library
sorted minimal JSON is equivalent to RFC 8785 JCS for the published input
domain.

## Frozen action identity

The action identity preimage contains:

```text
caller_id
intent_id
causal_parent
scope
reversibility
```

The binding preimage contains:

```text
request_method
request_target
arguments_digest
policy_ref
recipient_scope
budget_scope
approval_ref
```

A downstream observation must repeat both digests and bind to the exact
`authorization_record` reference.

## Decision mapping

| ProofPath decision | Portable authority meaning |
| --- | --- |
| `ACCEPT` | The exact frozen action context may proceed while fresh and unconsumed. |
| `HOLD` | Execution is not authorized yet; approval or revalidation remains open. |
| `BLOCK` | Execution is forbidden under the evaluated policy or context. |
| `REJECT` | The request is invalid for authorization. |

No downstream observation or honest response can retroactively convert `HOLD`,
`BLOCK`, or `REJECT` into `ACCEPT`.

## Freshness, consumption, and report time

The immutable authorization export preserves `issued_at`, `expires_at`,
`consumption_state`, `continuation_state`, and its intrinsic `current_state`.

Report time is deliberately supplied as separate verifier context rather than
inserted into the authorization record. The verifier derives a separate
`authority_state_at_report`, which may be `EXPIRED_AT_REPORT`, without changing
the canonical bytes or reference of the original authorization decision.

A record that later expires may remain historically auditable, but it must not
be reused as live authority. A consumed record may remain linked to its existing
resolution, but it must not permit a second side effect.

## Independent semantic verification

The deterministic exporter reproduces canonical records and references. The
independent verifier does not import that exporter. It separately validates:

- exact context shapes and SHA-256 reference syntax;
- policy binding consistency;
- decision, continuation, approval, and consumption combinations;
- intrinsic authorization state and report-time authority state;
- execution eligibility and zero-side-effect expectations;
- observation timing and authorization joins;
- response-integrity joins and their derived outcome.

This separation prevents the fixture and exporter from silently agreeing on the
same semantic mistake.

## Evidence handoff

A downstream runtime may produce an `observation_record` containing:

```text
authorization_ref
action_identity_digest
binding_digest
execution_status
observed_at
result_digest
```

A later verifier may produce a `response_integrity_record` containing:

```text
authorization_ref
observation_refs
claim verdicts
verifier identity
claim boundary
```

ProofPath evidence bundles may carry those external artifacts by digest and
schema/profile identifier. Importing them does not mean ProofPath authored their
semantic verdicts.

For the conformance fixtures, the semantic verifier derives one of:

- `MATCH` — the observation joins to live authority and no supplied integrity
  record reports failure;
- `MATCH_WITH_INTEGRITY_FAILURE` — authority and observation join, while the
  independently attributed response-integrity verdict is not `VERIFIED`;
- `HISTORICAL_ONLY` — execution occurred within the authorization window, but
  the report was evaluated after authority expired.

## Fixture cases

The fixture pack covers:

1. accepted reversible action;
2. accepted irreversible action with approval;
3. held action pending approval;
4. blocked expired intent;
5. blocked replayed or consumed intent;
6. accepted action with a matching downstream observation handoff;
7. accepted action with a contradicted external response-integrity verdict;
8. stale authorization paired with an honest historical report.

## Security and privacy boundary

The export should use digests and references for sensitive payloads. It must not
require raw credentials, private keys, complete payment payloads, or secrets.

This profile does not by itself prove signer identity, signature validity,
observation-source integrity, payment settlement, policy correctness,
regulatory compliance, or production security.

## Canonical invariant

> ProofPath exports the evidence for why an exact action could or could not
> proceed. Downstream systems may attach what happened and what the model later
> claimed, but those verdicts remain independent.
