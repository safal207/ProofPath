# Causal-temporal transition conformance

This corpus verifies a product-state graph for one immutable subject hash across
three independent axes:

- origin: `UNCOMMITTED → COMMITTED → REPRODUCIBLE`;
- freshness: `UNKNOWN ↔ FRESH ↔ STALE`;
- temporal: `UNANCHORED → PENDING → ANCHORED` with bounded failure states.

The design prevents one fact from overwriting another. A source can be stale
while its historical bytes remain reproducible and temporally anchored.

## Run

```bash
python3 scripts/check_causal_temporal_graph.py \
  conformance/guardrail-decision-v1/causal-temporal/graph.json \
  conformance/guardrail-decision-v1/causal-temporal/vectors.json

python3 scripts/check_causal_temporal_graph.py \
  conformance/guardrail-decision-v1/causal-temporal/graph.json \
  conformance/guardrail-decision-v1/causal-temporal/sealed-vectors.json
```

Expected results:

```text
Causal-temporal graph conformance passed: 12
Causal-temporal graph conformance passed: 6
```

## What the unsealed corpus catches

- illegal or undeclared transitions;
- sequence gaps and duplicates;
- broken parent links;
- event-byte mutation;
- subject-hash drift;
- local observation-time regression;
- undeclared mutation of a second state axis;
- missing evidence;
- temporal-anchor success without block/time bounds;
- attempted `ANCHORED → PENDING` rollback.

## What the sealed corpus adds

A trace seal commits to:

```text
subject_hash + total_events + terminal_event_id + sealed_at
```

This catches a silently dropped suffix inside the declared boundary. Without a
seal, a complete-looking prefix cannot prove that no tail was removed.

## Scope

The checker validates the consistency and bounded completeness of recorded
events. It cannot prove that the chosen seal boundary corresponds to every
real-world event that should have happened; boundary governance remains a
separate concern.
