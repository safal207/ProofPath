from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (
    ROOT / ".github" / "workflows" / "proofpath-deploy-guard.yml"
).read_text(encoding="utf-8")


class DeployGuardWorkflowSecurityTests(unittest.TestCase):
    def test_has_minimum_signing_permissions(self):
        self.assertIn("contents: read", WORKFLOW)
        self.assertIn("id-token: write", WORKFLOW)
        self.assertIn("attestations: write", WORKFLOW)
        self.assertNotIn("contents: write", WORKFLOW)
        self.assertNotIn("pull-requests: write", WORKFLOW)

    def test_never_performs_deployment(self):
        forbidden = (
            "kubectl apply",
            "helm upgrade",
            "aws deploy",
            "gcloud run deploy",
            "az deployment",
            "terraform apply",
            "pulumi up",
        )
        lowered = WORKFLOW.lower()
        for command in forbidden:
            self.assertNotIn(command, lowered)

    def test_attests_exact_accept_certificate(self):
        self.assertIn(
            "subject-path: artifacts/certificates/accept.json",
            WORKFLOW,
        )

    def test_attests_demo_manifest(self):
        self.assertIn(
            "subject-path: artifacts/deploy-guard-demo-manifest.json",
            WORKFLOW,
        )

    def test_all_four_decisions_are_asserted(self):
        for decision, exit_code in (
            ("ACCEPT", "0"),
            ("HOLD", "2"),
            ("BLOCK", "3"),
            ("CHALLENGE", "4"),
        ):
            self.assertIn(f"{decision} {exit_code}", WORKFLOW)

    def test_certificate_limits_are_asserted(self):
        self.assertIn("NOT_FINANCIALLY_COVERED", WORKFLOW)
        self.assertIn("SINGLE_WORKFLOW_REFERENCE", WORKFLOW)
        self.assertIn('certificate["authority_granted"] is False', WORKFLOW)

    def test_artifact_retention_is_bounded(self):
        self.assertIn("retention-days: 14", WORKFLOW)


if __name__ == "__main__":
    unittest.main()
