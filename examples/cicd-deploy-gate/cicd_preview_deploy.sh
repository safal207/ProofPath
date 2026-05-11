#!/usr/bin/env bash
set -euo pipefail

curl -i -X POST http://127.0.0.1:8787/demo/protected \
  -H 'content-type: application/json' \
  -H 'x-proofpath-intent-id: intent_preview_deploy_001' \
  -H 'x-proofpath-causal-parent: decision_pr_checks_passed' \
  -H 'x-proofpath-scope: cicd.preview.deploy' \
  -H 'x-proofpath-reversibility: reversible' \
  -d '{"agent":"devops-assistant","action":"preview_deploy","target":"preview-environment","note":"safe reversible preview deployment"}'
