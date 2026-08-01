import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE = ROOT / "control-cloud/governance/verify_workflow_governance.py"
INGEST = ROOT / "control-cloud/ingestion/governed_ingest.py"
DOCS = ROOT / "control-cloud/governance/README.md"
WORKFLOW = ROOT / ".github/workflows/proofpath-workflow-governance.yml"
SCHEMAS = [
    ROOT / "schemas/proofpath-control-cloud-workflow-governance-registry-v0.1.schema.json",
    ROOT / "schemas/proofpath-control-cloud-workflow-governance-decision-v0.1.schema.json",
    ROOT / "schemas/proofpath-control-cloud-governed-ingest-receipt-v0.1.schema.json",
]


class WorkflowGovernanceSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.governance = GOVERNANCE.read_text(encoding="utf-8")
        cls.ingest = INGEST.read_text(encoding="utf-8")
        cls.docs = DOCS.read_text(encoding="utf-8")
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_runtime_has_no_shell_or_repo_write_primitive(self):
        combined = self.governance + self.ingest
        for forbidden in ("subprocess.run", "subprocess.Popen", "os.system(", "shell=True", "git push", "gh api", "requests.post"):
            self.assertNotIn(forbidden, combined)
        self.assertIn('"repository_write_performed": False', combined)
        self.assertIn('"authority_granted": False', combined)

    def test_governance_decision_path_is_server_derived(self):
        self.assertIn('admission_result_root.split(":", 1)[1] + ".json"', self.ingest)
        self.assertIn("governance_dir.resolve()", self.ingest)
        self.assertIn("GOVERNANCE_DECISION_SYMLINK_REJECTED", self.ingest)
        self.assertNotIn('request["governance_decision_path"]', self.ingest)

    def test_governance_is_checked_before_append(self):
        governance_position = self.ingest.index("load_bound_governance_decision")
        append_position = self.ingest.index("admitted.ingest_admitted_request")
        self.assertLess(governance_position, append_position)
        self.assertIn('"governance_trust_verified_by_api": True', self.ingest)
        self.assertIn('"provenance_cryptographically_verified_by_api": True', self.ingest)

    def test_registry_pins_identity_scope_and_review(self):
        for token in (
            '"workflow_file_digest"', '"signer_sha"', '"allowed_event_types"',
            '"allowed_ref_prefixes"', '"reviewer_quorum"', '"effective_at"',
            '"expires_at"', '"owner_scope"', '"revocations"',
        ):
            self.assertIn(token, self.governance)

    def test_fail_closed_reason_codes_exist(self):
        for code in (
            "missing_trust_record", "signer_sha_not_pinned", "workflow_digest_mutated",
            "trust_window_inactive", "trust_record_revoked", "reviewer_quorum_missing",
            "event_type_not_allowed", "ref_not_allowed", "ambiguous_trust_record",
        ):
            self.assertIn(code, self.governance)

    def test_revocation_check_is_proposal_only(self):
        self.assertIn('"PROPOSE_REVOKE"', self.governance)
        self.assertIn('"NO_CHANGE"', self.governance)
        self.assertIn('"repository_write_performed": False', self.governance)
        self.assertNotIn("update_ref", self.governance)
        self.assertNotIn("delete_file", self.governance)

    def test_schemas_are_strict(self):
        for path in SCHEMAS:
            schema = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(schema["type"], "object")
            self.assertIs(schema["additionalProperties"], False)
            self.assertTrue(schema["required"])

    def test_workflow_actions_are_full_sha_pinned(self):
        uses = re.findall(r"uses:\s+([^@\s]+)@([^\s]+)", self.workflow)
        self.assertGreaterEqual(len(uses), 5)
        for action, ref in uses:
            self.assertRegex(ref, r"^[0-9a-f]{40}$", msg=f"{action} is not full-SHA pinned")

    def test_workflow_proves_accept_mutation_revocation_and_change_proposal(self):
        for phrase in (
            "Evaluate ACTIVE trusted workflow",
            "Append only after dual verification",
            "workflow_digest_mutated",
            "trust_record_revoked",
            "PROPOSE_REVOKE",
            "governance_trust_verified_by_api",
        ):
            self.assertIn(phrase, self.workflow)

    def test_workflow_permissions_are_narrow(self):
        self.assertIn("permissions: {}", self.workflow)
        self.assertNotIn("contents: write", self.workflow)
        self.assertNotIn("pull-requests: write", self.workflow)
        self.assertNotIn("actions: write", self.workflow)

    def test_uploaded_evidence_excludes_headers_and_secrets(self):
        upload = self.workflow.split("- name: Upload governance evidence", 1)[1]
        self.assertNotIn("headers.json", upload)
        self.assertNotIn("tenant-registry.json", upload)
        self.assertNotIn("PROOFPATH_GOVERNANCE_DEMO_SECRET", upload)

    def test_documentation_is_honest_about_reference_reviewers(self):
        for phrase in (
            "illustrative only",
            "**not** represent independent production approval",
            "synthetic reviewer identities",
            "does not",
            "Production still requires",
            "repository_write_performed: false",
        ):
            self.assertIn(phrase, self.docs)


if __name__ == "__main__":
    unittest.main()
