# PoCI v0.1 Threat Model

Status: Draft threat model  
Profile: `proofpath.poci.v0.1`

## 1. Purpose

This document defines adversarial conditions that Proof of Causal Integrity (PoCI) v0.1 is intended to prevent, detect, or surface before an AI-agent action is trusted.

PoCI verifies the declared evidence chain. It does not prove objective real-world truth, witness independence, hardware identity, model truthfulness, or distributed consensus.

## 2. Protected invariants

1. Model output is a proposal, not authorization.
2. Intent must be valid, scoped, non-replayed, and attributable to a principal.
3. Authority and causal grounding are separate requirements.
4. The executed action must remain bound to the accepted proposal.
5. Claimed execution and observed result are separate evidence stages.
6. Security-critical artifacts must be content-addressed.
7. Conflicting evidence must not silently degrade to `ACCEPT`.
8. Unsupported or ambiguous evidence must fail closed.

## 3. Trust boundaries

```text
principal signing boundary
  -> agent proposal boundary
  -> ProofPath decision boundary
  -> executor boundary
  -> observer boundary
  -> witness boundary
  -> offline verifier boundary
```

A deployment may reuse actors, but role reuse must be declared. PoCI v0.1 does not assume that two witness identifiers represent independent operators.

## 4. Threat taxonomy

| ID | Threat | Attacker capability | Violated invariant | PoCI mechanism | Expected result | Residual risk / future layer |
| --- | --- | --- | --- | --- | --- | --- |
| T01 | Forged intent | Substitute an unsigned statement | Authentic principal intent | Signature reference and intent binding | `BLOCK / INTENT_SIGNATURE_UNVERIFIED` | Production key management |
| T02 | Expired intent | Replay once-valid authorization after expiry | Time-bounded intent | Validity-window check | `BLOCK / INTENT_EXPIRED` | Trusted clock |
| T03 | Intent replay | Reuse a consumed nonce | Intended execution count | Durable replay store | `BLOCK / INTENT_REPLAYED` | Distributed replay coordination |
| T04 | Missing authority | Present a proposal without a usable grant | Proposal is not authorization | Authority preflight | `BLOCK / AUTHORITY_MISSING` | IAM adapter correctness |
| T05 | Authority escalation | Change principal, agent, executor, or action kind | Bound delegation | Cross-section identity binding | `BLOCK / AUTHORITY_SCOPE_VIOLATION` | Capability tokens |
| T06 | Scope drift | Propose outside approved scope | Least authority | Scope subset check | `BLOCK / AUTHORITY_SCOPE_VIOLATION` | Rich policy language |
| T07 | Budget drift | Exceed authorized amount | Bounded authority | Budget comparison | `BLOCK / AUTHORITY_BUDGET_EXCEEDED` | Settlement/oracle evidence |
| T08 | Irreversible action without approval | Execute without explicit approval | Strong evidence for irreversible effects | Approval-reference check | `BLOCK / IRREVERSIBLE_APPROVAL_MISSING` | Human-presence proof |
| T09 | Missing causal parent | Omit required lineage | Separate causal grounding | Required-parent policy | `HOLD / CAUSAL_PARENT_MISSING` | CML adapter |
| T10 | Invented causal parent | Reference unrelated lineage | Valid permission lineage | Parent relation binding | `BLOCK / CAUSAL_PARENT_MISMATCH` | Portable causal proofs |
| T11 | Unverified causal chain | Present an unresolved parent | Inspectable lineage | Parent artifact verification | `HOLD or BLOCK / CAUSAL_CHAIN_UNVERIFIED` | Checkpoints |
| T12 | Proposal/execution substitution | Execute another proposal | Proposal binds execution | Proposal id/digest binding | `CHALLENGE / PROPOSAL_EXECUTION_MISMATCH` | Executor attestation |
| T13 | Forged execution receipt | Mutate receipt bytes | Content-addressed execution | Digest comparison | `CHALLENGE / EXECUTION_RECEIPT_DIGEST_MISMATCH` | Signed/TEE receipts |
| T14 | Result substitution | Replace observed output | Result separate from receipt | Result digest comparison | `CHALLENGE / RESULT_DIGEST_MISMATCH` | Independent observation |
| T15 | Witness conflict | Produce incompatible verdicts | Conflict cannot become acceptance | Conflict aggregation | `CHALLENGE / WITNESS_CONFLICT` | Quorum/dispute protocol |
| T16 | Witness equivocation | One identity signs incompatible statements | Witness accountability | Statement digest comparison | `CHALLENGE / WITNESS_EQUIVOCATION` | Identity and transparency registry |
| T17 | Sybil witnesses | One operator creates many identities | Independence not assumed | Surface identity reuse; no independence claim | policy `HOLD/CHALLENGE` | Reputation/stake/operator proofs |
| T18 | Evidence omission | Include only favorable artifacts | Mandatory completeness | Schema plus semantic checks | `BLOCK / POCI_REQUIRED_EVIDENCE_MISSING` | Full-log commitments |
| T19 | Profile downgrade | Use unsupported semantics | Fail-closed versioning | Exact profile check | `BLOCK / POCI_PROFILE_UNSUPPORTED` | Protocol registry |
| T20 | Canonicalization ambiguity | Exploit parser differences | Same bytes/root across verifiers | Normative canonicalization | `BLOCK or CHALLENGE` | Cross-language vectors |
| T21 | Envelope-root substitution | Change fields without valid root | Whole-envelope integrity | Root recomputation | `CHALLENGE / ENVELOPE_ROOT_MISMATCH` | Transparency anchors |
| T22 | Rollback/stale checkpoint | Present an old valid state | Monotonic history | Prior checkpoint references | `HOLD or CHALLENGE` | LiminalDB anti-rollback |
| T23 | Verification DoS | Submit huge/deep evidence | Bounded verification | Size/depth/time limits | fail-closed | Metering/streaming |
| T24 | Verifier compromise | Modify verifier/runtime | Independent evaluation | Portable fixtures and cross-language comparison | not solved by one verifier | Reproducible builds and independent nodes |

## 5. Decision guidance

- `BLOCK`: authorization, policy, replay, profile, and security-structure failures.
- `HOLD`: incomplete but plausibly remediable evidence without integrity contradiction.
- `CHALLENGE`: contradictory, substituted, equivocated, or digest-mismatched evidence.
- `ACCEPT`: every mandatory invariant passes and no conflict remains.

```text
CHALLENGE > BLOCK > HOLD > ACCEPT
```

## 6. Fixture mapping

| Fixture | Threat | Expected |
| --- | --- | --- |
| `valid-action.accept.json` | control | `ACCEPT` |
| `missing-authority.block.json` | T04 | `BLOCK` |
| `expired-intent.block.json` | T02 | `BLOCK` |
| `intent-replay.block.json` | T03 | `BLOCK` |
| `missing-causal-parent.hold.json` | T09 | `HOLD` |
| `causal-parent-mismatch.block.json` | T10 | `BLOCK` |
| `scope-violation.block.json` | T06 | `BLOCK` |
| `tampered-execution-receipt.challenge.json` | T13 | `CHALLENGE` |
| `result-digest-mismatch.challenge.json` | T14 | `CHALLENGE` |
| `conflicting-witnesses.challenge.json` | T15 | `CHALLENGE` |
| `unknown-profile.block.json` | T19 | `BLOCK` |
| `irreversible-without-approval.block.json` | T08 | `BLOCK` |

## 7. Explicit non-claims

PoCI v0.1 does not prove GPU/TEE identity, zkML correctness, objective observation truth, witness independence, distributed finality, legal compliance, or model safety.

Its narrower claim is that a verifier can deterministically evaluate the declared action-evidence chain or fail closed with stable reason codes.
