# Mismatch catalog

## Core truth mismatches

### IDEA_INTENT_MISMATCH

The proposed strategy exceeds or contradicts current user authority.

Default: `BLOCK` or `HOLD`.

### INTENT_FACT_MISMATCH

Observed effects exceed, omit, or contradict the authorized effect.

Default: stop dependent work, contain, recover, verify.

### IDEA_FACT_MISMATCH

Reality contradicts the strategy's expected result.

Default: revise the Idea Graph; do not rewrite facts.

## Policy mismatches

### POLICY_INTENT_CONFLICT

Intent requests an effect that mandatory policy denies or constrains.

Default: `BLOCK`, or `HOLD` when a required approval can resolve it.

### POLICY_REVISION_STALE

The decision used an outdated policy revision.

Default: refresh policy at the execution boundary.

### POLICY_AUTHORITY_SUBSTITUTION

A permissive policy is treated as if it were user consent.

Default: `BLOCK` or `HOLD` for missing Intent.

## Memory mismatches

### MEMORY_AUTHORITY_LEAK

Retrieved or remembered context is used as permission for a side effect.

Examples:

- remembered recipient used to send a message;
- remembered budget used to purchase;
- past merge approval reused for a new PR.

Default: `BLOCK`.

### MEMORY_STALE

A high-impact decision relies on stale or unknown-freshness context.

Default: `HOLD` and refresh.

### MEMORY_CONFLICT

Retrieved memories disagree with each other or with current instructions.

Default: current Intent wins; unresolved conflict stays `HOLD`.

### MEMORY_SCOPE_EXCEEDED

The system retrieved or used context unrelated to the present purpose.

Default: exclude the context, minimize retrieval, and assess privacy impact.

### MEMORY_INFERENCE_EXPOSED_AS_FACT

An inferred preference or profile claim is presented as an observed fact.

Default: relabel as inference or remove.

## Risk mismatches

### RISK_UNDERSTATED

Likelihood, impact, irreversibility, or residual risk is materially understated.

Default: recompute and fail closed.

### RISK_UNKNOWN_ACCEPTED

Unknown risk is treated as low and the action is accepted.

Default: `HOLD` or `BLOCK`.

### MITIGATION_NOT_ENFORCED

A claimed mitigation is not present at the action boundary.

Default: remove mitigation credit and re-evaluate residual risk.

### SECONDARY_HARM_RISK

Containment or recovery could create additional harm.

Default: choose the smallest reversible action or escalate.

## Execution and evidence mismatches

### AUTHORITY_STALE

Approval expired or was revoked between planning and dispatch.

Default: refresh authority.

### FACT_MISSING

A required business outcome has no authoritative evidence.

Default: `UNKNOWN` or `HOLD`, never `VERIFIED`.

### UNKNOWN_PROMOTED_TO_SUCCESS

A timeout or ambiguous result is described as successful.

Default: block success announcement and reconcile.

### SCOPE_EXPANDED_DURING_RECOVERY

Recovery creates a new target, recipient, amount, key, or destructive effect.

Default: `BLOCK`; request fresh authority if needed.

### DUPLICATE_SIDE_EFFECT

More than one effect exists for a once-only Intent.

Default: stop retries and contain only the agent-created duplicate.

### TOOL_SUCCESS_BUSINESS_FAILURE

Tool status reports success while the authoritative invariant is false.

Default: freeze dependent actions, read authoritative state, recover, verify.

### EVIDENCE_LINEAGE_BROKEN

Request, authority, policy, memory, risk, execution, or verification cannot be tied to one lineage.

Default: fail closed and preserve evidence.
