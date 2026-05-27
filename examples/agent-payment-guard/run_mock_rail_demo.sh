#!/usr/bin/env bash
# ProofPath Agent Payment Guard — mock payment rail demo.
#
# Proves the core execution boundary:
#   ACCEPT -> adapter forwards to mock rail
#   BLOCK  -> adapter does NOT forward
#   HOLD   -> adapter does NOT forward
#
# Run from repo root:
#   bash examples/agent-payment-guard/run_mock_rail_demo.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

# ---- clean previous runtime files ----
rm -rf proofpath-evidence-bundle/
rm -f .proofpath/audit.jsonl .proofpath/replay-store.json .proofpath/mock-rail-transactions.jsonl

GUARD_URL="http://127.0.0.1:18790"
RAIL_URL="http://127.0.0.1:18791"
SERVICE="examples/agent-payment-guard/payment_guard_service.py"
CONFIG="examples/agent-payment-guard/payment_guard_service_config.json"
MOCK_RAIL="examples/agent-payment-guard/mock_payment_rail.py"
ADAPTER="examples/agent-payment-guard/payment_guard_to_mock_rail_adapter.py"

VALID_PROPOSAL="examples/agent-payment-guard/payment_proposal.valid_micro_payment.json"
VALID_INTENT="examples/agent-payment-guard/intent_envelopes/intent.valid.json"
HOLD_PROPOSAL="examples/agent-payment-guard/payment_proposal.recurring_without_approval.json"

TMPDIR="${TMPDIR:-/tmp}"
GUARD_LOG="$TMPDIR/payment_guard_mock_rail.log"
RAIL_LOG="$TMPDIR/mock_rail.log"
RAIL_TX="$TMPDIR/mock_rail_transactions.json"

echo
echo "[mock-rail-demo] ProofPath Agent Payment Guard — mock payment rail demo"
echo "[mock-rail-demo] core claim: ProofPath decides; mock rail executes only after ACCEPT."
echo

# ---- start services ----
echo "[mock-rail-demo] starting guard service..."
python3 "$SERVICE" --config "$CONFIG" --port "18790" >"$GUARD_LOG" 2>&1 &
GUARD_PID=$!

echo "[mock-rail-demo] starting mock payment rail..."
python3 "$MOCK_RAIL" --port "18791" >"$RAIL_LOG" 2>&1 &
RAIL_PID=$!

cleanup() {
  kill "$GUARD_PID" >/dev/null 2>&1 || true
  kill "$RAIL_PID" >/dev/null 2>&1 || true
  rm -rf proofpath-evidence-bundle/
}
trap cleanup EXIT

for _ in $(seq 1 50); do
  if curl -fsS "$GUARD_URL/v1/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done
echo "[mock-rail-demo] guard service ready."

for _ in $(seq 1 50); do
  if curl -fsS "$RAIL_URL/v1/mock-rail/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done
echo "[mock-rail-demo] mock payment rail ready."
echo

# =====================================================================
# STEP 1: ACCEPT — adapter forwards to mock rail
# =====================================================================
echo "[mock-rail-demo] step 1 — ACCEPT: valid signed intent proposal"
python3 "$ADAPTER" \
  --guard-url "$GUARD_URL" \
  --rail-url "$RAIL_URL" \
  --proposal "$VALID_PROPOSAL" \
  --intent-envelope "$VALID_INTENT" \
  --mode enforce
echo

echo "[mock-rail-demo] step 2 — verifying mock rail has exactly 1 transaction"
curl -fsS "$RAIL_URL/v1/mock-rail/transactions" > "$RAIL_TX"
python3 -c "
import json
r = json.load(open('$RAIL_TX'))
assert r['count'] == 1, f'expected 1 transaction, got {r[\"count\"]}'
tx = r['transactions'][0]
assert tx['status'] == 'MOCK_EXECUTED'
assert tx['proofpath_decision'] == 'ACCEPT'
print(f'  transactions: {r[\"count\"]}')
print(f'  last status: {tx[\"status\"]}')
print(f'  proofpath_decision: {tx[\"proofpath_decision\"]}')
"
echo

# =====================================================================
# STEP 2: BLOCK / INTENT_REPLAYED — adapter must NOT forward
# =====================================================================
echo "[mock-rail-demo] step 3 — BLOCK: replay same intent envelope"
set +e
python3 "$ADAPTER" \
  --guard-url "$GUARD_URL" \
  --rail-url "$RAIL_URL" \
  --proposal "$VALID_PROPOSAL" \
  --intent-envelope "$VALID_INTENT" \
  --mode enforce
status=$?
set -e
if [ "$status" -ne 2 ]; then
  echo "FAIL: expected adapter exit code 2 (BLOCK), got $status" >&2
  exit 1
fi
echo "  adapter correctly exited $status (BLOCK)"
echo

echo "[mock-rail-demo] step 4 — verifying mock rail was NOT called (still 1 transaction)"
curl -fsS "$RAIL_URL/v1/mock-rail/transactions" > "$RAIL_TX"
python3 -c "
import json
r = json.load(open('$RAIL_TX'))
assert r['count'] == 1, f'expected 1 transaction after BLOCK, got {r[\"count\"]}'
print(f'  transactions: {r[\"count\"]}')
"
echo

# =====================================================================
# STEP 3: HOLD / RECURRING_PAYMENT_REQUIRES_APPROVAL — must NOT forward
# =====================================================================
echo "[mock-rail-demo] step 5 — HOLD: recurring payment without approval"
set +e
python3 "$ADAPTER" \
  --guard-url "$GUARD_URL" \
  --rail-url "$RAIL_URL" \
  --proposal "$HOLD_PROPOSAL" \
  --mode enforce
status=$?
set -e
if [ "$status" -ne 2 ]; then
  echo "FAIL: expected adapter exit code 2 (HOLD), got $status" >&2
  exit 1
fi
echo "  adapter correctly exited $status (HOLD)"
echo

echo "[mock-rail-demo] step 6 — verifying mock rail was NOT called (still 1 transaction)"
curl -fsS "$RAIL_URL/v1/mock-rail/transactions" > "$RAIL_TX"
python3 -c "
import json
r = json.load(open('$RAIL_TX'))
assert r['count'] == 1, f'expected 1 transaction after HOLD, got {r[\"count\"]}'
print(f'  transactions: {r[\"count\"]}')
"
echo

# =====================================================================
# STEP 4: Export evidence bundle
# =====================================================================
echo "[mock-rail-demo] step 7 — stopping services and exporting evidence bundle"
kill "$GUARD_PID" >/dev/null 2>&1 || true
kill "$RAIL_PID" >/dev/null 2>&1 || true
sleep 0.2

python3 scripts/export_payment_guard_evidence.py --out proofpath-evidence-bundle/
echo

# =====================================================================
# STEP 5: Verify bundled audit log hash chain
# =====================================================================
echo "[mock-rail-demo] step 8 — verifying bundled audit log hash chain"
python3 scripts/verify_audit_log.py proofpath-evidence-bundle/audit.jsonl
echo

# =====================================================================
# Summary
# =====================================================================
echo "[mock-rail-demo] ========================================"
echo "[mock-rail-demo]  SUCCESS SUMMARY"
echo "[mock-rail-demo] ========================================"
echo "[mock-rail-demo]  ACCEPT reached mock rail via adapter"
echo "[mock-rail-demo]  BLOCK did not reach mock rail"
echo "[mock-rail-demo]  HOLD did not reach mock rail"
echo "[mock-rail-demo]  evidence bundle exported"
echo "[mock-rail-demo]  hash-chain verification passed"
echo "[mock-rail-demo] ========================================"

trap - EXIT
