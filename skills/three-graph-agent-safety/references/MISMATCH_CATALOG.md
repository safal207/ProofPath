# Mismatch catalog

## IDEA_INTENT_MISMATCH

The proposed strategy exceeds or contradicts user authority.

Examples:

- agent proposes two orders while intent permits one;
- agent selects a different recipient;
- agent proposes destructive recovery while only reversible recovery is allowed.

Default response: `BLOCK` or `HOLD`.

## INTENT_FACT_MISMATCH

Observed effects exceed, omit, or contradict the authorized effect.

Examples:

- two payments exist for `PAY_ONCE`;
- deleted resource differs from approved target;
- final limit exceeds policy maximum.

Default response: stop dependent work, contain, recover, verify.

## IDEA_FACT_MISMATCH

Reality contradicts the strategy's expected result.

Examples:

- HTTP 200 but authoritative state is wrong;
- retry strategy assumed no commit but an order already exists;
- tests pass but billing invariant fails.

Default response: revise the Idea Graph; do not rewrite facts.

## AUTHORITY_STALE

The action uses an approval snapshot that is no longer current.

Examples:

- approval revoked between planning and dispatch;
- policy revision changed;
- validity window expired.

Default response: refresh authority at the execution boundary.

## FACT_MISSING

A required business outcome has no authoritative evidence.

Default response: `UNKNOWN` or `HOLD`, never `VERIFIED`.

## UNKNOWN_PROMOTED_TO_SUCCESS

A timeout, missing response, or ambiguous result is described as successful.

Default response: block success announcement and reconcile.

## SCOPE_EXPANDED_DURING_RECOVERY

Recovery creates a new recipient, key, target, amount, or destructive effect not authorized by the original intent.

Default response: `BLOCK`; request fresh authority if needed.

## DUPLICATE_SIDE_EFFECT

More than one effect exists for a once-only intent.

Default response: stop retries, identify lineage, contain only the agent-created duplicate, preserve unrelated effects.

## TOOL_SUCCESS_BUSINESS_FAILURE

Transport or tool status reports success while the authoritative invariant is false.

Default response: freeze dependent actions, read authoritative state, recover, independently verify.

## EVIDENCE_LINEAGE_BROKEN

Request, authority, execution, recovery, or verification cannot be tied to the same intent/action lineage.

Default response: fail closed and preserve available evidence.

## SECONDARY_HARM_RISK

The proposed containment or recovery could cause additional harm.

Default response: choose the smallest reversible action or escalate to human review.
