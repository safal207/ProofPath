# Completion checklist — Personal Agent Safety v1.2

## Boundary

- [ ] Principal, actor, executor, action, target, side effect, and system of record are identified.
- [ ] Real and synthetic environments are separated.
- [ ] Write, merge, release, or external-action authority is explicit.

## Idea and Intent

- [ ] Strategy, assumptions, alternatives, risks, and verification are present.
- [ ] Exactly one current Intent is selected.
- [ ] Principal, target, scope, maximum effect, validity, revision, replay binding, recovery, and forbidden actions are explicit.

## Identity

- [ ] Principal, actor, and executor identities are evidenced.
- [ ] Identity issuer, audience, authentication time, assurance, and current state are explicit.
- [ ] Delegation is evidenced and does not expand scope.
- [ ] Evaluated principal matches current Intent principal.

## Policy

- [ ] Policy ID, issuer, revision, effect, precedence, and validity are explicit.
- [ ] Mandatory deny, constraint, and approval requirements are respected.

## Capability

- [ ] Selected capability ID, provider, action, target scope, state, and lease are explicit.
- [ ] Capability is enabled and bound to the verified executor.
- [ ] Capability availability is not treated as authority.
- [ ] Runtime did not substitute another capability after evaluation.

## Memory

- [ ] Included memory has provenance, purpose, freshness, and no conflict.
- [ ] Memory has `authority_effect = none`.
- [ ] Current Intent overrides historical preferences.

## Temporal

- [ ] Evaluation time and clock source are explicit.
- [ ] Intent, Policy, Identity/session, Capability, and approval windows are checked.
- [ ] Dispatch deadline and maximum clock skew are explicit.
- [ ] Bindings are revalidated immediately before dispatch.
- [ ] Event order is evidenced after execution.

## Risk

- [ ] Hazards, uncertainty, mitigation, and residual tier are explicit.
- [ ] Unknown risk is not accepted as low.
- [ ] Secondary-harm risk is evaluated for recovery.

## Fact and verification

- [ ] Every material Fact node has evidence, time/order, and source.
- [ ] Tool success is not substituted for business truth.
- [ ] Final state is independently read.
- [ ] Final invariant matches current Intent.
- [ ] Evidence manifest and digests are valid.

## Graph integrity

- [ ] All nine graphs exist and are acyclic.
- [ ] Every edge and cross-graph link resolves.
- [ ] Required aligned links exist.
- [ ] Open high/critical mismatches prevent `ACCEPT` and `VERIFIED`.

## Negative controls

- [ ] Memory-as-authority fails.
- [ ] Identity mismatch and weak assurance fail.
- [ ] Broken delegation fails.
- [ ] Revoked, unbound, substituted, or out-of-scope capability fails.
- [ ] Expired/not-yet-valid window and dispatch race fail.
- [ ] Blind retry, new idempotency key, and premature success fail.
- [ ] Missing evidence and tampered digest fail.

## Repository completion

- [ ] Focused tests pass.
- [ ] Repository-wide regression passes.
- [ ] CI is green.
- [ ] Review findings are resolved or dispositioned.
- [ ] PR is mergeable.
- [ ] Merge and release occur only after authorization.
- [ ] Claims remain limited to demonstrated evidence.
