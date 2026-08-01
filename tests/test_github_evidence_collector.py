from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy-guard" / "github-collector" / "collector.py"
FIXTURE = ROOT / "examples" / "deploy-guard" / "github-collector-config.fixture.json"

SPEC = importlib.util.spec_from_file_location("proofpath_github_collector", SCRIPT)
assert SPEC and SPEC.loader
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)

SHA = "a" * 40
DIGEST = "sha256:" + "b" * 64


class FakeResponse:
    def __init__(self, value):
        self._bytes = json.dumps(value).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._bytes


class GitHubEvidenceCollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        self.config = self.workspace / "collector-config.json"
        self.config.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
        self.output = self.workspace / "facts.json"
        self.report = self.workspace / "report.json"
        self.github_output = self.workspace / "github-output.txt"
        self.summary = self.workspace / "summary.md"
        self.responses = self._base_responses()
        self.environment = {
            "GITHUB_WORKSPACE": str(self.workspace),
            "GITHUB_API_URL": "https://api.github.com",
            "GITHUB_REPOSITORY": "safal207/ProofPath",
            "GITHUB_SHA": SHA,
            "GITHUB_OUTPUT": str(self.github_output),
            "GITHUB_STEP_SUMMARY": str(self.summary),
            "PROOFPATH_GITHUB_TOKEN": "test-token",
            "PROOFPATH_COLLECTOR_CONFIG": str(self.config),
            "PROOFPATH_ARTIFACT_RUN_ID": "77",
            "PROOFPATH_ARTIFACT_NAME": "deployable",
            "PROOFPATH_REPOSITORY": "safal207/ProofPath",
            "PROOFPATH_SOURCE_SHA": SHA,
            "PROOFPATH_PULL_REQUEST_NUMBER": "12",
            "PROOFPATH_OUTPUT": str(self.output),
            "PROOFPATH_REPORT": str(self.report),
        }

    def tearDown(self):
        self.temp.cleanup()

    def _base_responses(self):
        return {
            "/repos/safal207/ProofPath/actions/runs/77": {
                "id": 77,
                "run_number": 9,
                "workflow_id": 123,
                "event": "pull_request",
                "head_branch": "feature/deploy",
                "head_sha": SHA,
                "status": "completed",
                "conclusion": "success",
                "html_url": "https://github.com/safal207/ProofPath/actions/runs/77",
                "repository": {"full_name": "safal207/ProofPath"},
            },
            "/repos/safal207/ProofPath/actions/runs/77/jobs": {
                "total_count": 1,
                "jobs": [
                    {
                        "id": 5001,
                        "name": "build-artifact",
                        "status": "completed",
                        "conclusion": "success",
                    }
                ],
            },
            "/repos/safal207/ProofPath/actions/runs/77/artifacts": {
                "total_count": 1,
                "artifacts": [
                    {
                        "id": 9001,
                        "name": "deployable",
                        "digest": DIGEST,
                        "expired": False,
                        "size_in_bytes": 1234,
                        "created_at": "2026-08-01T20:00:00Z",
                        "expires_at": "2026-08-15T20:00:00Z",
                    }
                ],
            },
            f"/repos/safal207/ProofPath/commits/{SHA}/check-runs": {
                "total_count": 3,
                "check_runs": [
                    {
                        "id": 1,
                        "name": "unit-tests",
                        "head_sha": SHA,
                        "status": "completed",
                        "conclusion": "failure",
                        "app": {"slug": "github-actions"},
                    },
                    {
                        "id": 2,
                        "name": "unit-tests",
                        "head_sha": SHA,
                        "status": "completed",
                        "conclusion": "success",
                        "app": {"slug": "github-actions"},
                    },
                    {
                        "id": 3,
                        "name": "security-scan",
                        "head_sha": SHA,
                        "status": "completed",
                        "conclusion": "success",
                        "app": {"slug": "github-actions"},
                    },
                ],
            },
            "/repos/safal207/ProofPath/pulls/12": {"number": 12, "head": {"sha": SHA}},
            "/repos/safal207/ProofPath/pulls/12/reviews": [
                {"id": 10, "user": {"login": "Alice"}, "state": "APPROVED", "commit_id": SHA},
                {"id": 11, "user": {"login": "bob"}, "state": "APPROVED", "commit_id": SHA},
            ],
        }

    def _fake_urlopen(self, request, timeout=20):
        self.assertEqual(timeout, 20)
        self.assertEqual(request.get_header("Authorization"), "Bearer test-token")
        path = request.full_url.removeprefix("https://api.github.com").split("?", 1)[0]
        if path not in self.responses:
            raise AssertionError(f"unexpected API path: {path}")
        return FakeResponse(self.responses[path])

    def _run(self):
        with mock.patch.dict(os.environ, self.environment, clear=True):
            with mock.patch.object(collector.urllib.request, "urlopen", self._fake_urlopen):
                return collector.main()

    def test_collects_commit_bound_checks_reviews_job_and_artifact(self):
        self.assertEqual(self._run(), 0)
        facts = json.loads(self.output.read_text(encoding="utf-8"))
        report = json.loads(self.report.read_text(encoding="utf-8"))
        self.assertEqual(facts["profile_id"], "proofpath.deploy.evidence-inputs.v0.1")
        self.assertEqual(facts["build_provenance"]["commit_sha"], SHA)
        self.assertEqual(facts["build_provenance"]["artifact_digest"], DIGEST)
        self.assertFalse(facts["build_provenance"]["attestation_verified"])
        self.assertEqual([item["status"] for item in facts["checks"]], ["success", "success"])
        self.assertEqual([item["actor"] for item in facts["approvals"]], ["alice", "bob"])
        self.assertEqual(report["workflow_run"]["producer_job"]["name"], "build-artifact")
        self.assertTrue(report["collector_live_github_api"])
        self.assertFalse(report["collector_verified_authority"])
        self.assertFalse(report["collector_verified_attestation_claim"])
        self.assertFalse(report["deployment_performed"])
        self.assertRegex(report["report_root"], r"^sha256:[0-9a-f]{64}$")
        outputs = self.github_output.read_text(encoding="utf-8")
        self.assertIn(f"artifact-digest={DIGEST}", outputs)
        self.assertIn("check-count=2", outputs)
        self.assertIn("approval-count=2", outputs)

    def test_in_progress_run_is_allowed_after_producer_job_succeeds(self):
        self.responses["/repos/safal207/ProofPath/actions/runs/77"]["status"] = "in_progress"
        self.responses["/repos/safal207/ProofPath/actions/runs/77"]["conclusion"] = None
        self.assertEqual(self._run(), 0)

    def test_producer_job_must_be_completed_successfully(self):
        job = self.responses["/repos/safal207/ProofPath/actions/runs/77/jobs"]["jobs"][0]
        job["status"] = "in_progress"
        job["conclusion"] = None
        self.assertEqual(self._run(), 1)
        self.assertFalse(self.output.exists())

    def test_producer_job_name_must_match_exactly_once(self):
        self.responses["/repos/safal207/ProofPath/actions/runs/77/jobs"]["jobs"] = []
        self.assertEqual(self._run(), 1)

    def test_latest_check_rerun_wins_for_same_commit_and_app(self):
        self.assertEqual(self._run(), 0)
        report = json.loads(self.report.read_text(encoding="utf-8"))
        unit = next(item for item in report["check_selection"] if item["name"] == "unit-tests")
        self.assertEqual(unit["check_run_id"], 2)
        self.assertEqual(unit["normalized_status"], "success")

    def test_missing_configured_check_becomes_pending_for_guard_hold(self):
        self.responses[f"/repos/safal207/ProofPath/commits/{SHA}/check-runs"]["check_runs"] = []
        self.assertEqual(self._run(), 0)
        facts = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual([item["status"] for item in facts["checks"]], ["pending", "pending"])

    def test_stale_review_is_not_promoted_to_current_approval(self):
        self.responses["/repos/safal207/ProofPath/pulls/12/reviews"][0]["commit_id"] = "d" * 40
        self.assertEqual(self._run(), 0)
        facts = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual([item["actor"] for item in facts["approvals"]], ["bob"])

    def test_latest_nonapproval_revokes_previous_approval(self):
        self.responses["/repos/safal207/ProofPath/pulls/12/reviews"].append(
            {"id": 12, "user": {"login": "alice"}, "state": "CHANGES_REQUESTED", "commit_id": SHA}
        )
        self.assertEqual(self._run(), 0)
        facts = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual([item["actor"] for item in facts["approvals"]], ["bob"])

    def test_pull_request_head_mismatch_fails_before_output(self):
        self.responses["/repos/safal207/ProofPath/pulls/12"]["head"]["sha"] = "d" * 40
        self.assertEqual(self._run(), 1)
        self.assertFalse(self.output.exists())

    def test_artifact_run_head_mismatch_fails_before_output(self):
        self.responses["/repos/safal207/ProofPath/actions/runs/77"]["head_sha"] = "d" * 40
        self.assertEqual(self._run(), 1)
        self.assertFalse(self.output.exists())

    def test_failed_completed_run_fails_before_output(self):
        self.responses["/repos/safal207/ProofPath/actions/runs/77"]["conclusion"] = "failure"
        self.assertEqual(self._run(), 1)
        self.assertFalse(self.output.exists())

    def test_duplicate_artifact_name_fails_before_output(self):
        artifact = dict(self.responses["/repos/safal207/ProofPath/actions/runs/77/artifacts"]["artifacts"][0])
        artifact["id"] = 9002
        self.responses["/repos/safal207/ProofPath/actions/runs/77/artifacts"]["artifacts"].append(artifact)
        self.assertEqual(self._run(), 1)

    def test_unmapped_approved_reviewer_is_not_granted_a_role(self):
        self.responses["/repos/safal207/ProofPath/pulls/12/reviews"].append(
            {"id": 15, "user": {"login": "mallory"}, "state": "APPROVED", "commit_id": SHA}
        )
        self.assertEqual(self._run(), 0)
        facts = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertNotIn("mallory", [item["actor"] for item in facts["approvals"]])

    def test_change_ticket_must_bind_to_source_sha(self):
        value = json.loads(self.config.read_text(encoding="utf-8"))
        value["change_ticket"]["commit_sha"] = "d" * 40
        self.config.write_text(json.dumps(value), encoding="utf-8")
        self.assertEqual(self._run(), 1)

    def test_output_path_cannot_escape_workspace(self):
        self.environment["PROOFPATH_OUTPUT"] = str(self.workspace.parent / "escape.json")
        self.assertEqual(self._run(), 1)

    def test_non_https_api_origin_is_rejected(self):
        self.environment["GITHUB_API_URL"] = "http://api.github.com"
        self.assertEqual(self._run(), 1)

    def test_pull_request_collection_can_be_disabled(self):
        self.environment["PROOFPATH_PULL_REQUEST_NUMBER"] = "0"
        self.assertEqual(self._run(), 0)
        facts = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(facts["approvals"], [])


if __name__ == "__main__":
    unittest.main()
