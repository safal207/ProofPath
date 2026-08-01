from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / "deploy-guard" / "evidence-builder" / "action.yml"
BUILDER = ROOT / "deploy-guard" / "evidence-builder" / "build_evidence.py"
WORKFLOW = ROOT / ".github" / "workflows" / "proofpath-deploy-evidence-builder.yml"
CONSUMER = ROOT / "examples" / "deploy-guard" / "evidence-builder-consumer-workflow.yml"
DOC = ROOT / "docs" / "PROOFPATH_DEPLOY_EVIDENCE_BUILDER.md"


class DeployEvidenceBuilderSecurityTests(unittest.TestCase):
    def test_builder_is_a_separate_composite_action(self):
        text = ACTION.read_text(encoding="utf-8")
        self.assertIn("using: composite", text)
        self.assertIn("build_evidence.py", text)
        self.assertTrue((ROOT / "deploy-guard" / "action.yml").is_file())
        self.assertNotEqual(ACTION.resolve(), (ROOT / "action.yml").resolve())

    def test_inputs_reach_python_through_environment_not_direct_shell_interpolation(self):
        text = ACTION.read_text(encoding="utf-8")
        run_block = text.split("run: |", 1)[1]
        self.assertNotIn("${{ inputs.", run_block)
        for name in (
            "PROOFPATH_POLICY",
            "PROOFPATH_TRUSTED_FACTS",
            "PROOFPATH_ARTIFACT_DIGEST",
            "PROOFPATH_SOURCE_SHA",
            "PROOFPATH_OUTPUT",
        ):
            self.assertIn(name, text)

    def test_builder_has_no_network_shell_or_dynamic_execution_surface(self):
        text = BUILDER.read_text(encoding="utf-8")
        forbidden = (
            "subprocess",
            "urllib",
            "requests",
            "socket",
            "http.client",
            "os.system",
            "shell=True",
            "eval(",
            "exec(",
        )
        for item in forbidden:
            self.assertNotIn(item, text, item)

    def test_builder_constrains_all_file_paths_to_workspace(self):
        text = BUILDER.read_text(encoding="utf-8")
        self.assertIn("relative_to(workspace)", text)
        self.assertIn("must remain inside GITHUB_WORKSPACE", text)
        for name in ("policy", "trusted-facts", "output"):
            self.assertIn(f'"{name}"', text)

    def test_builder_rejects_ambiguous_json_and_floats(self):
        text = BUILDER.read_text(encoding="utf-8")
        self.assertIn("duplicate JSON key", text)
        self.assertIn("floats are forbidden", text)
        self.assertIn("object_pairs_hook=_reject_duplicate", text)

    def test_builder_requires_exact_commit_and_artifact_bindings(self):
        text = BUILDER.read_text(encoding="utf-8")
        for phrase in (
            "build provenance commit does not match source-sha",
            "build provenance artifact does not match artifact-digest",
            "check names must be unique",
            "commit does not match source-sha",
        ):
            self.assertIn(phrase, text)

    def test_builder_never_marks_execution_performed(self):
        text = BUILDER.read_text(encoding="utf-8")
        self.assertIn('"execution": {"performed": False}', text)
        self.assertNotIn('"performed": True', text)

    def test_builder_exports_a_complete_machine_readable_surface(self):
        text = ACTION.read_text(encoding="utf-8")
        for output in (
            "evidence-path",
            "evidence-root",
            "action-id",
            "repository",
            "source-branch",
            "source-sha",
            "artifact-digest",
        ):
            self.assertRegex(text, rf"(?m)^  {re.escape(output)}:")

    def test_conformance_workflow_has_read_only_permissions(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: read", text)
        self.assertNotIn("id-token: write", text)
        self.assertNotIn("attestations: write", text)
        self.assertNotIn("pull-requests: write", text)

    def test_numeric_looking_sha_literals_are_quoted_in_yaml(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        quoted = 'source-sha: "4444444444444444444444444444444444444444"'
        unquoted = "source-sha: 4444444444444444444444444444444444444444"
        self.assertEqual(text.count(quoted), 2)
        self.assertNotIn(unquoted, text)

    def test_conformance_runs_builder_then_guard_as_real_local_actions(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        builder_position = text.index("uses: ./deploy-guard/evidence-builder")
        guard_position = text.index("uses: ./deploy-guard\n")
        self.assertLess(builder_position, guard_position)
        self.assertIn("BUILDER_ROOT", text)
        self.assertIn("GUARD_EVIDENCE_ROOT", text)
        self.assertIn('test "$BUILDER_ROOT" = "$GUARD_EVIDENCE_ROOT"', text)

    def test_conformance_manifest_preserves_provenance_boundary(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('"source_sha"', text)
        self.assertIn('"workflow_subject_sha"', text)
        self.assertIn('"builder_verified_upstream_facts": False', text)
        self.assertIn('"deployment_performed": False', text)
        self.assertIn('"authority_granted": False', text)

    def test_consumer_pins_both_actions_and_keeps_deploy_separate(self):
        text = CONSUMER.read_text(encoding="utf-8")
        pin = "REPLACE_WITH_REVIEWED_40_CHAR_COMMIT_SHA"
        self.assertEqual(text.count(pin), 2)
        self.assertIn("deploy-guard/evidence-builder@", text)
        self.assertIn("deploy-guard@", text)
        self.assertIn("if: steps.guard.outputs.decision == 'ACCEPT'", text)
        self.assertIn("if: always()", text)
        self.assertIn("ProofPath does not perform the deployment", text)

    def test_documentation_states_builder_does_not_verify_facts(self):
        text = DOC.read_text(encoding="utf-8")
        for phrase in (
            "does not replace the systems that verify",
            "does not prove that upstream facts are true",
            "pin both Builder and Guard to the same reviewed full commit SHA",
            "`github.sha` can refer to GitHub's synthetic merge commit",
        ):
            self.assertIn(phrase, text)

    def test_no_real_deployment_command_is_added(self):
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ACTION, BUILDER, WORKFLOW, CONSUMER)
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
