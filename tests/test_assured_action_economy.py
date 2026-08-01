from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "evaluate_assured_action_economy.py"
FIXTURE = ROOT / "examples" / "assured-action-economy" / "deploy-quorum.accept.json"

SPEC = importlib.util.spec_from_file_location("assured_action_economy", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
ECONOMY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ECONOMY)


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def refresh_job_root(bundle: dict) -> None:
    bundle["job"]["job_root"] = ECONOMY.compute_job_root(bundle["job"])


def refresh_commitment(bundle: dict, witness_id: str) -> None:
    reveal = next(item for item in bundle["reveals"] if item["witness_id"] == witness_id)
    commitment = next(
        item for item in bundle["commitments"] if item["witness_id"] == witness_id
    )
    commitment["commitment_root"] = ECONOMY.compute_commitment(
        bundle["job"]["job_id"], reveal
    )


class AssuredActionEconomyTests(unittest.TestCase):
    def test_reference_job_is_ready_without_moving_money(self) -> None:
        receipt = ECONOMY.evaluate(load_fixture())

        self.assertEqual(receipt["decision"], "ACCEPT")
        self.assertEqual(receipt["primary_reason_code"], "ECONOMY_JOB_FULFILLED")
        self.assertEqual(receipt["action_consensus"]["verdict"], "ACCEPT")
        self.assertEqual(receipt["settlement_state"], "READY_FOR_EXTERNAL_PAYMENT_REQUEST")
        self.assertTrue(receipt["payment_request_ready"])
        self.assertFalse(receipt["external_payment_authority_granted"])
        self.assertFalse(receipt["payment_execution_performed"])
        self.assertFalse(receipt["slashing_performed"])
        self.assertEqual(receipt["coverage"], "NOT_FINANCIALLY_COVERED")
        self.assertTrue(receipt["economics"]["conservation_verified"])
        self.assertEqual(receipt["economics"]["allocation_total_minor"], 10000)

    def test_blocked_action_still_earns_when_verification_work_agrees(self) -> None:
        bundle = load_fixture()
        for reveal in bundle["reveals"]:
            reveal["verdict"] = "BLOCK"
            refresh_commitment(bundle, reveal["witness_id"])

        receipt = ECONOMY.evaluate(bundle)

        self.assertEqual(receipt["decision"], "ACCEPT")
        self.assertEqual(receipt["action_consensus"]["verdict"], "BLOCK")
        self.assertTrue(receipt["payment_request_ready"])
        self.assertEqual(receipt["economics"]["witness_payout_total_minor"], 5400)

    def test_open_challenge_window_holds_settlement(self) -> None:
        bundle = load_fixture()
        bundle["evaluated_at"] = "2026-08-01T20:30:00Z"

        receipt = ECONOMY.evaluate(bundle)

        self.assertEqual(receipt["decision"], "HOLD")
        self.assertEqual(receipt["primary_reason_code"], "ECONOMY_CHALLENGE_WINDOW_OPEN")
        self.assertFalse(receipt["payment_request_ready"])

    def test_honest_dissent_holds_without_slashing(self) -> None:
        bundle = load_fixture()
        bundle["reveals"][2]["verdict"] = "BLOCK"
        refresh_commitment(bundle, "witness-gamma")

        receipt = ECONOMY.evaluate(bundle)

        self.assertEqual(receipt["decision"], "HOLD")
        self.assertEqual(
            receipt["primary_reason_code"],
            "ECONOMY_WITNESS_DISSENT_REQUIRES_REVIEW",
        )
        self.assertFalse(receipt["slashing_performed"])
        self.assertIsNone(receipt["action_consensus"]["verdict"])

    def test_reveal_substitution_challenges_commitment(self) -> None:
        bundle = load_fixture()
        bundle["reveals"][0]["verdict"] = "BLOCK"

        receipt = ECONOMY.evaluate(bundle)

        self.assertEqual(receipt["decision"], "CHALLENGE")
        self.assertEqual(receipt["primary_reason_code"], "ECONOMY_COMMITMENT_MISMATCH")

    def test_admission_receipt_substitution_is_challenge(self) -> None:
        bundle = load_fixture()
        bundle["reveals"][0]["admission_receipt_root"] = "sha256:" + "9" * 64
        refresh_commitment(bundle, "witness-alpha")

        receipt = ECONOMY.evaluate(bundle)

        self.assertEqual(receipt["decision"], "CHALLENGE")
        self.assertEqual(
            receipt["primary_reason_code"], "ECONOMY_ADMISSION_RECEIPT_MISMATCH"
        )

    def test_clearance_substitution_is_challenge(self) -> None:
        bundle = load_fixture()
        bundle["reveals"][1]["action_clearance_root"] = "sha256:" + "8" * 64
        refresh_commitment(bundle, "witness-beta")

        receipt = ECONOMY.evaluate(bundle)

        self.assertEqual(receipt["decision"], "CHALLENGE")
        self.assertEqual(receipt["primary_reason_code"], "ECONOMY_CLEARANCE_ROOT_MISMATCH")

    def test_open_dispute_holds_settlement(self) -> None:
        bundle = load_fixture()
        bundle["disputes"] = [{
            "dispute_id": "dispute-0001",
            "challenger_id": "security-reviewer-alpha",
            "status": "OPEN",
            "reason_code": "EVIDENCE_RECOMPUTATION_MISMATCH",
            "filed_at": "2026-08-01T20:45:00Z",
        }]

        receipt = ECONOMY.evaluate(bundle)

        self.assertEqual(receipt["decision"], "HOLD")
        self.assertEqual(receipt["primary_reason_code"], "ECONOMY_OPEN_DISPUTE")

    def test_budget_mutation_blocks(self) -> None:
        bundle = load_fixture()
        bundle["job"]["platform_fee_minor"] += 1
        refresh_job_root(bundle)

        receipt = ECONOMY.evaluate(bundle)

        self.assertEqual(receipt["decision"], "BLOCK")
        self.assertEqual(receipt["primary_reason_code"], "ECONOMY_BUDGET_NOT_CONSERVED")
        self.assertFalse(receipt["economics"]["conservation_verified"])

    def test_same_control_domain_blocks_false_independence(self) -> None:
        bundle = load_fixture()
        bundle["assignments"][2]["control_domain"] = "operator-org-alpha"

        receipt = ECONOMY.evaluate(bundle)

        self.assertEqual(receipt["decision"], "BLOCK")
        self.assertEqual(
            receipt["primary_reason_code"],
            "ECONOMY_CONTROL_DOMAIN_DIVERSITY_INSUFFICIENT",
        )

    def test_single_implementation_blocks_false_diversity(self) -> None:
        bundle = load_fixture()
        for assignment in bundle["assignments"]:
            assignment["implementation_id"] = "one-shared-verifier"

        receipt = ECONOMY.evaluate(bundle)

        self.assertEqual(receipt["decision"], "BLOCK")
        self.assertEqual(
            receipt["primary_reason_code"],
            "ECONOMY_IMPLEMENTATION_DIVERSITY_INSUFFICIENT",
        )

    def test_missing_reveal_holds(self) -> None:
        bundle = load_fixture()
        bundle["reveals"].pop()

        receipt = ECONOMY.evaluate(bundle)

        self.assertEqual(receipt["decision"], "HOLD")
        codes = {item["code"] for item in receipt["findings"]}
        self.assertIn("ECONOMY_REVEAL_MISSING", codes)
        self.assertIn("ECONOMY_QUORUM_INSUFFICIENT", codes)

    def test_unassigned_reveal_is_challenge(self) -> None:
        bundle = load_fixture()
        extra = copy.deepcopy(bundle["reveals"][0])
        extra["witness_id"] = "witness-sybil"
        extra["nonce"] = "sybil-nonce"
        bundle["reveals"].append(extra)

        receipt = ECONOMY.evaluate(bundle)

        self.assertEqual(receipt["decision"], "CHALLENGE")
        self.assertEqual(receipt["primary_reason_code"], "ECONOMY_UNASSIGNED_REVEAL")

    def test_job_root_mutation_is_challenge(self) -> None:
        bundle = load_fixture()
        bundle["job"]["client_account_id"] = "substituted-client"

        receipt = ECONOMY.evaluate(bundle)

        self.assertEqual(receipt["decision"], "CHALLENGE")
        self.assertEqual(receipt["primary_reason_code"], "ECONOMY_JOB_ROOT_MISMATCH")

    def test_settlement_root_commits_exact_receipt(self) -> None:
        receipt = ECONOMY.evaluate(load_fixture())
        normalized = copy.deepcopy(receipt)
        normalized["settlement_root"] = None

        self.assertEqual(
            receipt["settlement_root"],
            ECONOMY.digest(ECONOMY.SETTLEMENT_DOMAIN, normalized),
        )

        mutated = copy.deepcopy(normalized)
        mutated["economics"]["platform_fee_minor"] += 1
        self.assertNotEqual(
            receipt["settlement_root"],
            ECONOMY.digest(ECONOMY.SETTLEMENT_DOMAIN, mutated),
        )

    def test_set_like_array_order_is_root_invariant(self) -> None:
        original = ECONOMY.evaluate(load_fixture())
        reordered_bundle = load_fixture()
        for field in ("assignments", "commitments", "reveals"):
            reordered_bundle[field].reverse()
        reordered = ECONOMY.evaluate(reordered_bundle)

        self.assertEqual(reordered["decision"], "ACCEPT")
        self.assertEqual(reordered["bundle_root"], original["bundle_root"])
        self.assertEqual(reordered["settlement_root"], original["settlement_root"])

    def test_strict_loader_rejects_duplicate_keys_and_floats(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            duplicate = Path(directory) / "duplicate.json"
            duplicate.write_text('{"profile_id":"a","profile_id":"b"}', encoding="utf-8")
            with self.assertRaises(ECONOMY.EconomyError):
                ECONOMY.load_json(duplicate)

            floating = Path(directory) / "float.json"
            floating.write_text('{"amount":1.5}', encoding="utf-8")
            with self.assertRaises(ECONOMY.EconomyError):
                ECONOMY.load_json(floating)

    def test_cli_exit_codes_follow_decision(self) -> None:
        accepted = subprocess.run(
            [sys.executable, str(SCRIPT), str(FIXTURE)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(accepted.returncode, 0, accepted.stderr)

        bundle = load_fixture()
        bundle["evaluated_at"] = "2026-08-01T20:30:00Z"
        with tempfile.TemporaryDirectory() as directory:
            held_path = Path(directory) / "held.json"
            held_path.write_text(json.dumps(bundle), encoding="utf-8")
            held = subprocess.run(
                [sys.executable, str(SCRIPT), str(held_path)],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(held.returncode, 2, held.stderr)

    def test_committed_schemas_parse_and_match_profiles(self) -> None:
        bundle_schema = json.loads(
            (ROOT / "schemas" / "assured-action-economy-bundle-v0.1.schema.json")
            .read_text(encoding="utf-8")
        )
        receipt_schema = json.loads(
            (ROOT / "schemas" / "assured-action-settlement-receipt-v0.1.schema.json")
            .read_text(encoding="utf-8")
        )

        self.assertEqual(bundle_schema["properties"]["profile_id"]["const"], ECONOMY.BUNDLE_PROFILE)
        self.assertEqual(receipt_schema["properties"]["profile_id"]["const"], ECONOMY.RECEIPT_PROFILE)

    def test_workflow_attests_plans_without_payment_authority(self) -> None:
        workflow = (
            ROOT / ".github" / "workflows" / "proofpath-assured-action-economy.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("contents: read", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertIn("attestations: write", workflow)
        self.assertIn("uses: actions/attest@v4", workflow)
        self.assertIn("payment_execution_performed", workflow)
        self.assertIn("external_payment_authority_granted", workflow)
        self.assertIn("slashing_performed", workflow)
        self.assertNotIn("secrets.", workflow)
        self.assertNotIn("payments: write", workflow)
        self.assertNotIn("issues: write", workflow)
        self.assertNotIn("pull-requests: write", workflow)


if __name__ == "__main__":
    unittest.main()
