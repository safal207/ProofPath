#!/usr/bin/env bash
set -euo pipefail

curl -i -X POST http://127.0.0.1:8787/demo/protected \
  -H 'content-type: application/json' \
  -H 'x-proofpath-intent-id: intent_change_production_network_policy_001' \
  -H 'x-proofpath-causal-parent: decision_agent_detected_network_issue' \
  -H 'x-proofpath-scope: network.firewall.change' \
  -H 'x-proofpath-reversibility: irreversible' \
  -d '{"agent":"infra-assistant","action":"change_network_policy","target":"production-edge","note":"production network policy change attempted without explicit human approval"}'
