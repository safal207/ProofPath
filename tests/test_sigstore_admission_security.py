
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "control-cloud/admission/verify_sigstore.py"
ADMITTED = ROOT / "control-cloud/ingestion/admitted_ingest.py"
DOCS = ROOT / "control-cloud/admission/README.md"
WORKFLOW = ROOT / ".github/workflows/proofpath-sigstore-admission.yml"
SCHEMAS = [
    ROOT / "schemas/proofpath-control-cloud-sigstore-admission-policy-v0.1.schema.json",
    ROOT / "schemas/proofpath-control-cloud-sigstore-admission-result-v0.1.schema.json",
    ROOT / "schemas/proofpath-control-cloud-admitted-ingest-receipt-v0.1.schema.json",
]


class SigstoreAdmissionSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verifier = VERIFIER.read_text(encoding="utf-8")
        cls.admitted = ADMITTED.read_text(encoding="utf-8")
        cls.docs = DOCS.read_text(encoding="utf-8")
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_verifier_invokes_gh_without_shell(self):
        self.assertIn('"gh",\n        "attestation",\n        "verify"', self.verifier)
        self.assertIn("subprocess.run", self.verifier)
        self.assertNotIn("shell=True", self.verifier)
        self.assertNotIn("os.system(", self.verifier)
        self.assertNotIn("subprocess.Popen(", self.verifier)
        self.assertNotIn("eval(", self.verifier)
        self.assertNotIn("exec(", self.verifier)

    def test_gh_identity_policy_is_fully_pinned(self):
        required = [
            '"--repo"',
            '"--signer-workflow"',
            '"--source-digest"',
            '"--signer-digest"',
            '"--cert-oidc-issuer"',
            '"--predicate-type"',
            '"--deny-self-hosted-runners"',
            '"--format"',
        ]
        for token in required:
            self.assertIn(token, self.verifier)
        self.assertIn("https://token.actions.githubusercontent.com", self.verifier)
        self.assertIn("https://slsa.dev/provenance/v1", self.verifier)

    def test_transparency_timestamp_is_required(self):
        self.assertIn("verifiedTimestamps", self.verifier)
        self.assertIn("TRANSPARENCY_TIMESTAMP_MISSING", self.verifier)
        self.assertIn('"transparency_timestamp_verified": True', self.verifier)

    def test_result_cannot_grant_authority_or_execute(self):
        for boundary in (
            '"authority_granted": False',
            '"deployment_performed": False',
            '"payments_executed": False',
        ):
            self.assertIn(boundary, self.verifier)

    def test_ingestion_uses_server_side_digest_derived_result_path(self):
        self.assertIn('filename = subject_digest.split(":", 1)[1] + ".json"', self.admitted)
        self.assertIn("admissions_dir.resolve()", self.admitted)
        self.assertIn("ADMISSION_RESULT_SYMLINK_REJECTED", self.admitted)
        self.assertNotIn('request["admission_result_path"]', self.admitted)

    def test_true_provenance_requires_validated_result(self):
        load_position = self.admitted.index("result = load_bound_admission_result")
        true_position = self.admitted.index('"provenance_cryptographically_verified_by_api": True')
        self.assertLess(load_position, true_position)
        self.assertIn("admission.validate_result", self.admitted)
        self.assertIn("certificate_canonical_digest", self.admitted)
        self.assertIn("ADMISSION_BINDING_CONFLICT", self.admitted)

    def test_admitted_store_is_append_only_and_no_follow(self):
        for token in ("fcntl.flock", "os.O_APPEND", "os.fsync", "O_NOFOLLOW"):
            self.assertIn(token, self.admitted)
        self.assertIn("STORE_SYMLINK_REJECTED", self.admitted)
        self.assertIn("admitted-events.jsonl", self.admitted)

    def test_admitted_receipt_preserves_financial_and_authority_boundaries(self):
        for boundary in (
            '"financial_status": "RECORDED_NOT_PAYABLE"',
            '"payments_executed": False',
            '"insurance_provided": False',
            '"deployment_performed": False',
            '"authority_granted": False',
        ):
            self.assertIn(boundary, self.admitted)

    def test_schemas_are_strict(self):
        for path in SCHEMAS:
            schema = json.loads(path.read_text(encoding="utf-8"))
            self.assertIs(schema["additionalProperties"], False)
            self.assertEqual(schema["type"], "object")
            self.assertTrue(schema["required"])

    def test_workflow_actions_are_full_sha_pinned(self):
        uses = re.findall(r"uses:\s+([^@\s]+)@([^\s]+)", self.workflow)
        self.assertGreaterEqual(len(uses), 8)
        for action, ref in uses:
            self.assertRegex(ref, r"^[0-9a-f]{40}$", msg=f"{action} is not full-SHA pinned")

    def test_workflow_runs_real_cryptographic_verification(self):
        self.assertIn("verify_sigstore.py verify", self.workflow)
        self.assertIn("GH_TOKEN: ${{ github.token }}", self.workflow)
        self.assertIn("Attest exact certificate bytes", self.workflow)
        self.assertIn("Ingest only after cryptographic admission", self.workflow)
        self.assertIn("provenance_cryptographically_verified_by_api", self.workflow)

    def test_workflow_does_not_upload_auth_headers_or_key_material(self):
        upload_section = self.workflow.split("- name: Upload admission evidence", 1)[1]
        self.assertNotIn("headers.json", upload_section)
        self.assertNotIn("tenant-registry.json", upload_section)
        self.assertNotIn("PROOFPATH_SIGSTORE_ADMISSION_DEMO_SECRET", upload_section)

    def test_workflow_permissions_are_narrow(self):
        self.assertIn("permissions: {}", self.workflow)
        self.assertNotIn("contents: write", self.workflow)
        self.assertNotIn("pull-requests: write", self.workflow)
        self.assertNotIn("actions: write", self.workflow)
        self.assertNotIn("packages: write", self.workflow)

    def test_documentation_states_limitations(self):
        for phrase in (
            "does **not**",
            "does not grant",
            "does not trust",
            "RECORDED_NOT_PAYABLE",
            "Production still requires",
            "compromised trusted workflow",
        ):
            self.assertIn(phrase, self.docs)


if __name__ == "__main__":
    unittest.main()
