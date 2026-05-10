#!/usr/bin/env bash
set -euo pipefail

curl -i -X POST http://127.0.0.1:8787/demo/protected \
  -H 'content-type: application/json' \
  -H 'x-proofpath-intent-id: intent_delete_account_approved_001' \
  -H 'x-proofpath-causal-parent: decision_human_approved_delete' \
  -H 'x-proofpath-scope: account.delete' \
  -H 'x-proofpath-reversibility: irreversible' \
  -H 'x-proofpath-human-approval: approval_human_42' \
  -d '{"agent":"demo-agent","action":"delete_account","account_id":"acct_123","note":"irreversible action with explicit human approval"}'
