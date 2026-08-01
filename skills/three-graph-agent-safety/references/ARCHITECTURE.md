# Architecture reference — Personal Agent Safety v1.2

## Nine independent planes

### Truth planes

```text
Idea   — what should happen
Intent — what the principal currently authorizes
Fact   — what evidence proves happened
```

### Control planes

```text
Identity   — who is acting
Policy     — which external rules apply
Capability — what the executor can technically do
Memory     — which prior context informed reasoning
Temporal   — whether bindings are current
Risk       — what harm remains possible
```

No plane may impersonate another.

## Execution chain

```text
Memory ───────────────→ Idea
                         │
Identity → Intent → Policy → Capability → Temporal → Risk
    │        │                                  │
    └────────┴──── alignment / mismatch ────────┘
                         │
                 ACCEPT / HOLD / BLOCK
                         │
                      dispatch
                         │
                       Fact
                         │
             independent verification
                         │
                VERIFIED / DIVERGED
```

## Authority chain

Only current Intent grants user authority.

```text
Identity proves principal
Intent grants scope
Policy narrows or requires approval
Capability proves technical availability
Temporal proves current validity
Risk gates execution
```

Memory, Identity, Policy, Capability, Temporal, Risk, Idea, and Fact all have `authority_effect = none`.

## Revalidation boundary

A planning-time acceptance is not a dispatch token. Immediately before a protected side effect, recompute or refresh:

```text
identity binding
intent revision and validity
policy revision and validity
capability state, scope, and executor binding
clock and deadline
risk conditions
nonce / idempotency state
```

A mismatch yields `HOLD` or `BLOCK`.

## State machine

```text
PROPOSED
→ IDENTITY_BOUND | IDENTITY_UNKNOWN
→ AUTHORIZED | HELD | BLOCKED
→ CAPABILITY_BOUND
→ TEMPORALLY_VALID
→ DISPATCHED
→ OBSERVED | UNKNOWN
→ DIVERGED | VERIFIED
→ CONTAINED
→ RECOVERED
→ VERIFIED
```

`UNKNOWN` remains stable until evidence changes it.

## Evidence boundaries

Keep separate:

```text
producer-authored graph claims
raw identity / policy / capability / clock / system evidence
independent verification output
```

Important artifacts should be digest-bound in the evidence manifest.

## Graph integrity

- unique node, edge, and link IDs;
- acyclic intra-graph edges;
- valid endpoints;
- explicit cross-graph links;
- evidence references resolve inside the evidence root;
- Fact, Identity, Capability, and Temporal nodes carry evidence;
- one lineage binds evaluation, dispatch, recovery, and verification;
- time ordering and clock domain are explicit.
