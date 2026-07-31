# Proof of Causal Integrity Multi-Graph Transition Space v0.1

Status: executable experimental profile  
Profile: `proofpath.poci.transition-space.v0.1`

## Purpose

A PoCI Action Proof Envelope proves one bounded action. The multi-graph
transition-space profile proves that the same action is coherent across several
independent dimensions instead of collapsing causality, authority, state,
evidence, and time into one status field.

The unit of verification is a **transition cell**:

```text
cell = (
  intent coordinate,
  authority coordinate,
  cause coordinate,
  state coordinate,
  evidence coordinates,
  time coordinate
)
```

Three ordered cells form the v0.1 path:

```text
proposal -> execution -> observation
```

A cell is acceptable only when every coordinate exists, adjacent coordinates
are connected in their own graphs, and the coordinates bind back to the same
Action Proof Envelope.

## Six graphs

| Graph | Question | Primary ecosystem source |
|---|---|---|
| `intent` | What outcome was declared and when is it satisfied? | ProofPath / Ibex transition intention |
| `authority` | Who granted, delegated, and executed the action? | ProofPath authority / CML permission lineage |
| `cause` | Why did proposal become execution and observation? | CML / TIP cause |
| `state` | Which state transition actually occurred? | TIP / T-Trace / LTP |
| `evidence` | Which exact bytes support each phase? | Ibex manifest and PoCI artifacts |
| `time` | In what order did the transition occur and persist? | T-Trace / LiminalDB continuity |

The graphs remain independent. A valid cause path does not repair a broken
authority path, and a valid final result does not repair a reversed time path.

## Transition-space document

A document contains:

- `profile` and `schema_version`;
- `envelope_binding`;
- exactly six named graphs;
- transition cells;
- one ordered path;
- pinned ecosystem adapters;
- `space_integrity` with a domain-separated SHA-256 root.

Each graph contains local nodes and directed edges. Edges do not silently cross
graph boundaries. Cross-graph composition occurs only through transition-cell
coordinates.

## Core invariants

1. Every required graph exists.
2. Node identifiers are unique inside a graph.
3. Every edge endpoint exists inside the same graph.
4. Every cell has coordinates for all six graphs.
5. Evidence coordinates contain at least one evidence node.
6. The ordered path is exactly `proposal -> execution -> observation`.
7. Each non-entry cell names its ordered predecessor.
8. Adjacent cause, state, intent, authority, and time coordinates are equal or
   reachable through directed graph edges.
9. Adjacent time coordinates are strictly increasing.
10. Phase-specific evidence roles are present:
    - proposal: `intent.signature`, `proposal.parameters`;
    - execution: `execution.receipt`;
    - observation: `observed.result`, `witness.statement`.
11. Intent, authority, causal parent, proposal, receipt, result, evidence
    digests, and phase timestamps match the bound Action Proof Envelope.
12. The base PoCI verifier must independently resolve the envelope to `ACCEPT`.
13. All six adapter contracts are pinned and complete.
14. A declared transition-space root must match the recomputed canonical root.

## Decision semantics

The profile uses the PoCI precedence:

```text
CHALLENGE > BLOCK > HOLD > ACCEPT
```

- `ACCEPT` — all graph-local and cross-graph invariants hold.
- `HOLD` — required coordinates or adapter evidence are incomplete.
- `BLOCK` — graph structure, path, authority, intent, cause, or adapter role is
  invalid.
- `CHALLENGE` — time, evidence, envelope binding, or integrity commitments
  conflict.

## Reason codes

| Code | Decision | Meaning |
|---|---|---|
| `GRAPH_REQUIRED_MISSING` | BLOCK | One of six graphs is absent |
| `GRAPH_NODE_DUPLICATE` | BLOCK | A graph repeats a node id |
| `GRAPH_EDGE_DANGLING` | BLOCK | An edge references an absent node |
| `CELL_COORDINATE_MISSING` | HOLD | A cell lacks a graph coordinate |
| `CELL_COORDINATE_UNKNOWN` | BLOCK | A coordinate references an absent node |
| `TRANSITION_PATH_DISCONNECTED` | BLOCK | Cell order or predecessor linkage is invalid |
| `CAUSE_PATH_DISCONNECTED` | BLOCK | Adjacent cause coordinates are not connected |
| `STATE_PATH_DISCONNECTED` | BLOCK | Adjacent state coordinates are not connected |
| `INTENT_PATH_DISCONNECTED` | BLOCK | Adjacent intent coordinates are not connected |
| `AUTHORITY_PATH_DISCONNECTED` | BLOCK | Adjacent authority coordinates are not connected |
| `TIME_ORDER_VIOLATION` | CHALLENGE | Adjacent cells are not strictly ordered |
| `INTENT_BINDING_MISMATCH` | BLOCK | Intent graph differs from the envelope |
| `AUTHORITY_BINDING_MISMATCH` | BLOCK | Authority graph differs from the envelope |
| `CAUSE_BINDING_MISMATCH` | BLOCK | Cause root differs from the causal parent |
| `EVIDENCE_BINDING_MISMATCH` | CHALLENGE | Evidence roles or digests differ |
| `TIME_BINDING_MISMATCH` | CHALLENGE | Time nodes differ from envelope timestamps |
| `ADAPTER_BINDING_MISSING` | HOLD | Required adapter or field is absent |
| `ADAPTER_SOURCE_UNSUPPORTED` | BLOCK | Adapter profile is not pinned |
| `ADAPTER_ROLE_MISMATCH` | BLOCK | Adapter points at the wrong graph coordinate |
| `ENVELOPE_NOT_ACCEPTED` | inherited | The base PoCI envelope did not accept |
| `TRANSITION_SPACE_ROOT_MISMATCH` | CHALLENGE | Declared space root differs |

## Canonical root

The verifier deep-copies the transition space, sets
`space_integrity.space_root` to `null`, serializes canonical JSON, prepends:

```text
proofpath:poci:v0.1:transition-space\n
```

and computes SHA-256.

## Reviewer commands

```bash
python3 scripts/verify_poci_transition_space.py \
  examples/poci-witness/transition-space/valid.accept.json \
  --envelope examples/poci-witness/fixtures/valid-action.accept.json \
  --pretty

python3 scripts/verify_poci_transition_space.py \
  examples/poci-witness/transition-space/manifest.json \
  --manifest --pretty

python3 -m unittest discover -s tests -p 'test_poci*.py' -v
```

## Non-claims

This profile does not prove objective truth, model correctness, witness
independence, distributed consensus, or legal compliance. It verifies that
committed evidence is mutually coherent across six explicitly modeled
transition dimensions.
