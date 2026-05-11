#!/usr/bin/env bash
set -euo pipefail

curl -i -X POST http://127.0.0.1:8787/demo/protected \
  -H 'content-type: application/json' \
  -H 'x-proofpath-intent-id: intent_approved_production_rollback_001' \
  -H 'x-proofpath-causal-parent: decision_human_approved_rollback' \
  -H 'x-proofpath-scope: cicd.production.rollback' \
  -H 'x-proofpath-reversibility: irreversible' \
  -H 'x-proofpath-human-approval: approval_release_manager_42' \
  -d '{"agent":"devops-assistant","action":"production_rollback","target":"production-environment","note":"production rollback with explicit human approval"}'
