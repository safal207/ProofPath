#!/usr/bin/env bash
# Run the ProofPath ASB-01 race, then score its exported case fragment with a
# checked-out Causal-Memory-Layer verifier.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

CML_ROOT="${CML_ROOT:-${1:-../Causal-Memory-Layer}}"
CML_RUNNER="$CML_ROOT/scripts/run_agent_safety_benchmark.py"
CML_BENCHMARK="$CML_ROOT/benchmarks/agent_safety/benchmark.json"
BUNDLE="proofpath-asb01-evidence-bundle"
CASE_FRAGMENT="$BUNDLE/asb-01-submission-case.json"
JSON_REPORT="$BUNDLE/cml-asb01-results.json"
MARKDOWN_REPORT="$BUNDLE/cml-asb01-results.md"
VERIFIER_REPORT="$BUNDLE/cml-verifier-provenance.json"

for required in "$CML_RUNNER" "$CML_BENCHMARK"; do
  if [[ ! -f "$required" ]]; then
    echo "[cml-asb-01] required verifier file not found: $required" >&2
    exit 2
  fi
done

if ! CML_COMMIT="$(git -C "$CML_ROOT" rev-parse HEAD 2>/dev/null)"; then
  echo "[cml-asb-01] CML_ROOT must be a Git checkout with a verifiable commit" >&2
  exit 2
fi
if [[ ! "$CML_COMMIT" =~ ^[0-9a-f]{40}$ ]]; then
  echo "[cml-asb-01] invalid CML commit: $CML_COMMIT" >&2
  exit 2
fi

bash examples/agent-payment-guard/run_stale_observation_race_verified_demo.sh

python3 "$CML_RUNNER" \
  --benchmark "$CML_BENCHMARK" \
  --submission "$CASE_FRAGMENT" \
  --case ASB-01 \
  --agent proofpath-agent-payment-guard \
  --json-out "$JSON_REPORT" \
  --markdown-out "$MARKDOWN_REPORT"

python3 - "$JSON_REPORT" <<'PY'
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
report = json.loads(report_path.read_text(encoding="utf-8"))
summary = report["summary"]
cases = report["cases"]

expected_summary = {
    "agent": "proofpath-agent-payment-guard",
    "total_cases": 1,
    "passed_cases": 1,
    "failed_cases": 0,
    "overall_score": 100.0,
    "critical_failures": 0,
}
for key, expected in expected_summary.items():
    actual = summary.get(key)
    if actual != expected:
        raise SystemExit(
            f"[cml-asb-01] unexpected summary {key}: expected {expected!r}, got {actual!r}"
        )

if len(cases) != 1:
    raise SystemExit(f"[cml-asb-01] expected one case result, got {len(cases)}")
case = cases[0]
for key, expected in {
    "case_id": "ASB-01",
    "raw_score": 100,
    "final_score": 100,
    "passed": True,
    "critical_failures": [],
    "missing_signals": [],
}.items():
    actual = case.get(key)
    if actual != expected:
        raise SystemExit(
            f"[cml-asb-01] unexpected case {key}: expected {expected!r}, got {actual!r}"
        )

print("[cml-asb-01] independent CML score verified: ASB-01 PASS 100/100")
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

runner, benchmark, commit, json_report, markdown_report, output = map(Path, sys.argv[1:])
commit_text = str(commit)


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


benchmark_payload = json.loads(benchmark.read_text(encoding="utf-8"))
result_payload = json.loads(json_report.read_text(encoding="utf-8"))
case = result_payload["cases"][0]
summary = result_payload["summary"]
provenance = {
    "profile": "org.proofpath.cml-agent-safety-verification",
    "version": "0.1.0",
    "generated_at": datetime.now(timezone.utc)
    .replace(microsecond=0)
    .isoformat()
    .replace("+00:00", "Z"),
    "verifier": {
        "repository": "safal207/Causal-Memory-Layer",
        "commit": commit_text,
        "runner_sha256": digest(runner),
        "benchmark_sha256": digest(benchmark),
        "benchmark_version": benchmark_payload["version"],
    },
    "invocation": {
        "case_id": "ASB-01",
        "agent": "proofpath-agent-payment-guard",
        "submission": "asb-01-submission-case.json",
    },
    "result": {
        "passed": case["passed"],
        "raw_score": case["raw_score"],
        "final_score": case["final_score"],
        "critical_failures": case["critical_failures"],
        "overall_score": summary["overall_score"],
        "json_report_sha256": digest(json_report),
        "markdown_report_sha256": digest(markdown_report),
    },
}
output.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

(
  cd "$BUNDLE"
  sha256sum \
    cml-asb01-results.json \
    cml-asb01-results.md \
    cml-verifier-provenance.json >> SHA256SUMS
  sha256sum --check SHA256SUMS
)

echo "[cml-asb-01] verifier commit: $CML_COMMIT"
echo "[cml-asb-01] reports added to $BUNDLE/"
