# PoCI ecosystem adapters and multi-graph transition space v0.1

Status: experimental executable profile  
Profile: `proofpath.poci.multigraph.v0.1`  
Parent protocol: `proofpath.poci.v0.1`  
Backlog: ProofPath #191

## 1. Purpose

A single causal chain is useful but insufficient for high-trust agent actions.

An action may have a valid-looking parent cause while still failing because:

- the actor was not authorized;
- the intended destination changed;
- the observed state does not match the committed transition;
- the evidence bytes belong to another execution;
- the timestamps regress;
- durable storage resumed from an older checkpoint.

PoCI multi-graph v0.1 represents one reviewed action as a coordinate in several independently checkable graphs.

```text
transition cell =
  (
    causal coordinate,
    intent coordinate,
    authority coordinate,
    state-transition coordinate,
    evidence coordinate,
    time/continuity coordinate
  )
```

The profile does not merge all information into one giant graph. It preserves six bounded graphs and then verifies explicit cross-graph bindings.

## 2. Product space

The implemented product space is:

```text
G = Gcause × Gintent × Gauthority × Gstate × Gevidence × Gtime
```

An action is acceptable only when every required transition cell resolves to one node in every graph and the cross-graph invariants hold.

### 2.1 Causal graph

Answers:

> Why did this action occur, and does its responsibility lineage reach the declared parent cause?

Primary source:

- Causal Memory Layer exported causal records.

Supporting source:

- TIP tension and interpreted cause.

Canonical relationships:

```text
tension -> motivates -> interpreted cause
parent cause -> supports -> interpreted cause
parent causal record -> causes -> child causal record
```

### 2.2 Intent graph

Answers:

> What did the principal want, how was it refined, and what result was expected?

Primary sources:

- PoCI intent and proposal;
- TIP justified action and reviewed next state.

Canonical path:

```text
principal -> intent -> proposal -> justified action -> expected result
```

### 2.3 Authority graph

Answers:

> Who owned the decision, which grant delegated power, and which executor could act?

Primary sources:

- PoCI authority and causal context;
- CML permission lineage.

Canonical path:

```text
principal -> authorizing decision -> grant
grant -> agent
grant -> executor
```

### 2.4 State-transition graph

Answers:

> From which state did the system leave, what boundary did it cross, and which destination was acknowledged?

Primary sources:

- TIP transition;
- T-Trace `sense -> transition -> commit`;
- Ibex transition-phase origin, boundary, and destination;
- PoCI execution and observed result.

Canonical path:

```text
origin state
  -> transition
  -> crossed/running state
  -> execution
  -> destination state
  -> acknowledged commit
```

### 2.5 Evidence graph

Answers:

> Which exact artifacts support intent, execution, result, witness judgment, and durable archival?

Primary sources:

- PoCI evidence inventory;
- Ibex evidence-role references;
- LiminalDB checkpoint;
- PoCI verifier output.

Canonical relationships:

```text
artifact -> committed by -> Action Proof Envelope
envelope -> evaluated by -> verifier
witness statement -> supports -> verifier
verifier -> durably anchored as -> checkpoint
```

### 2.6 Time and continuity graph

Answers:

> Did events occur in a coherent order, and may the side effect continue, retry, stop, or require revalidation?

Primary sources:

- PoCI RFC3339 timestamps;
- Ibex monotonic transition-phase timestamps;
- T-Trace ordering;
- LiminalDB continuity decision and checkpoint sequence.

Two clocks remain explicit:

- wall-clock RFC3339;
- monotonic nanoseconds.

The adapter does not invent an offset between them. It validates ordering inside each clock and binds both to the same transition cell.

## 3. Transition cells

The reference example creates three cells.

### Proposal cell

```text
cause        = PoCI/CML authorizing decision
intent       = PoCI proposal
authority    = PoCI grant
state        = T-Trace transition
evidence     = signed intent artifact
time         = proposal timestamp
```

### Execution cell

```text
cause        = CML execution record
intent       = TIP justified action
authority    = PoCI executor
state        = PoCI execution node
evidence     = execution receipt
time         = execution completion timestamp
```

### Observation cell

```text
cause        = CML result observation
intent       = PoCI observed result
authority    = principal accountability boundary
state        = reviewed destination state
evidence     = independent verification
time         = durable continuity checkpoint
```

The required cell path is:

```text
proposal -> execution -> observation
```

## 4. Adapter roles

| Adapter | Repository | Bounded responsibility | Must not become |
|---|---|---|---|
| TIP | `safal207/transition-intelligence-protocol` | Justified movement from state, tension and cause to action and review | Runtime executor or evidence store |
| CML | `safal207/Causal-Memory-Layer` | Causal parent, permission lineage and responsibility ancestry | General trace engine |
| LTP / T-Trace | `safal207/L-THREAD-Liminal-Thread-Secure-Protocol-LTP-`, `safal207/T-Trace` | Deterministic path, acknowledged transitions and replay continuity | Authority oracle |
| LiminalDB | `safal207/LiminalDB` | Durable checkpoint, anti-rollback boundary and continuation decision | Universal causal reasoner |
| Ibex Agent Verification | `safal207/ibex-agent-verification` | Exact evidence roles, manifest provenance and transition-phase verification | Intent owner |
| ProofPath PoCI | `safal207/ProofPath` | Portable envelope, multi-graph binding, decision and independent verification | Mandatory host for every external runtime |

## 5. Field-level mappings

### TIP to graph space

| TIP field | Multi-graph destination |
|---|---|
| `state.actors` | Intent/authority actor coverage |
| `tension` | Causal graph tension node |
| `cause.parent_cause` | Cross-binding to PoCI `causal_context.parent_id` |
| `transition.from` | Origin state |
| `transition.to` | Destination state |
| `transition.trigger` | Authorizing cause |
| `action.owner` | PoCI proposal agent |
| `review.evidence` | Evidence-role identifiers |
| `review.next_state` | Reviewed destination |

### CML to graph space

| CML field | Multi-graph destination |
|---|---|
| `id` | Causal node id |
| `parent_cause` | `causes` edge |
| `actor` | Responsibility/actor binding |
| `action` | Causal action kind |
| `permitted_by` | Permission lineage attribute |
| `timestamp` | Causal local ordering |
| record class / CTAG projection | Causal class attribute |

### T-Trace to graph space

| T-Trace field | Multi-graph destination |
|---|---|
| `thread_id` | Transition-thread boundary |
| `sense.state` | Origin state |
| `transition.id` | State-transition coordinate |
| `transition.from/to` | State edge |
| `transition.cause_id` | Cross-binding to causal graph |
| `commit.state` | Acknowledged destination |
| `commit.result_ref` | Cross-binding to evidence graph |
| `ts` | Wall-clock transition ordering |

### LiminalDB to graph space

The current adapter consumes a narrow exported receipt rather than importing LiminalDB runtime code.

| Exported receipt field | Multi-graph destination |
|---|---|
| `authorization_ref` | PoCI intent binding |
| `observation_ref` | PoCI observed-result binding |
| `response_integrity` | Evidence confidence boundary |
| `causal_audit_ref` | PoCI causal-parent binding |
| `continuity_decision` | Time/continuity terminal node |
| `checkpoint_id` | Durable checkpoint node |
| `checkpoint_digest` | Evidence commitment |
| `previous_checkpoint_digest` | Checkpoint ancestry |
| `sequence` | Anti-rollback ordering |

### Ibex transition phase to graph space

| Ibex field | Multi-graph destination |
|---|---|
| `transition_id` | T-Trace transition binding |
| `time.*` | Monotonic time graph |
| `intention.intent_id` | PoCI intent binding |
| `space.origin` | TIP/T-Trace origin |
| `space.boundary` | Transition metadata |
| `space.destination` | TIP/T-Trace destination |
| `evidence.intent_ref` | PoCI signature artifact |
| `evidence.action_ref` | PoCI receipt artifact |
| `evidence.result_ref` | PoCI result artifact |
| `evidence.verification_ref` | PoCI witness statement |
| `verification.*` | Transition completion checks |

## 6. Cross-graph invariants

The reference builder verifies these invariants.

### Cause

- TIP parent cause equals PoCI causal parent.
- T-Trace transition cause equals PoCI causal parent.
- CML observed result descends from that parent.

### Actor and authority

- TIP actor set covers principal, agent, executor and observer.
- TIP action owner equals PoCI proposal agent.
- CML lineage contains the PoCI decision, grant, proposal, execution and observation.

### Transition space

- TIP origin equals T-Trace origin and Ibex origin.
- TIP destination equals T-Trace committed state and Ibex destination.
- Ibex transition id equals T-Trace transition id.

### Evidence

- Ibex four evidence roles equal the four PoCI committed artifact ids.
- T-Trace committed result equals PoCI observed result.
- LiminalDB observation reference equals PoCI observed result.

### Time and continuity

- T-Trace timestamps are monotonic.
- Ibex phase timestamps are strictly increasing.
- LiminalDB checkpoint sequence cannot regress.
- A terminal observed one-shot result requires continuity decision `stop`.

### Graph structure

- Node ids are unique inside each graph.
- Every edge endpoint exists.
- Every transition-cell coordinate resolves to a node.
- Graph roots and the product-space root are deterministic under object-key reordering.

## 7. Decision semantics

The multi-graph profile uses the PoCI precedence:

```text
CHALLENGE > BLOCK > HOLD > ACCEPT
```

- `ACCEPT`: all adapters and cross-bindings agree.
- `HOLD`: evidence may become sufficient after revalidation or completion.
- `BLOCK`: required structure, parentage, chronology or authority is missing.
- `CHALLENGE`: two committed graphs contradict one another or durable evidence suggests substitution/rollback.

## 8. Reason codes

| Code | Meaning |
|---|---|
| `MULTIGRAPH_SOURCE_INVALID` | Source bundle is malformed |
| `ADAPTER_SET_INCOMPLETE` | One or more required adapters are absent |
| `ADAPTER_VERSION_UNPINNED` | Repository/protocol/version/mode is implicit |
| `ADAPTER_TIP_INVALID` | TIP record is incomplete or not committed |
| `ADAPTER_CML_INVALID` | CML record structure/order is invalid |
| `ADAPTER_CML_MISSING_PARENT` | CML parent does not exist before the child |
| `ADAPTER_TTRACE_INVALID` | T-Trace sequence is invalid |
| `ADAPTER_TTRACE_TIME_ORDER` | T-Trace timestamps regress |
| `ADAPTER_LIMINALDB_INVALID` | Continuity receipt is malformed/incomplete |
| `ADAPTER_LIMINALDB_ROLLBACK` | Checkpoint sequence or ancestry indicates rollback |
| `ADAPTER_IBEX_INVALID` | Transition phase is incomplete or chronologically invalid |
| `CROSS_GRAPH_CAUSE_MISMATCH` | Cause ids disagree |
| `CROSS_GRAPH_ACTOR_MISMATCH` | Actors or owners disagree |
| `CROSS_GRAPH_TRANSITION_MISMATCH` | Transition ids/origins disagree |
| `CROSS_GRAPH_DESTINATION_MISMATCH` | Destination states disagree |
| `CROSS_GRAPH_EVIDENCE_MISMATCH` | Evidence roles point to different artifacts |
| `CROSS_GRAPH_CONTINUITY_MISMATCH` | Durable continuity binds another action or requires review |
| `GRAPH_NODE_DUPLICATE` | A graph contains duplicate node ids |
| `GRAPH_EDGE_DANGLING` | An edge references an absent node |
| `TRANSITION_CELL_UNBOUND` | A cell coordinate cannot be resolved |
| `MULTIGRAPH_ROOT_MISMATCH` | Declared product root differs from computed root |
| `MULTIGRAPH_INTERNAL_FAIL_CLOSED` | Builder failed closed |

## 9. Dependency policy

PoCI core remains usable without any external repository.

The reference builder follows these rules:

1. External systems export JSON.
2. ProofPath does not import their Python or Rust packages.
3. Every adapter declares repository, protocol, version and mode.
4. Adapter formats are pinned at the boundary.
5. No adapter may silently query network state during verification.
6. Missing adapters fail explicitly.
7. External runtime upgrades require an adapter-version change and new negative tests.
8. Graph roots commit normalized exported data, not mutable runtime objects.

This prevents circular mandatory dependencies.

## 10. Current implementation versus future architecture

Implemented now:

- dependency-free Python builder;
- six independently rooted graphs;
- three transition cells;
- one valid mocked cross-repository source bundle;
- deterministic product-space root;
- adapter and cross-graph findings;
- mutation tests for destination substitution, missing CML parent, time regression, rollback, evidence substitution, actor mismatch and revalidation;
- CI report artifact.

Not implemented:

- live imports from external repositories;
- multi-process witness networking;
- distributed graph storage;
- graph query language;
- automatic dispute resolution;
- economic settlement or staking;
- cryptographic signatures over each external export;
- proof that external sensors or providers report objective truth.

## 11. Migration to multiple independent witnesses

### Stage 0 — local product space

One process receives exported JSON and builds all six graphs.

### Stage 1 — independent graph producers

Separate processes produce graph exports:

```text
TIP producer        -> intent/state rationale export
CML producer        -> causal/permission export
T-Trace producer    -> transition export
LiminalDB producer  -> continuity receipt
Ibex producer       -> evidence-role transition report
```

ProofPath verifies each export and joins them only through stable ids and digests.

### Stage 2 — independent witnesses

At least two operators independently:

- fetch the same source exports;
- compute graph roots;
- compute transition cells;
- emit signed witness statements.

Agreement requires matching:

- adapter versions;
- graph roots;
- product-space root;
- decision and primary reason code.

### Stage 3 — challenge exchange

A challenger submits:

- disputed graph name;
- node/edge/cell path;
- expected root;
- observed root;
- minimal contradictory evidence.

Challenge and resolution remain portable evidence, not hidden service state.

## 12. Separate network repository trigger

Do not create `liminal-proof-network` merely because the architecture mentions multiple witnesses.

Create it only when at least one condition is demonstrated:

1. two independently operated witness processes interoperate;
2. an external repository consumes Action Proof Envelope or the multi-graph profile;
3. dispute, discovery or settlement logic no longer belongs in ProofPath;
4. network-specific release cadence is required.

Until then, ProofPath remains the executable integration hub.

## 13. Reviewer commands

```bash
python3 scripts/build_poci_multigraph.py \
  examples/poci-witness/multigraph/source.valid.json \
  --pretty
```

Run tests:

```bash
python3 -m unittest discover \
  -s tests \
  -p 'test_poci_multigraph.py' \
  -v
```

Expected valid result:

```text
decision: ACCEPT
graphs: 6
transition cells: 3
```
