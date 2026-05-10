#!/usr/bin/env bash
set -euo pipefail

curl -i -X POST http://127.0.0.1:8787/demo/protected \
  -H 'content-type: application/json' \
  -H 'x-proofpath-intent-id: intent_inspect_account_001' \
  -H 'x-proofpath-causal-parent: decision_user_requested_inspection' \
  -H 'x-proofpath-scope: account.delete' \
  -H 'x-proofpath-reversibility: irreversible' \
  -d '{"agent":"demo-agent","action":"delete_account","account_id":"acct_123","note":"agent attempted irreversible action without approval"}'
