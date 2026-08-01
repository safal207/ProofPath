from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / "deploy-guard" / "run_action.py"
POLICY = ROOT / "examples" / "deploy-guard" / "deploy-policy.json"
FIXTURES = {
    "ACCEPT": ROOT / "examples" / "deploy-guard" / "deploy.accept.json",
    "HOLD": ROOT / "examples" / "deploy-guard" / "deploy.hold-missing-approval.json",
    "BLOCK": ROOT / "examples" / "deploy-guard" / "deploy.block-tests-failed.json",
    "CHALLENGE": ROOT / "examples" / "deploy-guard" / "deploy.challenge-artifact-mismatch.json",
}
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class DeployGuardActionTests(unittest.TestCase):
    def invoke(
        self,
        decision: str = "ACCEPT",
        *,
        mode: str = "enforce",
        policy_argument: str = "policy.json",
        evidence_argument: str = "evidence.json",
        certificate_argument: str = "artifacts/certificate.json",
        malformed_evidence: bool = False,
    ) -> dict[str, object]:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        workspace = Path(directory.name)
        shutil.copy2(POLICY, workspace / "policy.json")
        shutil.copy2(FIXTURES[decision], workspace / "evidence.json")
        if malformed_evidence:
            (workspace / "evidence.json").write_text('{"broken":', encoding="utf-8")

        output_path = workspace / "github-output.txt"
        summary_path = workspace / "step-summary.md"
        env = os.environ.copy()
        env.update(
            {
                "GITHUB_WORKSPACE": str(workspace),
                "GITHUB_OUTPUT": str(output_path),
                "GITHUB_STEP_SUMMARY": str(summary_path),
            }
        )
        completed = subprocess.run(
            [
                sys.executable,
                str(ACTION),
                "--policy",
                policy_argument,
                "--evidence",
                evidence_argument,
                "--certificate",
                certificate_argument,
                "--mode",
                mode,
            ],
            cwd=workspace,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        outputs: dict[str, str] = {}
        if output_path.exists():
            for line in output_path.read_text(encoding="utf-8").splitlines():
                key, value = line.split("=", 1)
                outputs[key] = value
        certificate_path = workspace / certificate_argument
        certificate = None
        if certificate_path.is_file():
            certificate = json.loads(certificate_path.read_text(encoding="utf-8"))
        return {
            "workspace": workspace,
            "completed": completed,
            "outputs": outputs,
            "summary": summary_path.read_text(encoding="utf-8") if summary_path.exists() else "",
            "certificate_path": certificate_path,
            "certificate": certificate,
        }

    def assert_complete_outputs(self, result: dict[str, object], decision: str) -> dict[str, str]:
        outputs = result["outputs"]
        self.assertIsInstance(outputs, dict)
        outputs = outputs  # type: ignore[assignment]
        self.assertEqual(outputs["decision"], decision)
        self.assertEqual(outputs["execution-allowed"], str(decision == "ACCEPT").lower())
        self.assertEqual(outputs["authority-granted"], "false")
        self.assertEqual(outputs["assurance-level"], "POLICY_VERIFIED")
        self.assertEqual(outputs["witness-level"], "SINGLE_WORKFLOW_REFERENCE")
        self.assertEqual(outputs["coverage"], "NOT_FINANCIALLY_COVERED")
        for key in ("clearance-root", "policy-root", "evidence-root"):
            self.assertRegex(outputs[key], DIGEST_RE)
        return outputs  # type: ignore[return-value]

    def test_accept_enforce_succeeds_and_emits_complete_outputs(self):
        result = self.invoke("ACCEPT", mode="enforce")
        completed = result["completed"]
        self.assertIsInstance(completed, subprocess.CompletedProcess)
        self.assertEqual(completed.returncode, 0)
        outputs = self.assert_complete_outputs(result, "ACCEPT")
        self.assertEqual(outputs["primary-reason-code"], "NONE")
        self.assertTrue(Path(outputs["certificate-path"]).is_file())
        self.assertIn("## ProofPath Deploy Guard", result["summary"])
        self.assertIn("`ACCEPT`", result["summary"])

    def test_hold_enforce_preserves_exit_code_two(self):
        result = self.invoke("HOLD", mode="enforce")
        completed = result["completed"]
        self.assertEqual(completed.returncode, 2)
        outputs = self.assert_complete_outputs(result, "HOLD")
        self.assertEqual(outputs["primary-reason-code"], "DEPLOY_APPROVAL_COUNT_INSUFFICIENT")

    def test_block_enforce_preserves_exit_code_three(self):
        result = self.invoke("BLOCK", mode="enforce")
        completed = result["completed"]
        self.assertEqual(completed.returncode, 3)
        outputs = self.assert_complete_outputs(result, "BLOCK")
        self.assertEqual(outputs["primary-reason-code"], "DEPLOY_CHECK_FAILED")

    def test_challenge_enforce_preserves_exit_code_four(self):
        result = self.invoke("CHALLENGE", mode="enforce")
        completed = result["completed"]
        self.assertEqual(completed.returncode, 4)
        outputs = self.assert_complete_outputs(result, "CHALLENGE")
        self.assertEqual(outputs["primary-reason-code"], "DEPLOY_PROVENANCE_ARTIFACT_MISMATCH")

    def test_observe_reports_non_accept_without_failing(self):
        for decision in ("HOLD", "BLOCK", "CHALLENGE"):
            with self.subTest(decision=decision):
                result = self.invoke(decision, mode="observe")
                completed = result["completed"]
                self.assertEqual(completed.returncode, 0)
                self.assert_complete_outputs(result, decision)

    def test_observe_still_fails_on_malformed_incomplete_certificate(self):
        result = self.invoke("ACCEPT", mode="observe", malformed_evidence=True)
        completed = result["completed"]
        self.assertEqual(completed.returncode, 1)
        certificate = result["certificate"]
        self.assertIsInstance(certificate, dict)
        self.assertEqual(certificate["decision"], "BLOCK")
        self.assertEqual(certificate["primary_reason_code"], "DEPLOY_EVIDENCE_INVALID")
        self.assertIn("full clearance-certificate profile", completed.stdout)

    def test_certificate_path_cannot_escape_workspace(self):
        result = self.invoke(
            "ACCEPT",
            certificate_argument="../escaped-certificate.json",
        )
        completed = result["completed"]
        self.assertEqual(completed.returncode, 1)
        workspace = result["workspace"]
        self.assertFalse((workspace.parent / "escaped-certificate.json").exists())
        self.assertIn("must remain inside GITHUB_WORKSPACE", completed.stdout)

    def test_policy_path_cannot_escape_workspace(self):
        result = self.invoke("ACCEPT", policy_argument="../policy.json")
        completed = result["completed"]
        self.assertEqual(completed.returncode, 1)
        self.assertIn("must remain inside GITHUB_WORKSPACE", completed.stdout)

    def test_repeated_runs_are_deterministic(self):
        first = self.invoke("ACCEPT", mode="observe")
        second = self.invoke("ACCEPT", mode="observe")
        first_outputs = first["outputs"]
        second_outputs = second["outputs"]
        for key in ("clearance-root", "policy-root", "evidence-root"):
            self.assertEqual(first_outputs[key], second_outputs[key])

    def test_invalid_mode_fails_closed_before_verification(self):
        result = self.invoke("ACCEPT", mode="permissive")
        completed = result["completed"]
        self.assertEqual(completed.returncode, 1)
        self.assertIn("mode must be enforce or observe", completed.stdout)
        self.assertFalse(result["certificate_path"].exists())


if __name__ == "__main__":
    unittest.main()
