# NOOA Liminal Guard — integration contract v0.1

## Purpose

This integration closes the first runnable path between NVIDIA Labs Object-Oriented Agents (NOOA) and the ProofPath/Liminal portfolio without creating another protocol repository.

The runtime contract is deliberately narrow:

```text
agent proposes an action
→ ProofPath evaluates authority before execution
→ only ACCEPT reaches the side-effect function
→ actual result is observed separately from authorization
→ causal/replay traces and durable evidence are exported
→ the bundle is independently hash-verified
```

## Portfolio roles

| Layer | Role in this implementation |
|---|---|
| NOOA | Agent class, typed capabilities, model-driven orchestration, parent-child spans |
| ProofPath | Pre-execution `ACCEPT / HOLD / BLOCK` authority decision |
| CML | Causal action records and explicit findings for broken lineage |
| LTP | `sense → transition → commit` replay-oriented export |
| LiminalDB | Hash-linked authorization/observation ledger handoff |
| Ibex verification pattern | Exact file inventory, size and SHA-256 verification |

The local files are adapter outputs. They do not claim that every downstream repository has already adopted a frozen cross-repository schema.

## Security invariants

A side effect is callable only when all applicable conditions hold:

1. declared `intent_id` exists;
2. `parent_cause` exists;
3. scope is allowed by policy;
4. a non-empty nonce exists and has not already been consumed;
5. secret-bearing network output targets an allowed destination;
6. network, irreversible, or configured high-trust actions carry human approval.

The nonce is consumed before the executor is invoked. This prevents a successful authorization from being reused after the side effect begins.

## Decision semantics

- `ACCEPT`: the wrapper may invoke the supplied capability.
- `HOLD`: action is structurally understood but awaits explicit approval.
- `BLOCK`: action is outside authority, malformed, replayed, or matches a denied risk pattern.

`HOLD` and `BLOCK` both produce an observation with `side_effect_executed=false`.

## NOOA integration strategy

The primary integration point is a guarded ordinary Python capability stored on the NOOA agent object. This is less brittle than modifying an internal execution strategy or trace viewer database.

The secondary integration point is `proposal_from_nooa_span`, which imports exported spans for after-the-fact audit. Because NOOA's public documentation promises tracing but not a permanent external JSON schema, the mapper accepts common aliases and requires security-critical values through explicit defaults. Real span and attribute values take precedence over defaults across all aliases.

## Evidence roles

Each action bundle contains:

- `authorization.json` — ProofPath decision, reason codes, and proposal digest;
- `evidence/intent.json` — declared authority and approval;
- `evidence/action.json` — normalized NOOA/action identity;
- `evidence/result.json` — observed execution result or non-execution;
- `evidence/verification.json` — decision and ledger binding;
- `cml-trace.jsonl` — CML-loadable causal records with integer nanosecond timestamps and complete actor envelopes;
- `cml-findings.json` — explicit CML-compatible audit findings kept separate from causal records;
- `ltp-trace.jsonl` — replay-oriented path;
- `liminaldb-ledger.jsonl` — current durable ledger snapshot;
- `manifest.json` — exact file sizes and SHA-256 digests;
- `bundle-verification.json` — local independent verification result.

Every attempt is stored in a separate sanitized `<span-id>-<decision>-<ledger-hash>` bundle directory, so accepted, held, blocked, and replay attempts cannot overwrite one another or escape the configured evidence root.

## Current non-claims

- no live model is required by CI;
- no real secret is read or transmitted;
- no offensive action is implemented;
- no in-process check is presented as sandbox containment;
- no production security certification is claimed;
- no official NVIDIA endorsement or integration is claimed.

## Definition of done for v0.1

- safe fixture reaches the executor;
- held and blocked fixtures never reach the executor;
- secret egress emits the expected CML-compatible finding;
- a consumed nonce is blocked without overwriting the accepted evidence;
- missing nonce and missing lineage are blocked;
- exported aliases cannot shadow real span data;
- untrusted span IDs cannot traverse outside the evidence root;
- CML exports satisfy the current `CausalRecord` envelope shape;
- every case produces a valid manifest-bound evidence bundle;
- CI reproduces the unit tests and benchmark summary.
