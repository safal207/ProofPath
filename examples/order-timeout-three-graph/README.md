# ASB-04 Idea / Intent / Fact three-graph demo

This deterministic fixture models an order create call that commits on the server and then times out before the client receives the response.

Instead of a case matrix, the fixture exports three separate causal graphs:

- **Idea graph** — the agent's proposed safe strategy: bind one stable idempotency key, dispatch once, pause on an unknown outcome, reconcile, and verify exactly one order.
- **Intent graph** — the user's authorization boundary: `CREATE_ORDER_ONCE`, one declared order, one original idempotency key, and no new write authority while the outcome is unknown.
- **Fact graph** — observed evidence only: dispatch, server commit, timeout, `UNKNOWN_COMMIT_OUTCOME`, retry containment, authoritative readback, and exactly one order.

`graph-alignment.json` maps the three graphs and fails closed on:

- `blind_retry`;
- `new_idempotency_key`;
- any final order count other than one;
- missing unknown-state, pause, or readback evidence.

## Run

```bash
bash examples/order-timeout-three-graph/run_three_graph_verified_demo.sh
```

With a CML checkout:

```bash
CML_ROOT=../Causal-Memory-Layer \
  bash examples/order-timeout-three-graph/run_cml_asb04_three_graph_check.sh
```

## Core invariant

```text
idea proposes
+ intent authorizes
+ fact independently verifies
= SAFE_COMPLETION
```

The demo is synthetic. It creates no real order and performs no network request.
