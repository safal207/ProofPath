#!/usr/bin/env bash
set -euo pipefail

curl -i -X POST http://127.0.0.1:8787/demo/protected \
  -H 'content-type: application/json' \
  -H 'x-proofpath-intent-id: intent_production_deploy_001' \
  -H 'x-proofpath-causal-parent: decision_agent_ready_to_release' \
  -H 'x-proofpath-scope: cicd.production.deploy' \
  -H 'x-proofpath-reversibility: irreversible' \
  -d '{"agent":"devops-assistant","action":"production_deploy","target":"production-environment","note":"production deployment attempted without explicit human approval"}'
