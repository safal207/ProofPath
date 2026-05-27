#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

rm -f .proofpath/audit.jsonl .proofpath/replay-store.json

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

# Legacy non-envelope checks
check_case ACCEPT PAYMENT_WITHIN_SCOPE_AND_BUDGET 0 "$BASE_PROPOSAL"
check_case BLOCK OVER_BUDGET 2 examples/agent-payment-guard/payment_proposal.over_budget.json
check_case BLOCK MISSING_PAYMENT_INTENT 2 examples/agent-payment-guard/payment_proposal.missing_intent.json
check_case BLOCK RECIPIENT_MISMATCH 2 examples/agent-payment-guard/payment_proposal.recipient_changed.json
check_case HOLD RECURRING_PAYMENT_REQUIRES_APPROVAL 3 examples/agent-payment-guard/payment_proposal.recurring_without_approval.json
check_case BLOCK ASSET_NOT_ALLOWED 2 examples/agent-payment-guard/payment_proposal.asset_not_allowed.json
check_case BLOCK INVALID_AMOUNT 2 examples/agent-payment-guard/payment_proposal.invalid_amount.json

# Signed-envelope checks
check_case ACCEPT PAYMENT_WITHIN_SIGNED_INTENT_ENVELOPE 0 "$BASE_PROPOSAL" --intent-envelope examples/agent-payment-guard/intent_envelopes/intent.valid.json --require-intent-envelope
check_case BLOCK MISSING_INTENT_ENVELOPE 2 "$BASE_PROPOSAL" --require-intent-envelope
check_case BLOCK INTENT_EXPIRED 2 "$BASE_PROPOSAL" --intent-envelope examples/agent-payment-guard/intent_envelopes/intent.expired.json
check_case BLOCK INTENT_RECIPIENT_MISMATCH 2 "$BASE_PROPOSAL" --intent-envelope examples/agent-payment-guard/intent_envelopes/intent.recipient_mismatch.json
check_case BLOCK INVALID_INTENT_SIGNATURE 2 "$BASE_PROPOSAL" --intent-envelope examples/agent-payment-guard/intent_envelopes/intent.invalid_signature.json
check_case BLOCK INTENT_REPLAYED 2 "$BASE_PROPOSAL" --intent-envelope examples/agent-payment-guard/intent_envelopes/intent.replayed.json
check_case BLOCK INTENT_ID_MISMATCH 2 "$BASE_PROPOSAL" --intent-envelope examples/agent-payment-guard/intent_envelopes/intent.intent_id_mismatch.json
check_case BLOCK INTENT_PAYMENT_MODE_MISMATCH 2 "$BASE_PROPOSAL" --intent-envelope examples/agent-payment-guard/intent_envelopes/intent.payment_mode_mismatch.json
check_case BLOCK MISSING_INTENT_ENVELOPE 2 "$BASE_PROPOSAL" --intent-envelope examples/agent-payment-guard/intent_envelopes/intent.missing.json
check_case BLOCK INVALID_INTENT_SIGNATURE 2 "$BASE_PROPOSAL" --intent-envelope examples/agent-payment-guard/intent_envelopes/intent.malformed.json

[[ -f .proofpath/audit.jsonl ]]
[[ -f .proofpath/replay-store.json ]]
python3 - <<'PY'
import json
from pathlib import Path
records = [json.loads(x) for x in Path('.proofpath/audit.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
assert len(records) == 17, len(records)
assert records[0]["intent_verified"] is False
assert records[7]["intent_verified"] is True
assert records[-2]["reason"] == "MISSING_INTENT_ENVELOPE"
assert records[-2]["intent_load_error"] == "missing"
assert records[-1]["reason"] == "INVALID_INTENT_SIGNATURE"
assert records[-1]["intent_load_error"] == "malformed"
store = json.loads(Path('.proofpath/replay-store.json').read_text(encoding='utf-8'))
assert "nonce_market_research_001" in store, store
assert len(store) == 1, store
PY

echo "Agent Payment Guard demo check passed."
python3 scripts/verify_audit_log.py .proofpath/audit.jsonl
