from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "verify_poci.py"
spec = importlib.util.spec_from_file_location("verify_poci", MODULE_PATH)
assert spec and spec.loader
verify_poci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify_poci)

FIXTURE_DIR = REPO_ROOT / "examples" / "poci-witness" / "fixtures"
MANIFEST = FIXTURE_DIR / "manifest.json"
VALID = FIXTURE_DIR / "valid-action.accept.json"


class PociConformanceTests(unittest.TestCase):
    def test_all_committed_fixtures_match_external_manifest(self) -> None:
        report = verify_poci.verify_manifest(MANIFEST)
        failures = [case for case in report["cases"] if not case["passed"]]
        self.assertTrue(report["passed"], json.dumps(failures, indent=2))
        self.assertEqual(12, report["case_count"])

    def test_embedded_verification_is_not_trusted(self) -> None:
        envelope = verify_poci.load_json(FIXTURE_DIR / "expired-intent.block.json")
        envelope["verification"] = {
            "verifier_id": "attacker",
            "decision": "ACCEPT",
            "primary_reason_code": None,
            "reason_codes": [],
            "verified_at": envelope["created_at"],
        }
        result = verify_poci.verify_envelope(envelope)
        self.assertEqual("BLOCK", result["decision"])
        self.assertEqual("INTENT_EXPIRED", result["primary_reason_code"])

    def test_key_order_does_not_change_root(self) -> None:
        envelope = verify_poci.load_json(VALID)
        reordered = {key: envelope[key] for key in reversed(list(envelope.keys()))}
        self.assertEqual(
            verify_poci.compute_envelope_root(envelope),
            verify_poci.compute_envelope_root(reordered),
        )

    def test_normalized_output_is_byte_stable(self) -> None:
        envelope = verify_poci.load_json(VALID)
        first = verify_poci.normalized_json_bytes(verify_poci.verify_envelope(envelope))
        second = verify_poci.normalized_json_bytes(verify_poci.verify_envelope(copy.deepcopy(envelope)))
        self.assertEqual(first, second)

    def test_declared_root_mismatch_is_challenged(self) -> None:
        envelope = verify_poci.load_json(VALID)
        envelope["evidence_integrity"]["envelope_root"] = "sha256:" + "f" * 64
        result = verify_poci.verify_envelope(envelope)
        self.assertEqual("CHALLENGE", result["decision"])
        self.assertEqual("ENVELOPE_ROOT_MISMATCH", result["primary_reason_code"])

    def test_duplicate_json_keys_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "duplicate.json"
            path.write_text('{"protocol":{},"protocol":{}}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                verify_poci.load_json(path)

    def test_twenty_security_mutations_never_accept(self) -> None:
        base = verify_poci.load_json(VALID)

        def remove_authority(x): x.pop("authority")
        def unsupported_profile(x): x["protocol"]["profile_id"] = "proofpath.poci.v9.9"
        def expire_intent(x): x["intent"]["expires_at"] = "2026-07-30T23:00:00Z"
        def replay_intent(x): x["extensions"] = {"proofpath.fixture": {"used_nonces": [x["intent"]["nonce"]]}}
        def remove_parent(x): x["causal_context"].update(parent_type="none", parent_id=None, parent_digest=None, relationship="none")
        def mismatch_parent(x): x["causal_context"]["relationship"] = "none"
        def expand_scope(x): x["proposal"]["scope"] = ["compute.training.unbounded"]
        def mismatch_receipt(x): x["execution"]["receipt_digest"] = "sha256:" + "7" * 64
        def mismatch_result(x): x["observed_result"]["result_digest"] = "sha256:" + "8" * 64
        def conflict_witness(x):
            other = copy.deepcopy(x["witnesses"][0]); other["witness_id"] = "witness_002"; other["verdict"] = "BLOCK"; x["witnesses"].append(other)
        def irreversible(x): x["authority"].update(reversibility="irreversible", approval_required=True)
        def wrong_principal(x): x["authority"]["principal_id"] = "other_principal"
        def wrong_agent(x): x["authority"]["agent_id"] = "other_agent"
        def wrong_executor(x): x["authority"]["executor_id"] = "other_executor"
        def wrong_action(x): x["authority"]["action_kind"] = "payment.send"
        def wrong_proposal_binding(x): x["execution"]["proposal_id"] = "other_proposal"
        def remove_receipt(x): x["execution"]["receipt_ref"] = None
        def remove_result(x): x["observed_result"]["result_ref"] = None
        def equivocate(x):
            other = copy.deepcopy(x["witnesses"][0]); other["statement_digest"] = "sha256:" + "9" * 64; other["statement_ref"]["digest"] = other["statement_digest"]; x["witnesses"].append(other)
        def bad_root(x): x["evidence_integrity"]["envelope_root"] = "sha256:" + "a" * 64

        mutations = [
            remove_authority, unsupported_profile, expire_intent, replay_intent,
            remove_parent, mismatch_parent, expand_scope, mismatch_receipt,
            mismatch_result, conflict_witness, irreversible, wrong_principal,
            wrong_agent, wrong_executor, wrong_action, wrong_proposal_binding,
            remove_receipt, remove_result, equivocate, bad_root,
        ]
        self.assertEqual(20, len(mutations))
        for mutation in mutations:
            with self.subTest(mutation=mutation.__name__):
                envelope = copy.deepcopy(base)
                mutation(envelope)
                result = verify_poci.verify_envelope(envelope)
                self.assertNotEqual("ACCEPT", result["decision"])
                self.assertFalse(result["valid"])
                self.assertIsNotNone(result["primary_reason_code"])


if __name__ == "__main__":
    unittest.main()
