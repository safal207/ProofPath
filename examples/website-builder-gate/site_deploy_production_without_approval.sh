#!/usr/bin/env bash
set -euo pipefail

curl -i -X POST http://127.0.0.1:8787/demo/protected \
  -H 'content-type: application/json' \
  -H 'x-proofpath-intent-id: intent_deploy_production_001' \
  -H 'x-proofpath-causal-parent: decision_agent_ready_to_deploy' \
  -H 'x-proofpath-scope: website.deploy.production' \
  -H 'x-proofpath-reversibility: irreversible' \
  -d '{"agent":"site-builder-agent","action":"deploy_production","target":"production","note":"production deploy attempted without explicit human approval"}'
