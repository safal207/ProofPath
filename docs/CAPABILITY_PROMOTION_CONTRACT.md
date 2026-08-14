# ProofPath Capability Promotion Contract v0.1

## Purpose

ProofPath has accumulated strong verified capabilities through stacked pull requests. The engineering problem is no longer lack of implementation; it is **canonical reality drift**: a capability may be real and well-tested on a branch while remaining absent from `main`, yet architecture documents or downstream repositories may begin to treat it as if it were canonical.

This contract makes capability state explicit and machine-readable.

## Source of truth

`governance/capability-manifest.v0.1.json` is the repository-local source of truth for whether an audited capability is:

- `CANONICAL` — present in reviewed repository history and allowed as a default dependency;
- `PROPOSED` — implemented on an exact PR head but not part of canonical repository state;
- `EXPERIMENTAL` — an opt-in experiment that must not be treated as a stable system contract;
- `SUPERSEDED` — preserved for history but replaced by another declared capability;
- `ARCHIVED` — retained as evidence/history and not an active implementation target.

Open PR titles, roadmap prose, issue discussions, master-context documents, and successful branch CI do **not** promote a capability by themselves.

## Consumer rule

A cross-repository consumer may depend by default only on a capability with:

```text
status = CANONICAL
consumer_default_allowed = true
canonical_commit = <exact 40-char commit>
```

Using a `PROPOSED` or `EXPERIMENTAL` capability is allowed only as an explicitly labelled experiment and requires:

```text
explicit opt-in
+ exact source PR
+ exact head SHA
+ no claim that the dependency exists in ProofPath main
```

A proposed capability must never be referenced as `latest`, `production`, `canonical`, or an ambient ProofPath feature.

## Promotion transition

The only normal promotion edge is:

```text
PROPOSED
  -> reconcile with current canonical base
  -> exact-head validation
  -> review / trust-boundary check
  -> merge
  -> capability manifest update bound to merged commit
  -> CANONICAL
```

For stacked capabilities, children may be developed before parents are promoted, but this does not create transitive canonicality. A child remains non-canonical until every required dependency is canonical or the child is deliberately refactored to remove that dependency.

## Branch graph rule

A long stack is evidence of an implementation trajectory, not of canonical repository state.

For the current PoCI / Deploy Guard / Control Cloud trajectory:

```text
#193 PoCI contract
 -> #194 fixtures
 -> #195 Python verifier
 -> #196 CI/demo
 -> #197 Rust verifier
 -> #198 multigraph
 -> #199 quorum
 -> #200 signed runners
 -> #201 federation
 -> #202 org independence
 -> #204 external SDK
 -> #205 external admission
 -> #206 Deploy Guard
 -> #207 reusable Action
 -> #208 Evidence Builder
 -> #209 GitHub Collector
 -> #211 Control Cloud
 -> #213 ingestion
 -> #214 Sigstore admission
 -> #215 workflow governance
 -> #216 reviewer separation
```

`#210 Assured Action Economy` is a parallel child of `#208`. `#217 MASTER_CONTEXT` is documentation and cannot promote runtime capabilities. `#218 Gonka Compute Witness` is an independent experiment.

## FCRP-SELF-005

The first meaningful divergence is **PR #193**, not the later Control Cloud stack:

```text
Idea:
ProofPath capabilities used by the ecosystem should have an unambiguous canonical identity.

First divergence:
PoCI v0.1 became the foundation of a long implementation stack while remaining PROPOSED outside main.

Symptom:
Downstream architecture can describe branch-only capabilities as if they are ordinary ProofPath surfaces.

Refactor point:
Repository-level capability promotion/canonicality contract.
```

This is intentionally not solved by blindly merging the entire stack. Promotion is a trust transition and each dependency boundary still requires reconciliation with current `main`.

## Positive control

SAFE Causal Incident Graph v0.1 (`#219`) is already present in `main` at the observed audit head. It demonstrates that ProofPath can promote a capability normally; the defect is the absence of a general lifecycle contract for distinguishing that state from branch-only architecture.

## Fail-closed invariants

The validator rejects:

- a non-canonical capability marked as a default consumer dependency;
- a canonical capability without an exact canonical commit;
- a canonical capability depending on a non-canonical capability;
- a proposed/experimental capability without an exact head SHA and source PR;
- unknown dependency IDs;
- dependency cycles;
- duplicate capability IDs or duplicate JSON keys;
- weakening of the manifest policy flags.

## Ecosystem integration

The same state vocabulary should be reused when the NEO REZONANS repositories are connected:

```text
RESONANCE       consumes published/canonical claims
CML             consumes canonical memory contracts or exact experimental pins
FCRP            records divergence and refactor decisions
LiminalOSAI     evaluates authorization separately from evidence
ContractGraph-QA verifies state transitions
ProofPath       emits evidence/provenance under explicit capability identity
LiminalDB       persists only contracts whose import status is explicit
RINSE           may reinterpret evidence but cannot silently promote capability status
```

The capability manifest is therefore the first repository-local building block for a later ecosystem-wide System Contract.
