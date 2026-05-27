#!/usr/bin/env bash
# ProofPath Agent Payment Guard — end-to-end evidence demo.
#
# Runs the full product story in one script:
#   1. Start guard service (enforce mode, signed intent required)
#   2. Send valid signed-intent proposal -> ACCEPT
#   3. Replay same envelope -> BLOCK / INTENT_REPLAYED
#   4. Stop service, export evidence bundle
#   5. Verify bundled audit log hash chain
#   6. Print summary
#
# Run from repo root:
#   bash examples/agent-payment-guard/run_e2e_evidence_demo.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

rm -rf proofpath-evidence-bundle/
rm -f .proofpath/audit.jsonl .proofpath/replay-store.json

HOST="127.0.0.1"
PORT="18789"
SERVICE="examples/agent-payment-guard/payment_guard_service.py"
CONFIG="examples/agent-payment-guard/payment_guard_service_config.json"

echo
echo "[e2e] ProofPath Agent Payment Guard \xe2\x80\x94 end-to-end evidence demo"
echo "[e2e] starting guard service (enforce mode, signed intent required)..."

python3 "$SERVICE" \
  --config "$CONFIG" \
  --port "$PORT" \
  >/tmp/payment_guard_e2e.log 2>&1 &
SERVICE_PID=$!
cleanup() {
  kill "$SERVICE_PID" >/dev/null 2>&1 || true
  rm -rf proofpath-evidence-bundle/
}
trap cleanup EXIT

for _ in $(seq 1 50); do
  if curl -fsS "http://$HOST:$PORT/v1/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done
echo "[e2e] service ready."
echo

VALID_INTENT=$(cat examples/agent-payment-guard/intent_envelopes/intent.valid.json)
VALID_PROPOSAL=$(cat examples/agent-payment-guard/payment_proposal.valid_micro_payment.json)

# --- step 1: ACCEPT ---
echo "[e2e] step 1 \xe2\x80\x94 valid signed intent: ACCEPT"
RESP=$(curl -fsS -X POST "http://$HOST:$PORT/v1/payment-proposals/evaluate" \
  -H 'content-type: application/json' \
  -d "{\"mode\":\"enforce\",\"proposal\":$VALID_PROPOSAL,\"intent_envelope\":$VALID_INTENT}")
python3 - <<EOF
import json, sys
r = json.loads('"'"'$RESP'"'"')
assert r['decision'] == 'ACCEPT', f"expected ACCEPT, got {r}"
assert r['execution_allowed'] is True
print(f"  decision: {r['decision']}")
print(f"  execution_allowed: {r['execution_allowed']}")
print(f"  audit_hash: {r['audit_hash']}")
EOF
echo

# --- step 2: BLOCK / INTENT_REPLAYED ---
echo "[e2e] step 2 \xe2\x80\x94 replay same envelope: BLOCK / INTENT_REPLAYED"
RESP2=$(curl -fsS -X POST "http://$HOST:$PORT/v1/payment-proposals/evaluate" \
  -H 'content-type: application/json' \
  -d "{\"mode\":\"enforce\",\"proposal\":$VALID_PROPOSAL,\"intent_envelope\":$VALID_INTENT}")
python3 - <<EOF
import json, sys
r = json.loads('"'"'$RESP2'"'"')
assert r['decision'] == 'BLOCK', f"expected BLOCK, got {r}"
assert r['reason'] == 'INTENT_REPLAYED', f"expected INTENT_REPLAYED, got {r['reason']}"
assert r['execution_allowed'] is False
print(f"  decision: {r['decision']}")
print(f"  reason: {r['reason']}")
print(f"  execution_allowed: {r['execution_allowed']}")
EOF
echo

# --- step 3: export ---
echo "[e2e] step 3 \xe2\x80\x94 stopping service and exporting evidence bundle"
kill "$SERVICE_PID" >/dev/null 2>&1 || true
sleep 0.2

python3 scripts/export_payment_guard_evidence.py \
  --out proofpath-evidence-bundle/
echo

# --- step 4: verify bundled audit log ---
echo "[e2e] step 4 \xe2\x80\x94 verifying bundled audit log hash chain"
python3 - <<'PYEOF'
import json, pathlib, sys
from hashlib import sha256

def canonical(r): return json.dumps(r, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
def compute_hash(r):
    p = dict(r); p.pop('hash', None)
    return 'sha256:' + sha256(canonical(p).encode()).hexdigest()

path = pathlib.Path('proofpath-evidence-bundle/audit.jsonl')
lines = [l for l in path.read_text().splitlines() if l.strip()]
prev = 'GENESIS'
for i, line in enumerate(lines, 1):
    rec = json.loads(line)
    assert rec.get('previous_hash') == prev, f"line {i}: previous_hash mismatch"
    assert rec.get('hash') == compute_hash(rec), f"line {i}: hash mismatch"
    prev = rec['hash']
print(f"  audit log: OK ({len(lines)} records, chain valid)")
PYEOF
echo

# --- summary ---
RECORDS=$(python3 -c "import pathlib; lines=[l for l in pathlib.Path('.proofpath/audit.jsonl').read_text().splitlines() if l.strip()]; print(len(lines))")
NONCES=$(python3 -c "import json,pathlib; d=json.loads(pathlib.Path('.proofpath/replay-store.json').read_text()); print(len(d))")

echo "[e2e] \xe2\x9c\x93 ProofPath Agent Payment Guard demo complete."
echo
echo "Bundle contents:"
echo "  proofpath-evidence-bundle/"
echo "    audit.jsonl                        ($RECORDS records)"
echo "    replay-store.json                  ($NONCES spent nonce)"
echo "    payment_guard_service_config.json"
echo "    payment_policy.json"
echo "    verification_report.json"
echo
echo "What was demonstrated:"
echo "  ACCEPT   valid signed intent envelope"
echo "  BLOCK    replayed intent (INTENT_REPLAYED)"
echo "  EXPORT   portable evidence bundle"
echo "  VERIFY   hash-chain integrity confirmed"

# disable cleanup trap for bundle (leave for user inspection)
trap - EXIT
kill "$SERVICE_PID" >/dev/null 2>&1 || true
