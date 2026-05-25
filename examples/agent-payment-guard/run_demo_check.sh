#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

rm -f .proofpath/audit.jsonl

check_case() {
  local expected_decision="$1" expected_reason="$2" expected_status="$3"
  shift 3
  set +e
  output=$(python3 examples/agent-payment-guard/payment_guard.py "$@")
  status=$?
  set -e
  [[ "$status" -eq "$expected_status" ]]
  python3 - "$output" "$expected_decision" "$expected_reason" <<'PY'
import json, sys
payload = json.loads(sys.argv[1])
assert payload["decision"] == sys.argv[2], payload
assert payload["reason"] == sys.argv[3], payload
PY
}

BASE_PROPOSAL="examples/agent-payment-guard/payment_proposal.valid_micro_payment.json"

check_case ACCEPT PAYMENT_WITHIN_SIGNED_INTENT_ENVELOPE 0 "$BASE_PROPOSAL" --intent-envelope examples/agent-payment-guard/intent_envelopes/intent.valid.json --require-intent-envelope
check_case BLOCK MISSING_INTENT_ENVELOPE 2 "$BASE_PROPOSAL" --require-intent-envelope
check_case BLOCK INTENT_EXPIRED 2 "$BASE_PROPOSAL" --intent-envelope examples/agent-payment-guard/intent_envelopes/intent.expired.json
check_case BLOCK INTENT_RECIPIENT_MISMATCH 2 "$BASE_PROPOSAL" --intent-envelope examples/agent-payment-guard/intent_envelopes/intent.recipient_mismatch.json
check_case BLOCK INVALID_INTENT_SIGNATURE 2 "$BASE_PROPOSAL" --intent-envelope examples/agent-payment-guard/intent_envelopes/intent.invalid_signature.json
check_case BLOCK INTENT_REPLAYED 2 "$BASE_PROPOSAL" --intent-envelope examples/agent-payment-guard/intent_envelopes/intent.replayed.json

[[ -f .proofpath/audit.jsonl ]]
python3 - <<'PY'
import json
from pathlib import Path
records = [json.loads(x) for x in Path('.proofpath/audit.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
assert len(records) == 6, len(records)
assert records[0]["intent_verified"] is True
PY

echo "Agent Payment Guard demo check passed."
python3 scripts/verify_audit_log.py .proofpath/audit.jsonl
