# Completion checklist

## Scope

- [ ] Actor, target, side effect, and authoritative system are identified.
- [ ] Write authority is explicit.
- [ ] Synthetic and real environments are clearly separated.

## Idea Graph

- [ ] Problem, goal, strategy, assumptions, risks, safe branch, and verification are present.
- [ ] Assumptions are not labeled as facts.
- [ ] Unsafe alternatives are visible.

## Intent Graph

- [ ] `intent_id` and intent code are present.
- [ ] Principal, target, scope, constraints, and maximum effect are explicit.
- [ ] Approval revision, expiry, revocation, and replay/idempotency binding are checked.
- [ ] Allowed recovery and forbidden actions are explicit.

## Fact Graph

- [ ] Each high-impact node has evidence references.
- [ ] Dispatch, external state transition, observation, containment, recovery, and readback are distinguished.
- [ ] Authoritative readback is not replaced by a tool response.
- [ ] Unknown states remain unknown.

## Alignment

- [ ] Idea→Intent, Intent→Fact, and Idea→Fact mappings exist.
- [ ] Every mismatch is named.
- [ ] Missing mapping does not count as alignment.
- [ ] Final status is derived, not asserted.

## Containment and recovery

- [ ] Retries and dependent actions stop before containment.
- [ ] Unrelated external effects are preserved.
- [ ] Recovery is the minimum targeted action.
- [ ] Recovery remains within original authority.
- [ ] Secondary-harm risk is evaluated.

## Verification

- [ ] Final state is read independently.
- [ ] Final invariant matches user intent.
- [ ] Evidence manifest and checksums are valid.
- [ ] Producer claim is separated from raw evidence and verifier output.

## Negative tests

- [ ] Relevant forbidden path fails.
- [ ] Blind retry is tested when outcome can be unknown.
- [ ] New lineage/idempotency key is tested when once-only intent applies.
- [ ] Premature success is tested.
- [ ] Stale/revoked authority is tested when applicable.
- [ ] Broken graph/evidence integrity is tested.

## Repository completion

- [ ] Focused tests pass.
- [ ] Repository-wide regressions pass.
- [ ] CI is green.
- [ ] Review findings are resolved or dispositioned.
- [ ] PR is mergeable.
- [ ] Merge occurs only after authorization.
- [ ] Claims remain limited to demonstrated evidence.
