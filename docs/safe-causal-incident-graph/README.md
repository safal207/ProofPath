# SCIG v0.1 Quickstart

The SAFE Causal Incident Graph (SCIG) is ProofPath's causal, temporal, recovery, verification, and evidence model for AI incidents and near misses.

## Artifacts

- [`SAFE_CAUSAL_INCIDENT_GRAPH.md`](./SAFE_CAUSAL_INCIDENT_GRAPH.md) — normative v0.1 proposal.
- [`../../schemas/safe-causal-incident-graph-v0.1.schema.json`](../../schemas/safe-causal-incident-graph-v0.1.schema.json) — Draft 2020-12 JSON Schema.
- [`../../examples/safe-near-miss.json`](../../examples/safe-near-miss.json) — reference near-miss.
- `proofpath-scig` — Rust verifier bundled with `proofpath-verifier`.

## Run

```bash
cargo run -p proofpath-verifier --bin proofpath-scig -- examples/safe-near-miss.json
```

Expected summary:

```text
SCIG SAFE-SCIG-2026-0001
INV-CRED-001       VIOLATED
INV-NET-001        HELD
CONTAINMENT        PASSED
RECOVERY           PASSED
VERIFICATION       PASSED
RESULT             VALID
```

## Test

```bash
cargo test -p proofpath-verifier --bin proofpath-scig
```

The verifier includes negative tests for broken state-transition references, missing evidence references, and verification that claims success without successful recovery.

## Design boundary

SCIG does not replace OpenTelemetry or SAFE-style exchange. It provides a causal interpretation layer over preserved evidence:

```text
telemetry/evidence → causal state graph → failed control → recovery → verification proof
```
