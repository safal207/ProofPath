#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

WORK_DIR="${PROOFPATH_LIVE_CHECK_DIR:-$(mktemp -d)}"
AUDIT_LOG="$WORK_DIR/proofpath-audit.jsonl"
METRICS_JSON="$WORK_DIR/action-boundary-live-metrics.json"
UPSTREAM_LOG="$WORK_DIR/upstream.log"
GATEWAY_LOG="$WORK_DIR/gateway.log"

UPSTREAM_PID=""
GATEWAY_PID=""

cleanup() {
  if [[ -n "${GATEWAY_PID}" ]]; then
    kill "${GATEWAY_PID}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${UPSTREAM_PID}" ]]; then
    kill "${UPSTREAM_PID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

wait_for_port() {
  local host="$1"
  local port="$2"
  local label="$3"

  python3 - "$host" "$port" "$label" <<'PY'
import socket
import sys
import time

host = sys.argv[1]
port = int(sys.argv[2])
label = sys.argv[3]

for _ in range(120):
    try:
        with socket.create_connection((host, port), timeout=0.5):
            print(f"{label} is ready on {host}:{port}")
            sys.exit(0)
    except OSError:
        time.sleep(0.25)

print(f"Timed out waiting for {label} on {host}:{port}", file=sys.stderr)
sys.exit(1)
PY
}

assert_metric() {
  local path="$1"
  local expected_json="$2"

  python3 - "$METRICS_JSON" "$path" "$expected_json" <<'PY'
import json
import sys

metrics_path, dotted_path, expected_json = sys.argv[1:]
with open(metrics_path, "r", encoding="utf-8") as handle:
    payload = json.load(handle)

value = payload
for part in dotted_path.split("."):
    value = value[part]

expected = json.loads(expected_json)
if value != expected:
    print(
        f"Metric assertion failed for {dotted_path}: expected {expected!r}, got {value!r}",
        file=sys.stderr,
    )
    sys.exit(1)
PY
}

rm -f "$AUDIT_LOG" "$METRICS_JSON" "$UPSTREAM_LOG" "$GATEWAY_LOG"
mkdir -p "$WORK_DIR"

python3 examples/upstream/demo_server.py >"$UPSTREAM_LOG" 2>&1 &
UPSTREAM_PID="$!"
wait_for_port 127.0.0.1 9797 "demo upstream API"

PROOFPATH_AUDIT_LOG="$AUDIT_LOG" \
PROOFPATH_UPSTREAM_URL="http://127.0.0.1:9797/protected" \
cargo run -q -p proofpath-gateway >"$GATEWAY_LOG" 2>&1 &
GATEWAY_PID="$!"
wait_for_port 127.0.0.1 8787 "ProofPath gateway"

bash examples/agent-dangerous-action/agent_delete_without_approval.sh >"$WORK_DIR/without-approval.out" 2>&1
bash examples/agent-dangerous-action/agent_delete_with_approval.sh >"$WORK_DIR/with-approval.out" 2>&1

if [[ ! -s "$AUDIT_LOG" ]]; then
  echo "Expected non-empty audit log at $AUDIT_LOG" >&2
  echo "--- gateway log ---" >&2
  cat "$GATEWAY_LOG" >&2 || true
  echo "--- upstream log ---" >&2
  cat "$UPSTREAM_LOG" >&2 || true
  exit 1
fi

python3 scripts/collect_action_boundary_metrics.py \
  --input "$AUDIT_LOG" \
  --output "$METRICS_JSON" \
  --run-id "live-action-boundary-ci" \
  --observed-at "1970-01-01T00:00:00+00:00"

assert_metric "metrics.actions_total.value" "2"
assert_metric "metrics.actions_blocked.value" "1"
assert_metric "metrics.actions_accepted.value" "1"
assert_metric "metrics.unsafe_without_approval_blocked.value" "1"
assert_metric "metrics.unsafe_without_approval_false_accepts.value" "0"
assert_metric "metrics.safe_with_approval_false_blocks.value" "0"
assert_metric "metrics.audit_records_written.value" "2"
assert_metric "metrics.blocked_forwarded_count.value" "0"
assert_metric "metrics.accepted_forwarded_count.value" "1"
assert_metric "metrics.audit_hash_chain_present.value" "true"

cat "$METRICS_JSON"

echo "Live action-boundary check passed. Work dir: $WORK_DIR"
