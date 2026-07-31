from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/poci-external-submission-admission.yml"


class ExternalSubmissionWorkflowSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_uses_pull_request_target_with_minimal_permissions(self):
        self.assertIn("pull_request_target:", self.text)
        self.assertIn("contents: read", self.text)
        self.assertIn("pull-requests: write", self.text)
        self.assertNotIn("contents: write", self.text)
        self.assertNotIn("id-token: write", self.text)
        self.assertNotIn("attestations: write", self.text)

    def test_checks_out_only_trusted_base(self):
        self.assertEqual(self.text.count("uses: actions/checkout@v4"), 1)
        self.assertIn("ref: ${{ github.event.pull_request.base.sha }}", self.text)
        self.assertNotIn("ref: ${{ github.event.pull_request.head.sha }}", self.text)

    def test_external_head_is_never_executed(self):
        forbidden = (
            "python3 artifacts/intake/",
            "bash artifacts/intake/",
            "source artifacts/intake/",
            "./artifacts/intake/",
            "git checkout ${{ github.event.pull_request.head.sha }}",
        )
        for token in forbidden:
            self.assertNotIn(token, self.text)

    def test_accepts_exactly_three_json_data_files(self):
        self.assertIn("response|submission|provenance", self.text)
        self.assertIn("len(files) != 3", self.text)
        self.assertIn("external-submissions/", self.text)
        self.assertIn("base64 --decode", self.text)

    def test_attestation_verification_is_fully_pinned(self):
        required = (
            "gh attestation verify artifacts/intake/response.json",
            '--repo "$OPERATOR_REPOSITORY"',
            '--signer-workflow "$OPERATOR_WORKFLOW"',
            '--source-digest "$SOURCE_SHA"',
            '--signer-digest "$SIGNER_SHA"',
            '--cert-oidc-issuer "https://token.actions.githubusercontent.com"',
            "--deny-self-hosted-runners",
        )
        for token in required:
            self.assertIn(token, self.text)

    def test_source_must_be_ancestor_of_pr_head(self):
        self.assertIn("compare/${SOURCE_SHA}...${HEAD_SHA}", self.text)
        self.assertIn("ahead|identical", self.text)
        self.assertIn("--source-ancestry-verified", self.text)

    def test_governance_acceptance_is_required(self):
        self.assertIn("verify_poci_organizational_independence.py", self.text)
        self.assertIn('governance.get("decision") != "ACCEPT"', self.text)
        self.assertIn('governance.get("external_owner_count", 0) < 1', self.text)
        self.assertIn('admission.get("authority_granted") is not False', self.text)


if __name__ == "__main__":
    unittest.main()
