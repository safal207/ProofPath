#!/usr/bin/env bash
set -euo pipefail

curl -i -X POST http://127.0.0.1:8787/demo/protected \
  -H 'x-proofpath-intent-id: intent_9f21' \
  -H 'x-proofpath-causal-parent: decision_71ab' \
  -H 'x-proofpath-scope: payments.transfer.once' \
  -H 'x-proofpath-reversibility: irreversible'
