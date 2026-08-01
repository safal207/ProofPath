import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEWERS = ROOT / "control-cloud/reviewers/verify_reviewer_separation.py"
INGEST = ROOT / "control-cloud/ingestion/separated_ingest.py"
DOCS = ROOT / "control-cloud/reviewers/README.md"
WORKFLOW = ROOT / ".github/workflows/proofpath-reviewer-separation.yml"
SCHEMAS = [
    ROOT / "schemas/proofpath-control-cloud-reviewer-identity-registry-v0.1.schema.json",
    ROOT / "schemas/proofpath-control-cloud-reviewer-approval-bundle-v0.1.schema.json",
    ROOT / "schemas/proofpath-control-cloud-reviewer-separation-decision-v0.1.schema.json",
    ROOT / "schemas/proofpath-control-cloud-separated-ingest-receipt-v0.1.schema.json",
]


class ReviewerSeparationSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reviewers = REVIEWERS.read_text(encoding="utf-8")
        cls.ingest = INGEST.read_text(encoding="utf-8")
        cls.docs = DOCS.read_text(encoding="utf-8")
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_runtime_has_no_shell_or_repo_write_primitive(self):
        combined = self.reviewers + self.ingest
        for forbidden in (
            "subprocess.run",
            "subprocess.Popen",
            "os.system(",
            "shell=True",
            "git push",
            "gh api",
            "requests.post",
            "update_ref",
            "merge_pull_request",
        ):
            self.assertNotIn(forbidden, combined)
        self.assertIn('"repository_write_performed": False', combined)
        self.assertIn('"authority_granted": False', combined)

    def test_decision_path_is_server_derived(self):
        self.assertIn('governance_decision_root.split(":", 1)[1] + ".json"', self.ingest)
        self.assertIn("separation_dir.resolve()", self.ingest)
        self.assertIn("REVIEWER_DECISION_SYMLINK_REJECTED", self.ingest)
        self.assertNotIn('request["reviewer_decision_path"]', self.ingest)

    def test_reviewer_gate_precedes_append(self):
        reviewer_position = self.ingest.index("load_bound_reviewer_decision")
        append_position = self.ingest.index("governed.ingest_governed_request")
        self.assertLess(reviewer_position, append_position)
        self.assertIn('"reviewer_identity_verified_by_api": True', self.ingest)
        self.assertIn('"separation_of_duties_verified_by_api": True', self.ingest)

    def test_fail_closed_reason_codes_exist(self):
        for code in (
            "author_self_approval",
            "author_organization_conflict",
            "author_control_cluster_conflict",
            "author_payment_cluster_conflict",
            "reviewer_control_cluster_collision",
            "reviewer_payment_cluster_collision",
            "reviewer_identity_suspended",
            "identity_evidence_mismatch",
            "reviewer_quorum_missing",
            "organization_diversity_missing",
            "approval_stale_or_future",
            "reviewer_rejected",
        ):
            self.assertIn(code, self.reviewers)

    def test_identity_change_is_proposal_only(self):
        self.assertIn('"PROPOSE_SUSPEND"', self.reviewers)
        self.assertIn('"NO_CHANGE"', self.reviewers)
        self.assertIn('"credential_revocation_performed": False', self.reviewers)
        self.assertIn('"repository_write_performed": False', self.reviewers)

    def test_schemas_are_strict(self):
        for path in SCHEMAS:
            schema = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(schema["type"], "object")
            self.assertIs(schema["additionalProperties"], False)
            self.assertTrue(schema["required"])

    def test_workflow_actions_are_full_sha_pinned(self):
        uses = re.findall(r"uses:\s+([^@\s]+)@([^\s]+)", self.workflow)
        self.assertGreaterEqual(len(uses), 4)
        for action, ref in uses:
            self.assertRegex(ref, r"^[0-9a-f]{40}$", msg=f"{action} is not full-SHA pinned")

    def test_workflow_permissions_are_narrow(self):
        self.assertIn("permissions: {}", self.workflow)
        self.assertNotIn("contents: write", self.workflow)
        self.assertNotIn("pull-requests: write", self.workflow)
        self.assertNotIn("actions: write", self.workflow)

    def test_workflow_proves_positive_and_negative_paths(self):
        for phrase in (
            "Evaluate independent reviewer identities",
            "Append only after triple verification",
            "author_self_approval",
            "reviewer_control_cluster_collision",
            "reviewer_identity_suspended",
            "PROPOSE_SUSPEND",
            "separation_of_duties_verified_by_api",
        ):
            self.assertIn(phrase, self.workflow)

    def test_uploaded_evidence_excludes_headers_and_registry_secrets(self):
        upload = self.workflow.split("- name: Upload reviewer separation evidence", 1)[1]
        self.assertNotIn("headers.json", upload)
        self.assertNotIn("tenant-registry.json", upload)
        self.assertNotIn("PROOFPATH_REVIEWER_DEMO_SECRET", upload)

    def test_documentation_is_honest(self):
        normalized = " ".join(self.docs.split())
        for phrase in (
            "synthetic reviewer identities",
            "does not prove that the named reviewers are independent humans",
            "does not perform KYC, KYB, sanctions screening, or beneficial-owner verification",
            "repository_write_performed: false",
            "Production still requires",
        ):
            self.assertIn(phrase, normalized)


if __name__ == "__main__":
    unittest.main()
