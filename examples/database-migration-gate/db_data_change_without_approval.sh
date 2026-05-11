#!/usr/bin/env bash
set -euo pipefail

curl -i -X POST http://127.0.0.1:8787/demo/protected \
  -H 'content-type: application/json' \
  -H 'x-proofpath-intent-id: intent_change_production_data_001' \
  -H 'x-proofpath-causal-parent: decision_agent_prepared_data_fix' \
  -H 'x-proofpath-scope: database.data.mutate' \
  -H 'x-proofpath-reversibility: irreversible' \
  -d '{"agent":"db-assistant","action":"change_production_data","target":"production-db","note":"production data-changing action attempted without explicit human approval"}'
