#!/usr/bin/env bash
set -euo pipefail

curl -i -X POST http://127.0.0.1:8787/demo/protected \
  -H 'content-type: application/json' \
  -H 'x-proofpath-intent-id: intent_change_database_schema_001' \
  -H 'x-proofpath-causal-parent: decision_agent_prepared_migration' \
  -H 'x-proofpath-scope: database.schema.migrate' \
  -H 'x-proofpath-reversibility: irreversible' \
  -d '{"agent":"db-assistant","action":"change_database_schema","target":"production-db","note":"production schema change attempted without explicit human approval"}'
