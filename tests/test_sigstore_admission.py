
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "control-cloud/admission/verify_sigstore.py"
spec = importlib.util.spec_from_file_location("sigstore_admission_test", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def certificate(source_sha="1"*40, repository="acme/payments"):
    return {
        "profile_id": "proofpath.deploy.clearance-certificate.v0.1",
        "product": "PROOFPATH_ASSURED_ACTION",
        "decision": "ACCEPT",
        "valid": True,
        "primary_reason_code": None,
        "action": {
            "action_id": "act-001",
            "action_type": "deploy",
            "agent_id": "agent-001",
            "repository": repository,
            "branch": "main",
            "commit_sha": source_sha,
            "environment": "production",
            "artifact_digest": "sha256:" + "a"*64,
        },
        "assurance": {
            "assurance_level": "POLICY_VERIFIED",
            "witness_level": "SINGLE_WORKFLOW_REFERENCE",
            "coverage": "NOT_FINANCIALLY_COVERED",
            "policy_id": "prod-deploy",
            "policy_version": "0.1.0",
        },
        "policy_root": "sha256:" + "b"*64,
        "evidence_root": "sha256:" + "c"*64,
        "clearance_root": "sha256:" + "d"*64,
        "execution_allowed": True,
        "authority_granted": False,
    }


def policy(source_sha="1"*40):
    return {
        "profile_id": module.POLICY_PROFILE,
        "repository": "acme/payments",
        "signer_repository": "acme/payments",
        "signer_workflow": "acme/payments/.github/workflows/deploy.yml",
        "source_sha": source_sha,
        "signer_sha": "2"*40,
        "cert_oidc_issuer": module.DEFAULT_ISSUER,
        "predicate_type": module.DEFAULT_PREDICATE,
        "deny_self_hosted_runners": True,
        "required_runner_environment": "github-hosted",
        "verifier_identity": "proofpath-control-cloud-admission",
    }


def gh_payload(timestamps=True):
    return [
        {
            "attestation": {"bundle": "opaque"},
            "verificationResult": {
                "signature": {"certificate": {"subjectAlternativeName": "x"}},
                "verifiedTimestamps": [{"type": "rekor"}] if timestamps else [],
                "statement": {
                    "predicateType": module.DEFAULT_PREDICATE,
                    "subject": [{"name": "cert", "digest": {"sha256": "0"*64}}],
                    "predicate": {},
                },
            },
        }
    ]


class SigstoreAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.subject = self.root / "certificate.json"
        self.subject.write_bytes(module.canonical_bytes(certificate()) + b"\n")
        self.policy = module.validate_policy(policy())

    def tearDown(self):
        self.temp.cleanup()

    def runner(self, payload=None, returncode=0, stderr=""):
        payload = gh_payload() if payload is None else payload
        def call(argv, **kwargs):
            self.last_argv = argv
            self.last_kwargs = kwargs
            return SimpleNamespace(returncode=returncode, stdout=json.dumps(payload), stderr=stderr)
        return call

    def test_success_builds_bound_result(self):
        with patch.object(module.shutil, "which", return_value="/usr/bin/gh"):
            result = module.verify_subject(
                subject=self.subject,
                policy=self.policy,
                verified_at="2026-08-02T00:00:00Z",
                runner=self.runner(),
            )
        module.validate_result(result)
        self.assertTrue(result["verified"])
        self.assertEqual(result["source_sha"], "1"*40)
        self.assertEqual(result["subject_digest"], module.raw_digest(self.subject.read_bytes()))
        self.assertEqual(result["certificate_canonical_digest"], module.raw_digest(module.canonical_bytes(certificate())))
        self.assertIn("--deny-self-hosted-runners", self.last_argv)
        self.assertIn("--source-digest", self.last_argv)
        self.assertFalse(self.last_kwargs.get("shell", False))

    def test_result_root_detects_tamper(self):
        with patch.object(module.shutil, "which", return_value="/usr/bin/gh"):
            result = module.verify_subject(
                subject=self.subject,
                policy=self.policy,
                verified_at="2026-08-02T00:00:00Z",
                runner=self.runner(),
            )
        result["repository"] = "evil/repo"
        with self.assertRaises(module.AdmissionError) as ctx:
            module.validate_result(result)
        self.assertEqual(ctx.exception.code, "RESULT_ROOT_MISMATCH")

    def test_missing_transparency_timestamp_fails(self):
        with patch.object(module.shutil, "which", return_value="/usr/bin/gh"):
            with self.assertRaises(module.AdmissionError) as ctx:
                module.verify_subject(
                    subject=self.subject,
                    policy=self.policy,
                    verified_at="2026-08-02T00:00:00Z",
                    runner=self.runner(gh_payload(False)),
                )
        self.assertEqual(ctx.exception.code, "TRANSPARENCY_TIMESTAMP_MISSING")

    def test_gh_failure_fails_closed(self):
        with patch.object(module.shutil, "which", return_value="/usr/bin/gh"):
            with self.assertRaises(module.AdmissionError) as ctx:
                module.verify_subject(
                    subject=self.subject,
                    policy=self.policy,
                    verified_at="2026-08-02T00:00:00Z",
                    runner=self.runner(returncode=1, stderr="no attestation"),
                )
        self.assertEqual(ctx.exception.code, "GH_VERIFICATION_FAILED")

    def test_source_binding_conflict_fails_before_gh(self):
        wrong = certificate(source_sha="9"*40)
        self.subject.write_bytes(module.canonical_bytes(wrong) + b"\n")
        with patch.object(module.shutil, "which", return_value="/usr/bin/gh"):
            with self.assertRaises(module.AdmissionError) as ctx:
                module.verify_subject(
                    subject=self.subject,
                    policy=self.policy,
                    verified_at="2026-08-02T00:00:00Z",
                    runner=self.runner(),
                )
        self.assertEqual(ctx.exception.code, "SOURCE_SHA_BINDING_CONFLICT")

    def test_policy_requires_exact_github_oidc(self):
        value = policy()
        value["cert_oidc_issuer"] = "https://example.invalid"
        with self.assertRaises(module.AdmissionError) as ctx:
            module.validate_policy(value)
        self.assertEqual(ctx.exception.code, "UNTRUSTED_ISSUER_POLICY")

    def test_policy_denies_self_hosted(self):
        value = policy()
        value["deny_self_hosted_runners"] = False
        with self.assertRaises(module.AdmissionError) as ctx:
            module.validate_policy(value)
        self.assertEqual(ctx.exception.code, "SELF_HOSTED_POLICY_FORBIDDEN")

    def test_subject_symlink_rejected(self):
        target = self.root / "target.json"
        target.write_bytes(self.subject.read_bytes())
        self.subject.unlink()
        self.subject.symlink_to(target)
        with self.assertRaises(module.AdmissionError) as ctx:
            module.verify_subject(
                subject=self.subject,
                policy=self.policy,
                verified_at="2026-08-02T00:00:00Z",
                runner=self.runner(),
            )
        self.assertEqual(ctx.exception.code, "SUBJECT_UNAVAILABLE")

    def test_duplicate_json_keys_rejected(self):
        self.subject.write_text('{"x":1,"x":2}')
        with self.assertRaises(ValueError):
            module.strict_loads(self.subject.read_bytes())

    def test_command_pins_all_identity_fields(self):
        argv = module.build_gh_command(self.subject, self.policy)
        expected = {
            "--repo", "--signer-repo", "--signer-workflow", "--source-digest",
            "--signer-digest", "--cert-oidc-issuer", "--predicate-type",
            "--deny-self-hosted-runners", "--format",
        }
        self.assertTrue(expected.issubset(set(argv)))


if __name__ == "__main__":
    unittest.main()
