#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

bash examples/agent-payment-guard/run_stale_observation_race_demo.sh
python3 scripts/finalize_asb01_evidence.py \
  --bundle proofpath-asb01-evidence-bundle \
  --proposal examples/agent-payment-guard/payment_proposal.valid_micro_payment.json \
  --intent examples/agent-payment-guard/intent_envelopes/intent.valid.json

python3 - <<'PY'
from pathlib import Path

bundle = Path("proofpath-asb01-evidence-bundle")
required = {
    "audit.jsonl",
    "replay-store.json",
    "mock-rail-transactions.jsonl",
    "asb-01-trace.json",
    "asb-01-submission-case.json",
    "payment-proposal.json",
    "signed-intent-envelope.json",
    "evidence-manifest.json",
    "SHA256SUMS",
}
missing = sorted(name for name in required if not (bundle / name).is_file())
assert not missing, missing
print("[asb-01-evidence] required self-contained evidence present")
PY
