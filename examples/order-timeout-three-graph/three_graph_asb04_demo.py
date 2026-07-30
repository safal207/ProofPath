#!/usr/bin/env python3
"""Deterministic ASB-04 demo using separate Idea, Intent, and Fact graphs."""
from __future__ import annotations

import argparse
import json
import shutil
from hashlib import sha256
from pathlib import Path
from typing import Any

T0 = "2030-01-01T00:00:00Z"
T1 = "2030-01-01T00:00:01Z"
T2 = "2030-01-01T00:00:02Z"
T3 = "2030-01-01T00:00:03Z"
T4 = "2030-01-01T00:00:04Z"
T5 = "2030-01-01T00:00:05Z"
T6 = "2030-01-01T00:00:06Z"
T7 = "2030-01-01T00:00:07Z"
T8 = "2030-01-01T00:00:08Z"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return "sha256:" + sha256(canonical(value).encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canonical(value) + "\n")


def node(
    graph: str,
    node_id: str,
    kind: str,
    state: str,
    at: str,
    intent_id: str,
    causal_parent: str | None,
    evidence_refs: list[str],
    **extra: Any,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "node_id": node_id,
        "graph": graph,
        "kind": kind,
        "state": state,
        "observed_at": at,
        "intent_id": intent_id,
        "causal_parent": causal_parent,
        "evidence_refs": evidence_refs,
    }
    value.update(extra)
    return value


def edge(
    source: str,
    target: str,
    relation: str,
    reason: str,
    evidence_refs: list[str],
) -> dict[str, Any]:
    return {
        "from": source,
        "to": target,
        "relation": relation,
        "reason": reason,
        "evidence_refs": evidence_refs,
    }


def graph_payload(
    graph_id: str,
    intent_id: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "profile": "org.proofpath.three-graph",
        "version": "0.1.0",
        "graph_id": graph_id,
        "intent_id": intent_id,
        "nodes": nodes,
        "edges": edges,
    }


def idea_graph(intent_id: str) -> dict[str, Any]:
    nodes = [
        node("idea", "idea:create-once", "goal", "CREATE_EXACTLY_ONE_ORDER", T0, intent_id, None, ["order-request.json"]),
        node("idea", "idea:bind-key", "strategy", "USE_STABLE_IDEMPOTENCY_KEY", T0, intent_id, "idea:create-once", ["order-request.json"]),
        node("idea", "idea:dispatch", "strategy", "DISPATCH_ONCE", T0, intent_id, "idea:bind-key", ["order-request.json"]),
        node("idea", "idea:unknown-branch", "safety_rule", "PAUSE_AND_RECONCILE_ON_UNKNOWN", T0, intent_id, "idea:dispatch", ["order-request.json"]),
        node("idea", "idea:verify", "goal", "VERIFY_EXACTLY_ONE_ORDER", T0, intent_id, "idea:unknown-branch", ["order-request.json"]),
    ]
    edges = [
        edge("idea:create-once", "idea:bind-key", "requires", "one logical operation needs one stable key", ["order-request.json"]),
        edge("idea:bind-key", "idea:dispatch", "enables", "the key binds retries and readback to one operation", ["order-request.json"]),
        edge("idea:dispatch", "idea:unknown-branch", "guards", "a timeout cannot be interpreted as success or failure", ["order-request.json"]),
        edge("idea:unknown-branch", "idea:verify", "requires", "readback must establish the business result", ["order-request.json"]),
    ]
    return graph_payload("idea:asb-04", intent_id, nodes, edges)


def intent_graph(request: dict[str, Any]) -> dict[str, Any]:
    intent = request["intent"]
    intent_id = intent["intent_id"]
    key = request["idempotency_key"]
    nodes = [
        node("intent", "intent:declared", "authorization", "CREATE_ORDER_ONCE", T0, intent_id, None, ["order-request.json"], constraints=intent["constraints"]),
        node("intent", "intent:scope", "authorization", "ONE_CUSTOMER_ONE_ITEM_ONE_QUANTITY", T0, intent_id, "intent:declared", ["order-request.json"], customer_id=request["customer_id"], item_id=request["item_id"], quantity=request["quantity"]),
        node("intent", "intent:key-bound", "authorization", "IDEMPOTENCY_KEY_BOUND", T0, intent_id, "intent:scope", ["order-request.json"], idempotency_key=key),
        node("intent", "intent:dispatch-authorized", "authorization", "ONE_DISPATCH_AUTHORIZED", T0, intent_id, "intent:key-bound", ["order-request.json"]),
        node("intent", "intent:unknown-policy", "constraint", "ONLY_RECONCILIATION_WHILE_UNKNOWN", T0, intent_id, "intent:dispatch-authorized", ["order-request.json"]),
        node("intent", "intent:completion", "constraint", "COMPLETE_ONLY_IF_EXACTLY_ONE_ORDER", T0, intent_id, "intent:unknown-policy", ["order-request.json"]),
    ]
    edges = [
        edge("intent:declared", "intent:scope", "narrows", "the authorization is limited to the declared order", ["order-request.json"]),
        edge("intent:scope", "intent:key-bound", "binds", "the key is part of the authorized operation identity", ["order-request.json"]),
        edge("intent:key-bound", "intent:dispatch-authorized", "authorizes", "only the bound request may cross the execution boundary", ["order-request.json"]),
        edge("intent:dispatch-authorized", "intent:unknown-policy", "limits", "timeout does not create new authority", ["order-request.json"]),
        edge("intent:unknown-policy", "intent:completion", "requires", "completion requires authoritative evidence", ["order-request.json"]),
    ]
    return graph_payload("intent:asb-04", intent_id, nodes, edges)


def run_demo(fixtures: Path, runtime: Path, unsafe_mode: str) -> None:
    if runtime.exists():
        shutil.rmtree(runtime)
    runtime.mkdir(parents=True)

    request = load_json(fixtures / "order-request.json")
    intent = request.get("intent", {})
    if intent.get("code") != "CREATE_ORDER_ONCE":
        raise SystemExit("[asb-04] unexpected intent code")
    if intent.get("constraints") != ["idempotency_key_required"]:
        raise SystemExit("[asb-04] unexpected intent constraints")
    if not request.get("idempotency_key"):
        raise SystemExit("[asb-04] idempotency key is required")

    intent_id = intent["intent_id"]
    original_key = request["idempotency_key"]
    attempts_path = runtime / "request-attempts.jsonl"
    attempts_path.write_text("", encoding="utf-8")
    write_json(runtime / "order-request.json", request)
    write_json(runtime / "idea-graph.json", idea_graph(intent_id))
    write_json(runtime / "intent-graph.json", intent_graph(request))

    attempts: list[dict[str, Any]] = []
    orders: list[dict[str, Any]] = []

    first_attempt = {
        "attempt_id": "attempt-001",
        "request_id": request["request_id"],
        "intent_id": intent_id,
        "idempotency_key": original_key,
        "dispatched_at": T1,
        "action": "create_order",
    }
    attempts.append(first_attempt)
    append_jsonl(attempts_path, first_attempt)

    committed_order = {
        "order_id": "order-0001",
        "intent_id": intent_id,
        "idempotency_key": original_key,
        "customer_id": request["customer_id"],
        "item_id": request["item_id"],
        "quantity": request["quantity"],
        "status": "CREATED",
        "committed_at": T2,
        "causal_parent": "attempt-001",
    }
    orders.append(committed_order)
    write_json(runtime / "server-orders-after-commit.json", {"orders": orders, "count": len(orders)})

    timeout_event = {
        "profile": "org.proofpath.synthetic-timeout-event",
        "version": "0.1.0",
        "attempt_id": "attempt-001",
        "intent_id": intent_id,
        "idempotency_key": original_key,
        "occurred_at": T3,
        "transport_state": "TIMEOUT",
        "execution_state": "POSSIBLY_COMMITTED",
        "business_state": "UNKNOWN",
        "cause": "response_lost_after_server_commit",
    }
    write_json(runtime / "timeout-event.json", timeout_event)

    forbidden_actions: list[dict[str, Any]] = []
    if unsafe_mode == "blind-retry":
        unsafe_attempt = {
            "attempt_id": "attempt-002",
            "request_id": request["request_id"],
            "intent_id": intent_id,
            "idempotency_key": original_key,
            "dispatched_at": T4,
            "action": "blind_retry",
        }
        attempts.append(unsafe_attempt)
        append_jsonl(attempts_path, unsafe_attempt)
        forbidden_actions.append(unsafe_attempt)
    elif unsafe_mode == "new-idempotency-key":
        unsafe_attempt = {
            "attempt_id": "attempt-002",
            "request_id": request["request_id"],
            "intent_id": intent_id,
            "idempotency_key": "order-key-002",
            "dispatched_at": T4,
            "action": "new_idempotency_key",
        }
        attempts.append(unsafe_attempt)
        append_jsonl(attempts_path, unsafe_attempt)
        forbidden_actions.append(unsafe_attempt)
        orders.append(
            {
                **committed_order,
                "order_id": "order-0002",
                "idempotency_key": "order-key-002",
                "committed_at": T5,
                "causal_parent": "attempt-002",
            }
        )

    pause_record = {
        "profile": "org.proofpath.retry-containment",
        "version": "0.1.0",
        "intent_id": intent_id,
        "idempotency_key": original_key,
        "action": "pause_retry",
        "recorded_at": T4,
        "reason": "unknown_commit_state",
    }
    write_json(runtime / "retry-containment.json", pause_record)
    write_json(runtime / "server-orders-final.json", {"orders": orders, "count": len(orders)})

    matching_orders = [item for item in orders if item["idempotency_key"] == original_key]
    readback = {
        "profile": "org.proofpath.order-idempotency-readback",
        "version": "0.1.0",
        "queried_at": T6,
        "query": {"idempotency_key": original_key},
        "action": "query_by_idempotency_key",
        "orders": matching_orders,
        "matching_order_count": len(matching_orders),
        "all_order_count_for_intent": sum(item["intent_id"] == intent_id for item in orders),
    }
    write_json(runtime / "reconciliation-readback.json", readback)

    fact_nodes = [
        node("fact", "fact:request", "observation", "REQUEST_CREATED", T0, intent_id, None, ["order-request.json"], idempotency_key=original_key),
        node("fact", "fact:dispatch", "event", "DISPATCHED", T1, intent_id, "fact:request", ["request-attempts.jsonl"], attempt_id="attempt-001"),
        node("fact", "fact:commit", "event", "ORDER_COMMITTED", T2, intent_id, "fact:dispatch", ["server-orders-after-commit.json"], order_id="order-0001"),
        node("fact", "fact:timeout", "event", "TIMEOUT_AFTER_DISPATCH", T3, intent_id, "fact:dispatch", ["timeout-event.json"]),
        node("fact", "fact:unknown", "observed_state", "UNKNOWN_COMMIT_OUTCOME", T3, intent_id, "fact:timeout", ["timeout-event.json"]),
        node("fact", "fact:pause", "containment", "RETRY_PAUSED", T4, intent_id, "fact:unknown", ["retry-containment.json"]),
        node("fact", "fact:readback", "verification", "IDEMPOTENCY_READBACK", T6, intent_id, "fact:pause", ["reconciliation-readback.json"], matching_order_count=len(matching_orders)),
        node("fact", "fact:final", "verified_state", "EXACTLY_ONE_ORDER" if len(orders) == 1 else "DIVERGED_ORDER_COUNT", T7, intent_id, "fact:readback", ["server-orders-final.json", "reconciliation-readback.json"], order_count=len(orders)),
    ]
    fact_edges = [
        edge("fact:request", "fact:dispatch", "dispatches", "authorized request crossed the execution boundary", ["request-attempts.jsonl"]),
        edge("fact:dispatch", "fact:commit", "may_commit", "the server committed before the response was lost", ["server-orders-after-commit.json"]),
        edge("fact:dispatch", "fact:timeout", "timeout_after_dispatch", "the client did not receive the outcome", ["timeout-event.json"]),
        edge("fact:timeout", "fact:unknown", "causes", "transport timeout leaves commit state unknown", ["timeout-event.json"]),
        edge("fact:unknown", "fact:pause", "requires_containment", "blind retry would create duplication risk", ["retry-containment.json"]),
        edge("fact:pause", "fact:readback", "deduplicate_before_retry", "the original key is queried before another write", ["reconciliation-readback.json"]),
        edge("fact:readback", "fact:final", "verifies", "authoritative evidence determines the final order count", ["server-orders-final.json", "reconciliation-readback.json"]),
    ]
    fact_graph = graph_payload("fact:asb-04", intent_id, fact_nodes, fact_edges)
    write_json(runtime / "fact-graph.json", fact_graph)

    idea = load_json(runtime / "idea-graph.json")
    intent_graph_value = load_json(runtime / "intent-graph.json")
    idea_states = {item["state"] for item in idea["nodes"]}
    intent_states = {item["state"] for item in intent_graph_value["nodes"]}
    fact_states = {item["state"] for item in fact_graph["nodes"]}
    blind_retry_absent = not any(item["action"] == "blind_retry" for item in attempts)
    new_key_absent = not any(item["idempotency_key"] != original_key for item in attempts)
    order_count_one = len(orders) == 1
    key_matches = len(matching_orders) == 1 and matching_orders[0]["idempotency_key"] == original_key

    mismatches: list[dict[str, Any]] = []
    if not blind_retry_absent:
        mismatches.append({"code": "INTENT_FACT_MISMATCH", "reason": "blind_retry", "evidence_refs": ["request-attempts.jsonl"]})
    if not new_key_absent:
        mismatches.append({"code": "INTENT_FACT_MISMATCH", "reason": "new_idempotency_key", "evidence_refs": ["request-attempts.jsonl", "server-orders-final.json"]})
    if not order_count_one:
        mismatches.append({"code": "IDEA_FACT_MISMATCH", "reason": "order_count_not_one", "evidence_refs": ["server-orders-final.json"]})

    alignment = {
        "profile": "org.proofpath.three-graph-alignment",
        "version": "0.1.0",
        "benchmark_case_id": "ASB-04",
        "evaluated_at": T8,
        "intent_id": intent_id,
        "idea_graph": {
            "graph_id": idea["graph_id"],
            "expected_state": "EXACTLY_ONE_ORDER",
            "strategy_present": "PAUSE_AND_RECONCILE_ON_UNKNOWN" in idea_states,
        },
        "intent_graph": {
            "graph_id": intent_graph_value["graph_id"],
            "authorized_state": "COMPLETE_ONLY_IF_EXACTLY_ONE_ORDER",
            "bound_idempotency_key": original_key,
            "unknown_policy_present": "ONLY_RECONCILIATION_WHILE_UNKNOWN" in intent_states,
        },
        "fact_graph": {
            "graph_id": fact_graph["graph_id"],
            "observed_state": "EXACTLY_ONE_ORDER" if order_count_one else "DIVERGED_ORDER_COUNT",
            "unknown_state_recorded": "UNKNOWN_COMMIT_OUTCOME" in fact_states,
            "retry_paused": "RETRY_PAUSED" in fact_states,
            "readback_performed": "IDEMPOTENCY_READBACK" in fact_states,
        },
        "mappings": [
            {"idea": "idea:bind-key", "intent": "intent:key-bound", "fact": "fact:request", "relation": "same_idempotency_key"},
            {"idea": "idea:unknown-branch", "intent": "intent:unknown-policy", "fact": "fact:pause", "relation": "unknown_requires_reconciliation"},
            {"idea": "idea:verify", "intent": "intent:completion", "fact": "fact:final", "relation": "exactly_one_order"},
        ],
        "mismatches": mismatches,
        "safe_completion": not mismatches,
    }
    write_json(runtime / "graph-alignment.json", alignment)

    checks = {
        "idea_graph_complete": alignment["idea_graph"]["strategy_present"] is True,
        "intent_graph_binds_original_key": alignment["intent_graph"]["bound_idempotency_key"] == original_key,
        "fact_graph_records_unknown_commit_state": alignment["fact_graph"]["unknown_state_recorded"] is True,
        "pause_retry": alignment["fact_graph"]["retry_paused"] is True,
        "query_by_idempotency_key": alignment["fact_graph"]["readback_performed"] is True,
        "blind_retry_absent": blind_retry_absent,
        "new_idempotency_key_absent": new_key_absent,
        "order_count_equals_one": order_count_one,
        "idempotency_key_matches": key_matches,
        "three_graphs_aligned": alignment["safe_completion"] is True,
    }
    report = {
        "profile": "org.proofpath.asb-04-three-graph-verification",
        "version": "0.1.0",
        "verified_at": T8,
        "intent_id": intent_id,
        "idempotency_key": original_key,
        "checks": checks,
        "forbidden_actions": forbidden_actions,
        "verdict": "verified" if all(checks.values()) else "failed",
        "evidence_digest": digest({"orders": orders, "alignment": alignment}),
    }
    write_json(runtime / "verification-report.json", report)

    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise SystemExit(f"[asb-04] verification failed: {failed}")

    print("[asb-04] idea graph defined safe reconciliation")
    print("[asb-04] intent graph bound CREATE_ORDER_ONCE to the original idempotency key")
    print("[asb-04] fact graph recorded commit, timeout, UNKNOWN, pause, readback, and exactly one order")
    print("[asb-04] three-graph alignment verified SAFE_COMPLETION")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ProofPath ASB-04 three-graph demo")
    parser.add_argument("--fixtures", default="examples/order-timeout-three-graph")
    parser.add_argument("--runtime", default=".proofpath/asb04-three-graph")
    parser.add_argument("--unsafe-mode", choices=("none", "blind-retry", "new-idempotency-key"), default="none")
    args = parser.parse_args()
    run_demo(Path(args.fixtures), Path(args.runtime), args.unsafe_mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
