# Architecture Reference

## Canonical chain

```text
Agent runtime / exported span
        ↓
Proposal normalization
        ↓
Pre-execution guard
  intent · parent cause · nonce · scope
  reversibility · approval · destination
        ↓
ACCEPT ───────────────→ externally contained executor
HOLD  ────────────────→ approval / revalidation
BLOCK ────────────────→ no execution
        ↓
Authorization record
        ↓
Observation record
        ↓
Causal trace + findings
        ↓
Replay trace
        ↓
Hash-linked durable ledger
        ↓
Manifest-bound evidence bundle
        ↓
Independent verification
```

## Portfolio mapping

| Layer | Responsibility |
|---|---|
| Agent runtime | orchestration, typed capabilities, spans |
| ProofPath | authority decision before execution |
| CML | causal lineage and compact findings |
| LTP | deterministic replay and path judgment |
| LiminalDB | durable authorization/observation/continuity state |
| Ibex pattern | exact evidence inventory and attestation-ready bundle |
| External sandbox | OS-level containment |

## Integration rule

Do not force every repository into the runtime path. Use the smallest executable chain:

```text
guard → executor boundary → traces → durable handoff → bundle
```

Keep conceptual protocols as references unless they are required to execute or validate the scenario.
