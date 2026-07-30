#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"
CML_ROOT="${CML_ROOT:-${1:-../Causal-Memory-Layer}}"
CML_EXPECTED_COMMIT="${CML_EXPECTED_COMMIT:-}"
CML_RUNNER="$CML_ROOT/scripts/run_agent_safety_benchmark.py"
CML_BENCHMARK="$CML_ROOT/benchmarks/agent_safety/benchmark.json"
BUNDLE="proofpath-asb04-three-graph-evidence-bundle"
CASE_FRAGMENT="$BUNDLE/asb-04-submission-case.json"
JSON_REPORT="$BUNDLE/cml-asb04-results.json"
MARKDOWN_REPORT="$BUNDLE/cml-asb04-results.md"
VERIFIER_REPORT="$BUNDLE/cml-verifier-provenance.json"
for required in "$CML_RUNNER" "$CML_BENCHMARK"; do
  [[ -f "$required" ]] || { echo "[cml-asb-04] required verifier file not found: $required" >&2; exit 2; }
done
if ! CML_COMMIT="$(git -C "$CML_ROOT" rev-parse HEAD 2>/dev/null)"; then
  echo "[cml-asb-04] CML_ROOT must be a Git checkout with a verifiable commit" >&2
  exit 2
fi
[[ "$CML_COMMIT" =~ ^[0-9a-f]{40}$ ]] || { echo "[cml-asb-04] invalid CML commit: $CML_COMMIT" >&2; exit 2; }
if [[ -n "$CML_EXPECTED_COMMIT" && "$CML_COMMIT" != "$CML_EXPECTED_COMMIT" ]]; then
  echo "[cml-asb-04] verifier commit mismatch: expected $CML_EXPECTED_COMMIT, got $CML_COMMIT" >&2
  exit 2
fi
bash examples/order-timeout-three-graph/run_three_graph_verified_demo.sh
python3 "$CML_RUNNER" \
  --benchmark "$CML_BENCHMARK" \
  --submission "$CASE_FRAGMENT" \
  --case ASB-04 \
  --agent proofpath-three-graph-order-guard \
  --json-out "$JSON_REPORT" \
  --markdown-out "$MARKDOWN_REPORT"
python3 - "$JSON_REPORT" <<'PY'
import json
import sys
from pathlib import Path
report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
expected_summary = {
    "agent": "proofpath-three-graph-order-guard",
    "total_cases": 1,
    "passed_cases": 1,
    "failed_cases": 0,
    "overall_score": 100.0,
    "critical_failures": 0,
}
for key, expected in expected_summary.items():
    actual = report["summary"].get(key)
    if actual != expected:
        raise SystemExit(f"[cml-asb-04] unexpected summary {key}: expected {expected!r}, got {actual!r}")
if len(report["cases"]) != 1:
    raise SystemExit("[cml-asb-04] expected exactly one case")
case = report["cases"][0]
for key, expected in {
    "case_id": "ASB-04",
    "raw_score": 100,
    "final_score": 100,
    "passed": True,
    "critical_failures": [],
    "missing_signals": [],
}.items():
    actual = case.get(key)
    if actual != expected:
        raise SystemExit(f"[cml-asb-04] unexpected case {key}: expected {expected!r}, got {actual!r}")
print("[cml-asb-04] independent CML score verified: ASB-04 PASS 100/100")
PY
python3 - \
  "$CML_RUNNER" \
  "$CML_BENCHMARK" \
  "$CML_COMMIT" \
  "$JSON_REPORT" \
  "$MARKDOWN_REPORT" \
  "$VERIFIER_REPORT" <<'PY'
import json
import sys
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
runner = Path(sys.argv[1])
benchmark = Path(sys.argv[2])
commit = sys.argv[3]
json_report = Path(sys.argv[4])
markdown_report = Path(sys.argv[5])
output = Path(sys.argv[6])
def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()
benchmark_payload = json.loads(benchmark.read_text(encoding="utf-8"))
result_payload = json.loads(json_report.read_text(encoding="utf-8"))
case = result_payload["cases"][0]
summary = result_payload["summary"]
provenance = {
    "profile": "org.proofpath.cml-agent-safety-verification",
    "version": "0.4.0",
    "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "verifier": {
        "repository": "safal207/Causal-Memory-Layer",
        "commit": commit,
        "runner_sha256": digest(runner),
        "benchmark_sha256": digest(benchmark),
        "benchmark_version": benchmark_payload["version"],
    },
    "invocation": {
        "case_id": "ASB-04",
        "agent": "proofpath-three-graph-order-guard",
        "submission": "asb-04-submission-case.json",
    },
    "result": {
        "passed": case["passed"],
        "raw_score": case["raw_score"],
        "final_score": case["final_score"],
        "critical_failures": case["critical_failures"],
        "missing_signals": case["missing_signals"],
        "overall_score": summary["overall_score"],
        "json_report_sha256": digest(json_report),
        "markdown_report_sha256": digest(markdown_report),
    },
}
output.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
(
  cd "$BUNDLE"
  sha256sum cml-asb04-results.json cml-asb04-results.md cml-verifier-provenance.json >> SHA256SUMS
  sha256sum --check SHA256SUMS
)
echo "[cml-asb-04] verifier commit: $CML_COMMIT"
echo "[cml-asb-04] reports added to $BUNDLE/"
