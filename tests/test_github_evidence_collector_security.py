from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / "deploy-guard" / "github-collector" / "action.yml"
COLLECTOR = ROOT / "deploy-guard" / "github-collector" / "collector.py"
WORKFLOW = ROOT / ".github" / "workflows" / "proofpath-github-evidence-collector.yml"
CONSUMER = ROOT / "examples" / "deploy-guard" / "github-collector-consumer-workflow.yml"
DOC = ROOT / "docs" / "PROOFPATH_GITHUB_EVIDENCE_COLLECTOR.md"
SCHEMA = ROOT / "schemas" / "proofpath-github-evidence-collector-config-v0.1.schema.json"


class GitHubEvidenceCollectorSecurityTests(unittest.TestCase):
    def test_collector_is_a_separate_composite_action(self):
        text = ACTION.read_text(encoding="utf-8")
        self.assertIn("using: composite", text)
        self.assertIn("collector.py", text)
        self.assertTrue((ROOT / "deploy-guard" / "evidence-builder" / "action.yml").is_file())
        self.assertTrue((ROOT / "deploy-guard" / "action.yml").is_file())

    def test_action_passes_inputs_through_environment_not_shell_interpolation(self):
        text = ACTION.read_text(encoding="utf-8")
        run_block = text.split("run: |", 1)[1]
        self.assertNotIn("${{ inputs.", run_block)
        for name in (
            "PROOFPATH_GITHUB_TOKEN",
            "PROOFPATH_COLLECTOR_CONFIG",
            "PROOFPATH_ARTIFACT_RUN_ID",
            "PROOFPATH_ARTIFACT_NAME",
            "PROOFPATH_SOURCE_SHA",
        ):
            self.assertIn(name, text)

    def test_collector_uses_only_get_requests_and_no_command_execution(self):
        text = COLLECTOR.read_text(encoding="utf-8")
        self.assertIn('method="GET"', text)
        for forbidden in (
            'method="POST"',
            'method="PUT"',
            'method="PATCH"',
            'method="DELETE"',
            "subprocess",
            "os.system",
            "shell=True",
            "eval(",
            "exec(",
        ):
            self.assertNotIn(forbidden, text)

    def test_token_is_sent_only_to_https_api_origin_without_embedded_credentials(self):
        text = COLLECTOR.read_text(encoding="utf-8")
        self.assertIn('parsed.scheme != "https"', text)
        self.assertIn("parsed.username", text)
        self.assertIn("parsed.password", text)
        self.assertIn('"Authorization": f"Bearer {token}"', text)

    def test_all_collector_files_remain_inside_workspace(self):
        text = COLLECTOR.read_text(encoding="utf-8")
        self.assertIn("path.relative_to(workspace)", text)
        self.assertIn("must remain inside GITHUB_WORKSPACE", text)
        for name in ("config", "output", "report"):
            self.assertIn(f'"{name}"', text)

    def test_artifact_is_bound_to_exact_run_head_and_successful_producer_job(self):
        text = COLLECTOR.read_text(encoding="utf-8")
        for phrase in (
            "artifact workflow run repository or head SHA does not match",
            "artifact_job_name must match exactly one job",
            "artifact producer job must be completed successfully",
            "artifact name must match exactly one artifact",
            "selected artifact is missing a valid SHA-256 digest",
        ):
            self.assertIn(phrase, text)

    def test_reviews_require_explicit_role_mapping_latest_approval_and_current_commit(self):
        text = COLLECTOR.read_text(encoding="utf-8")
        self.assertIn("approval_role_map", text)
        self.assertIn('review.get("state") == "APPROVED"', text)
        self.assertIn('review.get("commit_id") == sha', text)
        self.assertIn("LATEST_REVIEW_NOT_CURRENT_APPROVAL", text)
        self.assertNotIn('"role": "reviewer"', text)

    def test_missing_checks_are_pending_not_fabricated_successes(self):
        text = COLLECTOR.read_text(encoding="utf-8")
        self.assertIn('{"name": name, "status": "pending", "commit_sha": sha}', text)
        self.assertIn("NO_MATCHING_CHECK_RUN", text)

    def test_report_preserves_nonverification_boundary(self):
        text = COLLECTOR.read_text(encoding="utf-8")
        for field in (
            '"collector_verified_authority": False',
            '"collector_verified_attestation_claim": False',
            '"collector_verified_change_ticket": False',
            '"deployment_performed": False',
        ):
            self.assertIn(field, text)

    def test_schema_requires_explicit_artifact_producer_job(self):
        text = SCHEMA.read_text(encoding="utf-8")
        self.assertIn('"artifact_job_name"', text)
        self.assertIn('"additionalProperties": false', text)
        self.assertIn('"proofpath.github.evidence-collector-config.v0.1"', text)

    def test_live_workflow_has_only_required_read_permissions(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        for permission in (
            "contents: read",
            "actions: read",
            "checks: read",
            "pull-requests: read",
        ):
            self.assertIn(permission, text)
        for forbidden in (
            "contents: write",
            "actions: write",
            "checks: write",
            "pull-requests: write",
            "id-token: write",
            "attestations: write",
        ):
            self.assertNotIn(forbidden, text)

    def test_live_workflow_runs_real_collector_builder_guard_chain(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        seed = text.index("name: build-artifact")
        collector = text.index("uses: ./deploy-guard/github-collector")
        builder = text.index("uses: ./deploy-guard/evidence-builder")
        guard = text.index("uses: ./deploy-guard\n")
        self.assertLess(seed, collector)
        self.assertLess(collector, builder)
        self.assertLess(builder, guard)
        self.assertIn("needs: seed-artifact", text)
        self.assertIn("artifact-run-id: ${{ github.run_id }}", text)
        self.assertIn('"collector_live_github_api"] is True', text)

    def test_consumer_pins_all_three_actions_and_keeps_deploy_separate(self):
        text = CONSUMER.read_text(encoding="utf-8")
        pin = "REPLACE_WITH_REVIEWED_40_CHAR_COMMIT_SHA"
        self.assertEqual(text.count(pin), 3)
        self.assertIn("deploy-guard/github-collector@", text)
        self.assertIn("deploy-guard/evidence-builder@", text)
        self.assertIn("deploy-guard@", text)
        self.assertIn("if: always()", text)
        self.assertIn("if: steps.guard.outputs.decision == 'ACCEPT'", text)
        self.assertIn("ProofPath itself does not perform the deployment", text)

    def test_documentation_states_exact_trust_boundary(self):
        text = DOC.read_text(encoding="utf-8")
        for phrase in (
            "does not infer authority",
            "Only reviewers present in `approval_role_map` are considered",
            "An in-progress run is accepted only after its exact artifact-producing job has succeeded",
            "collector_verified_authority: false",
            "Pin Collector, Builder, and Guard to the same reviewed full commit SHA",
            "does not download the selected artifact",
        ):
            self.assertIn(phrase, text)

    def test_no_real_deployment_or_cloud_command_is_added(self):
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ACTION, COLLECTOR, WORKFLOW, CONSUMER)
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
