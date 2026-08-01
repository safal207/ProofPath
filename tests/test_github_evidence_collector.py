from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy-guard" / "github-collector" / "collector.py"


class GitHubEvidenceCollectorTests(unittest.TestCase):
    SHA = "a" * 40
    SIGNER_SHA = "c" * 40
    DIGEST = "sha256:" + "b" * 64
    REPOSITORY = "acme/app"
    RUN_ID = 123
    ARTIFACT_NAME = "deploy-bundle"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        self.fixtures = self.workspace / "fixtures"
        self.fixtures.mkdir()
        self.output = self.workspace / "facts.json"
        self.report = self.workspace / "report.json"

        self.policy = {
            "profile_id": "proofpath.deploy.guard-policy.v0.1",
            "policy_id": "production",
            "policy_version": "1",
            "allowed_repositories": [self.REPOSITORY],
            "allowed_environments": ["production"],
            "allowed_branches": ["main"],
            "allowed_actions": ["deploy"],
            "minimum_approvals": 2,
            "required_approval_roles": ["service-owner", "security"],
            "required_checks": ["unit-tests", "security-scan"],
            "maximum_critical_vulnerabilities": 0,
            "require_change_ticket": True,
            "require_artifact_attestation": True,
            "require_github_hosted_runner": True,
        }
        self.config = {
            "profile_id": "proofpath.github.evidence-collector-config.v0.1",
            "artifact_job_name": "build-artifact",
            "authority": {
                "active": True,
                "expires_at": "2026-12-31T23:59:59Z",
                "scope": {
                    "repositories": [self.REPOSITORY],
                    "environments": ["production"],
                    "actions": ["deploy"],
                },
            },
            "security": {"critical_vulnerabilities": 0},
            "approval_role_map": {
                "alice": "service-owner",
                "bob": "security",
            },
            "check_app_allowlist": {
                "unit-tests": "github-actions",
                "security-scan": "github-actions",
            },
            "change_ticket": {
                "id": "CHG-1",
                "status": "approved",
                "commit_sha": self.SHA,
            },
        }
        self.attestation = {
            "profile_id": "proofpath.github.attestation-result.v0.1",
            "verified": True,
            "source_sha": self.SHA,
            "artifact_digest": self.DIGEST,
            "workflow": f"{self.REPOSITORY}/.github/workflows/build.yml",
            "signer_sha": self.SIGNER_SHA,
            "runner_environment": "github-hosted",
        }
        self._write("policy.json", self.policy)
        self._write("config.json", self.config)
        self._write("attestation.json", self.attestation)
        self._install_default_api()

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, name: str, value):
        (self.workspace / name).write_text(
            json.dumps(value, sort_keys=True),
            encoding="utf-8",
        )

    def _fixture(self, endpoint: str, body):
        name = hashlib.sha256(endpoint.encode("utf-8")).hexdigest() + ".json"
        (self.fixtures / name).write_text(
            json.dumps({"body": body}, sort_keys=True),
            encoding="utf-8",
        )

    def _install_default_api(self):
        self._fixture(
            f"/repos/acme/app/actions/runs/{self.RUN_ID}",
            {
                "id": self.RUN_ID,
                "run_number": 1,
                "workflow_id": 2,
                "event": "workflow_dispatch",
                "head_branch": "main",
                "head_sha": self.SHA,
                "status": "in_progress",
                "conclusion": None,
                "path": ".github/workflows/build.yml@refs/heads/main",
                "html_url": "https://github.example/run/123",
                "repository": {"full_name": self.REPOSITORY},
            },
        )
        self._fixture(
            f"/repos/acme/app/actions/runs/{self.RUN_ID}/jobs?per_page=100&page=1",
            {
                "jobs": [
                    {
                        "id": 9,
                        "name": "build-artifact",
                        "status": "completed",
                        "conclusion": "success",
                    }
                ]
            },
        )
        self._fixture(
            f"/repos/acme/app/actions/runs/{self.RUN_ID}/artifacts?per_page=100&page=1",
            {
                "artifacts": [
                    {
                        "id": 77,
                        "name": self.ARTIFACT_NAME,
                        "expired": False,
                        "digest": self.DIGEST,
                        "size_in_bytes": 100,
                    }
                ]
            },
        )
        self._fixture(
            f"/repos/acme/app/commits/{self.SHA}/check-runs?filter=latest&per_page=100&page=1",
            {
                "check_runs": [
                    {
                        "id": 10,
                        "name": "unit-tests",
                        "head_sha": self.SHA,
                        "status": "completed",
                        "conclusion": "success",
                        "app": {"slug": "github-actions"},
                    },
                    {
                        "id": 11,
                        "name": "security-scan",
                        "head_sha": self.SHA,
                        "status": "completed",
                        "conclusion": "success",
                        "app": {"slug": "github-actions"},
                    },
                ]
            },
        )
        self._fixture(
            "/repos/acme/app/pulls/9",
            {"head": {"sha": self.SHA}},
        )
        self._fixture(
            "/repos/acme/app/pulls/9/reviews?per_page=100&page=1",
            [
                {
                    "id": 20,
                    "state": "APPROVED",
                    "commit_id": self.SHA,
                    "user": {"login": "Alice"},
                },
                {
                    "id": 21,
                    "state": "APPROVED",
                    "commit_id": self.SHA,
                    "user": {"login": "bob"},
                },
            ],
        )

    def _env(self):
        env = os.environ.copy()
        env.pop("GITHUB_ACTIONS", None)
        env.update(
            {
                "GITHUB_WORKSPACE": str(self.workspace),
                "GITHUB_REPOSITORY": self.REPOSITORY,
                "GITHUB_API_URL": "https://api.github.com",
                "PROOFPATH_COLLECTOR_FIXTURE_DIR": str(self.fixtures),
                "PROOFPATH_GITHUB_TOKEN": "fixture-token",
                "PROOFPATH_POLICY": "policy.json",
                "PROOFPATH_COLLECTOR_CONFIG": "config.json",
                "PROOFPATH_ARTIFACT_RUN_ID": str(self.RUN_ID),
                "PROOFPATH_ARTIFACT_NAME": self.ARTIFACT_NAME,
                "PROOFPATH_REPOSITORY": self.REPOSITORY,
                "PROOFPATH_SOURCE_SHA": self.SHA,
                "PROOFPATH_PULL_REQUEST_NUMBER": "9",
                "PROOFPATH_ATTESTATION_RESULT": "attestation.json",
                "PROOFPATH_OUTPUT": "facts.json",
                "PROOFPATH_REPORT": "report.json",
            }
        )
        return env

    def _run(self, **overrides):
        env = self._env()
        env.update({key: value for key, value in overrides.items() if value is not None})
        for key, value in overrides.items():
            if value is None:
                env.pop(key, None)
        return subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )

    def test_collects_exact_artifact_checks_reviews_and_workflow(self):
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stderr)
        facts = json.loads(self.output.read_text(encoding="utf-8"))
        report = json.loads(self.report.read_text(encoding="utf-8"))
        self.assertEqual(facts["build_provenance"]["artifact_digest"], self.DIGEST)
        self.assertEqual(
            facts["build_provenance"]["workflow"],
            f"{self.REPOSITORY}/.github/workflows/build.yml",
        )
        self.assertTrue(facts["build_provenance"]["attestation_verified"])
        self.assertEqual(
            [item["name"] for item in facts["checks"]],
            ["unit-tests", "security-scan"],
        )
        self.assertEqual(
            [item["actor"] for item in facts["approvals"]],
            ["alice", "bob"],
        )
        self.assertEqual(report["workflow_run"]["producer_job"]["name"], "build-artifact")
        self.assertFalse(report["collector_live_github_api"])
        self.assertFalse(report["collector_verified_attestation_cryptography"])
        self.assertRegex(report["report_root"], r"^sha256:[0-9a-f]{64}$")

    def test_output_is_byte_deterministic(self):
        first = self._run()
        first_facts = self.output.read_bytes()
        first_report = self.report.read_bytes()
        second = self._run()
        self.assertEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0)
        self.assertEqual(first_facts, self.output.read_bytes())
        self.assertEqual(first_report, self.report.read_bytes())

    def test_missing_required_check_becomes_pending(self):
        self._fixture(
            f"/repos/acme/app/commits/{self.SHA}/check-runs?filter=latest&per_page=100&page=1",
            {"check_runs": []},
        )
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stderr)
        facts = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual([item["status"] for item in facts["checks"]], ["pending", "pending"])

    def test_latest_changes_requested_revokes_approval(self):
        self._fixture(
            "/repos/acme/app/pulls/9/reviews?per_page=100&page=1",
            [
                {"id": 20, "state": "APPROVED", "commit_id": self.SHA, "user": {"login": "Alice"}},
                {"id": 30, "state": "CHANGES_REQUESTED", "commit_id": self.SHA, "user": {"login": "alice"}},
                {"id": 21, "state": "APPROVED", "commit_id": self.SHA, "user": {"login": "bob"}},
            ],
        )
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stderr)
        facts = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual([item["actor"] for item in facts["approvals"]], ["bob"])

    def test_stale_review_is_not_promoted(self):
        self._fixture(
            "/repos/acme/app/pulls/9/reviews?per_page=100&page=1",
            [
                {"id": 20, "state": "APPROVED", "commit_id": "d" * 40, "user": {"login": "Alice"}},
                {"id": 21, "state": "APPROVED", "commit_id": self.SHA, "user": {"login": "bob"}},
            ],
        )
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stderr)
        facts = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual([item["actor"] for item in facts["approvals"]], ["bob"])

    def test_run_head_mismatch_fails_before_output(self):
        self._fixture(
            f"/repos/acme/app/actions/runs/{self.RUN_ID}",
            {
                "repository": {"full_name": self.REPOSITORY},
                "head_sha": "d" * 40,
                "status": "completed",
                "conclusion": "success",
                "head_branch": "main",
                "path": ".github/workflows/build.yml",
            },
        )
        result = self._run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("head SHA does not match", result.stderr)
        self.assertFalse(self.output.exists())

    def test_incomplete_producer_job_fails_before_output(self):
        self._fixture(
            f"/repos/acme/app/actions/runs/{self.RUN_ID}/jobs?per_page=100&page=1",
            {
                "jobs": [
                    {
                        "id": 9,
                        "name": "build-artifact",
                        "status": "in_progress",
                        "conclusion": None,
                    }
                ]
            },
        )
        result = self._run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("producer job must be completed successfully", result.stderr)

    def test_duplicate_artifact_name_fails_closed(self):
        artifact = {
            "id": 77,
            "name": self.ARTIFACT_NAME,
            "expired": False,
            "digest": self.DIGEST,
        }
        self._fixture(
            f"/repos/acme/app/actions/runs/{self.RUN_ID}/artifacts?per_page=100&page=1",
            {"artifacts": [artifact, dict(artifact, id=78)]},
        )
        result = self._run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("exactly one non-expired artifact", result.stderr)

    def test_attestation_digest_mismatch_fails_closed(self):
        value = dict(self.attestation, artifact_digest="sha256:" + "d" * 64)
        self._write("attestation.json", value)
        result = self._run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("artifact_digest does not match selected artifact", result.stderr)

    def test_attestation_workflow_mismatch_fails_closed(self):
        value = dict(
            self.attestation,
            workflow=f"{self.REPOSITORY}/.github/workflows/other.yml",
        )
        self._write("attestation.json", value)
        result = self._run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("workflow does not match artifact-producing workflow", result.stderr)

    def test_no_attestation_result_stays_unverified(self):
        result = self._run(PROOFPATH_ATTESTATION_RESULT=None)
        self.assertEqual(result.returncode, 0, result.stderr)
        facts = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertFalse(facts["build_provenance"]["attestation_verified"])
        self.assertEqual(facts["build_provenance"]["runner_environment"], "unknown")

    def test_policy_is_source_of_required_check_names(self):
        self.policy["required_checks"] = ["unit-tests"]
        self._write("policy.json", self.policy)
        result = self._run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("check_app_allowlist may only reference policy.required_checks", result.stderr)

    def test_failed_completed_run_fails_closed(self):
        self._fixture(
            f"/repos/acme/app/actions/runs/{self.RUN_ID}",
            {
                "repository": {"full_name": self.REPOSITORY},
                "head_sha": self.SHA,
                "status": "completed",
                "conclusion": "failure",
                "head_branch": "main",
                "path": ".github/workflows/build.yml",
            },
        )
        result = self._run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("completed artifact workflow run must be successful", result.stderr)

    def test_fixture_mode_is_forbidden_inside_github_actions(self):
        result = self._run(GITHUB_ACTIONS="true")
        self.assertEqual(result.returncode, 1)
        self.assertIn("API fixtures are forbidden inside GitHub Actions", result.stderr)

    def test_output_and_report_paths_are_workspace_confined_and_distinct(self):
        escaped = self._run(PROOFPATH_OUTPUT="../escape.json")
        self.assertEqual(escaped.returncode, 1)
        same = self._run(PROOFPATH_REPORT="facts.json")
        self.assertEqual(same.returncode, 1)
        self.assertIn("output and report paths must differ", same.stderr)


if __name__ == "__main__":
    unittest.main()
