#!/usr/bin/env python3
"""Validate causal-temporal transition traces for one immutable subject hash."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def recompute_event_id(event: dict[str, Any]) -> str:
    preimage = {key: value for key, value in event.items() if key != "event_id"}
    return "sha256:" + hashlib.sha256(canonical_bytes(preimage)).hexdigest()


def parse_time(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def get_dotted(value: dict[str, Any], path: str) -> Any:
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(path)
        current = current[part]
    return current


def initial_state(graph: dict[str, Any]) -> dict[str, str]:
    return {name: spec["initial"] for name, spec in graph["axes"].items()}


def validate_graph(graph: dict[str, Any]) -> None:
    axes = graph["axes"]
    for axis, spec in axes.items():
        states = spec["states"]
        if len(states) != len(set(states)):
            raise ValueError(f"duplicate state on axis {axis}")
        if spec["initial"] not in states:
            raise ValueError(f"initial state missing on axis {axis}")

    event_types: set[str] = set()
    for transition in graph["transitions"]:
        event_type = transition["event_type"]
        if event_type in event_types:
            raise ValueError(f"duplicate event_type: {event_type}")
        event_types.add(event_type)
        axis = transition["axis"]
        if axis not in axes:
            raise ValueError(f"unknown axis: {axis}")
        allowed = set(axes[axis]["states"])
        if not set(transition["from"]).issubset(allowed):
            raise ValueError(f"unknown from-state in {event_type}")
        if transition["to"] not in allowed:
            raise ValueError(f"unknown to-state in {event_type}")


def fail(code: str, seq: int | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"ok": False, "error": code}
    if seq is not None:
        result["seq"] = seq
    return result


def verify_trace(graph: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    transitions = {item["event_type"]: item for item in graph["transitions"]}
    axes = graph["axes"]
    expected_axes = set(axes)
    current = initial_state(graph)
    previous_id: str | None = None
    previous_time: datetime | None = None
    subject_hash = case["subject_hash"]

    if not HASH_RE.fullmatch(subject_hash):
        return fail("INVALID_SUBJECT_HASH")

    events = case["events"]
    for index, event in enumerate(events):
        seq = event.get("seq")
        if seq != index:
            return fail("SEQUENCE_GAP_OR_DUPLICATE", index)

        if event.get("parent_event_id") != previous_id:
            return fail("PARENT_EVENT_MISMATCH", index)

        if event.get("subject_hash") != subject_hash:
            return fail("SUBJECT_HASH_DRIFT", index)

        event_id = event.get("event_id")
        if not isinstance(event_id, str) or event_id != recompute_event_id(event):
            return fail("EVENT_ID_MISMATCH", index)

        try:
            observed_at = parse_time(event["observed_at"])
        except (KeyError, TypeError, ValueError):
            return fail("INVALID_OBSERVED_AT", index)
        if previous_time is not None and observed_at < previous_time:
            return fail("OBSERVED_AT_REGRESSION", index)

        before = event.get("state_before")
        after = event.get("state_after")
        if not isinstance(before, dict) or not isinstance(after, dict):
            return fail("INVALID_STATE_VECTOR", index)
        if set(before) != expected_axes or set(after) != expected_axes:
            return fail("STATE_VECTOR_AXES_MISMATCH", index)
        for axis, spec in axes.items():
            if before[axis] not in spec["states"] or after[axis] not in spec["states"]:
                return fail("UNKNOWN_STATE", index)

        if before != current:
            return fail("STATE_BEFORE_MISMATCH", index)

        transition = transitions.get(event.get("event_type"))
        if transition is None:
            return fail("UNDECLARED_TRANSITION", index)

        axis = transition["axis"]
        if before[axis] not in transition["from"] or after[axis] != transition["to"]:
            return fail("ILLEGAL_AXIS_TRANSITION", index)

        for untouched_axis in expected_axes - {axis}:
            if before[untouched_axis] != after[untouched_axis]:
                return fail("UNDECLARED_AXIS_MUTATION", index)

        if transition.get("evidence_required") and not event.get("evidence_ref"):
            return fail("MISSING_TRANSITION_EVIDENCE", index)

        for required_path in transition.get("required_fields", []):
            try:
                required_value = get_dotted(event, required_path)
            except KeyError:
                return fail("MISSING_REQUIRED_TRANSITION_FIELD", index)
            if required_value in (None, ""):
                return fail("MISSING_REQUIRED_TRANSITION_FIELD", index)

        current = after
        previous_id = event_id
        previous_time = observed_at

    return {
        "ok": True,
        "error": None,
        "final_state": current,
        "terminal_event_id": previous_id,
        "event_count": len(events),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("graph", type=Path)
    parser.add_argument("vectors", type=Path)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    vectors = json.loads(args.vectors.read_text(encoding="utf-8"))
    validate_graph(graph)

    failures = 0
    for case in vectors["cases"]:
        actual = verify_trace(graph, case)
        expected = case["expected"]
        projection = {key: actual.get(key) for key in expected}
        if projection != expected:
            failures += 1
            print(f"FAIL {case['name']}")
            print("  expected:", json.dumps(expected, sort_keys=True))
            print("  actual:  ", json.dumps(projection, sort_keys=True))
        else:
            outcome = "PASS" if actual["ok"] else actual["error"]
            print(f"PASS {case['name']} -> {outcome}")

    if failures:
        print(f"\nCausal-temporal graph conformance failed: {failures}")
        return 1

    print(f"\nCausal-temporal graph conformance passed: {len(vectors['cases'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
