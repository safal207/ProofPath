#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

rm -f .proofpath/audit.jsonl .proofpath/replay-store.json

HOST="127.0.0.1"
PORT="18787"
SERVICE="examples/agent-payment-guard/payment_guard_service.py"
CONFIG="examples/agent-payment-guard/payment_guard_service_config.json"

# Start service with JSON config; --port overrides config port to avoid conflicts during tests
python3 "$SERVICE" \
  --config "$CONFIG" \
  --port "$PORT" \
  >/tmp/payment_guard_service.log 2>&1 &
SERVICE_PID=$!
cleanup() {
  kill "$SERVICE_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

for _ in $(seq 1 50); do
  if curl -fsS "http://$HOST:$PORT/v1/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done

# --- health ---
curl -fsS "http://$HOST:$PORT/v1/health" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["status"]=="ok"; assert r["surface"]=="agent-payment-guard-service"; assert r["version"]=="0.1"'

VALID_INTENT=$(cat examples/agent-payment-guard/intent_envelopes/intent.valid.json)
VALID_PROPOSAL=$(cat examples/agent-payment-guard/payment_proposal.valid_micro_payment.json)

# --- enforce ACCEPT (with intent envelope to satisfy require_signed_intent=true from config) ---
curl -fsS -X POST "http://$HOST:$PORT/v1/payment-proposals/evaluate" \
  -H 'content-type: application/json' \
  -d "{\"mode\":\"enforce\",\"proposal\":$VALID_PROPOSAL,\"intent_envelope\":$VALID_INTENT}" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["mode"]=="enforce"; assert r["decision"]=="ACCEPT"; assert r["execution_allowed"] is True; assert r["would_block"] is False; assert r["audit_hash"].startswith("sha256:")'

BAD_PROPOSAL=$(cat examples/agent-payment-guard/payment_proposal.asset_not_allowed.json)

# --- shadow BLOCK ---
curl -fsS -X POST "http://$HOST:$PORT/v1/payment-proposals/evaluate" \
  -H 'content-type: application/json' \
  -d "{\"mode\":\"shadow\",\"proposal\":$BAD_PROPOSAL,\"intent_envelope\":null}" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["mode"]=="shadow"; assert r["decision"]=="BLOCK"; assert r["execution_allowed"] is True; assert r["would_block"] is True; assert r["audit_hash"].startswith("sha256:")'

HOLD_PROPOSAL=$(cat examples/agent-payment-guard/payment_proposal.recurring_without_approval.json)

# --- enforce HOLD ---
curl -fsS -X POST "http://$HOST:$PORT/v1/payment-proposals/evaluate" \
  -H 'content-type: application/json' \
  -d "{\"mode\":\"enforce\",\"proposal\":$HOLD_PROPOSAL,\"intent_envelope\":null}" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["mode"]=="enforce"; assert r["decision"]=="HOLD"; assert r["reason"]=="RECURRING_PAYMENT_REQUIRES_APPROVAL"; assert r["execution_allowed"] is False; assert r["would_block"] is True; assert r["audit_hash"].startswith("sha256:")'

# --- shadow HOLD ---
curl -fsS -X POST "http://$HOST:$PORT/v1/payment-proposals/evaluate" \
  -H 'content-type: application/json' \
  -d "{\"mode\":\"shadow\",\"proposal\":$HOLD_PROPOSAL,\"intent_envelope\":null}" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["mode"]=="shadow"; assert r["decision"]=="HOLD"; assert r["reason"]=="RECURRING_PAYMENT_REQUIRES_APPROVAL"; assert r["execution_allowed"] is True; assert r["would_block"] is True; assert r["audit_hash"].startswith("sha256:")'

# --- request without mode uses config.mode (config has mode=enforce) ---
curl -fsS -X POST "http://$HOST:$PORT/v1/payment-proposals/evaluate" \
  -H 'content-type: application/json' \
  -d "{\"proposal\":$VALID_PROPOSAL,\"intent_envelope\":$VALID_INTENT}" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["mode"]=="enforce", f"expected config mode enforce, got {r[\"mode\"]}"; assert r["decision"]=="ACCEPT"; assert r["execution_allowed"] is True'

# --- require_signed_intent=true blocks valid proposal without envelope (shadow mode) ---
curl -fsS -X POST "http://$HOST:$PORT/v1/payment-proposals/evaluate" \
  -H 'content-type: application/json' \
  -d "{\"mode\":\"shadow\",\"proposal\":$VALID_PROPOSAL,\"intent_envelope\":null}" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["decision"]=="BLOCK", f"expected BLOCK, got {r[\"decision\"]}"; assert r["reason"]=="MISSING_INTENT_ENVELOPE", f"expected MISSING_INTENT_ENVELOPE, got {r[\"reason\"]}"; assert r["execution_allowed"] is True; assert r["would_block"] is True'

# --- audit limit: limit=999 clamped to max (100 from config) ---
curl -fsS "http://$HOST:$PORT/v1/audit/records?limit=999" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["limit"]==100, f"expected limit 100, got {r[\"limit\"]}"'

# --- audit limit: limit=abc returns 400 with JSON error ---
HTTP_CODE="$(curl -sS -o /tmp/payment_guard_bad_limit.json -w '%{http_code}' "http://$HOST:$PORT/v1/audit/records?limit=abc")"
if [ "$HTTP_CODE" != "400" ]; then
  echo "FAIL: expected 400 for limit=abc, got HTTP $HTTP_CODE" >&2
  exit 1
fi
python3 -c 'import json; r=json.load(open("/tmp/payment_guard_bad_limit.json",encoding="utf-8")); assert "error" in r, f"expected error field in response: {r}"'

# === replay-store tests (closes #149) ===

# After the first ACCEPT (test 1), replay-store.json must exist and contain exactly 1 nonce
curl -fsS "http://$HOST:$PORT/v1/replay-store" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["nonces"]==1, f"expected 1 nonce in replay store, got {r[\"nonces\"]}"'

# Replaying the same intent envelope must return BLOCK / INTENT_REPLAYED
curl -fsS -X POST "http://$HOST:$PORT/v1/payment-proposals/evaluate" \
  -H 'content-type: application/json' \
  -d "{\"mode\":\"enforce\",\"proposal\":$VALID_PROPOSAL,\"intent_envelope\":$VALID_INTENT}" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["decision"]=="BLOCK", f"expected BLOCK on replay, got {r[\"decision\"]}"; assert r["reason"]=="INTENT_REPLAYED", f"expected INTENT_REPLAYED, got {r[\"reason\"]}"; assert r["execution_allowed"] is False'

# replay-store.json must still contain exactly 1 nonce (replay attempt must not add a new entry)
curl -fsS "http://$HOST:$PORT/v1/replay-store" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["nonces"]==1, f"replay store grew unexpectedly: {r[\"nonces\"]} nonces"'

# restart-survival: verify replay-store.json exists on disk (service restart would reload it)
python3 -c 'import json, pathlib; p=pathlib.Path(".proofpath/replay-store.json"); data=json.loads(p.read_text()); assert len(data)==1, f"replay-store.json must have 1 entry, got {len(data)}"'

# --- audit records (8 total: enforce ACCEPT, shadow BLOCK, enforce HOLD, shadow HOLD,
#     config-mode ACCEPT, require_signed_intent BLOCK, replay-store ACCEPT, replay BLOCK) ---
curl -fsS "http://$HOST:$PORT/v1/audit/records" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["count"]==8, f"expected 8 audit records, got {r[\"count\"]}"; decisions=[row["decision"] for row in r["records"]]; assert decisions==["ACCEPT","BLOCK","HOLD","HOLD","ACCEPT","BLOCK","ACCEPT","BLOCK"], f"unexpected decisions: {decisions}"'

# --- hash-chain verification ---
python3 scripts/verify_audit_log.py .proofpath/audit.jsonl >/dev/null

echo "Agent Payment Guard service check passed."
