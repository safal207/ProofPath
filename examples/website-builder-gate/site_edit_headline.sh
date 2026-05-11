#!/usr/bin/env bash
set -euo pipefail

curl -i -X POST http://127.0.0.1:8787/demo/protected \
  -H 'content-type: application/json' \
  -H 'x-proofpath-intent-id: intent_update_landing_headline_001' \
  -H 'x-proofpath-causal-parent: decision_user_requested_site_copy_update' \
  -H 'x-proofpath-scope: website.content.edit' \
  -H 'x-proofpath-reversibility: reversible' \
  -d '{"agent":"site-builder-agent","action":"edit_headline","path":"src/pages/index.tsx","change":"Update landing page headline copy","note":"safe reversible content edit"}'
