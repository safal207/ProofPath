# Gonka Compute Witness Pilot

## Goal

Use an OpenAI-compatible Gonka broker as an optional execution provider for ProofPath Compute Witness while keeping the trust boundary explicit.

The pilot answers a narrow question:

```text
Can ProofPath send the same bounded request to several provider executions,
record what happened without leaking secrets, detect failures or divergence,
and emit a stable local receipt for downstream verification?
```

It does **not** claim that the broker proves GPU identity, validator independence, on-chain settlement, or model execution correctness.

## Architecture

```text
TRACE / agent / workflow
        |
        v
ProofPath Gonka adapter
  - canonical request hash
  - bounded timeout
  - N replicas
  - optional fallback
  - output comparison
        |
        v
OpenAI-compatible Gonka broker
        |
        v
model outputs + provider metadata
        |
        v
ProofPath local compute receipt
  - request/prompt hashes
  - per-execution response/output hashes
  - provider request IDs when available
  - CONSENSUS / DIVERGENT / DEGRADED verdict
  - explicit limitations
```

Raw model outputs are returned separately to the caller. They are not embedded in the receipt by default.

## Files

```text
examples/compute-witness/gonka_adapter.py
examples/compute-witness/gonka.env.example
scripts/test_gonka_adapter.py
docs/GONKA_COMPUTE_WITNESS_PILOT.md
```

## Safety properties

- Standard-library implementation; no new runtime dependency.
- API keys are read from environment variables only.
- API keys and prompts are not written into receipts.
- External endpoints must use HTTPS. Plain HTTP is allowed only for localhost mocks.
- Response bodies are size-bounded.
- Replica count is limited to 1–10.
- Timeouts are bounded to 0.1–300 seconds.
- Fallback is disabled unless all fallback settings are explicitly supplied.
- No wallet, token, settlement, custody, or payment operation is implemented.
- Receipt limitations are machine-readable and cannot be mistaken for hardware or cryptographic proof.

## Run tests

From the repository root:

```bash
python3 scripts/test_gonka_adapter.py
```

Covered cases:

1. three matching executions produce `CONSENSUS`;
2. different outputs produce `DIVERGENT`;
3. partial provider failure produces `DEGRADED`;
4. primary failure can use an explicitly configured fallback;
5. receipts exclude API keys and raw prompts;
6. insecure external HTTP endpoints are rejected.

## Configure a live broker

Copy values from the example without committing the resulting file:

```bash
export GONKA_BASE_URL="https://your-gonka-broker.example/v1"
export GONKA_API_KEY="..."
export GONKA_MODEL="..."
export GONKA_REPLICAS="3"
export GONKA_TIMEOUT_SECONDS="30"
export GONKA_AGREEMENT_THRESHOLD="0.85"
```

Optional fallback requires all three variables:

```bash
export GONKA_FALLBACK_BASE_URL="https://fallback-provider.example/v1"
export GONKA_FALLBACK_API_KEY="..."
export GONKA_FALLBACK_MODEL="..."
```

## Run a live pilot

Receipt only:

```bash
python3 examples/compute-witness/gonka_adapter.py \
  --claim-id trace-claim-001 \
  --prompt "Evaluate the claim and state evidence, uncertainty, and counterarguments."
```

Include raw outputs in stdout for local inspection:

```bash
python3 examples/compute-witness/gonka_adapter.py \
  --claim-id trace-claim-001 \
  --prompt-file /path/to/prompt.txt \
  --include-outputs
```

Do not use `--include-outputs` in logs containing sensitive material.

## Receipt contract

Top-level fields:

```json
{
  "profile": "proofpath.gonka.compute-receipt.v0.1",
  "run_id": "gonka-run-...",
  "claim_id": "trace-claim-001",
  "request_hash": "sha256:...",
  "prompt_hash": "sha256:...",
  "requested_replicas": 3,
  "successful_replicas": 3,
  "agreement_score": 1.0,
  "agreement_threshold": 0.85,
  "verdict": "CONSENSUS",
  "executions": [],
  "proof_level": "provider-response-hash-v0.1",
  "limitations": [],
  "receipt_hash": "sha256:..."
}
```

Per-execution evidence includes:

- execution ID;
- provider and model;
- endpoint origin, never embedded credentials;
- start and completion timestamps;
- HTTP status;
- fallback usage;
- provider request ID when available;
- canonical response hash;
- output hash;
- selected non-sensitive response headers;
- sanitized error state.

## Verdicts

| Verdict | Meaning |
| --- | --- |
| `CONSENSUS` | All requested replicas succeeded and average normalized similarity meets the threshold. |
| `DIVERGENT` | All replicas succeeded, but their outputs differ beyond the threshold. |
| `DEGRADED` | At least one replica succeeded, but fewer than requested succeeded. |
| `NO_SUCCESSFUL_EXECUTION` | No provider execution produced usable text. |

The current similarity score is a deterministic average of pairwise normalized text similarity. It is an operational signal, not a semantic truth metric.

## Integration with our projects

### TRACE

TRACE can use `claim_id`, `request_hash`, per-execution `output_hash`, and the verdict as execution evidence attached to a scientific verification task.

Recommended rule:

```text
CONSENSUS is evidence of output agreement, not evidence that the claim is true.
```

TRACE should still require source evidence, uncertainty, counterarguments, and independent review.

### ProofPath

The adapter extends the existing Compute Witness boundary from static fixtures to a live OpenAI-compatible provider. The next ProofPath step is to map this receipt into the existing audit packet and hash-chain format.

### LiminalDB

Store the receipt as a temporal execution event:

```text
CLAIM -> REQUEST_HASH -> EXECUTION -> OUTPUT_HASH -> VERDICT
```

Raw outputs should remain in a separate access-controlled store when they contain sensitive data.

### Temporal Market Intelligence

Use this adapter only for asynchronous research, ensemble analysis, and independent verification. Do not place it in a latency-critical trading path until broker routing, SLA, data retention, and execution independence are verified.

## Pilot acceptance criteria

The pilot is ready for a broker test when:

- unit tests pass;
- a supported broker URL and model are known;
- data-retention policy is reviewed;
- three identical requests complete without leaking secrets;
- receipt hashes are stable and parseable;
- failure and timeout behavior are observed;
- the team confirms whether replicas are routed independently.

## Next milestones

1. Run against one real Gonka-compatible broker with non-sensitive test prompts.
2. Capture p50/p95 latency, success rate, and cost outside the receipt.
3. Add the receipt to the existing Compute Witness audit packet.
4. Add optional broker attestation fields only when they are documented and verifiable.
5. Add a TRACE claim-verification example with three executions and one independent reviewer.
6. Add a LiminalDB event schema for request, execution, output, challenge, and reproduction links.

## Honest trust statement

```text
This pilot proves that ProofPath created a canonical request, attempted bounded
provider executions, recorded returned metadata and hashes, compared outputs,
and produced a tamper-evident local receipt.

It does not by itself prove where the model ran, which GPU executed it, whether
replicas were independent, whether settlement occurred, or whether the answer
is scientifically correct.
```
