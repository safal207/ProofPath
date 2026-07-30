---
name: three-graph-agent-safety
description: Separates an AI agent's idea, the user's authorized intent, and independently observed facts into three causal graphs. Use when a user asks to analyze, design, audit, test, or implement high-impact agent actions, retries, timeouts, stale observations, approval drift, tool-success/business-failure cases, evidence bundles, or safe recovery. Detects Idea–Intent–Fact mismatches and forbids treating assumptions, permissions, or UNKNOWN outcomes as verified success.
license: MIT
compatibility: Works in chat from pasted scenarios and files; best with repository, tool, API, audit-log, or GitHub access. Repository writes and merges require explicit user authorization.
metadata:
  author: safal207
  version: "1.0.0"
  source-project: ProofPath
---

# Three-Graph Agent Safety

Analyze every high-impact agent action through three separate causal graphs:

```text
Idea Graph   — what the agent believes should happen and why
Intent Graph — what the user actually authorized, including scope and limits
Fact Graph   — what independently observable evidence proves happened
```

## Core invariant

```text
Idea ≠ Intent ≠ Fact
```

Never promote:

- an idea into authority;
- authority into proof of execution;
- a tool response into a business result;
- missing evidence into success;
- `UNKNOWN` into either `SUCCESS` or a fresh authorization.

Safe completion requires:

```text
IDEA_ALIGNED
+ INTENT_AUTHORIZED
+ FACT_INDEPENDENTLY_VERIFIED
= SAFE_COMPLETION
```

## Activate this skill when

Use this skill when the user asks to:

- draw or build Idea, Intent, and Fact graphs;
- diagnose why an agent action, API call, payment, deletion, message, code change, or workflow became unsafe;
- handle timeout-after-dispatch, stale reads, retries, idempotency, duplicate effects, approval revocation, or partial failure;
- distinguish model reasoning from user authority and real-world state;
- audit tool success against business invariants;
- design containment, recovery, and independent verification;
- create machine-readable traces, evidence bundles, tests, CI checks, or repository changes;
- compare a planned action with what was allowed and what actually happened.

Do not activate for ordinary brainstorming with no meaningful action, authority, or factual-verification boundary.

## Operating modes

Infer the narrowest sufficient mode:

1. **Explain** — describe the three graphs in plain language.
2. **Model** — produce graph nodes, edges, invariants, mismatches, and recovery.
3. **Audit** — inspect supplied evidence without writing.
4. **Implement** — modify code or create repository artifacts only when explicitly requested.
5. **Validate** — run tests, CI, evidence checks, and review analysis.
6. **Merge** — merge only under explicit authorization.

Never silently expand read-only work into writes.

## Required workflow

### 1. Resolve the action boundary

Identify:

```text
actor
requested goal
proposed action
target
side effect
authority source
scope
constraints
execution boundary
authoritative system of record
possible recovery
required final proof
```

Use connected repository or tool data to resolve ambiguity before asking the user.

### 2. Build the Idea Graph

The Idea Graph represents reasoning and strategy, not permission or truth.

Minimum nodes:

```text
problem
goal
proposed strategy
risk
safe branch
unsafe branch
expected outcome
required verification
```

Every strategy node must answer:

- Why is this action expected to help?
- Which assumptions does it depend on?
- What could make the assumption stale or false?
- What observation would confirm or reject it?

Label assumptions explicitly. An assumption is never a Fact node.

### 3. Build the Intent Graph

The Intent Graph represents current authority.

Minimum fields:

```text
intent_id
intent_code
principal
target
scope
constraints
maximum effect
validity window
approval revision
idempotency or replay binding
revocation state
allowed recovery
forbidden actions
```

Rules:

- Authority must come from the user, policy, approval record, or trusted application layer.
- Historical approval is evidence of past authority, not proof of current authority.
- Timeout, tool error, or agent uncertainty does not expand scope.
- A new idempotency key, recipient, target, amount, or destructive scope requires authority unless the original contract explicitly permits it.
- Revoked or expired authority blocks dispatch.
- `HOLD` and `BLOCK` must not cause the protected side effect.

### 4. Build the Fact Graph

The Fact Graph contains only observed events and evidence-backed state.

Minimum node fields:

```text
node_id
event_or_state
observed_at
source
evidence_refs
state_before
state_after
causal_parent
confidence
```

Valid evidence may include:

- request and response records;
- server, queue, ledger, database, or audit logs;
- authoritative readback;
- stable transaction or operation identifiers;
- approval revisions;
- checksums and manifests;
- independent verifier output.

Statements such as “probably succeeded”, “the tool returned 200”, or “the agent intended to do it” are not final business facts.

### 5. Align the graphs

Create explicit mappings:

```text
idea node → intent node
intent node → fact node
idea expectation → observed result
```

Evaluate at least:

- `IDEA_INTENT_MISMATCH`
- `INTENT_FACT_MISMATCH`
- `IDEA_FACT_MISMATCH`
- `AUTHORITY_STALE`
- `FACT_MISSING`
- `UNKNOWN_PROMOTED_TO_SUCCESS`
- `SCOPE_EXPANDED_DURING_RECOVERY`
- `DUPLICATE_SIDE_EFFECT`
- `TOOL_SUCCESS_BUSINESS_FAILURE`

A missing mapping is not alignment.

### 6. Choose the decision

Use these meanings:

- `ACCEPT` — action is authorized and safe to dispatch now.
- `HOLD` — more authority, fresh state, or evidence is required.
- `BLOCK` — action is unauthorized, replayed, out of scope, or unsafe.
- `UNKNOWN` — execution outcome cannot yet be established.
- `DIVERGED` — observed state violates intent or the expected invariant.
- `VERIFIED` — authoritative evidence proves the required final state.

Do not use `SUCCESS` as a final verdict unless it is equivalent to `VERIFIED`.

### 7. Contain before recovering

When Fact diverges from Intent:

1. stop retries and dependent actions;
2. preserve evidence;
3. identify effects created by this agent action;
4. avoid touching unrelated external effects;
5. select the minimum targeted containment;
6. confirm recovery remains inside the original Intent Graph;
7. independently read the final state.

Containment must not create a larger secondary harm.

### 8. Treat timeout correctly

After dispatch timeout:

```text
transport_state = TIMEOUT
business_state = UNKNOWN
execution_state = POSSIBLY_COMMITTED
```

Required chain:

```text
pause retry
→ query authoritative state using original lineage/idempotency binding
→ reconcile existing effect
→ retry only if absence is proven and original authority still permits it
→ independently verify final invariant
```

Forbidden:

```text
blind_retry
new_idempotency_key
announce_success_without_readback
create_new_intent_to_hide_uncertainty
```

### 9. Produce machine-readable output

When useful, emit a bundle conforming to `assets/three-graph-bundle.schema.json` with:

```text
idea_graph
intent_graph
fact_graph
alignment
mismatches
decision
containment
recovery
verification
evidence_manifest
```

Keep producer-authored claims separate from raw evidence and independent verifier results.

### 10. Test negative causal paths

At minimum test the unsafe branch relevant to the scenario. Common controls:

- blind retry after unknown outcome;
- retry with a new idempotency key;
- success announcement before authoritative readback;
- dispatch using stale or revoked approval;
- tool/API success while business invariant is false;
- recovery outside original scope;
- duplicate effect;
- unrelated effect removed during containment;
- missing evidence references;
- graph cycle or broken edge;
- tampered evidence or checksum.

Negative tests must be synthetic and defensive.

### 11. Validate completion

Before declaring completion, verify:

- all three graphs exist and are acyclic;
- every edge endpoint exists;
- each Fact node has evidence;
- every high-impact action maps to current authority;
- no forbidden action appears in the Fact Graph;
- recovery remains within Intent;
- final state is independently read;
- the final invariant matches the user's intent;
- open risks and non-claims are stated honestly.

## Chat output contract

For ordinary chat, use this compact order:

```text
1. Idea Graph
2. Intent Graph
3. Fact Graph
4. Mismatches
5. Decision
6. Containment / Recovery
7. Independent verification
8. Next safe action
```

For repository implementation, also include:

```text
branch / PR
files changed
tests and CI
evidence bundle
benchmark result
merge status
remaining risk
```

## Hard boundaries

- Defensive use only.
- Do not invent authority, observations, logs, test results, or CI status.
- Do not treat model prose as signed user intent.
- Do not claim independent verification when the same producer merely restated its own output.
- Do not perform irreversible writes without authorization.
- Do not merge without explicit authorization.
- Do not use real secrets, real destructive targets, or offensive payloads in fixtures.
- Do not claim production certification or universal safety from synthetic scenarios.

See [architecture](references/ARCHITECTURE.md), [mismatch catalog](references/MISMATCH_CATALOG.md), and [completion checklist](references/COMPLETION_CHECKLIST.md).
