# Causal-temporal trace seal

Status: **experimental completeness sidecar**  
Companion to: `proofpath.causal-temporal-graph.v0.1`

## Why a seal is needed

A parent-linked hash chain exposes mutation and an omitted event in the middle.
It cannot, by itself, distinguish a complete chain from a prefix whose entire
tail was removed. A trace seal closes that bounded-completeness gap by declaring
where the trace ends.

## Seal shape

```json
{
  "subject_hash": "sha256:...",
  "total_events": 5,
  "terminal_event_id": "sha256:...",
  "sealed_at": "2026-07-22T05:01:00Z",
  "seal_id": "sha256:..."
}
```

`seal_id` is SHA-256 over compact sorted-key UTF-8 JSON of all members except
`seal_id`.

## Verification

A sealed trace is accepted only when:

1. the seal itself recomputes;
2. `subject_hash` equals the trace subject;
3. `total_events` equals the held event count;
4. `terminal_event_id` equals the last recomputed event ID;
5. `sealed_at` is not earlier than the final `observed_at`.

The checker returns explicit signals:

- `TRACE_SEAL_MISSING`;
- `TRACE_SEAL_ID_MISMATCH`;
- `TRACE_SEAL_SUBJECT_MISMATCH`;
- `TRACE_TOTAL_MISMATCH`;
- `TRACE_TERMINAL_EVENT_MISMATCH`;
- `INVALID_SEALED_AT`;
- `SEALED_AT_REGRESSION`.

## Causal boundary

A seal proves completeness only relative to the boundary it declares. It does
not prove that a producer chose the correct real-world boundary or recorded all
external events before sealing. Governance of who may seal, when sealing is
required, and how seals are externally witnessed remains a separate layer.

For stronger temporal evidence, the seal bytes themselves may be submitted to
the OpenTimestamps profile. That produces two independent guarantees:

```text
trace seal       → bounded event completeness
OTS proof        → seal bytes existed no later than a Bitcoin block
```

Neither guarantee substitutes for the other.
