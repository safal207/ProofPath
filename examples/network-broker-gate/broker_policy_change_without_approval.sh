#!/usr/bin/env bash
set -euo pipefail

curl -i -X POST http://127.0.0.1:8787/demo/protected \
  -H 'content-type: application/json' \
  -H 'x-proofpath-intent-id: intent_change_broker_policy_001' \
  -H 'x-proofpath-causal-parent: decision_agent_reduce_message_lag' \
  -H 'x-proofpath-scope: broker.policy.change' \
  -H 'x-proofpath-reversibility: irreversible' \
  -d '{"agent":"infra-assistant","action":"change_broker_policy","target":"production-message-stream","note":"high-risk broker policy change attempted without explicit human approval"}'
