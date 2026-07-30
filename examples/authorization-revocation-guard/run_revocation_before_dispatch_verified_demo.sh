#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

rm -rf .proofpath/asb02 proofpath-asb02-evidence-bundle

python3 examples/authorization-revocation-guard/revocation_guard_demo.py \
  --fixtures examples/authorization-revocation-guard \
  --runtime .proofpath/asb02

python3 scripts/finalize_asb02_evidence.py \
  --runtime .proofpath/asb02 \
  --bundle proofpath-asb02-evidence-bundle

(
  cd proofpath-asb02-evidence-bundle
  sha256sum --check SHA256SUMS
)

echo "[asb-02] verified evidence: proofpath-asb02-evidence-bundle/"
