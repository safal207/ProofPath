# Temporal Graph

## Purpose

The Temporal Graph proves when identity, authority, policy, capability, observations, and decisions are valid.

```text
planning time
≠ evaluation time
≠ dispatch time
≠ observation time
≠ verification time
```

A decision valid during planning may be stale at dispatch.

## Node kinds

```text
instant
window
deadline
anchor
```

Required attributes:

```text
time_kind
occurred_at and/or not_before / not_after
source
clock_domain
max_skew_seconds
confidence
authority_effect = none
```

## Required windows

For high-impact actions model at least:

- identity authentication/session validity;
- Intent validity;
- Policy revision effectiveness;
- Capability lease validity;
- approval validity;
- nonce/idempotency lifetime where applicable;
- evaluation time;
- dispatch deadline;
- dispatch, observation, and verification time.

## Invariants

1. Time never creates or renews authority.
2. Evaluation must occur inside every required window.
3. Dispatch must occur before the deadline and inside every still-current window.
4. Clock source and permitted skew must be explicit.
5. Unknown time or excessive skew fails closed for high-impact actions.
6. A material change between evaluation and dispatch requires revalidation.
7. Timeout preserves `UNKNOWN`; elapsed time does not imply success or failure.

## Common mismatches

```text
TEMPORAL_WINDOW_EXPIRED
TEMPORAL_NOT_YET_VALID
CLOCK_SKEW_EXCEEDED
EVALUATION_DISPATCH_RACE
POLICY_REVISION_STALE
AUTHORITY_STALE
CAPABILITY_EXPIRED
OBSERVATION_ORDER_UNKNOWN
```

## Dispatch protocol

```text
evaluate
→ capture evaluation time
→ re-read current identity / intent / policy / capability
→ compare revisions and bindings
→ confirm dispatch deadline
→ atomically consume nonce if used
→ dispatch
→ record observed dispatch time
```

If the boundary cannot be revalidated, return `HOLD`.
