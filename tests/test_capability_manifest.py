from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "governance" / "capability-manifest.v0.1.json"
VALIDATOR = ROOT / "scripts" / "validate_capability_manifest.py"

spec = importlib.util.spec_from_file_location("proofpath_capability_manifest", VALIDATOR)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CapabilityManifestTests(unittest.TestCase):
    def load(self) -> dict:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_committed_manifest_is_valid(self) -> None:
        data = self.load()
        self.assertEqual(module.validate_manifest(data), [])

    def test_noncanonical_capability_cannot_be_default_dependency(self) -> None:
        data = self.load()
        target = next(c for c in data["capabilities"] if c["id"] == "proofpath.poci.contract.v0.1")
        target["consumer_default_allowed"] = True
        errors = module.validate_manifest(data)
        self.assertTrue(any("non-canonical capability cannot be a default consumer dependency" in e for e in errors))

    def test_canonical_capability_cannot_depend_on_proposed_capability(self) -> None:
        data = self.load()
        scig = next(c for c in data["capabilities"] if c["id"] == "proofpath.scig.v0.1")
        scig["depends_on"] = ["proofpath.poci.contract.v0.1"]
        errors = module.validate_manifest(data)
        self.assertTrue(any("CANONICAL capability depends on non-canonical" in e for e in errors))

    def test_proposed_capability_requires_exact_head_sha(self) -> None:
        data = self.load()
        target = next(c for c in data["capabilities"] if c["id"] == "proofpath.deploy-guard.v0.1")
        target["head_sha"] = "main"
        errors = module.validate_manifest(data)
        self.assertTrue(any("requires exact lowercase head_sha" in e for e in errors))

    def test_dependency_cycle_fails_closed(self) -> None:
        data = self.load()
        root = next(c for c in data["capabilities"] if c["id"] == "proofpath.poci.contract.v0.1")
        root["depends_on"] = ["proofpath.reviewer-separation.v0.1"]
        errors = module.validate_manifest(data)
        self.assertTrue(any("dependency cycle" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
