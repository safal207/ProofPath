#!/usr/bin/env bash
set -euo pipefail

curl -i -X POST http://127.0.0.1:8787/demo/protected \
  -H 'content-type: application/json' \
  -H 'x-proofpath-intent-id: intent_replace_public_assets_001' \
  -H 'x-proofpath-causal-parent: decision_agent_cleanup_assets' \
  -H 'x-proofpath-scope: website.delete' \
  -H 'x-proofpath-reversibility: irreversible' \
  -d '{"agent":"site-builder-agent","action":"replace_public_assets","path":"public/","note":"destructive website asset change attempted without approval"}'
