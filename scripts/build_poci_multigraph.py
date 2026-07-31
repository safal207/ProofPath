#!/usr/bin/env python3
"""Build and verify a PoCI multi-graph transition space from exported adapter JSON."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PROFILE = "proofpath.poci.multigraph.v0.1"
SOURCE_PROFILE = "proofpath.poci.multigraph.source.v0.1"
POCI_PROFILE = "proofpath.poci.v0.1"
POCI_DOMAIN = b"proofpath:poci:v0.1:envelope\n"
ROOT_DOMAIN = b"proofpath:poci:multigraph:v0.1:root\n"
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
DECISION_RANK = {"ACCEPT": 0, "HOLD": 1, "BLOCK": 2, "CHALLENGE": 3}
EXIT_CODE = {"ACCEPT": 0, "HOLD": 2, "BLOCK": 3, "CHALLENGE": 4}
PRIORITY = {
    "MULTIGRAPH_SOURCE_INVALID": 10,
    "ADAPTER_SET_INCOMPLETE": 20,
    "ADAPTER_VERSION_UNPINNED": 30,
    "ADAPTER_TIP_INVALID": 100,
    "ADAPTER_CML_INVALID": 110,
    "ADAPTER_CML_MISSING_PARENT": 120,
    "ADAPTER_TTRACE_INVALID": 130,
    "ADAPTER_TTRACE_TIME_ORDER": 140,
    "ADAPTER_LIMINALDB_INVALID": 150,
    "ADAPTER_LIMINALDB_ROLLBACK": 160,
    "ADAPTER_IBEX_INVALID": 170,
    "CROSS_GRAPH_CAUSE_MISMATCH": 200,
    "CROSS_GRAPH_ACTOR_MISMATCH": 210,
    "CROSS_GRAPH_TRANSITION_MISMATCH": 220,
    "CROSS_GRAPH_DESTINATION_MISMATCH": 230,
    "CROSS_GRAPH_EVIDENCE_MISMATCH": 240,
    "CROSS_GRAPH_CONTINUITY_MISMATCH": 250,
    "GRAPH_NODE_DUPLICATE": 300,
    "GRAPH_EDGE_DANGLING": 310,
    "TRANSITION_CELL_UNBOUND": 320,
    "MULTIGRAPH_ROOT_MISMATCH": 400,
    "MULTIGRAPH_INTERNAL_FAIL_CLOSED": 999,
}
REQUIRED_ADAPTERS = {"tip", "cml", "ttrace", "liminaldb", "ibex"}


class DuplicateKeyError(ValueError):
    """Raised when JSON contains duplicate object keys."""


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise DuplicateKeyError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs)
    except (OSError, json.JSONDecodeError, DuplicateKeyError) as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object in {path}")
    return value


def _contains_float(value: Any) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, dict):
        return any(_contains_float(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_float(item) for item in value)
    return False


def canonical_json_bytes(value: Any) -> bytes:
    if _contains_float(value):
        raise ValueError("floating-point values are forbidden in canonical graph evidence")
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _digest(domain: bytes, value: Any) -> str:
    return "sha256:" + hashlib.sha256(domain + canonical_json_bytes(value)).hexdigest()


def compute_poci_root(envelope: dict[str, Any]) -> str:
    normalized = copy.deepcopy(envelope)
    normalized.setdefault("evidence_integrity", {})["envelope_root"] = None
    return _digest(POCI_DOMAIN, normalized)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: dict[str, Any], key: str) -> str | None:
    item = value.get(key)
    return item if isinstance(item, str) and item else None


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)
        return datetime.fromisoformat(value).astimezone(timezone.utc)
    except ValueError:
        return None


def _node(node_id: str, kind: str, **attrs: Any) -> dict[str, Any]:
    return {"id": node_id, "kind": kind, "attrs": attrs}


def _edge(source: str, target: str, relation: str, **attrs: Any) -> dict[str, Any]:
    return {"from": source, "to": target, "relation": relation, "attrs": attrs}


class MultiGraphBuilder:
    def __init__(self, source: dict[str, Any], source_path: Path):
        self.source = source
        self.source_path = source_path
        self.findings: list[dict[str, str]] = []
        self._seen_findings: set[tuple[str, str]] = set()
        self.envelope: dict[str, Any] = {}
        self.graphs: dict[str, dict[str, Any]] = {}
        self.cells: list[dict[str, Any]] = []

    def add(self, code: str, decision: str, path: str, message: str) -> None:
        key = (code, path)
        if key in self._seen_findings:
            return
        self._seen_findings.add(key)
        self.findings.append(
            {"code": code, "decision": decision, "path": path, "message": message}
        )

    def build(self) -> dict[str, Any]:
        try:
            self._validate_source()
            self._load_poci()
            self._validate_tip()
            self._validate_cml()
            self._validate_ttrace()
            self._validate_liminaldb()
            self._validate_ibex()
            self._validate_cross_graph()
            self._build_graphs()
            self._build_cells()
            self._validate_graph_structure()
            return self._output()
        except (KeyError, TypeError, ValueError, OSError) as exc:
            self.add(
                "MULTIGRAPH_INTERNAL_FAIL_CLOSED",
                "BLOCK",
                "$",
                str(exc),
            )
            return self._output()

    def _validate_source(self) -> None:
        if self.source.get("profile_id") != SOURCE_PROFILE:
            self.add(
                "MULTIGRAPH_SOURCE_INVALID",
                "BLOCK",
                "$.profile_id",
                "unsupported multi-graph source profile",
            )
        if not _text(self.source, "graph_set_id"):
            self.add(
                "MULTIGRAPH_SOURCE_INVALID",
                "BLOCK",
                "$.graph_set_id",
                "graph_set_id is required",
            )
        if _contains_float(self.source):
            self.add(
                "MULTIGRAPH_SOURCE_INVALID",
                "BLOCK",
                "$",
                "floating-point values are forbidden; encode confidence as integer basis points or strings",
            )

        adapters = [item for item in _list(self.source.get("adapters")) if isinstance(item, dict)]
        adapter_ids = [_text(item, "adapter_id") for item in adapters]
        actual = {item for item in adapter_ids if item}
        if actual != REQUIRED_ADAPTERS:
            self.add(
                "ADAPTER_SET_INCOMPLETE",
                "BLOCK",
                "$.adapters",
                f"expected adapters {sorted(REQUIRED_ADAPTERS)}, got {sorted(actual)}",
            )
        if len(adapter_ids) != len(set(adapter_ids)):
            self.add(
                "MULTIGRAPH_SOURCE_INVALID",
                "BLOCK",
                "$.adapters",
                "adapter identifiers must be unique",
            )
        for index, adapter in enumerate(adapters):
            for key in ("repository", "protocol", "version", "mode"):
                if not _text(adapter, key):
                    self.add(
                        "ADAPTER_VERSION_UNPINNED",
                        "BLOCK",
                        f"$.adapters[{index}].{key}",
                        "adapter repository, protocol, version, and mode must be explicit",
                    )

    def _load_poci(self) -> None:
        raw_path = _text(self.source, "poci_envelope_path")
        if not raw_path:
            self.add(
                "MULTIGRAPH_SOURCE_INVALID",
                "BLOCK",
                "$.poci_envelope_path",
                "PoCI envelope path is required",
            )
            return
        envelope_path = (self.source_path.parent / raw_path).resolve()
        self.envelope = load_json(envelope_path)
        if _dict(self.envelope.get("protocol")).get("profile_id") != POCI_PROFILE:
            self.add(
                "MULTIGRAPH_SOURCE_INVALID",
                "BLOCK",
                "$.poci_envelope_path",
                "referenced envelope is not PoCI v0.1",
            )

    def _validate_tip(self) -> None:
        tip = _dict(self.source.get("tip"))
        required = ("id", "status", "state", "tension", "cause", "transition", "cooperation", "action")
        if any(key not in tip for key in required):
            self.add("ADAPTER_TIP_INVALID", "BLOCK", "$.tip", "TIP record is incomplete")
            return
        if tip.get("status") not in {"committed", "reviewed"}:
            self.add(
                "ADAPTER_TIP_INVALID",
                "HOLD",
                "$.tip.status",
                "transition reasoning is not committed or reviewed",
            )
        transition = _dict(tip.get("transition"))
        if not _text(transition, "from") or not _text(transition, "to"):
            self.add(
                "ADAPTER_TIP_INVALID",
                "BLOCK",
                "$.tip.transition",
                "TIP transition requires from and to states",
            )
        cause = _dict(tip.get("cause"))
        if not _text(cause, "parent_cause"):
            self.add(
                "ADAPTER_TIP_INVALID",
                "HOLD",
                "$.tip.cause.parent_cause",
                "TIP cause is not bound to an upstream causal parent",
            )

    def _validate_cml(self) -> None:
        records = [item for item in _list(_dict(self.source.get("cml")).get("records")) if isinstance(item, dict)]
        if not records:
            self.add("ADAPTER_CML_INVALID", "BLOCK", "$.cml.records", "CML record set is empty")
            return
        ids = [_text(record, "id") for record in records]
        if any(item is None for item in ids) or len(ids) != len(set(ids)):
            self.add(
                "ADAPTER_CML_INVALID",
                "BLOCK",
                "$.cml.records",
                "CML record ids must be present and unique",
            )
        seen: set[str] = set()
        previous_time: int | None = None
        for index, record in enumerate(records):
            record_id = _text(record, "id")
            timestamp = record.get("timestamp")
            if not isinstance(timestamp, int):
                self.add(
                    "ADAPTER_CML_INVALID",
                    "BLOCK",
                    f"$.cml.records[{index}].timestamp",
                    "CML timestamp must be an integer",
                )
            elif previous_time is not None and timestamp < previous_time:
                self.add(
                    "ADAPTER_CML_INVALID",
                    "BLOCK",
                    f"$.cml.records[{index}].timestamp",
                    "CML timestamps must be monotonic",
                )
            if isinstance(timestamp, int):
                previous_time = timestamp
            parent = record.get("parent_cause")
            if parent is not None and parent not in seen:
                self.add(
                    "ADAPTER_CML_MISSING_PARENT",
                    "BLOCK",
                    f"$.cml.records[{index}].parent_cause",
                    f"parent cause {parent!r} is absent or appears after the child",
                )
            if record_id:
                seen.add(record_id)

        parent_by_id = {
            _text(record, "id"): record.get("parent_cause")
            for record in records
            if _text(record, "id")
        }
        observed_record = next(
            (record for record in reversed(records) if record.get("action") == "observe"),
            records[-1],
        )
        target = _text(observed_record, "id")
        expected_root = _dict(self.envelope.get("causal_context")).get("parent_id")
        cursor: str | None = target
        visited: set[str] = set()
        while cursor and cursor not in visited:
            visited.add(cursor)
            cursor = parent_by_id.get(cursor)
        has_missing_parent = any(
            finding["code"] == "ADAPTER_CML_MISSING_PARENT"
            for finding in self.findings
        )
        if expected_root and expected_root not in visited and not has_missing_parent:
            self.add(
                "CROSS_GRAPH_CAUSE_MISMATCH",
                "CHALLENGE",
                "$.cml.records",
                "observed result does not descend from the PoCI causal parent",
            )

    def _validate_ttrace(self) -> None:
        records = [item for item in _list(_dict(self.source.get("ttrace")).get("records")) if isinstance(item, dict)]
        if not records:
            self.add("ADAPTER_TTRACE_INVALID", "BLOCK", "$.ttrace.records", "T-Trace is empty")
            return
        ids = [_text(record, "id") for record in records]
        if any(item is None for item in ids) or len(ids) != len(set(ids)):
            self.add(
                "ADAPTER_TTRACE_INVALID",
                "BLOCK",
                "$.ttrace.records",
                "T-Trace ids must be present and unique",
            )
        threads = {_text(record, "thread_id") for record in records}
        if None in threads or len(threads) != 1:
            self.add(
                "ADAPTER_TTRACE_INVALID",
                "BLOCK",
                "$.ttrace.records",
                "mock adapter requires one explicit thread_id",
            )
        allowed = {"sense", "transition", "commit"}
        previous: datetime | None = None
        seen_types: list[str] = []
        for index, record in enumerate(records):
            kind = _text(record, "type")
            if kind not in allowed:
                self.add(
                    "ADAPTER_TTRACE_INVALID",
                    "BLOCK",
                    f"$.ttrace.records[{index}].type",
                    "unsupported T-Trace record type",
                )
            else:
                seen_types.append(kind)
            stamp = _timestamp(record.get("ts"))
            if stamp is None:
                self.add(
                    "ADAPTER_TTRACE_INVALID",
                    "BLOCK",
                    f"$.ttrace.records[{index}].ts",
                    "T-Trace timestamp must be ISO-8601",
                )
            elif previous is not None and stamp < previous:
                self.add(
                    "ADAPTER_TTRACE_TIME_ORDER",
                    "BLOCK",
                    f"$.ttrace.records[{index}].ts",
                    "T-Trace timestamps regress",
                )
            if stamp is not None:
                previous = stamp
        if seen_types != ["sense", "transition", "commit"]:
            self.add(
                "ADAPTER_TTRACE_INVALID",
                "BLOCK",
                "$.ttrace.records",
                "expected acknowledged sense -> transition -> commit sequence",
            )

    def _validate_liminaldb(self) -> None:
        receipt = _dict(self.source.get("liminaldb"))
        required = (
            "authorization_ref",
            "observation_ref",
            "response_integrity",
            "causal_audit_ref",
            "continuity_decision",
            "checkpoint_id",
            "checkpoint_digest",
            "sequence",
        )
        if any(key not in receipt for key in required):
            self.add(
                "ADAPTER_LIMINALDB_INVALID",
                "BLOCK",
                "$.liminaldb",
                "continuity receipt is incomplete",
            )
            return
        digest = receipt.get("checkpoint_digest")
        if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
            self.add(
                "ADAPTER_LIMINALDB_INVALID",
                "BLOCK",
                "$.liminaldb.checkpoint_digest",
                "checkpoint digest is malformed",
            )
        sequence = receipt.get("sequence")
        if not isinstance(sequence, int):
            self.add(
                "ADAPTER_LIMINALDB_INVALID",
                "BLOCK",
                "$.liminaldb.sequence",
                "checkpoint sequence must be an integer",
            )
        elif sequence < 1:
            self.add(
                "ADAPTER_LIMINALDB_ROLLBACK",
                "CHALLENGE",
                "$.liminaldb.sequence",
                "checkpoint sequence indicates rollback",
            )
        elif sequence > 1 and not receipt.get("previous_checkpoint_digest"):
            self.add(
                "ADAPTER_LIMINALDB_ROLLBACK",
                "CHALLENGE",
                "$.liminaldb.previous_checkpoint_digest",
                "non-genesis checkpoint lacks ancestry",
            )
        if receipt.get("response_integrity") != "verified":
            self.add(
                "ADAPTER_LIMINALDB_INVALID",
                "HOLD",
                "$.liminaldb.response_integrity",
                "response integrity is not verified",
            )
        if receipt.get("continuity_decision") not in {"stop", "continue", "retry", "revalidate"}:
            self.add(
                "ADAPTER_LIMINALDB_INVALID",
                "BLOCK",
                "$.liminaldb.continuity_decision",
                "unsupported continuity decision",
            )
        elif receipt.get("continuity_decision") == "revalidate":
            self.add(
                "CROSS_GRAPH_CONTINUITY_MISMATCH",
                "HOLD",
                "$.liminaldb.continuity_decision",
                "continuity layer requires revalidation",
            )

    def _validate_ibex(self) -> None:
        ibex = _dict(self.source.get("ibex"))
        if ibex.get("schema_version") != 1:
            self.add(
                "ADAPTER_IBEX_INVALID",
                "BLOCK",
                "$.ibex.schema_version",
                "unsupported transition-phase schema",
            )
        time = _dict(ibex.get("time"))
        ordered_keys = (
            "observed_before_ns",
            "intent_declared_ns",
            "commit_ns",
            "action_started_ns",
            "result_observed_ns",
            "evaluated_ns",
        )
        values = [time.get(key) for key in ordered_keys]
        if any(not isinstance(value, int) for value in values):
            self.add(
                "ADAPTER_IBEX_INVALID",
                "BLOCK",
                "$.ibex.time",
                "transition-phase timestamps must be integers",
            )
        elif values != sorted(values) or len(set(values)) != len(values):
            self.add(
                "ADAPTER_IBEX_INVALID",
                "CHALLENGE",
                "$.ibex.time",
                "transition-phase chronology is not strictly increasing",
            )
        deadline = time.get("deadline_ns")
        if isinstance(deadline, int) and isinstance(values[-1], int) and deadline < values[-1]:
            self.add(
                "ADAPTER_IBEX_INVALID",
                "BLOCK",
                "$.ibex.time.deadline_ns",
                "evaluation occurred after the declared deadline",
            )
        verification = _dict(ibex.get("verification"))
        for key in ("result_matches_expectation", "destination_observed", "stopping_condition_met"):
            if verification.get(key) is not True:
                self.add(
                    "ADAPTER_IBEX_INVALID",
                    "HOLD",
                    f"$.ibex.verification.{key}",
                    "transition phase is not fully verified",
                )

    def _validate_cross_graph(self) -> None:
        if not self.envelope:
            return
        intent = _dict(self.envelope.get("intent"))
        authority = _dict(self.envelope.get("authority"))
        causal = _dict(self.envelope.get("causal_context"))
        proposal = _dict(self.envelope.get("proposal"))
        observed = _dict(self.envelope.get("observed_result"))
        tip = _dict(self.source.get("tip"))
        tip_cause = _dict(tip.get("cause"))
        tip_transition = _dict(tip.get("transition"))
        tip_action = _dict(tip.get("action"))
        ibex = _dict(self.source.get("ibex"))
        ibex_intention = _dict(ibex.get("intention"))
        ibex_space = _dict(ibex.get("space"))
        ibex_evidence = _dict(ibex.get("evidence"))
        ttrace = [item for item in _list(_dict(self.source.get("ttrace")).get("records")) if isinstance(item, dict)]
        transition_record = next((item for item in ttrace if item.get("type") == "transition"), {})
        commit_record = next((item for item in ttrace if item.get("type") == "commit"), {})
        liminal = _dict(self.source.get("liminaldb"))

        if tip_cause.get("parent_cause") != causal.get("parent_id"):
            self.add(
                "CROSS_GRAPH_CAUSE_MISMATCH",
                "CHALLENGE",
                "$.tip.cause.parent_cause",
                "TIP cause does not match the PoCI causal parent",
            )
        if transition_record.get("cause_id") != causal.get("parent_id"):
            self.add(
                "CROSS_GRAPH_CAUSE_MISMATCH",
                "CHALLENGE",
                "$.ttrace.records",
                "T-Trace transition is bound to a different cause",
            )

        actors = set(_list(_dict(tip.get("state")).get("actors")))
        expected_actors = {
            intent.get("principal_id"),
            proposal.get("agent_id"),
            authority.get("executor_id"),
            observed.get("observer_id"),
        }
        if not expected_actors.issubset(actors):
            self.add(
                "CROSS_GRAPH_ACTOR_MISMATCH",
                "BLOCK",
                "$.tip.state.actors",
                "TIP actor set does not cover PoCI principal, agent, executor, and observer",
            )
        if tip_action.get("owner") != proposal.get("agent_id"):
            self.add(
                "CROSS_GRAPH_ACTOR_MISMATCH",
                "BLOCK",
                "$.tip.action.owner",
                "TIP action owner differs from PoCI proposal agent",
            )

        if ibex_intention.get("intent_id") != intent.get("intent_id"):
            self.add(
                "CROSS_GRAPH_TRANSITION_MISMATCH",
                "CHALLENGE",
                "$.ibex.intention.intent_id",
                "Ibex transition intent differs from PoCI intent",
            )
        if ibex.get("transition_id") != transition_record.get("id"):
            self.add(
                "CROSS_GRAPH_TRANSITION_MISMATCH",
                "CHALLENGE",
                "$.ibex.transition_id",
                "Ibex transition id differs from T-Trace transition id",
            )
        if (
            tip_transition.get("from") != ibex_space.get("origin")
            or transition_record.get("from") != ibex_space.get("origin")
        ):
            self.add(
                "CROSS_GRAPH_TRANSITION_MISMATCH",
                "CHALLENGE",
                "$.ibex.space.origin",
                "origin state differs across TIP, T-Trace, and Ibex",
            )
        if (
            tip_transition.get("to") != ibex_space.get("destination")
            or commit_record.get("state") != ibex_space.get("destination")
        ):
            self.add(
                "CROSS_GRAPH_DESTINATION_MISMATCH",
                "CHALLENGE",
                "$.ibex.space.destination",
                "destination state differs across TIP, T-Trace, and Ibex",
            )

        artifact_ids = {
            item.get("artifact_id")
            for item in _list(_dict(self.envelope.get("evidence_integrity")).get("artifacts"))
            if isinstance(item, dict)
        }
        required_refs = {
            _dict(intent.get("signature_ref")).get("artifact_id"),
            _dict(_dict(self.envelope.get("execution")).get("receipt_ref")).get("artifact_id"),
            _dict(observed.get("result_ref")).get("artifact_id"),
            _dict(_list(self.envelope.get("witnesses"))[0].get("statement_ref")).get("artifact_id")
            if _list(self.envelope.get("witnesses"))
            else None,
        }
        ibex_refs = {
            ibex_evidence.get("intent_ref"),
            ibex_evidence.get("action_ref"),
            ibex_evidence.get("result_ref"),
            ibex_evidence.get("verification_ref"),
        }
        if required_refs != ibex_refs or not ibex_refs.issubset(artifact_ids):
            self.add(
                "CROSS_GRAPH_EVIDENCE_MISMATCH",
                "CHALLENGE",
                "$.ibex.evidence",
                "Ibex evidence roles do not match PoCI committed artifacts",
            )
        if commit_record.get("result_ref") != _dict(observed.get("result_ref")).get("artifact_id"):
            self.add(
                "CROSS_GRAPH_EVIDENCE_MISMATCH",
                "CHALLENGE",
                "$.ttrace.records",
                "T-Trace commit result differs from PoCI observed result",
            )

        expected_refs = (
            intent.get("intent_id"),
            _dict(observed.get("result_ref")).get("artifact_id"),
            causal.get("parent_id"),
        )
        actual_refs = (
            liminal.get("authorization_ref"),
            liminal.get("observation_ref"),
            liminal.get("causal_audit_ref"),
        )
        if expected_refs != actual_refs:
            self.add(
                "CROSS_GRAPH_CONTINUITY_MISMATCH",
                "CHALLENGE",
                "$.liminaldb",
                "LiminalDB receipt is not bound to the same authorization, observation, and cause",
            )
        if observed.get("status") == "observed" and liminal.get("continuity_decision") != "stop":
            self.add(
                "CROSS_GRAPH_CONTINUITY_MISMATCH",
                "HOLD",
                "$.liminaldb.continuity_decision",
                "observed terminal result should stop this one-shot action",
            )

    def _add_graph(self, name: str, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
        nodes = sorted(nodes, key=lambda item: item["id"])
        edges = sorted(edges, key=lambda item: (item["from"], item["to"], item["relation"]))
        payload = {"nodes": nodes, "edges": edges}
        self.graphs[name] = {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": nodes,
            "edges": edges,
            "root": _digest(f"proofpath:poci:multigraph:v0.1:{name}\n".encode(), payload),
        }

    def _build_graphs(self) -> None:
        if not self.envelope:
            return
        intent = _dict(self.envelope.get("intent"))
        authority = _dict(self.envelope.get("authority"))
        causal = _dict(self.envelope.get("causal_context"))
        proposal = _dict(self.envelope.get("proposal"))
        execution = _dict(self.envelope.get("execution"))
        observed = _dict(self.envelope.get("observed_result"))
        receipt_id = _dict(execution.get("receipt_ref")).get("artifact_id")
        witness = _dict(_list(self.envelope.get("witnesses"))[0]) if _list(self.envelope.get("witnesses")) else {}
        verification = _dict(self.envelope.get("verification"))
        tip = _dict(self.source.get("tip"))
        tip_transition = _dict(tip.get("transition"))
        tip_tension = _dict(tip.get("tension"))
        cml_records = [item for item in _list(_dict(self.source.get("cml")).get("records")) if isinstance(item, dict)]
        ttrace = [item for item in _list(_dict(self.source.get("ttrace")).get("records")) if isinstance(item, dict)]
        liminal = _dict(self.source.get("liminaldb"))
        ibex = _dict(self.source.get("ibex"))

        causal_nodes = [
            _node(f"tip:tension:{tip.get('id')}", "tension", summary=tip_tension.get("summary"), severity=tip_tension.get("severity")),
            _node(f"tip:cause:{tip.get('id')}", "interpreted_cause", summary=_dict(tip.get("cause")).get("summary")),
        ]
        causal_edges = [
            _edge(f"tip:tension:{tip.get('id')}", f"tip:cause:{tip.get('id')}", "motivates"),
            _edge(f"cml:{causal.get('parent_id')}", f"tip:cause:{tip.get('id')}", "supports"),
        ]
        for record in cml_records:
            record_id = record.get("id")
            causal_nodes.append(
                _node(
                    f"cml:{record_id}",
                    "causal_record",
                    action=record.get("action"),
                    actor=_dict(record.get("actor")).get("id"),
                    permitted_by=record.get("permitted_by"),
                    record_class=record.get("class"),
                )
            )
            if record.get("parent_cause"):
                causal_edges.append(
                    _edge(
                        f"cml:{record.get('parent_cause')}",
                        f"cml:{record_id}",
                        "causes",
                    )
                )
        self._add_graph("causal", causal_nodes, causal_edges)

        intent_nodes = [
            _node(f"principal:{intent.get('principal_id')}", "principal"),
            _node(f"intent:{intent.get('intent_id')}", "intent", action_kind=intent.get("action_kind"), statement=intent.get("statement")),
            _node(f"proposal:{proposal.get('proposal_id')}", "proposal", action_kind=proposal.get("action_kind")),
            _node(f"tip:action:{tip.get('id')}", "justified_action", summary=_dict(tip.get("action")).get("summary")),
            _node(f"result:{_dict(observed.get('result_ref')).get('artifact_id')}", "observed_result", result_kind=observed.get("result_kind")),
        ]
        intent_edges = [
            _edge(f"principal:{intent.get('principal_id')}", f"intent:{intent.get('intent_id')}", "declares"),
            _edge(f"intent:{intent.get('intent_id')}", f"proposal:{proposal.get('proposal_id')}", "refines_into"),
            _edge(f"proposal:{proposal.get('proposal_id')}", f"tip:action:{tip.get('id')}", "justifies"),
            _edge(f"tip:action:{tip.get('id')}", f"result:{_dict(observed.get('result_ref')).get('artifact_id')}", "expects"),
        ]
        self._add_graph("intent", intent_nodes, intent_edges)

        authority_nodes = [
            _node(f"principal:{authority.get('principal_id')}", "principal"),
            _node(f"decision:{causal.get('parent_id')}", "authorizing_decision"),
            _node(f"grant:{authority.get('grant_id')}", "grant", scope=authority.get("scope"), reversibility=authority.get("reversibility")),
            _node(f"agent:{authority.get('agent_id')}", "agent"),
            _node(f"executor:{authority.get('executor_id')}", "executor"),
        ]
        authority_edges = [
            _edge(f"principal:{authority.get('principal_id')}", f"decision:{causal.get('parent_id')}", "owns"),
            _edge(f"decision:{causal.get('parent_id')}", f"grant:{authority.get('grant_id')}", "authorizes"),
            _edge(f"grant:{authority.get('grant_id')}", f"agent:{authority.get('agent_id')}", "delegates_to"),
            _edge(f"grant:{authority.get('grant_id')}", f"executor:{authority.get('executor_id')}", "permits_execution_by"),
        ]
        self._add_graph("authority", authority_nodes, authority_edges)

        transition_record = next((item for item in ttrace if item.get("type") == "transition"), {})
        commit_record = next((item for item in ttrace if item.get("type") == "commit"), {})
        running_state = transition_record.get("to")
        transition_nodes = [
            _node(f"state:{tip_transition.get('from')}", "state", phase="origin"),
            _node(f"transition:{transition_record.get('id')}", "transition", trigger=tip_transition.get("trigger")),
            _node(f"state:{running_state}", "state", phase="crossed"),
            _node(f"execution:{receipt_id}", "execution", status=execution.get("status"), proposal_id=execution.get("proposal_id")),
            _node(f"state:{tip_transition.get('to')}", "state", phase="destination"),
            _node(f"commit:{commit_record.get('id')}", "acknowledged_commit"),
        ]
        transition_edges = [
            _edge(f"state:{tip_transition.get('from')}", f"transition:{transition_record.get('id')}", "leaves"),
            _edge(f"transition:{transition_record.get('id')}", f"state:{running_state}", "enters"),
            _edge(f"state:{running_state}", f"execution:{receipt_id}", "executes_within"),
            _edge(f"execution:{receipt_id}", f"state:{tip_transition.get('to')}", "produces"),
            _edge(f"state:{tip_transition.get('to')}", f"commit:{commit_record.get('id')}", "acknowledged_by"),
        ]
        self._add_graph("state_transition", transition_nodes, transition_edges)

        artifacts = [
            item
            for item in _list(_dict(self.envelope.get("evidence_integrity")).get("artifacts"))
            if isinstance(item, dict)
        ]
        evidence_nodes = [
            _node(f"envelope:{self.envelope.get('envelope_id')}", "action_proof_envelope"),
            _node(f"checkpoint:{liminal.get('checkpoint_id')}", "durable_checkpoint", digest=liminal.get("checkpoint_digest")),
            _node(f"verification:{verification.get('verifier_id')}", "verification", decision=verification.get("decision")),
        ]
        evidence_edges = []
        for artifact in artifacts:
            artifact_id = artifact.get("artifact_id")
            evidence_nodes.append(
                _node(
                    f"artifact:{artifact_id}",
                    "artifact",
                    role=artifact.get("role"),
                    digest=artifact.get("digest"),
                )
            )
            evidence_edges.append(
                _edge(f"artifact:{artifact_id}", f"envelope:{self.envelope.get('envelope_id')}", "committed_by")
            )
        evidence_edges.extend(
            [
                _edge(f"envelope:{self.envelope.get('envelope_id')}", f"verification:{verification.get('verifier_id')}", "evaluated_by"),
                _edge(f"verification:{verification.get('verifier_id')}", f"checkpoint:{liminal.get('checkpoint_id')}", "durably_anchored_as"),
                _edge(f"artifact:{witness.get('statement_ref', {}).get('artifact_id')}", f"verification:{verification.get('verifier_id')}", "supports"),
            ]
        )
        self._add_graph("evidence", evidence_nodes, evidence_edges)

        ibex_time = _dict(ibex.get("time"))
        monotonic_keys = (
            "observed_before_ns",
            "intent_declared_ns",
            "commit_ns",
            "action_started_ns",
            "result_observed_ns",
            "evaluated_ns",
        )
        time_nodes = [
            _node(f"time:ibex:{key}", "monotonic_event", value_ns=ibex_time.get(key))
            for key in monotonic_keys
        ]
        time_edges = [
            _edge(f"time:ibex:{left}", f"time:ibex:{right}", "before")
            for left, right in zip(monotonic_keys, monotonic_keys[1:])
        ]
        rfc_events = [
            ("proposal", proposal.get("proposed_at")),
            ("execution_started", execution.get("started_at")),
            ("execution_completed", execution.get("completed_at")),
            ("result_observed", observed.get("observed_at")),
            ("witness_evaluated", witness.get("evaluated_at")),
            ("verified", verification.get("verified_at")),
        ]
        time_nodes.extend(
            _node(f"time:rfc3339:{name}", "wall_clock_event", timestamp=value)
            for name, value in rfc_events
        )
        time_edges.extend(
            _edge(f"time:rfc3339:{left[0]}", f"time:rfc3339:{right[0]}", "before")
            for left, right in zip(rfc_events, rfc_events[1:])
        )
        time_nodes.append(
            _node(
                f"continuity:{liminal.get('checkpoint_id')}",
                "continuity_decision",
                decision=liminal.get("continuity_decision"),
                sequence=liminal.get("sequence"),
            )
        )
        time_edges.append(
            _edge(
                "time:rfc3339:verified",
                f"continuity:{liminal.get('checkpoint_id')}",
                "closes_with",
            )
        )
        self._add_graph("time_continuity", time_nodes, time_edges)

    def _build_cells(self) -> None:
        if not self.envelope:
            return
        proposal = _dict(self.envelope.get("proposal"))
        execution = _dict(self.envelope.get("execution"))
        observed = _dict(self.envelope.get("observed_result"))
        causal = _dict(self.envelope.get("causal_context"))
        authority = _dict(self.envelope.get("authority"))
        tip = _dict(self.source.get("tip"))
        ttrace = [item for item in _list(_dict(self.source.get("ttrace")).get("records")) if isinstance(item, dict)]
        transition_record = next((item for item in ttrace if item.get("type") == "transition"), {})
        liminal = _dict(self.source.get("liminaldb"))
        verification = _dict(self.envelope.get("verification"))
        cml_records = [
            item
            for item in _list(_dict(self.source.get("cml")).get("records"))
            if isinstance(item, dict)
        ]
        cml_execution_id = _text(
            next((record for record in cml_records if record.get("action") == "execute"), {}),
            "id",
        )
        cml_observation_id = _text(
            next((record for record in cml_records if record.get("action") == "observe"), {}),
            "id",
        )
        receipt_id = _dict(execution.get("receipt_ref")).get("artifact_id")

        self.cells = [
            {
                "cell_id": "cell:proposal",
                "phase": "proposal",
                "coordinates": {
                    "causal": f"cml:{causal.get('parent_id')}",
                    "intent": f"proposal:{proposal.get('proposal_id')}",
                    "authority": f"grant:{authority.get('grant_id')}",
                    "state_transition": f"transition:{transition_record.get('id')}",
                    "evidence": f"artifact:{_dict(_dict(self.envelope.get('intent')).get('signature_ref')).get('artifact_id')}",
                    "time_continuity": "time:rfc3339:proposal",
                },
            },
            {
                "cell_id": "cell:execution",
                "phase": "execution",
                "coordinates": {
                    "causal": f"cml:{cml_execution_id}",
                    "intent": f"tip:action:{tip.get('id')}",
                    "authority": f"executor:{authority.get('executor_id')}",
                    "state_transition": f"execution:{receipt_id}",
                    "evidence": f"artifact:{_dict(execution.get('receipt_ref')).get('artifact_id')}",
                    "time_continuity": "time:rfc3339:execution_completed",
                },
            },
            {
                "cell_id": "cell:observation",
                "phase": "observation",
                "coordinates": {
                    "causal": f"cml:{cml_observation_id}",
                    "intent": f"result:{_dict(observed.get('result_ref')).get('artifact_id')}",
                    "authority": f"principal:{authority.get('principal_id')}",
                    "state_transition": f"state:{_dict(tip.get('transition')).get('to')}",
                    "evidence": f"verification:{verification.get('verifier_id')}",
                    "time_continuity": f"continuity:{liminal.get('checkpoint_id')}",
                },
            },
        ]

    def _validate_graph_structure(self) -> None:
        for graph_name, graph in self.graphs.items():
            ids = [node["id"] for node in graph["nodes"]]
            if len(ids) != len(set(ids)):
                self.add(
                    "GRAPH_NODE_DUPLICATE",
                    "BLOCK",
                    f"$.graphs.{graph_name}.nodes",
                    "graph node ids must be unique",
                )
            known = set(ids)
            for index, edge in enumerate(graph["edges"]):
                if edge["from"] not in known or edge["to"] not in known:
                    self.add(
                        "GRAPH_EDGE_DANGLING",
                        "BLOCK",
                        f"$.graphs.{graph_name}.edges[{index}]",
                        f"dangling edge {edge['from']} -> {edge['to']}",
                    )

        for cell_index, cell in enumerate(self.cells):
            for graph_name, node_id in _dict(cell.get("coordinates")).items():
                graph = self.graphs.get(graph_name)
                known = {node["id"] for node in graph["nodes"]} if graph else set()
                if node_id not in known:
                    self.add(
                        "TRANSITION_CELL_UNBOUND",
                        "BLOCK",
                        f"$.transition_cells[{cell_index}].coordinates.{graph_name}",
                        f"cell coordinate {node_id!r} is absent from graph {graph_name}",
                    )

    def _output(self) -> dict[str, Any]:
        findings = sorted(
            self.findings,
            key=lambda item: (
                -DECISION_RANK[item["decision"]],
                PRIORITY.get(item["code"], 500),
                item["code"],
                item["path"],
            ),
        )
        primary = findings[0] if findings else None
        decision = primary["decision"] if primary else "ACCEPT"
        source_bindings = sorted(
            [item for item in _list(self.source.get("adapters")) if isinstance(item, dict)],
            key=lambda item: str(item.get("adapter_id")),
        )
        root_payload = {
            "profile_id": PROFILE,
            "graph_set_id": self.source.get("graph_set_id"),
            "poci_envelope_id": self.envelope.get("envelope_id") if self.envelope else None,
            "computed_poci_envelope_root": compute_poci_root(self.envelope) if self.envelope else None,
            "source_bindings": source_bindings,
            "graphs": {name: graph for name, graph in sorted(self.graphs.items())},
            "transition_cells": self.cells,
        }
        try:
            computed_root = _digest(ROOT_DOMAIN, root_payload)
        except ValueError as exc:
            self.add("MULTIGRAPH_INTERNAL_FAIL_CLOSED", "BLOCK", "$", str(exc))
            computed_root = None

        declared_root = self.source.get("declared_multigraph_root")
        if isinstance(declared_root, str) and computed_root != declared_root:
            self.add(
                "MULTIGRAPH_ROOT_MISMATCH",
                "CHALLENGE",
                "$.declared_multigraph_root",
                "declared multi-graph root differs from computed root",
            )
            findings = sorted(
                self.findings,
                key=lambda item: (
                    -DECISION_RANK[item["decision"]],
                    PRIORITY.get(item["code"], 500),
                    item["code"],
                    item["path"],
                ),
            )
            primary = findings[0] if findings else None
            decision = primary["decision"] if primary else "ACCEPT"

        return {
            "profile_id": PROFILE,
            "graph_set_id": self.source.get("graph_set_id"),
            "decision": decision,
            "primary_reason_code": primary["code"] if primary else None,
            "reason_codes": sorted({item["code"] for item in findings}),
            "findings": findings,
            "source_bindings": source_bindings,
            "poci_envelope_id": self.envelope.get("envelope_id") if self.envelope else None,
            "computed_poci_envelope_root": compute_poci_root(self.envelope) if self.envelope else None,
            "graphs": {name: graph for name, graph in sorted(self.graphs.items())},
            "transition_cells": self.cells,
            "invariants": {
                "required_graphs": [
                    "causal",
                    "intent",
                    "authority",
                    "state_transition",
                    "evidence",
                    "time_continuity",
                ],
                "cell_path": ["proposal", "execution", "observation"],
                "no_hidden_runtime_coupling": True,
                "external_inputs_are_exported_json": True,
            },
            "computed_multigraph_root": computed_root,
            "declared_multigraph_root": declared_root,
            "valid": decision == "ACCEPT",
        }


def build_multigraph(source: dict[str, Any], source_path: Path) -> dict[str, Any]:
    return MultiGraphBuilder(source, source_path).build()


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build and verify a PoCI multi-graph transition space"
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--allow-non-accept", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        source_path = args.source.resolve()
        result = build_multigraph(load_json(source_path), source_path)
        code = EXIT_CODE[result["decision"]]
    except (OSError, ValueError, TypeError, KeyError) as exc:
        result = {
            "profile_id": PROFILE,
            "decision": "BLOCK",
            "primary_reason_code": "MULTIGRAPH_INTERNAL_FAIL_CLOSED",
            "reason_codes": ["MULTIGRAPH_INTERNAL_FAIL_CLOSED"],
            "findings": [
                {
                    "code": "MULTIGRAPH_INTERNAL_FAIL_CLOSED",
                    "decision": "BLOCK",
                    "path": "$",
                    "message": str(exc),
                }
            ],
            "valid": False,
        }
        code = 1

    text = (
        json.dumps(result, indent=2, ensure_ascii=False)
        if args.pretty
        else json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    ) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    if args.allow_non_accept:
        return 0
    return code


if __name__ == "__main__":
    raise SystemExit(main())
