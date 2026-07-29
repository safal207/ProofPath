#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT/examples/nooa-liminal-guard"

python3 -m unittest -v test_nooa_liminal_guard.py
rm -rf "$ROOT/.proofpath/nooa-liminal-demo" "$ROOT/.proofpath/nooa-liminal-state"
python3 run_demo.py \
  --output "$ROOT/.proofpath/nooa-liminal-demo" \
  --state "$ROOT/.proofpath/nooa-liminal-state"
python3 - <<'PY'
import json
from pathlib import Path
summary = json.loads(Path("../../.proofpath/nooa-liminal-demo/benchmark-summary.json").read_text())
assert summary["metrics"]["matched"] == summary["metrics"]["total"]
assert summary["metrics"]["false_negative"] == 0
assert summary["metrics"]["evidence_completeness"] == 1.0
assert "replay-should-not-run" not in summary["executed_cases"]
print("PASS: NOOA Liminal guard chain is reproducible")
PY
