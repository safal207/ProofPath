#!/usr/bin/env python3
"""Safe GitHub Action wrapper for ProofPath Deploy Guard."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

DECISIONS = {"ACCEPT", "HOLD", "BLOCK", "CHALLENGE"}
EXPECTED_EXIT = {"ACCEPT": 0, "HOLD": 2, "BLOCK": 3, "CHALLENGE": 4}
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
REASON_RE = re.compile(r"^[A-Z0-9_]+$")
TRANSITIONS = {
    "DEPLOY_TO_PRODUCTION",
    "WAIT_FOR_REQUIRED_EVIDENCE",
    "REPAIR_POLICY_OR_SAFETY_FAILURE",
    "INVESTIGATE_CONFLICTING_EVIDENCE",
}


class ActionError(RuntimeError):
    """Raised when the action cannot produce a trustworthy certificate."""


def _safe_text(value: str, label: str) -> str:
    if not value or any(character in value for character in ("\n", "\r", "\x00")):
        raise ActionError(f"{label} must be one non-empty line")
    return value


def _workspace_path(raw: str, workspace: Path, label: str) -> Path:
    value = _safe_text(raw, label)
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = workspace / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(workspace)
    except ValueError as exc:
        raise ActionError(f"{label} must remain inside GITHUB_WORKSPACE") from exc
    return resolved


def _load_certificate(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ActionError(f"clearance certificate is unreadable: {exc}") from exc
    if not isinstance(value, dict):
        raise ActionError("clearance certificate must contain one JSON object")
    return value


def _controlled_fields(certificate: dict[str, Any]) -> dict[str, str]:
    decision = certificate.get("decision")
    if decision not in DECISIONS:
        raise ActionError("clearance certificate has an unsupported decision")

    primary = certificate.get("primary_reason_code")
    if primary is None:
        primary_text = "NONE"
    elif isinstance(primary, str) and REASON_RE.fullmatch(primary):
        primary_text = primary
    else:
        raise ActionError("clearance certificate has an unsafe primary reason code")

    fields = {
        "decision": decision,
        "primary-reason-code": primary_text,
        "clearance-root": certificate.get("clearance_root") or "",
        "policy-root": certificate.get("policy_root") or "",
        "evidence-root": certificate.get("evidence_root") or "",
        "execution-allowed": str(certificate.get("execution_allowed") is True).lower(),
        "authority-granted": str(certificate.get("authority_granted") is True).lower(),
        "permitted-next-transition": certificate.get("permitted_next_transition") or "",
        "assurance-level": "",
        "witness-level": "",
        "coverage": "",
    }
    assurance = certificate.get("assurance")
    if isinstance(assurance, dict):
        fields["assurance-level"] = str(assurance.get("assurance_level") or "")
        fields["witness-level"] = str(assurance.get("witness_level") or "")
        fields["coverage"] = str(assurance.get("coverage") or "")
    for key, value in fields.items():
        if "\n" in value or "\r" in value or "\x00" in value:
            raise ActionError(f"unsafe multiline action output: {key}")
    return fields


def _validate_complete_certificate(
    certificate: dict[str, Any], fields: dict[str, str], verifier_exit: int
) -> None:
    if certificate.get("profile_id") != "proofpath.deploy.clearance-certificate.v0.1":
        raise ActionError("verifier did not emit the full clearance-certificate profile")
    if certificate.get("certificate_version") != "0.1":
        raise ActionError("unsupported clearance-certificate version")
    for key in ("clearance-root", "policy-root", "evidence-root"):
        if not DIGEST_RE.fullmatch(fields[key]):
            raise ActionError(f"clearance certificate has an invalid {key}")
    decision = fields["decision"]
    if verifier_exit != EXPECTED_EXIT[decision]:
        raise ActionError("verifier exit code does not match its certificate decision")
    if certificate.get("valid") is not (decision == "ACCEPT"):
        raise ActionError("certificate validity does not match its decision")
    if certificate.get("execution_allowed") is not (decision == "ACCEPT"):
        raise ActionError("execution_allowed does not match the decision")
    if certificate.get("authority_granted") is not False:
        raise ActionError("Deploy Guard must never create or claim new authority")
    if fields["permitted-next-transition"] not in TRANSITIONS:
        raise ActionError("certificate has an unsupported next transition")
    if fields["assurance-level"] != "POLICY_VERIFIED":
        raise ActionError("unexpected assurance level")
    if fields["witness-level"] != "SINGLE_WORKFLOW_REFERENCE":
        raise ActionError("unexpected witness level")
    if fields["coverage"] != "NOT_FINANCIALLY_COVERED":
        raise ActionError("unexpected financial-coverage label")


def _append_outputs(path: str | None, fields: dict[str, str], certificate: Path) -> None:
    if not path:
        return
    output_path = Path(path)
    with output_path.open("a", encoding="utf-8") as output:
        for key, value in fields.items():
            output.write(f"{key}={value}\n")
        output.write(f"certificate-path={certificate}\n")


def _append_summary(path: str | None, fields: dict[str, str], mode: str) -> None:
    if not path:
        return
    lines = [
        "## ProofPath Deploy Guard",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Decision | `{fields['decision']}` |",
        f"| Primary reason | `{fields['primary-reason-code']}` |",
        f"| Mode | `{mode}` |",
        f"| Execution allowed | `{fields['execution-allowed']}` |",
        f"| Clearance root | `{fields['clearance-root'] or 'UNAVAILABLE'}` |",
        f"| Assurance | `{fields['assurance-level'] or 'INVALID_CERTIFICATE'}` |",
        f"| Witnesses | `{fields['witness-level'] or 'INVALID_CERTIFICATE'}` |",
        f"| Coverage | `{fields['coverage'] or 'INVALID_CERTIFICATE'}` |",
        "",
        "This action evaluates evidence only. It does not deploy, merge, modify IAM, or grant authority.",
        "",
    ]
    with Path(path).open("a", encoding="utf-8") as summary:
        summary.write("\n".join(lines))


def _command_escape(message: str) -> str:
    return message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--certificate", required=True)
    parser.add_argument("--mode", required=True)
    args = parser.parse_args(argv)

    try:
        mode = _safe_text(args.mode, "mode")
        if mode not in {"enforce", "observe"}:
            raise ActionError("mode must be enforce or observe")
        workspace = Path(os.environ.get("GITHUB_WORKSPACE", os.getcwd())).resolve()
        policy = _workspace_path(args.policy, workspace, "policy")
        evidence = _workspace_path(args.evidence, workspace, "evidence")
        certificate = _workspace_path(args.certificate, workspace, "certificate")
        if not policy.is_file():
            raise ActionError("policy file does not exist")
        if not evidence.is_file():
            raise ActionError("evidence file does not exist")

        verifier = Path(__file__).resolve().parents[1] / "scripts" / "verify_proofpath_deploy_guard.py"
        if not verifier.is_file():
            raise ActionError("bundled Deploy Guard verifier is missing")
        certificate.parent.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(
            [
                sys.executable,
                str(verifier),
                str(policy),
                str(evidence),
                "--pretty",
                "--output",
                str(certificate),
            ],
            cwd=workspace,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.stderr:
            sys.stderr.write(completed.stderr)
        if not certificate.is_file():
            raise ActionError("verifier did not write a clearance certificate")

        certificate_value = _load_certificate(certificate)
        fields = _controlled_fields(certificate_value)
        _append_outputs(os.environ.get("GITHUB_OUTPUT"), fields, certificate)
        _append_summary(os.environ.get("GITHUB_STEP_SUMMARY"), fields, mode)
        _validate_complete_certificate(certificate_value, fields, completed.returncode)

        print(
            "ProofPath Deploy Guard: "
            f"{fields['decision']} / {fields['primary-reason-code']} / {fields['clearance-root']}"
        )
        if mode == "observe":
            return 0
        return EXPECTED_EXIT[fields["decision"]]
    except (ActionError, OSError, ValueError) as exc:
        print(f"::error title=ProofPath Deploy Guard::{_command_escape(str(exc))}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
