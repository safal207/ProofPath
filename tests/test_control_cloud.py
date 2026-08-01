from __future__ import annotations

import copy
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "control-cloud" / "build_snapshot.py"
DATASET = ROOT / "examples" / "control-cloud" / "assured-actions.json"
POLICY = ROOT / "examples" / "control-cloud" / "settlement-policy.json"

SPEC = importlib.util.spec_from_file_location("proofpath_control_cloud", SCRIPT)
assert SPEC and SPEC.loader
cloud = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cloud)


class ControlCloudTests(unittest.TestCase):
    def setUp(self):
        self.dataset = json.loads(DATASET.read_text(encoding="utf-8"))
        self.policy = json.loads(POLICY.read_text(encoding="utf-8"))

    def build(self):
        return cloud.build_snapshot(copy.deepcopy(self.dataset), copy.deepcopy(self.policy))

    def test_reference_snapshot_is_exact_and_deterministic(self):
        first = self.build()
        second = self.build()
        self.assertEqual(first, second)
        self.assertEqual(
            first["snapshot_root"],
            "sha256:a782f7a1b8fc5d7a6a11815066191a304a32231d969381637902a75f55467deb",
        )
        self.assertEqual(cloud.compute_snapshot_root(first), first["snapshot_root"])

    def test_decision_and_risk_counts(self):
        snapshot = self.build()
        self.assertEqual(
            snapshot["decision_counts"],
            {"ACCEPT": 1, "HOLD": 1, "BLOCK": 1, "CHALLENGE": 1},
        )
        self.assertEqual(
            snapshot["risk_counts"],
            {"low": 1, "medium": 1, "high": 1, "critical": 1},
        )

    def test_reference_financial_summary(self):
        snapshot = self.build()
        self.assertEqual(
            snapshot["financial_summary"],
            {
                "gross_revenue_minor": 25500,
                "operator_pool_minor": 14024,
                "dispute_reserve_minor": 2550,
                "infrastructure_minor": 1274,
                "platform_revenue_minor": 7652,
            },
        )

    def test_every_minor_unit_is_conserved(self):
        snapshot = self.build()
        summary = snapshot["financial_summary"]
        self.assertEqual(
            summary["gross_revenue_minor"],
            summary["operator_pool_minor"]
            + summary["dispute_reserve_minor"]
            + summary["infrastructure_minor"]
            + summary["platform_revenue_minor"],
        )
        self.assertEqual(
            summary["operator_pool_minor"],
            sum(item["earnings_minor"] for item in snapshot["operator_earnings"]),
        )
        for action in snapshot["actions"]:
            self.assertEqual(
                action["gross_price_minor"],
                action["operator_pool_minor"]
                + action["dispute_reserve_minor"]
                + action["infrastructure_minor"]
                + action["platform_revenue_minor"],
            )
            self.assertEqual(
                action["operator_pool_minor"],
                sum(item["amount_minor"] for item in action["operator_payouts"]),
            )

    def test_operator_remainder_allocation_is_deterministic(self):
        payouts = cloud.allocate_operator_pool(
            7,
            [
                {"operator_id": "b", "role": "witness", "weight": 1},
                {"operator_id": "a", "role": "witness", "weight": 1},
            ],
        )
        self.assertEqual([item["operator_id"] for item in payouts], ["b", "a"])
        self.assertEqual([item["amount_minor"] for item in payouts], [4, 3])

    def test_duplicate_action_id_is_rejected(self):
        duplicate = copy.deepcopy(self.dataset["actions"][0])
        duplicate["certificate"]["clearance_root"] = "sha256:" + "f" * 64
        self.dataset["actions"].append(duplicate)
        with self.assertRaisesRegex(cloud.ControlCloudError, "duplicate action_id"):
            self.build()

    def test_duplicate_clearance_root_is_rejected(self):
        duplicate = copy.deepcopy(self.dataset["actions"][0])
        duplicate["certificate"]["action"]["action_id"] = "act-extra"
        self.dataset["actions"].append(duplicate)
        with self.assertRaisesRegex(cloud.ControlCloudError, "duplicate clearance_root"):
            self.build()

    def test_accept_cannot_deny_execution(self):
        self.dataset["actions"][0]["certificate"]["execution_allowed"] = False
        with self.assertRaisesRegex(cloud.ControlCloudError, "ACCEPT must be valid"):
            self.build()

    def test_non_accept_cannot_allow_execution(self):
        self.dataset["actions"][1]["certificate"]["execution_allowed"] = True
        with self.assertRaisesRegex(cloud.ControlCloudError, "non-ACCEPT must be invalid"):
            self.build()

    def test_certificate_cannot_grant_authority(self):
        self.dataset["actions"][0]["certificate"]["authority_granted"] = True
        with self.assertRaisesRegex(cloud.ControlCloudError, "attempts to grant authority"):
            self.build()

    def test_allocation_basis_points_must_sum_to_10000(self):
        self.policy["allocations_bps"]["platform"] = 2999
        with self.assertRaisesRegex(cloud.ControlCloudError, "sum to exactly 10000"):
            self.build()

    def test_operator_assignments_must_be_unique_and_nonempty(self):
        self.dataset["actions"][0]["operator_assignments"] = []
        with self.assertRaisesRegex(cloud.ControlCloudError, "must be non-empty"):
            self.build()
        self.dataset = json.loads(DATASET.read_text(encoding="utf-8"))
        self.dataset["actions"][0]["operator_assignments"].append(
            copy.deepcopy(self.dataset["actions"][0]["operator_assignments"][0])
        )
        with self.assertRaisesRegex(cloud.ControlCloudError, "duplicate operator_id"):
            self.build()

    def test_floating_point_json_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "float.json"
            path.write_text('{"price": 1.5}', encoding="utf-8")
            with self.assertRaisesRegex(cloud.ControlCloudError, "floating-point"):
                cloud.load_json(path)

    def test_output_paths_must_remain_inside_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            with mock.patch.dict(os.environ, {"GITHUB_WORKSPACE": str(workspace)}, clear=True):
                with self.assertRaisesRegex(cloud.ControlCloudError, "inside the workspace"):
                    cloud.workspace_path(str(workspace.parent / "escape.json"), "output")

    def test_audit_export_has_one_canonical_line_per_action(self):
        snapshot = self.build()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            cloud.write_audit_export(path, snapshot)
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), snapshot["action_count"])
            events = [json.loads(line) for line in lines]
            self.assertTrue(all(event["snapshot_root"] == snapshot["snapshot_root"] for event in events))
            self.assertEqual(
                [event["action"]["action_id"] for event in events],
                [action["action_id"] for action in snapshot["actions"]],
            )


if __name__ == "__main__":
    unittest.main()
