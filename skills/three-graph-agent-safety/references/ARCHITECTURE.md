# Architecture reference — Personal Agent Safety v1.1

## Core truth planes

### Idea plane

```text
problem → assumptions → strategy → expected outcome → required proof
```

Reasoning only. It cannot authorize execution or establish reality.

### Intent plane

```text
principal → current intent → scope → constraints → allowed effects
```

Current user authority only. It can expire, be revoked, or be narrower than the Idea Graph.

### Fact plane

```text
observed state → dispatch → external transition → readback → verified state
```

Evidence-backed reality only.

## Context-control planes

### Policy plane

```text
issuer → policy revision → rule → condition → effect → precedence
```

Policy may deny or narrow Intent. A permissive rule does not create Intent.

### Memory plane

```text
source → recorded claim → retrieval → freshness/conflict → permitted use
```

Memory is contextual evidence about the past. It has `authority_effect=none`.

### Risk plane

```text
hazard → causal path → likelihood/impact → mitigation → residual risk
```

Risk is an assessment. It influences the gate but does not create authority or fact.

## Decision architecture

```text
                    ┌──────── Memory Graph ────────┐
                    │ informs strategy             │
                    │ never authorizes              │
                    ▼                              │
Idea Graph → compare with Intent Graph → Policy Graph
     │                  │                 │
     │                  └──── authority ──┘
     │
     └──────────────→ Risk Graph
                         │
                         ▼
                ACCEPT / HOLD / BLOCK
                         │
                         ▼
                      Executor
                         │
                         ▼
                     Fact Graph
                         │
                         ▼
           DIVERGED / UNKNOWN / VERIFIED
```

## Authority precedence

```text
current Intent
→ mandatory Policy
→ Risk gate
→ execution decision
```

Memory is deliberately absent from this chain.

## Alignment links

Each link should contain:

```text
link_id
from_graph
from_node_id
to_graph
to_node_id
rule
status
evidence_refs
```

Statuses:

```text
ALIGNED
MISMATCH
UNKNOWN
NOT_APPLICABLE
```

## State machine

```text
PROPOSED
→ CONTEXT_LOADED
→ INTENT_CURRENT | INTENT_MISSING
→ POLICY_ALLOWED | POLICY_DENIED | POLICY_UNKNOWN
→ RISK_ACCEPTABLE | RISK_HIGH | RISK_UNKNOWN
→ ACCEPTED | HELD | BLOCKED
→ DISPATCHED
→ OBSERVED | UNKNOWN
→ DIVERGED | VERIFIED
→ CONTAINED
→ RECOVERED
→ VERIFIED
```

`UNKNOWN` is stable until new evidence arrives.

## Trust boundaries

1. Model output is a proposal.
2. Memory is retrieved context, not current permission.
3. User Intent is external to model reasoning and memory.
4. Policy is versioned external control.
5. Risk is an explicit assessment with uncertainty.
6. Executor and system of record are external.
7. Raw evidence is distinct from producer-authored graphs.
8. Independent verification recomputes conclusions from raw evidence when practical.

## Graph integrity rules

- unique graph, node, edge, and link IDs;
- acyclic causal edges;
- valid edge and link endpoints;
- explicit causal parents;
- Fact nodes have timestamps and evidence;
- Memory nodes have provenance, purpose, freshness, conflict state, and `authority_effect=none`;
- Policy nodes bind an issuer and exact revision;
- Risk nodes preserve likelihood, impact, uncertainty, mitigation, and residual risk;
- evidence references resolve inside the evidence root;
- no path traversal;
- one lineage binding across dispatch, reconciliation, recovery, and verification.

## Personal agent side-effect protocol

```text
proposal
→ build Idea Graph
→ load current Intent Graph
→ load exact Policy Graph revision
→ retrieve minimal relevant Memory Graph
→ build Risk Graph
→ align context and authority
→ ACCEPT / HOLD / BLOCK
→ dispatch once
→ record Fact Graph
→ authoritative readback
→ contain divergence
→ recover within Intent and Policy
→ independently verify final invariant
```
