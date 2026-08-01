---
name: three-graph-agent-safety
description: Separates agent ideas, current user intent, and independently observed facts, then evaluates policy, memory, risk, identity, capability, and time as separate causal graphs. Use for high-impact agent actions, personal-agent memory, delegated execution, tool permissions, approvals, retries, timeouts, stale authority, recovery, evidence bundles, repository implementation, and CI validation. Prevents identity, capability, memory, policy, model reasoning, tool status, or UNKNOWN outcomes from becoming invented authority or verified success.
license: MIT
compatibility: Works in chat and with repositories, APIs, policies, identity records, capability registries, clocks, memory records, audit logs, and GitHub. External communication, payments, publication, irreversible writes, merge, and release require explicit current authorization.
metadata:
  author: safal207
  version: "1.2.0"
  source-project: ProofPath
---

# Three-Graph Agent Safety v1.2

Model high-impact agent work with three truth graphs and six independent control graphs.

```text
Truth:
Idea Graph       — proposal, assumptions, strategy, expected result
Intent Graph     — current user authority, scope, limits, validity
Fact Graph       — independently evidenced events and states

Controls:
Policy Graph     — versioned external rules
Memory Graph     — prior context with provenance and freshness
Risk Graph       — hazards, uncertainty, mitigations, residual risk
Identity Graph   — who the principal, actor, and executor are
Capability Graph — what the executor can technically do
Temporal Graph   — when identity, authority, policy, and capability are valid
```

## Non-substitution invariant

```text
Idea ≠ Intent ≠ Fact
Memory ≠ Intent
Policy allow ≠ user consent
Identity proof ≠ authorization
Capability available ≠ permission
Temporal record ≠ current validity
Risk estimate ≠ Fact
Tool success ≠ business success
UNKNOWN ≠ SUCCESS
```

Identity proves who is acting. Capability proves what is technically available. Time proves whether evaluated bindings are current. None of them creates user authority.

## Decision invariant

```text
IDENTITY_BOUND
+ IDEA_INTENT_ALIGNED
+ INTENT_CURRENT
+ POLICY_ALLOWED
+ CAPABILITY_ENABLED_AND_SCOPED
+ TEMPORAL_WINDOW_VALID
+ MEMORY_PROVENANCED
+ RISK_ACCEPTABLE
= ACCEPT

ACCEPT
+ FACT_INDEPENDENTLY_VERIFIED
+ FINAL_INVARIANT_MATCHES_INTENT
= SAFE_COMPLETION
```

Authority precedence is:

```text
verified identity binding
→ current Intent
→ mandatory Policy
→ scoped Capability
→ Temporal validity
→ Risk gate
→ execution decision
```

Memory is deliberately absent from this authority chain.

## Activate this skill when

Use for:

- personal AI agents and remembered preferences;
- delegated or multi-agent execution;
- tool permissions and capability registries;
- messages, payments, purchases, publication, deletion, deployment, merge, or release;
- retries, timeout-after-dispatch, stale reads, idempotency, and partial failure;
- expiring approvals, credential leases, session identity, and clock windows;
- evidence bundles, audits, tests, CI, and repository implementation.

Do not activate for ordinary brainstorming with no action, authority, identity, capability, time, risk, or factual-verification boundary.

## Operating modes

1. **Explain** — plain-language model.
2. **Model** — graph nodes, edges, links, mismatches, decision.
3. **Audit** — inspect supplied evidence without writes.
4. **Implement** — write only when explicitly requested.
5. **Validate** — tests, CI, evidence, and review.
6. **Merge / Release** — only under explicit authorization.

Never silently expand read-only work into writes.

## Required workflow

### 1. Resolve the action boundary

Identify:

```text
principal
actor
executor
goal
proposed action
target
side effect
authority source
scope and maximum effect
identity source and assurance
delegation chain
capability source, state, and target scope
policy source and revision
memory sources and freshness
risk dimensions
evaluation time and clock source
intent / policy / capability validity windows
execution boundary
authoritative system of record
possible containment and recovery
required final proof
```

### 2. Build the Idea Graph

Include problem, goal, strategy, assumptions, alternatives, safe and unsafe branches, expected outcome, and required verification.

Label every influence from Memory, Policy, Identity, Capability, and Temporal evidence. Idea never authorizes or proves.

### 3. Build the Intent Graph

Include:

```text
intent_id
principal_id
target
scope
constraints
maximum effect
valid_from / valid_until
approval revision
replay or idempotency binding
revocation state
allowed recovery
forbidden actions
authority evidence
```

Historical intent is not current intent. Timeout and uncertainty do not expand scope.

### 4. Build the Identity Graph

Bind:

```text
subject_id
actor_type
issuer
authenticated_at
assurance_level
credential_ref
audience
delegated_by
current
authority_effect = none
```

Identity answers **who**, not **what they may do**.

Rules:

- the current Intent principal must match the evaluated principal;
- the actor and executor must be current identities;
- delegation must be evidenced and may not expand scope;
- identity changes after evaluation require revalidation;
- unknown or mismatched identity fails closed for high-impact actions.

### 5. Build the Policy Graph

Bind every rule to policy ID, issuer, revision, validity, effect, precedence, and evidence.

```text
ALLOW | DENY | CONSTRAIN | REQUIRE_APPROVAL
```

A permissive policy plus missing Intent still yields `HOLD` or `BLOCK`.

### 6. Build the Capability Graph

Represent technical ability separately from authority:

```text
capability_id
provider
action
target_scope
status
bound_subject_id
valid_from / expires_at
reversibility
authority_effect = none
```

Rules:

- `ENABLED` means technically available, not authorized;
- selected capability must match action, target, and verified executor;
- disabled, revoked, expired, unbound, or out-of-scope capability blocks dispatch;
- a capability may never create or broaden Intent;
- capability substitution requires a fresh alignment check.

### 7. Build the Memory Graph

Every memory node needs source, recorded and retrieved time, purpose, freshness, conflict state, evidence, and:

```text
authority_effect = none
```

Memory may influence tone, reversible options, terminology, or search order. It may not authorize sending, paying, deleting, purchasing, publishing, sharing, merging, releasing, or changing recipient, target, or scope.

### 8. Build the Temporal Graph

Model instants, windows, deadlines, and anchors:

```text
time_kind
occurred_at
not_before
not_after
source
clock_domain
max_skew_seconds
confidence
authority_effect = none
```

At minimum bind:

- identity authentication time;
- intent validity window;
- policy effective window;
- capability lease window;
- evaluation time;
- dispatch deadline;
- dispatch and observation time after execution.

Time does not renew authority. A valid evaluation can become stale before dispatch.

### 9. Build the Risk Graph

Include hazard, affected asset or person, causal path, likelihood, impact, detectability, reversibility, uncertainty, mitigation, residual tier, and escalation threshold.

Unknown risk is not low. Critical residual risk means `BLOCK` or escalation; high normally means `HOLD`.

### 10. Build the Fact Graph

Use only observed, evidence-backed events and states. Every material Fact node needs timestamp or order, source, evidence references, before and after state, causal parent, and confidence.

Identity, Intent, Policy, Capability, Memory, Temporal records, or tool status are not proof of a business result.

### 11. Align all graphs

Create explicit links:

```text
Idea → Intent
Identity → Intent
Identity → Capability
Intent → Policy
Memory → Idea
Risk → proposed action or capability
Temporal → Identity
Temporal → Intent
Temporal → Policy
Temporal → Capability
Intent → Fact
Capability → Fact
Idea expectation → Fact
```

A missing link is not alignment.

Detect at least:

```text
IDEA_INTENT_MISMATCH
INTENT_FACT_MISMATCH
IDEA_FACT_MISMATCH
POLICY_INTENT_CONFLICT
POLICY_REVISION_STALE
MEMORY_AUTHORITY_LEAK
MEMORY_STALE
MEMORY_CONFLICT
IDENTITY_INTENT_MISMATCH
IDENTITY_ASSURANCE_INSUFFICIENT
DELEGATION_CHAIN_BROKEN
IDENTITY_CHANGED_AFTER_EVALUATION
CAPABILITY_AUTHORITY_LEAK
CAPABILITY_REVOKED
CAPABILITY_SCOPE_MISMATCH
CAPABILITY_IDENTITY_MISMATCH
CAPABILITY_SUBSTITUTED
TEMPORAL_WINDOW_EXPIRED
TEMPORAL_NOT_YET_VALID
CLOCK_SKEW_EXCEEDED
EVALUATION_DISPATCH_RACE
AUTHORITY_STALE
FACT_MISSING
UNKNOWN_PROMOTED_TO_SUCCESS
SCOPE_EXPANDED_DURING_RECOVERY
DUPLICATE_SIDE_EFFECT
TOOL_SUCCESS_BUSINESS_FAILURE
SECONDARY_HARM_RISK
```

### 12. Decide

```text
verified Identity
→ current Intent
→ mandatory Policy
→ selected Capability
→ Temporal validity
→ Risk gate
→ ACCEPT / HOLD / BLOCK
```

After dispatch, use `UNKNOWN`, `DIVERGED`, or `VERIFIED`. Never use final `SUCCESS` unless it is equivalent to independently verified completion.

### 13. Revalidate at dispatch

Immediately before a protected side effect, re-check:

```text
identity still current
intent still current
policy revision unchanged
capability still enabled and identity-bound
time still inside all required windows
risk not materially changed
nonce / idempotency binding unused
```

If any binding changed, return `HOLD` or `BLOCK`. Do not rely on an earlier planning-time decision.

### 14. Contain and recover

On divergence:

1. stop retries and dependent actions;
2. preserve evidence;
3. identify effects created by this lineage;
4. preserve unrelated effects;
5. evaluate secondary harm;
6. choose minimum targeted containment;
7. remain within current Intent, Policy, Capability, and Temporal bounds;
8. independently read final state.

### 15. Timeout protocol

```text
transport_state = TIMEOUT
business_state = UNKNOWN
execution_state = POSSIBLY_COMMITTED
```

Required chain:

```text
pause retry
→ revalidate identity, intent, policy, capability, and time
→ query authoritative state using original lineage/idempotency binding
→ reconcile existing effect
→ retry only after proven absence and fresh checks
→ independently verify final invariant
```

Forbidden:

```text
blind_retry
new_idempotency_key
announce_success_without_readback
use_memory_as_retry_authority
use_capability_as_authority
reuse_expired_identity_or_intent
dispatch_after_deadline
downgrade_unknown_risk_to_low
```

### 16. Machine-readable output

Compatibility contracts:

```text
assets/three-graph-bundle.schema.json
assets/personal-agent-safety-bundle.schema.json          # v1.1
assets/personal-agent-safety-v1.2-bundle.schema.json     # v1.2
```

The v1.2 bundle contains nine graphs, links, mismatches, memory use, policy/risk/identity/capability/temporal evaluations, decision, containment, recovery, verification, and evidence manifest.

Validate with:

```bash
python3 tools/validate_personal_agent_safety_bundle.py \
  assets/personal-agent-safety.example.json \
  --self-test
```

### 17. Negative controls

Test the unsafe branches relevant to the scenario, including:

- memory used as authority;
- stale or conflicted memory included;
- identity principal mismatch;
- weak or unknown identity assurance;
- broken delegation;
- capability revoked, substituted, unbound, or out of scope;
- capability availability treated as permission;
- expired or not-yet-valid windows;
- clock skew above policy;
- evaluation-to-dispatch race;
- blind retry and new idempotency key;
- premature success;
- stale approval or policy revision;
- business invariant failure;
- recovery outside scope;
- duplicate effect;
- broken graph or evidence integrity.

Negative tests must be synthetic and defensive.

### 18. Completion checks

Before completion verify:

- all nine graphs exist and are acyclic;
- every edge and cross-graph link resolves;
- Fact, Identity, Capability, and Temporal nodes have evidence;
- exactly one current Intent is selected;
- identity principal, actor, executor, and delegation are bound;
- selected capability is enabled, scoped, and bound to the executor;
- evaluation and dispatch occur inside all required windows;
- Memory has provenance and no authority effect;
- Policy revision and precedence are explicit;
- residual Risk is acceptable;
- recovery stays within all current boundaries;
- final invariant is independently verified;
- tests, CI, review, merge, and release status are reported honestly.

## Chat output order

```text
1. Idea Graph
2. Intent Graph
3. Identity Graph
4. Policy Graph
5. Capability Graph
6. Memory Graph
7. Temporal Graph
8. Risk Graph
9. Fact Graph
10. Mismatches
11. Decision
12. Containment / Recovery
13. Independent verification
14. Next safe action
```

## Hard boundaries

Defensive use only. Never invent identity, authority, policy, capability, memory, time, facts, logs, tests, or CI. Never perform external communication, payment, purchase, publication, sharing, irreversible writes, merge, or release without explicit current authorization. Synthetic tests do not prove production certification.

See the architecture and graph-specific references in `references/`.
