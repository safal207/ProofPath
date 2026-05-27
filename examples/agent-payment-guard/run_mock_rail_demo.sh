#!/usr/bin/env bash
# ProofPath Agent Payment Guard — mock payment rail demo.
#
# Proves the core execution boundary:
#   ACCEPT -> reaches mock rail
#   BLOCK  -> never reaches mock rail
#   HOLD   -> never reaches mock rail
#
# Run from repo root:
#   bash examples/agent-payment-guard/run_mock_rail_demo.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

# ---- clean previous runtime files ----
rm -rf proofpath-evidence-bundle/
rm -f .proofpath/audit.jsonl .proofpath/replay-store.json .proofpath/mock-rail-transactions.jsonl

GUARD_HOST="127.0.0.1"
GUARD_PORT="18790"
RAIL_HOST="127.0.0.1"
RAIL_PORT="18791"
GUARD_URL="http://$GUARD_HOST:$GUARD_PORT"
RAIL_URL="http://$RAIL_HOST:$RAIL_PORT"
SERVICE="examples/agent-payment-guard/payment_guard_service.py"
CONFIG="examples/agent-payment-guard/payment_guard_service_config.json"
MOCK_RAIL="examples/agent-payment-guard/mock_payment_rail.py"

TMPDIR="${TMPDIR:-/tmp}"
GUARD_LOG="$TMPDIR/payment_guard_mock_rail.log"
RAIL_LOG="$TMPDIR/mock_rail.log"
GUARD_RESP="$TMPDIR/mock_rail_guard_resp.json"
GUARD_RESP2="$TMPDIR/mock_rail_guard_resp2.json"
GUARD_RESP3="$TMPDIR/mock_rail_guard_resp3.json"
RAIL_TX="$TMPDIR/mock_rail_transactions.json"

echo
echo "[mock-rail-demo] ProofPath Agent Payment Guard — mock payment rail demo"
echo "[mock-rail-demo] core claim: ProofPath decides; mock rail executes only after ACCEPT."
echo

# ---- start services ----
echo "[mock-rail-demo] starting guard service (port $GUARD_PORT)..."
python3 "$SERVICE" --config "$CONFIG" --port "$GUARD_PORT" >"$GUARD_LOG" 2>&1 &
GUARD_PID=$!

echo "[mock-rail-demo] starting mock payment rail (port $RAIL_PORT)..."
python3 "$MOCK_RAIL" --port "$RAIL_PORT" >"$RAIL_LOG" 2>&1 &
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

# ---- load fixtures ----
VALID_INTENT=$(cat examples/agent-payment-guard/intent_envelopes/intent.valid.json)
VALID_PROPOSAL=$(cat examples/agent-payment-guard/payment_proposal.valid_micro_payment.json)
HOLD_PROPOSAL=$(cat examples/agent-payment-guard/payment_proposal.recurring_without_approval.json)

# =====================================================================
# STEP 1: ACCEPT — reach mock rail
# =====================================================================
echo "[mock-rail-demo] step 1 — ACCEPT: valid signed intent proposal"
curl -fsS -X POST "$GUARD_URL/v1/payment-proposals/evaluate" \
  -H 'content-type: application/json' \
  -d "{\"mode\":\"enforce\",\"proposal\":$VALID_PROPOSAL,\"intent_envelope\":$VALID_INTENT}" \
  > "$GUARD_RESP"
python3 -c "
import json, sys
r = json.load(open('$GUARD_RESP'))
assert r['decision'] == 'ACCEPT', f'expected ACCEPT, got {r}'
assert r['execution_allowed'] is True
print(f'  decision: {r[\"decision\"]}')
print(f'  execution_allowed: {r[\"execution_allowed\"]}')
print(f'  audit_hash: {r[\"audit_hash\"]}')
"

# Forward to mock rail
echo "[mock-rail-demo] step 2 — forwarding ACCEPT to mock rail..."
AUDIT_HASH=$(python3 -c "import json; print(json.load(open('$GUARD_RESP'))['audit_hash'])")
curl -fsS -X POST "$RAIL_URL/v1/mock-rail/execute" \
  -H 'content-type: application/json' \
  -d "{\"agent_id\":\"agent_researcher_01\",\"asset\":\"USDC\",\"amount\":\"0.07\",\"recipient\":\"market-data-api.example\",\"proofpath_decision\":\"ACCEPT\",\"proofpath_audit_hash\":\"$AUDIT_HASH\"}" \
  | python3 -c "import json,sys; r=json.load(sys.stdin); assert r['status']=='MOCK_EXECUTED', f'expected MOCK_EXECUTED, got {r}'; print(f'  mock rail status: {r[\"status\"]}')"

echo "[mock-rail-demo] step 3 — verifying mock rail has exactly 1 transaction"
curl -fsS "$RAIL_URL/v1/mock-rail/transactions" > "$RAIL_TX"
python3 -c "
import json
r = json.load(open('$RAIL_TX'))
assert r['count'] == 1, f'expected 1 transaction, got {r[\"count\"]}'
print(f'  transactions: {r[\"count\"]}')
tx = r['transactions'][0]
assert tx['status'] == 'MOCK_EXECUTED'
assert tx['proofpath_decision'] == 'ACCEPT'
print(f'  last status: {tx[\"status\"]}')
print(f'  proofpath_decision: {tx[\"proofpath_decision\"]}')
"
echo

# =====================================================================
# STEP 2: BLOCK / INTENT_REPLAYED — must NOT reach mock rail
# =====================================================================
echo "[mock-rail-demo] step 4 — BLOCK: replay same intent envelope"
curl -fsS -X POST "$GUARD_URL/v1/payment-proposals/evaluate" \
  -H 'content-type: application/json' \
  -d "{\"mode\":\"enforce\",\"proposal\":$VALID_PROPOSAL,\"intent_envelope\":$VALID_INTENT}" \
  > "$GUARD_RESP2"
python3 -c "
import json
r = json.load(open('$GUARD_RESP2'))
assert r['decision'] == 'BLOCK', f'expected BLOCK, got {r}'
assert r['reason'] == 'INTENT_REPLAYED', f'expected INTENT_REPLAYED, got {r[\"reason\"]}'
assert r['execution_allowed'] is False
print(f'  decision: {r[\"decision\"]}')
print(f'  reason: {r[\"reason\"]}')
print(f'  execution_allowed: {r[\"execution_allowed\"]}')
"

echo "[mock-rail-demo] step 5 — verifying mock rail was NOT called (still 1 transaction)"
curl -fsS "$RAIL_URL/v1/mock-rail/transactions" > "$RAIL_TX"
python3 -c "
import json
r = json.load(open('$RAIL_TX'))
assert r['count'] == 1, f'expected 1 transaction after BLOCK, got {r[\"count\"]}'
print(f'  transactions: {r[\"count\"]}')
"
echo

# =====================================================================
# STEP 3: HOLD / RECURRING_PAYMENT_REQUIRES_APPROVAL — must NOT reach mock rail
# =====================================================================
echo "[mock-rail-demo] step 6 — HOLD: recurring payment without approval"
curl -fsS -X POST "$GUARD_URL/v1/payment-proposals/evaluate" \
  -H 'content-type: application/json' \
  -d "{\"mode\":\"enforce\",\"proposal\":$HOLD_PROPOSAL,\"intent_envelope\":null}" \
  > "$GUARD_RESP3"
python3 -c "
import json
r = json.load(open('$GUARD_RESP3'))
assert r['decision'] == 'HOLD', f'expected HOLD, got {r}'
assert r['reason'] == 'RECURRING_PAYMENT_REQUIRES_APPROVAL', f'expected RECURRING_PAYMENT_REQUIRES_APPROVAL, got {r[\"reason\"]}'
assert r['execution_allowed'] is False
print(f'  decision: {r[\"decision\"]}')
print(f'  reason: {r[\"reason\"]}')
print(f'  execution_allowed: {r[\"execution_allowed\"]}')
"

echo "[mock-rail-demo] step 7 — verifying mock rail was NOT called (still 1 transaction)"
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
echo "[mock-rail-demo] step 8 — stopping services and exporting evidence bundle"
kill "$GUARD_PID" >/dev/null 2>&1 || true
kill "$RAIL_PID" >/dev/null 2>&1 || true
sleep 0.2

python3 scripts/export_payment_guard_evidence.py --out proofpath-evidence-bundle/
echo

# =====================================================================
# STEP 5: Verify bundled audit log hash chain
# =====================================================================
echo "[mock-rail-demo] step 9 — verifying bundled audit log hash chain"
python3 scripts/verify_audit_log.py proofpath-evidence-bundle/audit.jsonl
echo

# =====================================================================
# Summary
# =====================================================================
echo "[mock-rail-demo] ========================================"
echo "[mock-rail-demo]  SUCCESS SUMMARY"
echo "[mock-rail-demo] ========================================"
echo "[mock-rail-demo]  ACCEPT reached mock rail"
echo "[mock-rail-demo]  BLOCK did not reach mock rail"
echo "[mock-rail-demo]  HOLD did not reach mock rail"
echo "[mock-rail-demo]  evidence bundle exported"
echo "[mock-rail-demo]  hash-chain verification passed"
echo "[mock-rail-demo] ========================================"

trap - EXIT
