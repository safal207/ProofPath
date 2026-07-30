# Completion checklist — v1.1

## Scope

- [ ] Actor, target, side effect, and authoritative system are identified.
- [ ] Write authority is explicit and current.
- [ ] Synthetic and real environments are separated.
- [ ] Policy, memory, and risk sources are identified.

## Idea Graph

- [ ] Problem, strategy, assumptions, alternatives, unsafe branch, and verification are present.
- [ ] Assumptions are not labeled as facts.
- [ ] Memory influences are referenced explicitly.

## Intent Graph

- [ ] `intent_id`, principal, target, scope, constraints, and maximum effect are explicit.
- [ ] Approval revision, expiry, revocation, and replay/idempotency binding are checked.
- [ ] Allowed recovery and forbidden actions are explicit.
- [ ] No Memory node acts as authority.

## Policy Graph

- [ ] Policy ID, issuer, revision, validity, rule, effect, and precedence are explicit.
- [ ] Mutable policy was refreshed at the execution boundary.
- [ ] Policy does not silently broaden Intent.
- [ ] Unknown policy state fails closed.

## Memory Graph

- [ ] Every node has provenance, purpose, recorded/retrieved time, and confidence.
- [ ] Freshness and conflict state are explicit.
- [ ] `authority_effect=none` for every Memory node.
- [ ] Retrieval is minimized to the current purpose.
- [ ] Stale, conflicted, inferred, or superseded context is not exposed as current fact.
- [ ] Sensitive context is excluded unless necessary.

## Risk Graph

- [ ] Hazards, causal paths, likelihood, impact, uncertainty, and reversibility are explicit.
- [ ] Mitigations map to causal paths.
- [ ] Residual risk and escalation threshold are explicit.
- [ ] Unknown risk is not treated as low.
- [ ] Containment and recovery risk are evaluated.

## Fact Graph

- [ ] Each high-impact node has evidence references.
- [ ] Dispatch, external transition, observation, containment, recovery, and readback are distinguished.
- [ ] Authoritative readback is not replaced by tool status, memory, policy, or risk assessment.
- [ ] Unknown states remain unknown.

## Alignment

- [ ] Idea→Intent, Intent→Policy, Memory→Idea, Risk→Action, Intent→Fact, and Idea→Fact links exist.
- [ ] Every mismatch is named.
- [ ] Missing mapping does not count as alignment.
- [ ] Final status is derived, not asserted.

## Containment and recovery

- [ ] Retries and dependent actions stop first.
- [ ] Unrelated external effects are preserved.
- [ ] Recovery is the minimum targeted action.
- [ ] Recovery remains within current Intent and Policy.
- [ ] Secondary-harm risk is evaluated.

## Verification

- [ ] Final state is read independently.
- [ ] Final invariant matches user Intent.
- [ ] Evidence manifest and checksums are valid.
- [ ] Producer claim is separated from raw evidence and verifier output.

## Negative tests

- [ ] Memory-as-authority fails.
- [ ] Stale or conflicted memory fails when decision-critical.
- [ ] Policy revision drift fails.
- [ ] Critical or unknown risk cannot be accepted.
- [ ] Blind retry, new lineage, and premature success fail where applicable.
- [ ] Broken graph/evidence integrity fails.

## Repository completion

- [ ] Focused tests pass.
- [ ] Package validator positive example passes.
- [ ] Semantic negative self-tests pass.
- [ ] Repository-wide regressions pass.
- [ ] CI is green.
- [ ] Review findings are resolved or dispositioned.
- [ ] PR is mergeable.
- [ ] Merge and release occur only after authorization.
- [ ] Claims remain limited to demonstrated evidence.
