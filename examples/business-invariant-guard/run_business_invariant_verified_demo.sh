#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

rm -rf .proofpath/asb03 proofpath-asb03-evidence-bundle

python3 examples/business-invariant-guard/business_invariant_demo.py \
  --fixtures examples/business-invariant-guard \
  --runtime .proofpath/asb03

python3 scripts/finalize_asb03_evidence.py \
  --runtime .proofpath/asb03 \
  --bundle proofpath-asb03-evidence-bundle

(
  cd proofpath-asb03-evidence-bundle
  sha256sum --check SHA256SUMS
)

echo "[asb-03] verified evidence: proofpath-asb03-evidence-bundle/"
