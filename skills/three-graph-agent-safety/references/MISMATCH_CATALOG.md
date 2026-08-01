# Mismatch catalog — Personal Agent Safety v1.2

## Truth and authority

### IDEA_INTENT_MISMATCH
The strategy exceeds or contradicts current Intent. Default: `BLOCK` or `HOLD`.

### INTENT_FACT_MISMATCH
Observed effects exceed, omit, or contradict authorized effects. Default: contain, recover, verify.

### IDEA_FACT_MISMATCH
Reality contradicts the expected strategy. Revise Idea; never rewrite facts.

### AUTHORITY_STALE
Intent or approval is expired, revoked, or superseded. Refresh at the execution boundary.

## Identity

### IDENTITY_INTENT_MISMATCH
The evaluated principal differs from the current Intent principal. Default: `BLOCK`.

### IDENTITY_ASSURANCE_INSUFFICIENT
Authentication assurance is below the required level. Default: `HOLD` or stronger authentication.

### DELEGATION_CHAIN_BROKEN
The executor cannot be tied to the principal without scope expansion. Default: `BLOCK`.

### IDENTITY_CHANGED_AFTER_EVALUATION
Principal, actor, executor, session, credential, or audience changed before dispatch. Default: re-evaluate.

### IDENTITY_AUDIENCE_MISMATCH
Identity evidence was issued for a different system or audience. Default: `BLOCK`.

## Capability

### CAPABILITY_AUTHORITY_LEAK
Technical availability is treated as permission. Default: `BLOCK`.

### CAPABILITY_REVOKED
The selected capability is disabled or revoked. Default: `BLOCK`.

### CAPABILITY_SCOPE_MISMATCH
Action or target exceeds the capability's declared scope. Default: `BLOCK`.

### CAPABILITY_IDENTITY_MISMATCH
Capability is bound to a different executor. Default: `BLOCK`.

### CAPABILITY_SUBSTITUTED
Runtime selected a different tool or capability after evaluation. Default: re-evaluate.

### CAPABILITY_EXPIRED
Capability lease ended before dispatch. Default: `HOLD` or renew through an authorized path.

## Temporal

### TEMPORAL_WINDOW_EXPIRED
A required validity window ended. Default: `HOLD` or `BLOCK`.

### TEMPORAL_NOT_YET_VALID
Action is attempted before authority or policy becomes active. Default: `HOLD`.

### CLOCK_SKEW_EXCEEDED
Clock uncertainty exceeds policy. Default: `HOLD`.

### EVALUATION_DISPATCH_RACE
A material binding changed after evaluation but before dispatch. Default: stop and revalidate.

### OBSERVATION_ORDER_UNKNOWN
Event order cannot be established. Default: `UNKNOWN`.

## Policy, memory, and risk

### POLICY_INTENT_CONFLICT
Policy denies or narrows the current Intent. Default: obey mandatory policy and explain the conflict.

### POLICY_REVISION_STALE
A superseded policy revision was evaluated. Default: refresh.

### MEMORY_AUTHORITY_LEAK
Memory is used to create, expand, renew, or transfer authority. Default: `BLOCK`.

### MEMORY_STALE
Stale memory influences a high-impact decision. Default: exclude it or confirm current intent.

### MEMORY_CONFLICT
Retrieved memories disagree. Default: exclude or resolve.

### RISK_UNDERSTATED
Residual risk is lower than supported by evidence. Default: recalculate and hold.

### RISK_UNKNOWN_ACCEPTED
Unknown risk is treated as low. Default: `HOLD`.

## Execution and evidence

### FACT_MISSING
Required business outcome lacks authoritative evidence. Default: `UNKNOWN`, never `VERIFIED`.

### UNKNOWN_PROMOTED_TO_SUCCESS
Timeout or ambiguity is announced as success. Default: reconcile.

### SCOPE_EXPANDED_DURING_RECOVERY
Recovery changes target, recipient, amount, key, or destructive scope. Default: `BLOCK`.

### DUPLICATE_SIDE_EFFECT
More than one effect exists for a once-only Intent. Stop retries and contain only lineage-created duplicates.

### TOOL_SUCCESS_BUSINESS_FAILURE
Transport reports success while the business invariant is false. Read authoritative state and recover.

### EVIDENCE_LINEAGE_BROKEN
Identity, Intent, Policy, Capability, dispatch, or verification cannot be tied to one lineage. Fail closed.

### SECONDARY_HARM_RISK
Containment or recovery may cause additional harm. Choose the smallest reversible action or escalate.
