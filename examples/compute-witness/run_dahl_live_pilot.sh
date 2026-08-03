#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTPUT_DIR="${PROOFPATH_PILOT_OUTPUT_DIR:-$REPO_ROOT/.proofpath/gonka-pilots}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
CLAIM_ID="${GONKA_PILOT_CLAIM_ID:-dahl-live-pilot-$TIMESTAMP}"
RECEIPT_PATH="$OUTPUT_DIR/$CLAIM_ID.receipt.json"
KEY_ENTERED_HERE=0

cleanup() {
  if [[ "$KEY_ENTERED_HERE" -eq 1 ]]; then
    unset GONKA_API_KEY
  fi
}
trap cleanup EXIT INT TERM

export GONKA_BASE_URL="${GONKA_BASE_URL:-https://inference.dahl.global/v1/chat/completions}"
export GONKA_MODEL="${GONKA_MODEL:-MiniMaxAI/MiniMax-M2.7}"
export GONKA_REPLICAS="${GONKA_REPLICAS:-3}"
export GONKA_TIMEOUT_SECONDS="${GONKA_TIMEOUT_SECONDS:-90}"
export GONKA_AGREEMENT_THRESHOLD="${GONKA_AGREEMENT_THRESHOLD:-0.95}"

if [[ -z "${GONKA_API_KEY:-}" ]]; then
  read -rsp "Dahl/Gonka API key: " GONKA_API_KEY
  echo
  export GONKA_API_KEY
  KEY_ENTERED_HERE=1
fi

if [[ ! "$GONKA_REPLICAS" =~ ^[0-9]+$ ]] || (( GONKA_REPLICAS < 2 || GONKA_REPLICAS > 10 )); then
  echo "FAIL GONKA_REPLICAS must be an integer between 2 and 10 for a live pilot" >&2
  exit 2
fi

mkdir -p "$OUTPUT_DIR"
chmod 700 "$OUTPUT_DIR"

TMP_RECEIPT="$(mktemp "$OUTPUT_DIR/.pilot.XXXXXX")"
trap 'rm -f "$TMP_RECEIPT"; cleanup' EXIT INT TERM

python3 "$REPO_ROOT/examples/compute-witness/gonka_adapter.py" \
  --claim-id "$CLAIM_ID" \
  --replicas "$GONKA_REPLICAS" \
  --prompt 'Reply with exactly: ProofPath OK' \
  > "$TMP_RECEIPT"

chmod 600 "$TMP_RECEIPT"
mv "$TMP_RECEIPT" "$RECEIPT_PATH"
trap cleanup EXIT INT TERM

set +e
python3 "$REPO_ROOT/scripts/gonka_pilot_summary.py" "$RECEIPT_PATH"
SUMMARY_STATUS=$?
set -e

echo
echo "Pilot receipt saved to: $RECEIPT_PATH"
echo "The receipt contains hashes and metadata, not the API key or reasoning text."

if [[ "$SUMMARY_STATUS" -ne 0 ]]; then
  exit "$SUMMARY_STATUS"
fi
