#!/usr/bin/env python3
"""ProofPath guard and evidence bridge for NVIDIA NOOA-style agent actions.

The module is deliberately standard-library only. It provides a stable guard
around high-impact Python capabilities and a format-tolerant adapter for exported
NOOA spans. It does not depend on NOOA internals and does not pretend that an
in-process policy check is a sandbox.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, MutableMapping, Optional


JsonObject = dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_ref(value: bytes | Any) -> str:
    material = value if isinstance(value, bytes) else canonical_bytes(value)
    return "sha256:" + hashlib.sha256(material).hexdigest()


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def write_json(path: Path, value: Any) -> None:
    atomic_write(path, json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    text = "".join(json.dumps(dict(row), sort_keys=True, ensure_ascii=False) + "\n" for row in rows)
    atomic_write(path, text)


@dataclass(frozen=True)
class ActionProposal:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    agent: str
    method: str
    intent_id: Optional[str]
    parent_cause: Optional[str]
    action: str
    scope: str
    target: str
    reversibility: str = "reversible"
    approval_ref: Optional[str] = None
    nonce: Optional[str] = None
    contains_secret: bool = False
    destination: Optional[str] = None
    metadata: JsonObject = field(default_factory=dict)

    def digest(self) -> str:
        return sha256_ref(asdict(self))


@dataclass(frozen=True)
class GuardDecision:
    decision: str
    reason_codes: tuple[str, ...]
    execution_allowed: bool
    proposal_digest: str
    decided_at: str
    cml_findings: tuple[JsonObject, ...] = ()

    def to_dict(self) -> JsonObject:
        value = asdict(self)
        value["reason_codes"] = list(self.reason_codes)
        value["cml_findings"] = list(self.cml_findings)
        return value


@dataclass(frozen=True)
class ExecutionObservation:
    status: str
    started_at: Optional[str]
    completed_at: str
    result_digest: Optional[str]
    error_type: Optional[str]
    side_effect_executed: bool

    def to_dict(self) -> JsonObject:
        return asdict(self)


@dataclass(frozen=True)
class GuardedResult:
    decision: GuardDecision
    observation: ExecutionObservation
    result: Any
    evidence_dir: Path


class Policy:
    def __init__(self, value: Mapping[str, Any]) -> None:
        self.allowed_scopes = frozenset(str(item) for item in value.get("allowed_scopes", []))
        self.network_allowlist = frozenset(str(item).lower() for item in value.get("network_allowlist", []))
        self.irreversible_actions = frozenset(str(item).lower() for item in value.get("irreversible_actions", []))
        self.approval_required_scopes = frozenset(
            str(item) for item in value.get("approval_required_scopes", [])
        )
        self.default_decision = str(value.get("default_decision", "BLOCK")).upper()

    @classmethod
    def load(cls, path: Path) -> "Policy":
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("policy must be a JSON object")
        return cls(value)


class NonceStore:
    """Small atomic replay store for the demo integration."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _load(self) -> MutableMapping[str, JsonObject]:
        if not self.path.exists():
            return {}
        value = json.loads(self.path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}

    def consumed(self, nonce: Optional[str]) -> bool:
        return bool(nonce and nonce in self._load())

    def consume(self, nonce: Optional[str], proposal_digest: str) -> None:
        if not nonce:
            return
        values = self._load()
        if nonce in values:
            raise RuntimeError("nonce already consumed")
        values[nonce] = {"proposal_digest": proposal_digest, "consumed_at": utc_now()}
        write_json(self.path, values)


class HashLedger:
    """Append-only hash-linked JSONL ledger used as the local LiminalDB handoff."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _last_hash(self) -> Optional[str]:
        if not self.path.exists():
            return None
        rows = [line for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not rows:
            return None
        value = json.loads(rows[-1])
        return value.get("record_hash")

    def append(self, record_type: str, payload: Mapping[str, Any]) -> JsonObject:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record: JsonObject = {
            "record_type": record_type,
            "recorded_at": utc_now(),
            "previous_hash": self._last_hash(),
            "payload": dict(payload),
        }
        record["record_hash"] = sha256_ref(record)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
        return record


def proposal_from_nooa_span(span: Mapping[str, Any], *, defaults: Optional[Mapping[str, Any]] = None) -> ActionProposal:
    """Map an exported NOOA-style span into a ProofPath proposal.

    NOOA's public promise is parent-child tracing, not a frozen external JSON
    schema. This adapter therefore accepts common top-level and ``attributes``
    names while requiring security-critical fields to be supplied explicitly.
    """

    defaults = dict(defaults or {})
    attributes = span.get("attributes")
    attrs = dict(attributes) if isinstance(attributes, Mapping) else {}

    def pick(*names: str, default: Any = None) -> Any:
        for name in names:
            value = span.get(name)
            if value is not None:
                return value
            value = attrs.get(name)
            if value is not None:
                return value
            if name in defaults:
                return defaults[name]
        return default

    method = str(pick("method", "name", "span_name", default="unknown_method"))
    action = str(pick("action", default=method)).lower()
    span_id = str(pick("span_id", "id", default=sha256_ref(span)[7:23]))
    return ActionProposal(
        trace_id=str(pick("trace_id", default=f"trace-{span_id}")),
        span_id=span_id,
        parent_span_id=_optional_text(pick("parent_span_id", "parent_id")),
        agent=str(pick("agent", "agent_class", default="NOOAAgent")),
        method=method,
        intent_id=_optional_text(pick("intent_id")),
        parent_cause=_optional_text(pick("parent_cause")),
        action=action,
        scope=str(pick("scope", default="unknown")),
        target=str(pick("target", "resource", default="unknown")),
        reversibility=str(pick("reversibility", default="reversible")),
        approval_ref=_optional_text(pick("approval_ref", "human_approval")),
        nonce=_optional_text(pick("nonce")),
        contains_secret=bool(pick("contains_secret", default=False)),
        destination=_optional_text(pick("destination", "host")),
        metadata={"source": "nooa-export", "raw_span_digest": sha256_ref(span)},
    )


def _optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class ProofPathNOOAGuard:
    def __init__(self, policy: Policy, state_dir: Path, evidence_root: Path) -> None:
        self.policy = policy
        self.state_dir = state_dir
        self.evidence_root = evidence_root
        self.nonces = NonceStore(state_dir / "consumed-nonces.json")
        self.ledger = HashLedger(state_dir / "liminaldb-ledger.jsonl")

    def evaluate(self, proposal: ActionProposal) -> GuardDecision:
        reasons: list[str] = []
        findings: list[JsonObject] = []
        decision = "ACCEPT"

        if not proposal.intent_id:
            reasons.append("MISSING_INTENT")
            decision = "BLOCK"
        if not proposal.parent_cause:
            reasons.append("MISSING_CAUSAL_PARENT")
            decision = "BLOCK"
        if proposal.scope not in self.policy.allowed_scopes:
            reasons.append("INVALID_SCOPE")
            decision = "BLOCK"
        if self.nonces.consumed(proposal.nonce):
            reasons.append("INTENT_REPLAYED")
            decision = "BLOCK"

        is_network = proposal.action in {"network_send", "send", "http_post", "upload"}
        destination_allowed = bool(
            proposal.destination and proposal.destination.lower() in self.policy.network_allowlist
        )
        if is_network and proposal.contains_secret and not destination_allowed:
            reasons.append("SECRET_EGRESS_DENIED")
            decision = "BLOCK"
            findings.append(
                {
                    "code": "CML-AUDIT-R3-SECRET_NET_MISSING_CHAIN",
                    "severity": "FAIL",
                    "record_id": proposal.span_id,
                    "message": "Secret-bearing network egress lacks an allowed destination and valid causal chain.",
                }
            )

        needs_approval = (
            proposal.reversibility.lower() == "irreversible"
            or proposal.action.lower() in self.policy.irreversible_actions
            or proposal.scope in self.policy.approval_required_scopes
        )
        if decision == "ACCEPT" and needs_approval and not proposal.approval_ref:
            reasons.append("HUMAN_APPROVAL_REQUIRED")
            decision = "HOLD"

        if not reasons:
            reasons.append("POLICY_MATCH")

        allowed = decision == "ACCEPT"
        return GuardDecision(
            decision=decision,
            reason_codes=tuple(reasons),
            execution_allowed=allowed,
            proposal_digest=proposal.digest(),
            decided_at=utc_now(),
            cml_findings=tuple(findings),
        )

    def execute(self, proposal: ActionProposal, executor: Callable[[], Any]) -> GuardedResult:
        decision = self.evaluate(proposal)
        authorization = self.ledger.append(
            "authorization",
            {"proposal": asdict(proposal), "decision": decision.to_dict()},
        )

        result: Any = None
        started_at: Optional[str] = None
        error_type: Optional[str] = None
        status = "NOT_EXECUTED"
        side_effect_executed = False

        if decision.execution_allowed:
            # Consume authority before invoking the side effect so a concurrent
            # retry cannot reuse the same nonce after authorization succeeds.
            self.nonces.consume(proposal.nonce, decision.proposal_digest)
            started_at = utc_now()
            side_effect_executed = True
            try:
                result = executor()
                status = "SUCCEEDED"
            except Exception as exc:  # evidence must survive executor failure
                status = "FAILED"
                error_type = type(exc).__name__
                result = {"error": str(exc)}

        observation = ExecutionObservation(
            status=status,
            started_at=started_at,
            completed_at=utc_now(),
            result_digest=sha256_ref(result) if result is not None else None,
            error_type=error_type,
            side_effect_executed=side_effect_executed,
        )
        observation_record = self.ledger.append(
            "observation",
            {
                "authorization_record_hash": authorization["record_hash"],
                "proposal_digest": decision.proposal_digest,
                "observation": observation.to_dict(),
            },
        )
        evidence_dir = self._export_evidence(proposal, decision, observation, result, observation_record)
        return GuardedResult(decision=decision, observation=observation, result=result, evidence_dir=evidence_dir)

    def _export_evidence(
        self,
        proposal: ActionProposal,
        decision: GuardDecision,
        observation: ExecutionObservation,
        result: Any,
        observation_record: Mapping[str, Any],
    ) -> Path:
        bundle = self.evidence_root / proposal.span_id
        evidence = bundle / "evidence"
        evidence.mkdir(parents=True, exist_ok=True)

        intent_record = {
            "intent_id": proposal.intent_id,
            "parent_cause": proposal.parent_cause,
            "scope": proposal.scope,
            "approval_ref": proposal.approval_ref,
        }
        action_record = {
            "trace_id": proposal.trace_id,
            "span_id": proposal.span_id,
            "parent_span_id": proposal.parent_span_id,
            "agent": proposal.agent,
            "method": proposal.method,
            "action": proposal.action,
            "target": proposal.target,
            "destination": proposal.destination,
            "proposal_digest": decision.proposal_digest,
        }
        verification_record = {
            "decision": decision.to_dict(),
            "ledger_record_hash": observation_record["record_hash"],
            "claim_boundary": "policy decision and local evidence only; not sandbox certification",
        }
        result_record = {"observation": observation.to_dict(), "result": result}

        write_json(evidence / "intent.json", intent_record)
        write_json(evidence / "action.json", action_record)
        write_json(evidence / "result.json", result_record)
        write_json(evidence / "verification.json", verification_record)
        write_json(bundle / "authorization.json", decision.to_dict())

        cml_rows = self._cml_rows(proposal, decision, observation)
        ltp_rows = self._ltp_rows(proposal, decision, observation)
        write_jsonl(bundle / "cml-trace.jsonl", cml_rows)
        write_jsonl(bundle / "ltp-trace.jsonl", ltp_rows)
        # Copy the current durable ledger head into the bundle, preserving the
        # local runtime ledger separately under state_dir.
        atomic_write(bundle / "liminaldb-ledger.jsonl", self.ledger.path.read_text(encoding="utf-8"))

        manifest = build_manifest(bundle)
        write_json(bundle / "manifest.json", manifest)
        verification = verify_bundle(bundle)
        write_json(bundle / "bundle-verification.json", verification)
        return bundle

    @staticmethod
    def _cml_rows(
        proposal: ActionProposal, decision: GuardDecision, observation: ExecutionObservation
    ) -> list[JsonObject]:
        root_id = proposal.parent_cause or f"gap:{proposal.span_id}"
        rows: list[JsonObject] = [
            {
                "id": root_id,
                "timestamp": decision.decided_at,
                "actor": {"comm": "human_or_policy_authority"},
                "action": "authorize_intent" if proposal.parent_cause else "observed_gap",
                "object": {"intent_id": proposal.intent_id, "scope": proposal.scope},
                "permitted_by": proposal.approval_ref or "declared_intent",
                "parent_cause": None,
            },
            {
                "id": proposal.span_id,
                "timestamp": decision.decided_at,
                "actor": {"comm": proposal.agent},
                "action": proposal.action,
                "object": {
                    "target": proposal.target,
                    "destination": proposal.destination,
                    "contains_secret": proposal.contains_secret,
                },
                "permitted_by": decision.decision,
                "parent_cause": proposal.parent_cause,
            },
            {
                "id": f"observation:{proposal.span_id}",
                "timestamp": observation.completed_at,
                "actor": {"comm": "proofpath_guard"},
                "action": "observe_result",
                "object": observation.to_dict(),
                "permitted_by": "proofpath_observation",
                "parent_cause": proposal.span_id,
            },
        ]
        rows.extend({"type": "finding", **finding} for finding in decision.cml_findings)
        return rows

    @staticmethod
    def _ltp_rows(
        proposal: ActionProposal, decision: GuardDecision, observation: ExecutionObservation
    ) -> list[JsonObject]:
        return [
            {
                "type": "sense",
                "trace_id": proposal.trace_id,
                "event_id": f"sense:{proposal.span_id}",
                "parent_event_id": proposal.parent_span_id,
                "payload": {"proposal_digest": decision.proposal_digest},
            },
            {
                "type": "transition",
                "trace_id": proposal.trace_id,
                "event_id": f"transition:{proposal.span_id}",
                "parent_event_id": f"sense:{proposal.span_id}",
                "payload": {
                    "decision": decision.decision,
                    "reason_codes": list(decision.reason_codes),
                },
            },
            {
                "type": "commit",
                "trace_id": proposal.trace_id,
                "event_id": f"commit:{proposal.span_id}",
                "parent_event_id": f"transition:{proposal.span_id}",
                "payload": observation.to_dict(),
            },
        ]


def build_manifest(bundle: Path) -> JsonObject:
    files: list[JsonObject] = []
    excluded = {"manifest.json", "bundle-verification.json"}
    for path in sorted(item for item in bundle.rglob("*") if item.is_file()):
        relative = path.relative_to(bundle).as_posix()
        if relative in excluded:
            continue
        material = path.read_bytes()
        files.append({"path": relative, "size": len(material), "sha256": hashlib.sha256(material).hexdigest()})
    return {
        "profile": "org.proofpath.nooa-liminal-evidence.v0.1",
        "created_at": utc_now(),
        "files": files,
    }


def verify_bundle(bundle: Path) -> JsonObject:
    manifest_path = bundle / "manifest.json"
    if not manifest_path.exists():
        return {"valid": False, "errors": ["manifest missing"]}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    expected = {item["path"]: item for item in manifest.get("files", [])}
    allowed_meta = {"manifest.json", "bundle-verification.json"}
    actual = {
        path.relative_to(bundle).as_posix(): path
        for path in bundle.rglob("*")
        if path.is_file() and path.relative_to(bundle).as_posix() not in allowed_meta
    }
    for name in sorted(set(expected) - set(actual)):
        errors.append(f"missing:{name}")
    for name in sorted(set(actual) - set(expected)):
        errors.append(f"unlisted:{name}")
    for name in sorted(set(expected) & set(actual)):
        material = actual[name].read_bytes()
        digest = hashlib.sha256(material).hexdigest()
        if digest != expected[name].get("sha256"):
            errors.append(f"digest:{name}")
        if len(material) != expected[name].get("size"):
            errors.append(f"size:{name}")
    return {"valid": not errors, "errors": errors, "verified_at": utc_now()}
