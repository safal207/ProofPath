from __future__ import annotations

import copy
import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "build_poci_multigraph.py"
SPEC = importlib.util.spec_from_file_location("build_poci_multigraph", MODULE_PATH)
assert SPEC and SPEC.loader
multigraph = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(multigraph)

SOURCE_PATH = ROOT / "examples" / "poci-witness" / "multigraph" / "source.valid.json"
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def source() -> dict:
    return json.loads(SOURCE_PATH.read_text(encoding="utf-8"))


def build(value: dict) -> dict:
    return multigraph.build_multigraph(value, SOURCE_PATH)


def reverse_objects(value):
    if isinstance(value, dict):
        return {key: reverse_objects(item) for key, item in reversed(list(value.items()))}
    if isinstance(value, list):
        return [reverse_objects(item) for item in value]
    return value


class PociMultiGraphTests(unittest.TestCase):
    def test_valid_source_builds_six_graph_product_space(self):
        result = build(source())

        self.assertEqual(result["decision"], "ACCEPT")
        self.assertTrue(result["valid"])
        self.assertEqual(
            set(result["graphs"]),
            {
                "causal",
                "intent",
                "authority",
                "state_transition",
                "evidence",
                "time_continuity",
            },
        )
        self.assertEqual(
            [cell["phase"] for cell in result["transition_cells"]],
            ["proposal", "execution", "observation"],
        )
        self.assertRegex(result["computed_poci_envelope_root"], DIGEST)
        self.assertRegex(result["computed_multigraph_root"], DIGEST)
        for graph in result["graphs"].values():
            self.assertRegex(graph["root"], DIGEST)
            self.assertEqual(graph["node_count"], len(graph["nodes"]))
            self.assertEqual(graph["edge_count"], len(graph["edges"]))

    def test_root_is_invariant_to_json_key_order(self):
        left = build(source())
        right = build(reverse_objects(source()))

        self.assertEqual(left["computed_multigraph_root"], right["computed_multigraph_root"])
        self.assertEqual(
            {name: graph["root"] for name, graph in left["graphs"].items()},
            {name: graph["root"] for name, graph in right["graphs"].items()},
        )

    def test_destination_mismatch_is_challenged(self):
        value = source()
        value["ibex"]["space"]["destination"] = "compute.result.unverified"

        result = build(value)

        self.assertEqual(result["decision"], "CHALLENGE")
        self.assertEqual(result["primary_reason_code"], "CROSS_GRAPH_DESTINATION_MISMATCH")

    def test_missing_cml_parent_blocks(self):
        value = source()
        value["cml"]["records"][3]["parent_cause"] = "proposal_missing"

        result = build(value)

        self.assertEqual(result["decision"], "BLOCK")
        self.assertEqual(result["primary_reason_code"], "ADAPTER_CML_MISSING_PARENT")

    def test_ttrace_time_regression_blocks(self):
        value = source()
        value["ttrace"]["records"][2]["ts"] = "2026-07-31T00:04:00Z"

        result = build(value)

        self.assertEqual(result["decision"], "BLOCK")
        self.assertEqual(result["primary_reason_code"], "ADAPTER_TTRACE_TIME_ORDER")

    def test_liminaldb_rollback_is_challenged(self):
        value = source()
        value["liminaldb"]["sequence"] = 0

        result = build(value)

        self.assertEqual(result["decision"], "CHALLENGE")
        self.assertEqual(result["primary_reason_code"], "ADAPTER_LIMINALDB_ROLLBACK")

    def test_ibex_evidence_substitution_is_challenged(self):
        value = source()
        value["ibex"]["evidence"]["result_ref"] = "result_substituted"

        result = build(value)

        self.assertEqual(result["decision"], "CHALLENGE")
        self.assertEqual(result["primary_reason_code"], "CROSS_GRAPH_EVIDENCE_MISMATCH")

    def test_actor_mismatch_blocks(self):
        value = source()
        value["tip"]["action"]["owner"] = "agent_other"

        result = build(value)

        self.assertEqual(result["decision"], "BLOCK")
        self.assertEqual(result["primary_reason_code"], "CROSS_GRAPH_ACTOR_MISMATCH")

    def test_revalidation_requirement_holds(self):
        value = source()
        value["liminaldb"]["continuity_decision"] = "revalidate"

        result = build(value)

        self.assertEqual(result["decision"], "HOLD")
        self.assertEqual(result["primary_reason_code"], "CROSS_GRAPH_CONTINUITY_MISMATCH")

    def test_declared_root_mismatch_is_challenged(self):
        value = source()
        value["declared_multigraph_root"] = "sha256:" + "0" * 64

        result = build(value)

        self.assertEqual(result["decision"], "CHALLENGE")
        self.assertEqual(result["primary_reason_code"], "MULTIGRAPH_ROOT_MISMATCH")

    def test_every_transition_cell_coordinate_resolves(self):
        result = build(source())

        for cell in result["transition_cells"]:
            for graph_name, node_id in cell["coordinates"].items():
                nodes = {node["id"] for node in result["graphs"][graph_name]["nodes"]}
                self.assertIn(node_id, nodes)


if __name__ == "__main__":
    unittest.main()
