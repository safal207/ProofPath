from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "deploy-guard" / "evidence-builder" / "build_evidence.py"
VERIFIER = ROOT / "scripts" / "verify_proofpath_deploy_guard.py"
POLICY = ROOT / "examples" / "deploy-guard" / "deploy-policy.json"
FACTS = ROOT / "examples" / "deploy-guard" / "trusted-facts.accept.json"
SHA = "4444444444444444444444444444444444444444"
ARTIFACT = "sha256:" + "a" * 64


class DeployEvidenceBuilderTests(unittest.TestCase):
    def invoke(
        self,
        *,
        mutate=None,
        output: str = "artifacts/evidence.json",
        policy: str = "policy.json",
        facts_path: str = "facts.json",
        source_sha: str = SHA,
        artifact_digest: str = ARTIFACT,
        evaluated_at: str = "2026-08-01T18:00:00Z",
        repository: str = "safal207/ProofPath",
        branch: str = "main",
        action_id: str = "",
    ) -> dict[str, object]:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        workspace = Path(directory.name)
        shutil.copy2(POLICY, workspace / "policy.json")
        facts = json.loads(FACTS.read_text(encoding="utf-8"))
        if mutate:
            mutate(facts)
        (workspace / "facts.json").write_text(
            json.dumps(facts, indent=2) + "\n", encoding="utf-8"
        )
        github_output = workspace / "github-output.txt"
        summary = workspace / "summary.md"
        env = os.environ.copy()
        env.update(
            {
                "GITHUB_WORKSPACE": str(workspace),
                "GITHUB_OUTPUT": str(github_output),
                "GITHUB_STEP_SUMMARY": str(summary),
            }
        )
        command = [
            sys.executable,
            str(BUILDER),
            "--workspace",
            str(workspace),
            "--policy",
            policy,
            "--trusted-facts",
            facts_path,
            "--artifact-digest",
            artifact_digest,
            "--environment",
            "production",
            "--agent-id",
            "agent/cloud-deployer-01",
            "--repository",
            repository,
            "--source-branch",
            branch,
            "--source-sha",
            source_sha,
            "--evaluated-at",
            evaluated_at,
            "--output",
            output,
        ]
        if action_id:
            command.extend(["--action-id", action_id])
        completed = subprocess.run(
            command,
            cwd=workspace,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        outputs: dict[str, str] = {}
        if github_output.exists():
            for line in github_output.read_text(encoding="utf-8").splitlines():
                key, value = line.split("=", 1)
                outputs[key] = value
        evidence_path = workspace / output
        evidence = (
            json.loads(evidence_path.read_text(encoding="utf-8"))
            if evidence_path.is_file()
            else None
        )
        return {
            "workspace": workspace,
            "completed": completed,
            "outputs": outputs,
            "evidence_path": evidence_path,
            "evidence": evidence,
            "summary": summary.read_text(encoding="utf-8") if summary.exists() else "",
        }

    def verify(self, result: dict[str, object]) -> dict[str, object]:
        workspace = result["workspace"]
        completed = subprocess.run(
            [
                sys.executable,
                str(VERIFIER),
                str(workspace / "policy.json"),
                str(result["evidence_path"]),
            ],
            cwd=workspace,
            text=True,
            capture_output=True,
            check=False,
        )
        return {
            "completed": completed,
            "certificate": json.loads(completed.stdout),
        }

    def test_builder_output_is_accepted_by_deploy_guard(self):
        result = self.invoke()
        self.assertEqual(result["completed"].returncode, 0)
        self.assertTrue(result["evidence_path"].is_file())
        outputs = result["outputs"]
        self.assertEqual(outputs["repository"], "safal207/ProofPath")
        self.assertEqual(outputs["source-sha"], SHA)
        self.assertEqual(outputs["artifact-digest"], ARTIFACT)
        self.assertRegex(outputs["evidence-root"], r"^sha256:[0-9a-f]{64}$")
        verified = self.verify(result)
        self.assertEqual(verified["completed"].returncode, 0)
        self.assertEqual(verified["certificate"]["decision"], "ACCEPT")
        self.assertEqual(
            verified["certificate"]["evidence_root"], outputs["evidence-root"]
        )

    def test_fixed_inputs_are_byte_deterministic(self):
        first = self.invoke()
        second = self.invoke()
        self.assertEqual(
            first["evidence_path"].read_bytes(), second["evidence_path"].read_bytes()
        )
        self.assertEqual(
            first["outputs"]["evidence-root"], second["outputs"]["evidence-root"]
        )
        self.assertEqual(first["outputs"]["action-id"], second["outputs"]["action-id"])

    def test_explicit_action_id_is_preserved(self):
        result = self.invoke(action_id="release-prod-0042")
        self.assertEqual(result["completed"].returncode, 0)
        self.assertEqual(result["evidence"]["action_id"], "release-prod-0042")
        self.assertEqual(result["outputs"]["action-id"], "release-prod-0042")

    def test_provenance_commit_mismatch_fails_before_output(self):
        result = self.invoke(
            mutate=lambda facts: facts["build_provenance"].update(
                {"commit_sha": "6" * 40}
            )
        )
        self.assertEqual(result["completed"].returncode, 1)
        self.assertFalse(result["evidence_path"].exists())
        self.assertIn("provenance commit does not match", result["completed"].stdout)

    def test_provenance_artifact_mismatch_fails_before_output(self):
        result = self.invoke(
            mutate=lambda facts: facts["build_provenance"].update(
                {"artifact_digest": "sha256:" + "b" * 64}
            )
        )
        self.assertEqual(result["completed"].returncode, 1)
        self.assertFalse(result["evidence_path"].exists())
        self.assertIn("provenance artifact does not match", result["completed"].stdout)

    def test_check_commit_mismatch_fails_before_output(self):
        result = self.invoke(
            mutate=lambda facts: facts["checks"][0].update({"commit_sha": "6" * 40})
        )
        self.assertEqual(result["completed"].returncode, 1)
        self.assertFalse(result["evidence_path"].exists())
        self.assertIn("checks[0] commit does not match", result["completed"].stdout)

    def test_approval_commit_mismatch_fails_before_output(self):
        result = self.invoke(
            mutate=lambda facts: facts["approvals"][0].update(
                {"commit_sha": "6" * 40}
            )
        )
        self.assertEqual(result["completed"].returncode, 1)
        self.assertFalse(result["evidence_path"].exists())
        self.assertIn("approvals[0] commit does not match", result["completed"].stdout)

    def test_ticket_commit_mismatch_fails_before_output(self):
        result = self.invoke(
            mutate=lambda facts: facts["change_ticket"].update(
                {"commit_sha": "6" * 40}
            )
        )
        self.assertEqual(result["completed"].returncode, 1)
        self.assertFalse(result["evidence_path"].exists())
        self.assertIn("change ticket commit does not match", result["completed"].stdout)

    def test_output_cannot_escape_workspace(self):
        result = self.invoke(output="../escaped.json")
        self.assertEqual(result["completed"].returncode, 1)
        self.assertFalse((result["workspace"].parent / "escaped.json").exists())
        self.assertIn("must remain inside GITHUB_WORKSPACE", result["completed"].stdout)

    def test_invalid_artifact_digest_fails_closed(self):
        result = self.invoke(artifact_digest="latest")
        self.assertEqual(result["completed"].returncode, 1)
        self.assertFalse(result["evidence_path"].exists())
        self.assertIn("artifact-digest must match", result["completed"].stdout)

    def test_duplicate_json_key_fails_closed(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        workspace = Path(directory.name)
        shutil.copy2(POLICY, workspace / "policy.json")
        (workspace / "facts.json").write_text(
            '{"profile_id":"proofpath.deploy.evidence-inputs.v0.1",'
            '"profile_id":"proofpath.deploy.evidence-inputs.v0.1"}\n',
            encoding="utf-8",
        )
        completed = subprocess.run(
            [
                sys.executable,
                str(BUILDER),
                "--workspace",
                str(workspace),
                "--policy",
                "policy.json",
                "--trusted-facts",
                "facts.json",
                "--artifact-digest",
                ARTIFACT,
                "--environment",
                "production",
                "--agent-id",
                "agent/test",
                "--repository",
                "safal207/ProofPath",
                "--source-branch",
                "main",
                "--source-sha",
                SHA,
                "--evaluated-at",
                "2026-08-01T18:00:00Z",
            ],
            cwd=workspace,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("duplicate JSON key", completed.stdout)

    def test_authority_scope_mismatch_is_preserved_for_guard_decision(self):
        result = self.invoke(
            mutate=lambda facts: facts["authority"]["scope"].update(
                {"repositories": ["other/repository"]}
            )
        )
        self.assertEqual(result["completed"].returncode, 0)
        verified = self.verify(result)
        self.assertEqual(verified["completed"].returncode, 3)
        self.assertEqual(verified["certificate"]["decision"], "BLOCK")
        self.assertIn(
            "DEPLOY_AUTHORITY_SCOPE_MISMATCH",
            verified["certificate"]["reason_codes"],
        )

    def test_missing_approvals_are_preserved_as_hold_not_builder_failure(self):
        result = self.invoke(mutate=lambda facts: facts.update({"approvals": []}))
        self.assertEqual(result["completed"].returncode, 0)
        verified = self.verify(result)
        self.assertEqual(verified["completed"].returncode, 2)
        self.assertEqual(verified["certificate"]["decision"], "HOLD")
        self.assertIn(
            "DEPLOY_APPROVAL_COUNT_INSUFFICIENT",
            verified["certificate"]["reason_codes"],
        )

    def test_builder_summary_states_non_verification_boundary(self):
        result = self.invoke()
        self.assertEqual(result["completed"].returncode, 0)
        self.assertIn("does not verify authority", result["summary"])
        self.assertIn(result["outputs"]["evidence-root"], result["summary"])


if __name__ == "__main__":
    unittest.main()
