# Dahl three-replica live pilot

This runbook performs a non-sensitive three-request pilot against the Dahl OpenAI-compatible endpoint using `MiniMaxAI/MiniMax-M2.7`.

It is designed for Android/Termux, a Linux container, macOS, or ordinary Linux.

## What it verifies

The pilot verifies that:

- API-key authentication works;
- three bounded requests complete;
- each execution returns a provider request ID when available;
- MiniMax reasoning markup is safely excluded from final-answer comparison;
- all final answers agree above the configured threshold;
- a secret-free ProofPath receipt is written locally.

It does not prove that the three requests used independent hosts or GPUs. Distinct request IDs are evidence of distinct API executions, not evidence of independent routing.

## Run

From any directory with Git installed:

```bash
git clone --branch feat/gonka-compute-witness-pilot --single-branch \
  https://github.com/safal207/ProofPath.git
cd ProofPath
bash examples/compute-witness/run_dahl_live_pilot.sh
```

The script asks for the API key using hidden terminal input. Do not paste the key into the command line or commit it to a file.

Existing checkout:

```bash
git fetch origin feat/gonka-compute-witness-pilot
git switch feat/gonka-compute-witness-pilot
git pull --ff-only
bash examples/compute-witness/run_dahl_live_pilot.sh
```

## Defaults

```text
endpoint: https://inference.dahl.global/v1/chat/completions
model: MiniMaxAI/MiniMax-M2.7
replicas: 3
timeout: 90 seconds
agreement threshold: 0.95
prompt: Reply with exactly: ProofPath OK
```

Override a value before running when needed:

```bash
export GONKA_REPLICAS=5
export GONKA_TIMEOUT_SECONDS=120
bash examples/compute-witness/run_dahl_live_pilot.sh
```

## Expected summary

```json
{
  "verdict": "CONSENSUS",
  "requested_replicas": 3,
  "successful_replicas": 3,
  "agreement_score": 1.0,
  "provider_request_ids": ["...", "...", "..."],
  "reasoning_markup": ["closed", "closed", "closed"],
  "receipt_hash": "sha256:..."
}
```

The exact `reasoning_markup` values may be `closed` or `none`. Either is acceptable when all three final answers are safely extracted.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | all requested executions succeeded and verdict is `CONSENSUS` |
| `2` | invalid local configuration |
| `3` | fewer executions succeeded than requested |
| `4` | all may have succeeded, but final answers did not reach consensus |

## Receipt location

Receipts are stored under:

```text
.proofpath/gonka-pilots/
```

The directory is created with owner-only permissions and each receipt is set to mode `600`.

The receipt contains hashes and execution metadata. It does not contain the API key, prompt text, model reasoning text, or full model outputs.

## What to share for review

Safe fields to share:

- verdict;
- requested and successful replica counts;
- agreement score;
- provider request IDs;
- reasoning-markup statuses;
- receipt hash;
- HTTP statuses.

Do not share the API key or terminal history containing it.
