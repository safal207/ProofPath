#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

rm -f .proofpath/audit.jsonl

HOST="127.0.0.1"
PORT="18787"
SERVICE="examples/agent-payment-guard/payment_guard_service.py"

python3 "$SERVICE" --host "$HOST" --port "$PORT" >/tmp/payment_guard_service.log 2>&1 &
SERVICE_PID=$!
cleanup() {
  kill "$SERVICE_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

for _ in $(seq 1 50); do
  if curl -fsS "http://$HOST:$PORT/v1/health" >/dev/null; then
    break
  fi
  sleep 0.1
done
curl -fsS "http://$HOST:$PORT/v1/health" | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["status"]=="ok"; assert r["surface"]=="agent-payment-guard-service"; assert r["version"]=="0.1"'

VALID_INTENT=$(cat examples/agent-payment-guard/intent_envelopes/intent.valid.json)
VALID_PROPOSAL=$(cat examples/agent-payment-guard/payment_proposal.valid_micro_payment.json)

curl -fsS -X POST "http://$HOST:$PORT/v1/payment-proposals/evaluate" \
  -H 'content-type: application/json' \
  -d "{\"mode\":\"enforce\",\"proposal\":$VALID_PROPOSAL,\"intent_envelope\":$VALID_INTENT}" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["mode"]=="enforce"; assert r["decision"]=="ACCEPT"; assert r["execution_allowed"] is True; assert r["would_block"] is False; assert r["audit_hash"].startswith("sha256:")'

BAD_PROPOSAL=$(cat examples/agent-payment-guard/payment_proposal.asset_not_allowed.json)
curl -fsS -X POST "http://$HOST:$PORT/v1/payment-proposals/evaluate" \
  -H 'content-type: application/json' \
  -d "{\"mode\":\"shadow\",\"proposal\":$BAD_PROPOSAL,\"intent_envelope\":null}" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["mode"]=="shadow"; assert r["decision"]=="BLOCK"; assert r["execution_allowed"] is True; assert r["would_block"] is True; assert r["audit_hash"].startswith("sha256:")'

curl -fsS "http://$HOST:$PORT/v1/audit/records" | python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["count"]==2; assert len(r["records"])==2; assert r["records"][0]["decision"]=="ACCEPT"; assert r["records"][1]["decision"]=="BLOCK"'

python3 scripts/verify_audit_log.py .proofpath/audit.jsonl >/dev/null

echo "Agent Payment Guard service check passed."
