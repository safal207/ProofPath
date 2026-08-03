#!/usr/bin/env python3
"""Summarize a Gonka live-pilot receipt without exposing prompts or reasoning."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROUTING_INSUFFICIENT_EXECUTIONS = "INSUFFICIENT_SUCCESSFUL_EXECUTIONS"
ROUTING_MISSING_IDS = "MISSING_PROVIDER_REQUEST_IDS"
ROUTING_DUPLICATE_IDS = "DUPLICATE_PROVIDER_REQUEST_IDS"
ROUTING_DISTINCT_IDS = "DISTINCT_PROVIDER_REQUEST_IDS_NOT_INDEPENDENCE_PROOF"


def classify_routing_evidence(
    executions: list[dict[str, Any]],
    successful_replicas: int,
) -> tuple[str, list[str]]:
    """Classify request-ID evidence without claiming routing independence."""

    request_ids = [
        str(item["provider_request_id"]).strip()
        for item in executions
        if item.get("status") == "SUCCESS"
        and isinstance(item.get("provider_request_id"), str)
        and str(item["provider_request_id"]).strip()
    ]
    unique_ids = sorted(set(request_ids))

    if successful_replicas < 2:
        return ROUTING_INSUFFICIENT_EXECUTIONS, unique_ids
    if len(request_ids) < successful_replicas:
        return ROUTING_MISSING_IDS, unique_ids
    if len(unique_ids) < len(request_ids):
        return ROUTING_DUPLICATE_IDS, unique_ids
    return ROUTING_DISTINCT_IDS, unique_ids


def summarize_receipt(payload: dict[str, Any], receipt_path: Path) -> dict[str, Any]:
    receipt = payload.get("receipt")
    if not isinstance(receipt, dict):
        raise ValueError("payload has no receipt object")

    executions_raw = receipt.get("executions", [])
    if not isinstance(executions_raw, list):
        raise ValueError("receipt executions must be a list")
    executions = [item for item in executions_raw if isinstance(item, dict)]

    requested = _as_int(receipt.get("requested_replicas"), "requested_replicas")
    successful = _as_int(receipt.get("successful_replicas"), "successful_replicas")
    routing_status, unique_request_ids = classify_routing_evidence(
        executions,
        successful,
    )

    request_ids = [
        item.get("provider_request_id")
        for item in executions
        if item.get("status") == "SUCCESS" and item.get("provider_request_id")
    ]
    markup = [
        item.get("reasoning_markup", "none")
        for item in executions
        if item.get("status") == "SUCCESS"
    ]
    origins = sorted(
        {
            item.get("endpoint_origin")
            for item in executions
            if item.get("endpoint_origin")
        }
    )

    return {
        "claim_id": receipt.get("claim_id"),
        "verdict": receipt.get("verdict"),
        "requested_replicas": requested,
        "successful_replicas": successful,
        "agreement_score": receipt.get("agreement_score"),
        "provider_request_ids": request_ids,
        "unique_provider_request_ids": unique_request_ids,
        "unique_provider_request_id_count": len(unique_request_ids),
        "routing_evidence": routing_status,
        "independent_routing_proven": False,
        "reasoning_markup": markup,
        "endpoint_origins": origins,
        "receipt_hash": receipt.get("receipt_hash"),
        "receipt_path": str(receipt_path),
    }


def validation_exit_code(summary: dict[str, Any]) -> int:
    if summary["successful_replicas"] != summary["requested_replicas"]:
        return 3
    if summary["verdict"] != "CONSENSUS":
        return 4
    if summary["routing_evidence"] == ROUTING_DUPLICATE_IDS:
        return 5
    if summary["routing_evidence"] == ROUTING_MISSING_IDS:
        return 6
    if summary["routing_evidence"] == ROUTING_INSUFFICIENT_EXECUTIONS:
        return 7
    return 0


def _as_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"receipt {field} must be an integer")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print a secret-free summary of a Gonka pilot receipt"
    )
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()

    try:
        with args.receipt.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        summary = summarize_receipt(payload, args.receipt)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL {exc}", flush=True)
        return 2

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    code = validation_exit_code(summary)
    if code == 5:
        print(
            "FAIL duplicate provider_request_id values: output consensus is real, "
            "but independent routing was not observed.",
            flush=True,
        )
    elif code == 6:
        print(
            "FAIL one or more successful executions have no provider_request_id; "
            "routing evidence is incomplete.",
            flush=True,
        )
    elif code == 7:
        print(
            "FAIL fewer than two successful executions; routing evidence is insufficient.",
            flush=True,
        )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
