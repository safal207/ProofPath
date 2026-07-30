#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"
rm -rf .proofpath/asb04-three-graph proofpath-asb04-three-graph-evidence-bundle
python3 examples/order-timeout-three-graph/three_graph_asb04_demo.py \
  --fixtures examples/order-timeout-three-graph \
  --runtime .proofpath/asb04-three-graph
python3 scripts/finalize_asb04_three_graph_evidence.py \
  --runtime .proofpath/asb04-three-graph \
  --bundle proofpath-asb04-three-graph-evidence-bundle
(
  cd proofpath-asb04-three-graph-evidence-bundle
  sha256sum --check SHA256SUMS
)
echo "[asb-04] verified three-graph evidence: proofpath-asb04-three-graph-evidence-bundle/"
