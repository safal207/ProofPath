from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTION = (ROOT / "deploy-guard" / "action.yml").read_text(encoding="utf-8")
WRAPPER = (ROOT / "deploy-guard" / "run_action.py").read_text(encoding="utf-8")
WORKFLOW = (
    ROOT / ".github" / "workflows" / "proofpath-deploy-guard-action.yml"
).read_text(encoding="utf-8")
CONSUMER = (
    ROOT / "examples" / "deploy-guard" / "consumer-workflow.yml"
).read_text(encoding="utf-8")
DOC = (ROOT / "docs" / "PROOFPATH_DEPLOY_GUARD_ACTION.md").read_text(encoding="utf-8")


class DeployGuardActionSecurityTests(unittest.TestCase):
    def test_action_is_composite_and_keeps_existing_root_action_separate(self):
        self.assertIn("using: composite", ACTION)
        self.assertIn('python3 "$GITHUB_ACTION_PATH/run_action.py"', ACTION)
        self.assertTrue((ROOT / "action.yml").is_file())
        self.assertNotEqual(
            (ROOT / "action.yml").resolve(),
            (ROOT / "deploy-guard" / "action.yml").resolve(),
        )

    def test_inputs_are_mapped_through_environment_not_shell_interpolation(self):
        for name in (
            "PROOFPATH_POLICY",
            "PROOFPATH_EVIDENCE",
            "PROOFPATH_CERTIFICATE",
            "PROOFPATH_MODE",
        ):
            self.assertIn(name, ACTION)
        run_block = ACTION.split("run: |", 1)[1]
        self.assertNotIn("${{ inputs.", run_block)
        self.assertIn('"$PROOFPATH_POLICY"', run_block)
        self.assertIn('"$PROOFPATH_EVIDENCE"', run_block)

    def test_wrapper_never_invokes_a_shell_or_dynamic_python(self):
        self.assertIn("subprocess.run(", WRAPPER)
        self.assertNotIn("shell=True", WRAPPER)
        self.assertNotIn("os.system", WRAPPER)
        self.assertNotIn("eval(", WRAPPER)
        self.assertNotIn("exec(", WRAPPER)

    def test_wrapper_constrains_paths_to_github_workspace(self):
        self.assertIn("GITHUB_WORKSPACE", WRAPPER)
        self.assertIn("resolved.relative_to(workspace)", WRAPPER)
        self.assertIn("must remain inside GITHUB_WORKSPACE", WRAPPER)

    def test_wrapper_validates_decision_exit_and_assurance_contracts(self):
        required = (
            "verifier exit code does not match its certificate decision",
            "execution_allowed does not match the decision",
            "Deploy Guard must never create or claim new authority",
            'fields["assurance-level"] != "POLICY_VERIFIED"',
            'fields["witness-level"] != "SINGLE_WORKFLOW_REFERENCE"',
            'fields["coverage"] != "NOT_FINANCIALLY_COVERED"',
        )
        for token in required:
            self.assertIn(token, WRAPPER)

    def test_action_exposes_the_complete_machine_readable_surface(self):
        for output in (
            "decision",
            "primary-reason-code",
            "clearance-root",
            "policy-root",
            "evidence-root",
            "execution-allowed",
            "authority-granted",
            "permitted-next-transition",
            "assurance-level",
            "witness-level",
            "coverage",
            "certificate-path",
        ):
            self.assertIn(f"  {output}:\n", ACTION)

    def test_conformance_workflow_has_read_only_repository_permissions(self):
        self.assertIn("permissions:\n  contents: read", WORKFLOW)
        self.assertNotIn("contents: write", WORKFLOW)
        self.assertNotIn("pull-requests: write", WORKFLOW)
        self.assertNotIn("id-token: write", WORKFLOW)
        self.assertNotIn("attestations: write", WORKFLOW)

    def test_conformance_workflow_proves_both_modes(self):
        self.assertIn("Evaluate ACCEPT in enforce mode", WORKFLOW)
        self.assertIn("Evaluate HOLD in observe mode", WORKFLOW)
        self.assertIn("Evaluate BLOCK in observe mode", WORKFLOW)
        self.assertIn("Evaluate CHALLENGE in observe mode", WORKFLOW)
        self.assertIn("Prove enforce mode stops on HOLD", WORKFLOW)
        self.assertIn('test "$ENFORCE_HOLD_OUTCOME" = "failure"', WORKFLOW)

    def test_action_and_conformance_never_execute_a_deployment(self):
        combined = "\n".join((ACTION, WRAPPER, WORKFLOW)).lower()
        forbidden = (
            "kubectl apply",
            "helm upgrade",
            "aws deploy",
            "gcloud run deploy",
            "az deployment",
            "terraform apply",
            "pulumi up",
        )
        for command in forbidden:
            self.assertNotIn(command, combined)

    def test_consumer_uses_a_pinned_commit_placeholder_and_separate_boundary(self):
        self.assertIn(
            "safal207/ProofPath/deploy-guard@REPLACE_WITH_FULL_40_CHARACTER_COMMIT_SHA",
            CONSUMER,
        )
        self.assertIn("if: steps.deploy_guard.outputs.decision == 'ACCEPT'", CONSUMER)
        self.assertIn("if: always()", CONSUMER)
        self.assertNotIn("@main", CONSUMER)
        self.assertIn("Do not use a mutable branch", DOC)

    def test_artifact_retention_is_bounded(self):
        self.assertIn("retention-days: 14", WORKFLOW)
        self.assertIn("retention-days: 14", CONSUMER)


if __name__ == "__main__":
    unittest.main()
