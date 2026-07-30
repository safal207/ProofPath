# Architecture reference

## Three independent planes

### Idea plane

Contains the agent's reasoning:

```text
problem → hypothesis → proposed strategy → expected outcome
```

It may contain uncertainty and alternatives. It cannot authorize execution and cannot establish reality.

### Intent plane

Contains current authority:

```text
principal → intent → scope → constraints → approval revision → allowed effects
```

It answers whether the action is permitted now. Intent can expire, be revoked, or be narrower than the Idea Graph.

### Fact plane

Contains evidence-backed state transitions:

```text
observed state → dispatch → external transition → readback → verified state
```

It answers what happened, not what should have happened.

## Alignment plane

Alignment is a fourth, derived layer. It does not replace the three graphs.

```text
Idea expectation ─┐
                  ├→ alignment rule → status
Intent constraint ┤
Fact observation ─┘
```

Each alignment record should identify:

```text
alignment_id
idea_node_id
intent_node_id
fact_node_id
rule
status
evidence_refs
```

Allowed statuses:

```text
ALIGNED
MISMATCH
UNKNOWN
NOT_APPLICABLE
```

## State machine

```text
PROPOSED
→ AUTHORIZED | HELD | BLOCKED
→ DISPATCHED
→ OBSERVED | UNKNOWN
→ DIVERGED | VERIFIED
→ CONTAINED
→ RECOVERED
→ VERIFIED
```

`UNKNOWN` is stable until new evidence arrives. It is not a temporary spelling of success.

## Trust boundaries

1. Model output is a proposal.
2. User/policy authority is external to model reasoning.
3. Executor and system of record are external to both.
4. Raw evidence is distinct from a producer-authored graph.
5. Independent verification must recompute conclusions from raw evidence when practical.

## Graph integrity rules

- unique node and edge IDs;
- acyclic causal edges;
- valid edge endpoints;
- explicit causal parents;
- timestamps or ordering evidence for Fact nodes;
- evidence references resolve inside the evidence root;
- no path traversal;
- content digests for important request, authority, and result artifacts;
- one lineage binding across dispatch, reconciliation, recovery, and verification.

## Safe side-effect protocol

```text
proposal
→ build Idea Graph
→ load current Intent Graph
→ compare proposal with authority
→ ACCEPT / HOLD / BLOCK
→ dispatch once
→ record Fact Graph
→ authoritative readback
→ align graphs
→ contain divergence
→ recover within intent
→ independently verify final invariant
```
