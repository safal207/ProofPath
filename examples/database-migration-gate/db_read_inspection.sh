#!/usr/bin/env bash
set -euo pipefail

curl -i -X POST http://127.0.0.1:8787/demo/protected \
  -H 'content-type: application/json' \
  -H 'x-proofpath-intent-id: intent_read_database_schema_001' \
  -H 'x-proofpath-causal-parent: decision_user_requested_db_inspection' \
  -H 'x-proofpath-scope: database.read.inspect' \
  -H 'x-proofpath-reversibility: reversible' \
  -d '{"agent":"db-assistant","action":"inspect_database_schema","target":"staging-db","note":"safe read-only database inspection"}'
