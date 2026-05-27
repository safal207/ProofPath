#!/usr/bin/env bash
# Smoke-test for the evidence export bundle (closes #151).
#
# What this does:
#   1. Starts the payment guard service (enforce mode, signed intent required)
#   2. Sends a valid signed-intent ACCEPT request (creates audit record + replay-store nonce)
#   3. Stops the service
#   4. Runs export_payment_guard_evidence.py
#   5. Verifies the bundle structure and verification_report.json fields
#   6. Re-runs verify_audit_log.py against the bundled audit.jsonl
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

rm -rf proofpath-evidence-bundle/
rm -f .proofpath/audit.jsonl .proofpath/replay-store.json

HOST="127.0.0.1"
PORT="18788"
SERVICE="examples/agent-payment-guard/payment_guard_service.py"
CONFIG="examples/agent-payment-guard/payment_guard_service_config.json"

python3 "$SERVICE" \
  --config "$CONFIG" \
  --port "$PORT" \
  >/tmp/payment_guard_evidence_svc.log 2>&1 &
SERVICE_PID=$!
cleanup() {
  kill "$SERVICE_PID" >/dev/null 2>&1 || true
  rm -rf proofpath-evidence-bundle/
}
trap cleanup EXIT

# Wait for service to be ready
for _ in $(seq 1 50); do
  if curl -fsS "http://$HOST:$PORT/v1/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done

# Send one valid signed-intent request (ACCEPT)
VALID_INTENT=$(cat examples/agent-payment-guard/intent_envelopes/intent.valid.json)
VALID_PROPOSAL=$(cat examples/agent-payment-guard/payment_proposal.valid_micro_payment.json)

curl -fsS -X POST "http://$HOST:$PORT/v1/payment-proposals/evaluate" \
  -H 'content-type: application/json' \
  -d "{\"mode\":\"enforce\",\"proposal\":$VALID_PROPOSAL,\"intent_envelope\":$VALID_INTENT}" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["decision"]=="ACCEPT", f"expected ACCEPT, got {r}"'

# Stop service before export
kill "$SERVICE_PID" >/dev/null 2>&1 || true
sleep 0.2

# --- run export ---
python3 scripts/export_payment_guard_evidence.py \
  --out proofpath-evidence-bundle/

# --- verify bundle structure ---
for f in audit.jsonl replay-store.json payment_guard_service_config.json payment_policy.json verification_report.json; do
  [ -f "proofpath-evidence-bundle/$f" ] || { echo "FAIL: missing proofpath-evidence-bundle/$f" >&2; exit 1; }
done

# --- verify verification_report.json ---
python3 - <<'EOF'
import json, pathlib, sys
r = json.loads(pathlib.Path("proofpath-evidence-bundle/verification_report.json").read_text())
assert r["bundle_type"] == "agent-payment-guard-evidence", f"bundle_type mismatch: {r}"
assert r["audit_records_count"] >= 1, f"expected >= 1 audit record, got {r['audit_records_count']}"
assert r["replay_store_nonces"] >= 1, f"expected >= 1 nonce, got {r['replay_store_nonces']}"
assert r["hash_chain_valid"] is True, f"hash_chain_valid is not True: {r}"
assert "generated_at" in r, "missing generated_at"
assert "source_files" in r, "missing source_files"
assert "copied_files" in r, "missing copied_files"
for k in ("audit", "replay_store", "config", "policy"):
    assert k in r["source_files"], f"missing source_files.{k}"
print(f"  report OK: {r['audit_records_count']} records, {r['replay_store_nonces']} nonces, chain={r['hash_chain_valid']}")
EOF

# --- re-verify hash chain against bundled audit.jsonl ---
python3 scripts/verify_audit_log.py proofpath-evidence-bundle/audit.jsonl >/dev/null

echo "Evidence export check passed."
