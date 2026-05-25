#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

rm -f .proofpath/audit.jsonl

check_case() {
  local file="$1" expected_decision="$2" expected_reason="$3" expected_status="$4"
  set +e
  output=$(python3 examples/agent-payment-guard/payment_guard.py "$file")
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

check_case examples/agent-payment-guard/payment_proposal.valid_micro_payment.json ACCEPT PAYMENT_WITHIN_SCOPE_AND_BUDGET 0
check_case examples/agent-payment-guard/payment_proposal.over_budget.json BLOCK OVER_BUDGET 2
check_case examples/agent-payment-guard/payment_proposal.missing_intent.json BLOCK MISSING_PAYMENT_INTENT 2
check_case examples/agent-payment-guard/payment_proposal.recipient_changed.json BLOCK RECIPIENT_MISMATCH 2
check_case examples/agent-payment-guard/payment_proposal.recurring_without_approval.json HOLD RECURRING_PAYMENT_REQUIRES_APPROVAL 3

[[ -f .proofpath/audit.jsonl ]]
python3 - <<'PY'
import json
from pathlib import Path
records = [json.loads(x) for x in Path('.proofpath/audit.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
assert len(records) == 5, len(records)
PY

echo "Agent Payment Guard demo check passed."
