---
name: three-graph-agent-safety
description: Separates agent ideas, current user intent, and independently observed facts, then evaluates versioned policy, provenance-aware memory, and explicit risk as separate causal graphs. Use for high-impact agent actions, personal-agent memory, approvals, retries, timeouts, recovery, evidence bundles, repository implementation, and CI validation. Prevents memory, policy, model reasoning, tool status, or UNKNOWN outcomes from becoming invented authority or verified success.
license: MIT
compatibility: Works in chat and with repositories, APIs, policies, memory records, audit logs, and GitHub. External communication, payments, publication, irreversible writes, merge, and release require explicit current authorization.
metadata:
  author: safal207
  version: "1.1.0"
  source-project: ProofPath
---

# Three-Graph Agent Safety v1.1

Model high-impact agent work with three truth graphs and three context-control graphs.

```text
Truth:
Idea Graph   — proposal, assumptions, strategy, expected result
Intent Graph — current user authority, scope, constraints, validity
Fact Graph   — independently evidenced events and states

Controls:
Policy Graph — versioned external rules
Memory Graph — retrieved prior context with provenance and freshness
Risk Graph   — hazards, uncertainty, mitigations, residual risk
```

## Non-substitution invariant

```text
Idea ≠ Intent ≠ Fact
Memory ≠ Intent
Policy allow ≠ user consent
Risk estimate ≠ Fact
UNKNOWN ≠ SUCCESS
```

Memory may personalize reasoning. It may not create, expand, renew, or transfer authority.

```text
IDEA_INTENT_ALIGNED
+ INTENT_CURRENT
+ POLICY_ALLOWED
+ MEMORY_PROVENANCED
+ RISK_ACCEPTABLE
= ACCEPT

ACCEPT
+ FACT_INDEPENDENTLY_VERIFIED
+ FINAL_INVARIANT_MATCHES_INTENT
= SAFE_COMPLETION
```

## Activate when

Use for personal AI agents, remembered preferences, external messages, payments, purchases, publication, deletion, code changes, retries, timeout-after-dispatch, stale reads, approval drift, idempotency, policy checks, risk gates, evidence bundles, CI, and repository changes.

Do not activate for ordinary brainstorming with no action, authority, memory, risk, or factual-verification boundary.

## Operating modes

1. Explain — plain-language model.
2. Model — graph nodes, edges, links, mismatches, decision.
3. Audit — inspect evidence without writes.
4. Implement — write only when explicitly requested.
5. Validate — tests, CI, evidence, review.
6. Merge / Release — only under explicit authorization.

## Required workflow

### 1. Resolve the boundary

Identify actor, goal, proposed action, target, side effect, authority source, scope, constraints, execution boundary, system of record, policy source/revision, memory sources/retrieval time, risk dimensions, recovery, and final proof.

### 2. Idea Graph

Include problem, goal, strategy, assumptions, alternatives, safe/unsafe branches, expected outcome, and required verification. Label assumptions and memory influences. Idea never authorizes or proves.

### 3. Intent Graph

Include `intent_id`, principal, target, scope, constraints, maximum effect, validity, approval revision, replay/idempotency binding, revocation, allowed recovery, forbidden actions, and authority evidence.

Historical approval is not current authority. Memory is never authority. Policy may narrow Intent but cannot silently broaden it. Timeout does not expand scope. `HOLD` and `BLOCK` execute no protected side effect.

### 4. Policy Graph

Bind every rule to policy ID, issuer, revision, validity, condition, effect, precedence, and evidence.

```text
ALLOW | DENY | CONSTRAIN | REQUIRE_APPROVAL
```

A permissive policy plus missing Intent still yields `HOLD` or `BLOCK`. Unknown high-impact policy state fails closed.

### 5. Memory Graph

Every node requires claim, source/reference, recorded/retrieved time, subject, scope, purpose, confidence, freshness, conflict state, evidence, and:

```text
authority_effect = none
```

Memory may inform tone, reversible options, terminology, or which resource to inspect. It may not authorize sending, paying, deleting, purchasing, publishing, sharing, merging, releasing, or changing recipient, target, or scope. Current explicit Intent overrides memory. Stale, conflicted, inferred, superseded, or irrelevant memory cannot be the sole basis for a high-impact decision.

### 6. Risk Graph

Include hazard, affected asset/person, causal path, likelihood, impact, detectability, reversibility, uncertainty, mitigation, residual likelihood/impact/tier, and escalation threshold. Unknown risk is not low. Critical residual risk means `BLOCK` or escalation; high normally means `HOLD`.

### 7. Fact Graph

Use only observed, evidence-backed events and states. Every material Fact node needs timestamp/order, source, evidence references, before/after state, causal parent, and confidence. Tool success, Memory, Policy, or Intent is not proof of a business result.

### 8. Align graphs

Create explicit links:

```text
Idea → Intent
Intent → Policy
Memory → Idea
Memory → Intent comparison
Risk → proposed action
Risk → containment/recovery
Intent → Fact
Idea expectation → Fact
Policy decision → execution boundary
```

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
MEMORY_SCOPE_EXCEEDED
RISK_UNDERSTATED
RISK_UNKNOWN_ACCEPTED
AUTHORITY_STALE
FACT_MISSING
UNKNOWN_PROMOTED_TO_SUCCESS
SCOPE_EXPANDED_DURING_RECOVERY
DUPLICATE_SIDE_EFFECT
TOOL_SUCCESS_BUSINESS_FAILURE
SECONDARY_HARM_RISK
```

A missing link is not alignment.

### 9. Decide

```text
current Intent
→ mandatory Policy
→ Risk gate
→ ACCEPT / HOLD / BLOCK
```

Memory is absent from authority precedence. After dispatch use `UNKNOWN`, `DIVERGED`, or `VERIFIED`. Never use final `SUCCESS` unless equivalent to `VERIFIED`.

### 10. Contain and recover

On divergence: stop retries and dependent actions, preserve evidence, identify agent-created effects, preserve unrelated effects, evaluate secondary harm, choose minimum targeted containment, stay within current Intent and Policy, and independently read final state.

### 11. Timeout protocol

```text
transport_state = TIMEOUT
business_state = UNKNOWN
execution_state = POSSIBLY_COMMITTED
```

Pause retry, query authoritative state with original lineage/idempotency binding, reconcile existing effect, retry only after proven absence and fresh Intent/Policy/Risk checks, then independently verify.

Forbidden: `blind_retry`, `new_idempotency_key`, `announce_success_without_readback`, `use_memory_as_retry_authority`, `downgrade_unknown_risk_to_low`.

### 12. Machine-readable output

Legacy contract: `assets/three-graph-bundle.schema.json`.

Personal Agent Safety v1.1 contract: `assets/personal-agent-safety-bundle.schema.json`.

The v1.1 bundle contains six graphs, links, mismatches, memory use, policy evaluation, risk assessment, decision, containment, recovery, verification, and evidence manifest.

### 13. Negative controls

Test memory-as-authority, stale memory, stale policy, critical/unknown risk accepted, blind retry, new idempotency key, premature success, stale approval, business-invariant failure, recovery outside scope, duplicate effect, broken graph/evidence, and tampered checksum.

### 14. Completion checks

Verify graphs are acyclic, endpoints exist, Fact nodes have evidence, Memory has provenance and no authority, current Intent is explicit, Policy revision/precedence is explicit, residual Risk is acceptable, recovery stays within Intent and Policy, final invariant is independently verified, and tests/CI/reviews/merge/release status are reported honestly.

## Chat output order

```text
1. Idea Graph
2. Intent Graph
3. Policy Graph
4. Memory Graph
5. Risk Graph
6. Fact Graph
7. Mismatches
8. Decision
9. Containment / Recovery
10. Independent verification
11. Next safe action
```

## Hard boundaries

Defensive use only. Never invent authority, policy, memory, facts, logs, tests, or CI. Never perform external communication, payment, purchase, publication, sharing, irreversible writes, merge, or release without explicit current authorization. Synthetic tests do not prove production certification.

See the architecture, Memory, Policy, Risk, mismatch, and completion references in `references/`.
