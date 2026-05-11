#!/usr/bin/env bash
set -euo pipefail

curl -i -X POST http://127.0.0.1:8787/demo/protected \
  -H 'content-type: application/json' \
  -H 'x-proofpath-intent-id: intent_read_network_status_001' \
  -H 'x-proofpath-causal-parent: decision_user_requested_network_diagnostic' \
  -H 'x-proofpath-scope: network.diagnostic.read' \
  -H 'x-proofpath-reversibility: reversible' \
  -d '{"agent":"infra-assistant","action":"read_network_status","target":"staging-edge","note":"safe read-only network diagnostic"}'
