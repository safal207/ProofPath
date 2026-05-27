#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

rm -f .proofpath/audit.jsonl .proofpath/replay-store.json

HOST="127.0.0.1"
PORT="18787"
SERVICE="examples/agent-payment-guard/payment_guard_service.py"
CONFIG="examples/agent-payment-guard/payment_guard_service_config.json"
VALID_INTENT_TEMPLATE="examples/agent-payment-guard/intent_envelopes/intent.valid.json"

make_intent() {
  local nonce="$1"
  python3 - "$VALID_INTENT_TEMPLATE" "$nonce" <<'PY'
import json
import sys
from hashlib import sha256

secret = "proofpath-demo-secret-v0"
path, nonce = sys.argv[1], sys.argv[2]
intent = json.load(open(path, encoding="utf-8"))
intent["nonce"] = nonce
intent.pop("signature", None)
canonical = json.dumps(intent, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
intent["signature"] = sha256((canonical + secret).encode("utf-8")).hexdigest()
print(json.dumps(intent, separators=(",", ":")))
PY
}

start_service() {
  python3 "$SERVICE" \
    --config "$CONFIG" \
    --port "$PORT" \
    >/tmp/payment_guard_service.log 2>&1 &
  SERVICE_PID=$!
  for _ in $(seq 1 50); do
    if curl -fsS "http://$HOST:$PORT/v1/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.1
  done
  echo "FAIL: service did not start" >&2
  cat /tmp/payment_guard_service.log >&2 || true
  return 1
}

stop_service() {
  if [ -n "${SERVICE_PID:-}" ]; then
    kill "$SERVICE_PID" >/dev/null 2>&1 || true
    wait "$SERVICE_PID" >/dev/null 2>&1 || true
  fi
}

cleanup() {
  stop_service
}
trap cleanup EXIT

start_service

# --- health ---
curl -fsS "http://$HOST:$PORT/v1/health" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["status"]=="ok"; assert r["surface"]=="agent-payment-guard-service"; assert r["version"]=="0.1"'

VALID_PROPOSAL=$(cat examples/agent-payment-guard/payment_proposal.valid_micro_payment.json)
VALID_INTENT_ACCEPT=$(make_intent nonce_service_accept_001)
VALID_INTENT_CONFIG_MODE=$(make_intent nonce_service_config_mode_001)

# --- enforce ACCEPT (with intent envelope to satisfy require_signed_intent=true from config) ---
curl -fsS -X POST "http://$HOST:$PORT/v1/payment-proposals/evaluate" \
  -H 'content-type: application/json' \
  -d "{\"mode\":\"enforce\",\"proposal\":$VALID_PROPOSAL,\"intent_envelope\":$VALID_INTENT_ACCEPT}" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["mode"]=="enforce"; assert r["decision"]=="ACCEPT"; assert r["execution_allowed"] is True; assert r["would_block"] is False; assert r["audit_hash"].startswith("sha256:")'

# --- replay store contains accepted nonce ---
curl -fsS "http://$HOST:$PORT/v1/replay-store" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["nonces"]==1, r; assert "nonce_service_accept_001" in r["entries"], r'

# --- replaying the same envelope is blocked and does not grow replay store ---
curl -fsS -X POST "http://$HOST:$PORT/v1/payment-proposals/evaluate" \
  -H 'content-type: application/json' \
  -d "{\"mode\":\"enforce\",\"proposal\":$VALID_PROPOSAL,\"intent_envelope\":$VALID_INTENT_ACCEPT}" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["mode"]=="enforce"; assert r["decision"]=="BLOCK", r; assert r["reason"]=="INTENT_REPLAYED", r; assert r["execution_allowed"] is False; assert r["would_block"] is True; assert r["audit_hash"].startswith("sha256:")'

curl -fsS "http://$HOST:$PORT/v1/replay-store" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["nonces"]==1, r; assert "nonce_service_accept_001" in r["entries"], r'

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
  -d "{\"proposal\":$VALID_PROPOSAL,\"intent_envelope\":$VALID_INTENT_CONFIG_MODE}" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["mode"]=="enforce", ("expected config mode enforce", r); assert r["decision"]=="ACCEPT"; assert r["execution_allowed"] is True'

# --- require_signed_intent=true blocks valid proposal without envelope (shadow mode) ---
curl -fsS -X POST "http://$HOST:$PORT/v1/payment-proposals/evaluate" \
  -H 'content-type: application/json' \
  -d "{\"mode\":\"shadow\",\"proposal\":$VALID_PROPOSAL,\"intent_envelope\":null}" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["decision"]=="BLOCK", ("expected BLOCK", r); assert r["reason"]=="MISSING_INTENT_ENVELOPE", ("expected MISSING_INTENT_ENVELOPE", r); assert r["execution_allowed"] is True; assert r["would_block"] is True'

# --- audit limit: limit=999 clamped to max (100 from config) ---
curl -fsS "http://$HOST:$PORT/v1/audit/records?limit=999" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["limit"]==100, ("expected limit 100", r)'

# --- audit limit: limit=abc returns 400 with JSON error ---
HTTP_CODE="$(curl -sS -o /tmp/payment_guard_bad_limit.json -w '%{http_code}' "http://$HOST:$PORT/v1/audit/records?limit=abc")"
if [ "$HTTP_CODE" != "400" ]; then
  echo "FAIL: expected 400 for limit=abc, got HTTP $HTTP_CODE" >&2
  exit 1
fi
python3 -c 'import json; r=json.load(open("/tmp/payment_guard_bad_limit.json",encoding="utf-8")); assert "error" in r, ("expected error field", r)'

# --- replay store survives service restart ---
[[ -f .proofpath/replay-store.json ]]
stop_service
start_service
curl -fsS "http://$HOST:$PORT/v1/replay-store" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["nonces"]==2, r; assert "nonce_service_accept_001" in r["entries"], r; assert "nonce_service_config_mode_001" in r["entries"], r'

# --- audit records (7 total: ACCEPT, replay BLOCK, BLOCK, HOLD, HOLD, ACCEPT, missing-envelope BLOCK) ---
curl -fsS "http://$HOST:$PORT/v1/audit/records" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["count"]==7, ("expected 7 audit records", r); decisions=[row["decision"] for row in r["records"]]; assert decisions==["ACCEPT","BLOCK","BLOCK","HOLD","HOLD","ACCEPT","BLOCK"], ("unexpected decisions", decisions)'

# --- hash-chain verification ---
python3 scripts/verify_audit_log.py .proofpath/audit.jsonl >/dev/null

echo "Agent Payment Guard service check passed."
