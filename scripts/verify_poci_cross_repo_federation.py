#!/usr/bin/env python3
"""Verify a two-domain ProofPath PoCI cross-repository federation."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

POLICY_PROFILE = "proofpath.poci.cross-repo-federation-policy.v0.1"
PROFILE = "proofpath.poci.cross-repo-federation.v0.1"
PRODUCER_PROFILE = "proofpath.poci.multigraph.witness-quorum.v0.1"
CONSUMER_PROFILE = "ibex.poci.external-consumer-receipt.v0.1"
RECEIPT_DOMAIN = b"ibex:poci:external-consumer:v0.1:receipt\n"
FEDERATION_DOMAIN = b"proofpath:poci:cross-repo-federation:v0.1:root\n"
ATTESTATION_DOMAIN = b"proofpath:poci:cross-repo-federation:v0.1:attestation-result\n"
REQUIRED_GRAPHS = (
    "causal",
    "intent",
    "authority",
    "state_transition",
    "evidence",
    "time_continuity",
)
DECISION_RANK = {"ACCEPT": 0, "BLOCK": 1, "CHALLENGE": 2}
EXIT_CODE = {"ACCEPT": 0, "BLOCK": 3, "CHALLENGE": 4}


class DuplicateKeyError(ValueError):
    """Raised when JSON repeats an object key."""


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise DuplicateKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_value(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs)
    except (OSError, json.JSONDecodeError, DuplicateKeyError) as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc


def load_object(path: Path) -> dict[str, Any]:
    value = load_value(path)
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
        raise ValueError("floating-point values are forbidden")
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _digest(domain: bytes, value: Any) -> str:
    return "sha256:" + hashlib.sha256(domain + canonical_json_bytes(value)).hexdigest()


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def compute_consumer_receipt_root(receipt: dict[str, Any]) -> str:
    normalized = copy.deepcopy(receipt)
    normalized["receipt_root"] = None
    return _digest(RECEIPT_DOMAIN, normalized)


def compute_federation_root(report: dict[str, Any]) -> str:
    normalized = copy.deepcopy(report)
    normalized["federation_root"] = None
    return _digest(FEDERATION_DOMAIN, normalized)


def _finding(code: str, decision: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "decision": decision, "path": path, "message": message}


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _attestation_digest(value: Any | None) -> str | None:
    if value is None:
        return None
    return _digest(ATTESTATION_DOMAIN, value)


def verify_federation(
    policy: dict[str, Any],
    producer_report: dict[str, Any],
    consumer_receipt: dict[str, Any],
    *,
    producer_report_digest: str,
    consumer_receipt_digest: str,
    producer_attestation_result: Any | None,
    consumer_attestation_result: Any | None,
) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    producer_policy = _object(policy.get("producer"))
    consumer_policy = _object(policy.get("external_consumer"))
    expected = _object(policy.get("expected"))

    def add(code: str, decision: str, path: str, message: str) -> None:
        findings.append(_finding(code, decision, path, message))

    if policy.get("profile_id") != POLICY_PROFILE:
        add("FEDERATION_POLICY_INVALID", "BLOCK", "$.profile_id", "unsupported policy")

    required_policy_fields = (
        "repository",
        "workflow",
        "attestation_source_sha",
        "attestation_signer_sha",
    )
    for namespace, value in (
        ("producer", producer_policy),
        ("external_consumer", consumer_policy),
    ):
        for key in required_policy_fields:
            if not isinstance(value.get(key), str) or not value.get(key):
                add(
                    "FEDERATION_POLICY_INVALID",
                    "BLOCK",
                    f"$.{namespace}.{key}",
                    "repository, workflow, source SHA, and signer SHA must be pinned",
                )

    expected_roots = expected.get("graph_roots")
    if not isinstance(expected_roots, dict) or set(expected_roots) != set(REQUIRED_GRAPHS):
        add(
            "FEDERATION_POLICY_INVALID",
            "BLOCK",
            "$.expected.graph_roots",
            "exactly six graph roots must be pinned",
        )
        expected_roots = {}

    if expected.get("required_domain_count") != 2:
        add(
            "FEDERATION_POLICY_INVALID",
            "BLOCK",
            "$.expected.required_domain_count",
            "v0.1 requires exactly two repository domains",
        )
    if expected.get("external_consumer_required") is not True:
        add(
            "FEDERATION_POLICY_INVALID",
            "BLOCK",
            "$.expected.external_consumer_required",
            "an external consumer domain is mandatory",
        )
    if producer_policy.get("repository") == consumer_policy.get("repository"):
        add(
            "FEDERATION_DOMAIN_NOT_DISTINCT",
            "BLOCK",
            "$.external_consumer.repository",
            "producer and consumer repositories must differ",
        )
    if producer_policy.get("workflow") == consumer_policy.get("workflow"):
        add(
            "FEDERATION_DOMAIN_NOT_DISTINCT",
            "BLOCK",
            "$.external_consumer.workflow",
            "producer and consumer workflows must differ",
        )

    if producer_report_digest != producer_policy.get("report_sha256"):
        add(
            "FEDERATION_PRODUCER_SUBJECT_MISMATCH",
            "CHALLENGE",
            "$.producer.report_sha256",
            "producer report bytes differ from the pinned attested subject",
        )
    if consumer_receipt_digest != consumer_policy.get("receipt_sha256"):
        add(
            "FEDERATION_CONSUMER_SUBJECT_MISMATCH",
            "CHALLENGE",
            "$.external_consumer.receipt_sha256",
            "consumer receipt bytes differ from the pinned attested subject",
        )
    if producer_attestation_result is None:
        add(
            "FEDERATION_PRODUCER_ATTESTATION_MISSING",
            "BLOCK",
            "$.producer.attestation",
            "verified producer attestation result is required",
        )
    if consumer_attestation_result is None:
        add(
            "FEDERATION_CONSUMER_ATTESTATION_MISSING",
            "BLOCK",
            "$.external_consumer.attestation",
            "verified external-consumer attestation result is required",
        )

    producer_consensus = _object(producer_report.get("consensus"))
    producer_valid = (
        producer_report.get("profile_id") == PRODUCER_PROFILE
        and producer_report.get("decision") == "ACCEPT"
        and producer_report.get("valid") is True
        and producer_report.get("attestation_profile")
        == "github-keyless-slsa-provenance"
        and producer_report.get("verified_attestation_count") == 3
        and producer_report.get("signer_workflow") == producer_policy.get("workflow")
        and producer_report.get("source_digest")
        == producer_policy.get("attestation_source_sha")
        and producer_report.get("signer_digest")
        == producer_policy.get("attestation_signer_sha")
        and producer_report.get("self_hosted_runners_denied") is True
    )
    if not producer_valid:
        add(
            "FEDERATION_PRODUCER_REPORT_INVALID",
            "BLOCK",
            "$.producer_report",
            "producer report violates the pinned accepted-quorum profile",
        )

    consumer_metadata = _object(consumer_receipt.get("consumer"))
    consumer_producer = _object(consumer_receipt.get("producer"))
    consumer_consensus = _object(consumer_receipt.get("accepted_consensus"))
    consumer_verification = _object(consumer_receipt.get("verification"))
    required_verification_flags = (
        "producer_attestation_verified",
        "producer_report_digest_verified",
        "producer_code_sha_verified",
        "source_recomputed",
        "six_graph_roots_recomputed",
        "transition_cells_recomputed",
        "consumer_attestation_required",
    )
    consumer_valid = (
        consumer_receipt.get("profile_id") == CONSUMER_PROFILE
        and consumer_receipt.get("decision") == "ACCEPT"
        and consumer_receipt.get("valid") is True
        and consumer_metadata.get("repository") == consumer_policy.get("repository")
        and consumer_metadata.get("workflow") == consumer_policy.get("workflow")
        and consumer_metadata.get("commit_sha")
        == consumer_policy.get("attestation_source_sha")
        and consumer_producer.get("repository") == producer_policy.get("repository")
        and consumer_producer.get("workflow") == producer_policy.get("workflow")
        and consumer_producer.get("attestation_source_sha")
        == producer_policy.get("attestation_source_sha")
        and consumer_producer.get("attestation_signer_sha")
        == producer_policy.get("attestation_signer_sha")
        and consumer_producer.get("report_sha256")
        == producer_policy.get("report_sha256")
        and all(consumer_verification.get(key) is True for key in required_verification_flags)
    )
    if not consumer_valid:
        add(
            "FEDERATION_CONSUMER_RECEIPT_INVALID",
            "BLOCK",
            "$.consumer_receipt",
            "external consumer receipt violates the pinned verification profile",
        )

    try:
        computed_receipt_root = compute_consumer_receipt_root(consumer_receipt)
    except (TypeError, ValueError) as exc:
        computed_receipt_root = None
        add(
            "FEDERATION_CONSUMER_RECEIPT_ROOT_MISMATCH",
            "CHALLENGE",
            "$.consumer_receipt",
            str(exc),
        )
    declared_receipt_root = consumer_receipt.get("receipt_root")
    if (
        computed_receipt_root != declared_receipt_root
        or declared_receipt_root != consumer_policy.get("receipt_root")
    ):
        add(
            "FEDERATION_CONSUMER_RECEIPT_ROOT_MISMATCH",
            "CHALLENGE",
            "$.external_consumer.receipt_root",
            "consumer receipt root is not bound to the pinned receipt bytes",
        )

    field_pairs = {
        "round_id": (producer_report.get("round_id"), consumer_consensus.get("round_id")),
        "consensus_root": (
            producer_report.get("consensus_root"),
            consumer_consensus.get("consensus_root"),
        ),
        "source_digest": (
            producer_consensus.get("source_digest"),
            consumer_consensus.get("source_digest"),
        ),
        "graph_set_id": (
            producer_consensus.get("graph_set_id"),
            consumer_consensus.get("graph_set_id"),
        ),
        "poci_envelope_id": (
            producer_consensus.get("poci_envelope_id"),
            consumer_consensus.get("poci_envelope_id"),
        ),
        "graph_roots": (
            producer_consensus.get("graph_roots"),
            consumer_consensus.get("graph_roots"),
        ),
        "transition_cells_root": (
            producer_consensus.get("transition_cells_root"),
            consumer_consensus.get("transition_cells_root"),
        ),
        "computed_multigraph_root": (
            producer_consensus.get("computed_multigraph_root"),
            consumer_consensus.get("computed_multigraph_root"),
        ),
    }
    for key, (producer_value, consumer_value) in field_pairs.items():
        expected_value = expected.get(key)
        if producer_value != expected_value:
            add(
                "FEDERATION_PRODUCER_CONSENSUS_MISMATCH",
                "CHALLENGE",
                f"$.expected.{key}",
                f"producer consensus differs: {key}",
            )
        if consumer_value != expected_value:
            add(
                "FEDERATION_CONSUMER_CONSENSUS_MISMATCH",
                "CHALLENGE",
                f"$.expected.{key}",
                f"consumer consensus differs: {key}",
            )
        if producer_value != consumer_value:
            add(
                "FEDERATION_CROSS_DOMAIN_MISMATCH",
                "CHALLENGE",
                f"$.consensus.{key}",
                f"producer and consumer disagree: {key}",
            )

    unique = {
        (item["code"], item["path"], item["message"]): item for item in findings
    }
    findings = sorted(
        unique.values(),
        key=lambda item: (
            -DECISION_RANK[item["decision"]],
            item["code"],
            item["path"],
            item["message"],
        ),
    )
    primary = findings[0] if findings else None
    decision = primary["decision"] if primary else "ACCEPT"

    domains = [
        {
            "role": "producer",
            "repository": producer_policy.get("repository"),
            "workflow": producer_policy.get("workflow"),
            "attestation_source_sha": producer_policy.get("attestation_source_sha"),
            "attestation_signer_sha": producer_policy.get("attestation_signer_sha"),
            "subject_sha256": producer_report_digest,
            "attestation_result_digest": _attestation_digest(
                producer_attestation_result
            ),
        },
        {
            "role": "external_consumer",
            "repository": consumer_policy.get("repository"),
            "workflow": consumer_policy.get("workflow"),
            "attestation_source_sha": consumer_policy.get("attestation_source_sha"),
            "attestation_signer_sha": consumer_policy.get("attestation_signer_sha"),
            "subject_sha256": consumer_receipt_digest,
            "subject_root": declared_receipt_root,
            "attestation_result_digest": _attestation_digest(
                consumer_attestation_result
            ),
        },
    ]

    report: dict[str, Any] = {
        "profile_id": PROFILE,
        "decision": decision,
        "primary_reason_code": primary["code"] if primary else None,
        "reason_codes": sorted({item["code"] for item in findings}),
        "findings": findings,
        "domain_count": 2,
        "external_consumer_required": True,
        "domains": domains,
        "consensus": {
            "round_id": expected.get("round_id"),
            "consensus_root": expected.get("consensus_root"),
            "source_digest": expected.get("source_digest"),
            "graph_set_id": expected.get("graph_set_id"),
            "poci_envelope_id": expected.get("poci_envelope_id"),
            "graph_roots": expected_roots,
            "transition_cells_root": expected.get("transition_cells_root"),
            "computed_multigraph_root": expected.get("computed_multigraph_root"),
        },
        "verification": {
            "producer_subject_verified": (
                producer_report_digest == producer_policy.get("report_sha256")
            ),
            "producer_attestation_verified": producer_attestation_result is not None,
            "external_consumer_subject_verified": (
                consumer_receipt_digest == consumer_policy.get("receipt_sha256")
            ),
            "external_consumer_attestation_verified": (
                consumer_attestation_result is not None
            ),
            "external_consumer_receipt_root_verified": (
                computed_receipt_root == declared_receipt_root
                == consumer_policy.get("receipt_root")
            ),
            "cross_domain_consensus_equal": all(
                producer_value == consumer_value == expected.get(key)
                for key, (producer_value, consumer_value) in field_pairs.items()
            ),
        },
        "honest_limitations": [
            "the two attestations use different repositories and workflow identities",
            "both repositories are currently controlled by the same GitHub account owner",
            "federation proves committed evidence consistency, not objective real-world truth",
        ],
        "federation_root": None,
        "valid": decision == "ACCEPT",
    }
    report["federation_root"] = compute_federation_root(report)
    return report


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("policy", type=Path)
    parser.add_argument("--producer-report", type=Path, required=True)
    parser.add_argument("--consumer-receipt", type=Path, required=True)
    parser.add_argument("--producer-attestation-result", type=Path, required=True)
    parser.add_argument("--consumer-attestation-result", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        policy = load_object(args.policy)
        producer_report = load_object(args.producer_report)
        consumer_receipt = load_object(args.consumer_receipt)
        producer_attestation_result = load_value(args.producer_attestation_result)
        consumer_attestation_result = load_value(args.consumer_attestation_result)
        report = verify_federation(
            policy,
            producer_report,
            consumer_receipt,
            producer_report_digest=file_digest(args.producer_report),
            consumer_receipt_digest=file_digest(args.consumer_receipt),
            producer_attestation_result=producer_attestation_result,
            consumer_attestation_result=consumer_attestation_result,
        )
        code = EXIT_CODE[report["decision"]]
    except (OSError, ValueError, TypeError, KeyError) as exc:
        report = {
            "profile_id": PROFILE,
            "decision": "BLOCK",
            "primary_reason_code": "FEDERATION_INTERNAL_FAIL_CLOSED",
            "reason_codes": ["FEDERATION_INTERNAL_FAIL_CLOSED"],
            "findings": [
                _finding("FEDERATION_INTERNAL_FAIL_CLOSED", "BLOCK", "$", str(exc))
            ],
            "domain_count": 0,
            "external_consumer_required": True,
            "federation_root": None,
            "valid": False,
        }
        report["federation_root"] = compute_federation_root(report)
        code = 1

    text = (
        json.dumps(report, indent=2, ensure_ascii=False)
        if args.pretty
        else json.dumps(
            report, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
    ) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
