from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "control-cloud" / "build_snapshot.py"
DASHBOARD = ROOT / "control-cloud" / "index.html"
DOC = ROOT / "control-cloud" / "README.md"
WORKFLOW = ROOT / ".github" / "workflows" / "proofpath-control-cloud.yml"
DATASET_SCHEMA = ROOT / "schemas" / "proofpath-control-cloud-dataset-v0.1.schema.json"
SNAPSHOT_SCHEMA = ROOT / "schemas" / "proofpath-control-cloud-snapshot-v0.1.schema.json"


class ControlCloudSecurityTests(unittest.TestCase):
    def test_builder_has_no_network_payment_or_command_execution(self):
        text = BUILDER.read_text(encoding="utf-8")
        for forbidden in (
            "urllib",
            "requests",
            "http.client",
            "socket",
            "subprocess",
            "os.system",
            "shell=True",
            "eval(",
            "exec(",
            "stripe",
            "paypal",
            "web3",
        ):
            self.assertNotIn(forbidden, text.lower())

    def test_financial_math_uses_integer_minor_units_and_basis_points(self):
        text = BUILDER.read_text(encoding="utf-8")
        self.assertIn("allocations_bps", text)
        self.assertIn("// 10_000", text)
        self.assertIn("floating-point numbers are forbidden", text)
        self.assertNotRegex(text, r"\bfloat\(")

    def test_snapshot_preserves_nonpayment_and_no_authority_boundary(self):
        text = BUILDER.read_text(encoding="utf-8")
        for phrase in (
            '"financial_mode": "SIMULATION_ONLY"',
            '"financial_status": "SIMULATION_ONLY_NOT_PAYABLE"',
            '"payments_executed": False',
            '"insurance_provided": False',
            '"deployment_performed": False',
            '"authority_granted": False',
            '"external_quorum_claimed": False',
        ):
            self.assertIn(phrase, text)

    def test_dashboard_is_dependency_free_and_uses_safe_text_rendering(self):
        text = DASHBOARD.read_text(encoding="utf-8")
        self.assertNotIn("https://", text)
        self.assertNotIn("http://", text)
        self.assertNotIn("document.write", text)
        self.assertIn("textContent", text)
        self.assertIn('accept="application/json"', text)
        self.assertIn("SIMULATION ONLY", text)

    def test_dashboard_does_not_execute_payments_or_deployments(self):
        text = DASHBOARD.read_text(encoding="utf-8").lower()
        for forbidden in (
            "stripe",
            "paypal",
            "walletconnect",
            "ethereum",
            "kubectl",
            "terraform apply",
            "fetch('/pay",
        ):
            self.assertNotIn(forbidden, text)

    def test_workflow_permissions_are_narrow_and_snapshot_is_attested(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("contents: read", text)
        self.assertIn("id-token: write", text)
        self.assertIn("attestations: write", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("pull-requests: write", text)
        self.assertEqual(text.count("actions/attest-build-provenance@v2"), 2)

    def test_workflow_builds_exact_fixture_and_audit_export(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        for value in (
            "control-cloud/build_snapshot.py",
            "examples/control-cloud/assured-actions.json",
            "examples/control-cloud/settlement-policy.json",
            "control-cloud-snapshot.json",
            "audit-export.jsonl",
            "sha256:a782f7a1b8fc5d7a6a11815066191a304a32231d969381637902a75f55467deb",
        ):
            self.assertIn(value, text)

    def test_schemas_are_strict_and_keep_simulation_mode_constant(self):
        dataset = DATASET_SCHEMA.read_text(encoding="utf-8")
        snapshot = SNAPSHOT_SCHEMA.read_text(encoding="utf-8")
        for text in (dataset, snapshot):
            self.assertIn('"additionalProperties": false', text)
            self.assertIn('"const": "SIMULATION_ONLY"', text)
        self.assertIn('"proofpath.control-cloud.dataset.v0.1"', dataset)
        self.assertIn('"proofpath.control-cloud.snapshot.v0.1"', snapshot)

    def test_documentation_is_explicit_about_product_boundary(self):
        text = DOC.read_text(encoding="utf-8")
        for phrase in (
            "does not move money",
            "not an invoice",
            "not insurance",
            "does not re-run Deploy Guard",
            "signed build artifact",
            "SIMULATION_ONLY_NOT_PAYABLE",
        ):
            self.assertIn(phrase, text)

    def test_no_real_cloud_or_deployment_command_is_added(self):
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (BUILDER, DASHBOARD, WORKFLOW)
        )
        forbidden_patterns = (
            r"\bkubectl\s+(apply|set|rollout)",
            r"\bterraform\s+apply",
            r"\baws\s+.*deploy",
            r"\bgcloud\s+.*deploy",
            r"\baz\s+.*deploy",
            r"\bhelm\s+(install|upgrade)",
        )
        for pattern in forbidden_patterns:
            self.assertIsNone(re.search(pattern, combined, re.IGNORECASE), pattern)


if __name__ == "__main__":
    unittest.main()
