# PoCI Multi-Graph Witness Quorum v0.1

Status: executable experimental profile  
Coordinator profile: `proofpath.poci.multigraph.witness-quorum.v0.1`

## Purpose

The multi-graph builder proves that one exported source bundle is coherent across
six graph dimensions. The witness-quorum layer adds a process boundary: several
configured witness processes independently read the same frozen source bytes,
recompute all six graph roots and the product-space root, and emit deterministic
commitments.

The coordinator accepts only when an exact root vector reaches the configured
quorum.

```text
frozen source bundle
  ├─ witness alpha process ─┐
  ├─ witness beta process  ├─ exact-root quorum ─> consensus root
  └─ witness gamma process ┘
```

The canonical demo uses `2-of-3`.

## Witness statement

Profile: `proofpath.poci.multigraph.witness-statement.v0.1`

Each statement commits to:

- witness round, witness id, declared operator id, and nonce;
- canonical source digest;
- graph set and PoCI envelope ids;
- all six independently rooted graphs;
- transition-cell root;
- computed multi-graph root;
- the underlying builder decision and reason codes.

`statement_root` is domain-separated SHA-256 over the statement with
`statement_root = null`.

It is a tamper-evident commitment, not an identity signature.

## Exact-root voting

A vote is the canonical commitment to:

```text
source digest
+ graph set id
+ PoCI envelope id
+ builder profile
+ six graph roots
+ transition-cell root
+ multi-graph root
```

A witness counts at most once. Repeated identical transport copies do not add
weight. Different commitments from the same witness in the same round are
equivocation.

With quorum `2`, two matching witnesses may accept despite one distinct
dissenting operator. Dissent remains visible in the report.

## Fail-closed findings

| Code | Decision | Meaning |
|---|---|---|
| `WITNESS_SET_INVALID` | BLOCK | Witness configuration is malformed |
| `WITNESS_OPERATOR_NOT_INDEPENDENT` | BLOCK | Operator ids are duplicated or substituted |
| `WITNESS_UNKNOWN` | BLOCK | Statement came from an unconfigured witness |
| `WITNESS_PROCESS_FAILED` | HOLD/BLOCK | A process failed and quorum cannot be established |
| `WITNESS_ROUND_REPLAY` | CHALLENGE | Round id or nonce belongs to another round |
| `WITNESS_SOURCE_MISMATCH` | CHALLENGE | Witness read different source bytes |
| `WITNESS_STATEMENT_TAMPERED` | CHALLENGE | Statement commitment does not match its bytes |
| `WITNESS_EQUIVOCATION` | CHALLENGE | One witness emitted conflicting commitments |
| `WITNESS_GRAPH_COVERAGE_INCOMPLETE` | BLOCK | Statement omitted one of six graph roots |
| `WITNESS_MISSING` | HOLD | Too few valid statements reached the coordinator |
| `WITNESS_QUORUM_NOT_REACHED` | BLOCK | No exact root vector reached quorum |

Decision precedence remains:

```text
CHALLENGE > BLOCK > HOLD > ACCEPT
```

## Reviewer commands

```bash
python3 scripts/verify_poci_multigraph_quorum.py \
  examples/poci-witness/multigraph/witnesses.json \
  --pretty \
  --statements-dir /tmp/poci-witness-statements
```

Expected:

```text
decision: ACCEPT
configured witnesses: 3
quorum: 2
agreeing witnesses: 3
graphs committed by each witness: 6
```

Focused tests:

```bash
python3 -m unittest discover \
  -s tests \
  -p 'test_poci_multigraph_witness.py' \
  -v
```

## Trust boundary and non-claims

The current implementation demonstrates:

- separate operating-system processes inside one CI runner;
- deterministic root reconstruction;
- exact-root `2-of-3` quorum;
- replay, tamper, source mismatch, operator duplication, and equivocation
  detection;
- portable witness statements and consensus report artifacts.

It does **not** yet prove that operator ids represent different organizations,
authenticate operator identity, distribute processes across machines, protect
private keys, provide network discovery, or establish objective real-world
truth.

A separate witness-network repository becomes justified when at least two
externally operated processes exchange these statements or an external
repository consumes the quorum report.
