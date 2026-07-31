# PoCI multi-graph transition-space demo

This example joins one PoCI Action Proof Envelope with exported shapes from:

- Transition Intelligence Protocol;
- Causal Memory Layer;
- T-Trace;
- LiminalDB;
- Ibex Agent Verification.

No external package is imported. The example is a pinned JSON adapter boundary.

## Run

```bash
python3 scripts/build_poci_multigraph.py \
  examples/poci-witness/multigraph/source.valid.json \
  --pretty
```

Expected summary:

```text
decision: ACCEPT
graphs: 6
transition cells: 3
PoCI root: sha256:ae08edd47da5e6b6704a02d770ce6a76d0efdfb5b734ba3dcc4bb23742998e20
multi-graph root: sha256:98543066cb16c06b5300b56749af43b2fdd48eed47650488ac57987156e38219
```

Graph sizes:

| Graph | Nodes | Edges |
|---|---:|---:|
| Causal | 7 | 6 |
| Intent | 5 | 4 |
| Authority | 5 | 4 |
| State transition | 6 | 5 |
| Evidence | 7 | 7 |
| Time / continuity | 13 | 11 |

## Negative checks

The unit tests mutate the valid source and require deterministic rejection of:

- destination mismatch;
- missing CML parent;
- T-Trace timestamp regression;
- LiminalDB rollback;
- Ibex evidence substitution;
- actor mismatch;
- continuity revalidation;
- declared root mismatch.

See `docs/POCI_ECOSYSTEM_ADAPTERS.md`.
