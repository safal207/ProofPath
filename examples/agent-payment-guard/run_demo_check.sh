#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
rm -f .proofpath/audit.jsonl

run_and_assert() {
  local file="$1" expected="$2"
  set +e
  out=$(python3 examples/agent-payment-guard/payment_guard.py "$file")
  rc=$?
  set -e
  if [[ "$out" != "$expected" ]]; then
    echo "unexpected output for $file: $out"
    exit 1
  fi
  case "$expected" in
    *'"decision":"ACCEPT"'*) [[ $rc -eq 0 ]] ;;
    *'"decision":"BLOCK"'*) [[ $rc -eq 2 ]] ;;
    *'"decision":"HOLD"'*) [[ $rc -eq 3 ]] ;;
  esac
}

run_and_assert examples/agent-payment-guard/payment_proposal.valid_micro_payment.json '{"decision":"ACCEPT","reason":"PAYMENT_WITHIN_SCOPE_AND_BUDGET"}'
run_and_assert examples/agent-payment-guard/payment_proposal.over_budget.json '{"decision":"BLOCK","reason":"OVER_BUDGET"}'
run_and_assert examples/agent-payment-guard/payment_proposal.missing_intent.json '{"decision":"BLOCK","reason":"MISSING_PAYMENT_INTENT"}'
run_and_assert examples/agent-payment-guard/payment_proposal.recipient_changed.json '{"decision":"BLOCK","reason":"RECIPIENT_MISMATCH"}'
run_and_assert examples/agent-payment-guard/payment_proposal.recurring_without_approval.json '{"decision":"HOLD","reason":"RECURRING_PAYMENT_REQUIRES_APPROVAL"}'

[[ -f .proofpath/audit.jsonl ]]
[[ $(wc -l < .proofpath/audit.jsonl) -eq 5 ]]
echo "demo check passed"
