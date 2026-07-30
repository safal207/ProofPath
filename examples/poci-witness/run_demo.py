#!/usr/bin/env python3
"""Run the deterministic PoCI v0.1 reviewer demo and export reports."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = Path(__file__).resolve().parent / "demo"
VALID_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "valid-action.accept.json"
TAMPERED_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "result-digest-mismatch.challenge.json"
EXPECTED_TRANSCRIPT = DEMO_DIR / "expected-transcript.txt"


def _load_verifier() -> ModuleType:
    path = REPO_ROOT / "scripts" / "verify_poci.py"
    spec = importlib.util.spec_from_file_location("proofpath_verify_poci", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load verifier from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _transcript(accept: dict[str, Any], challenge: dict[str, Any]) -> str:
    return "\n".join(
        [
            "PoCI v0.1 evidence demo",
            f"valid-action.accept.json -> {accept['decision']} (primary={accept['primary_reason_code']})",
            (
                "result-digest-mismatch.challenge.json -> "
                f"{challenge['decision']} (primary={challenge['primary_reason_code']})"
            ),
            "portable reports: accept-report.json, challenge-report.json, demo-summary.json",
            "PASS evidence accepted; tampering challenged",
            "",
        ]
    )


def run_demo(output_dir: Path, check: bool) -> str:
    verifier = _load_verifier()
    accept = verifier.verify_envelope(verifier.load_json(VALID_FIXTURE))
    challenge = verifier.verify_envelope(verifier.load_json(TAMPERED_FIXTURE))

    if accept.get("decision") != "ACCEPT" or accept.get("primary_reason_code") is not None:
        raise AssertionError(f"valid evidence did not ACCEPT: {accept}")
    if challenge.get("decision") != "CHALLENGE":
        raise AssertionError(f"tampered evidence did not CHALLENGE: {challenge}")
    if challenge.get("primary_reason_code") != "RESULT_DIGEST_MISMATCH":
        raise AssertionError(f"unexpected challenge reason: {challenge}")

    accept_again = verifier.verify_envelope(verifier.load_json(VALID_FIXTURE))
    challenge_again = verifier.verify_envelope(verifier.load_json(TAMPERED_FIXTURE))
    if verifier.normalized_json_bytes(accept) != verifier.normalized_json_bytes(accept_again):
        raise AssertionError("ACCEPT report is not byte-stable")
    if verifier.normalized_json_bytes(challenge) != verifier.normalized_json_bytes(challenge_again):
        raise AssertionError("CHALLENGE report is not byte-stable")

    summary = {
        "profile_id": "proofpath.poci.v0.1",
        "scenario": "bounded-action-then-result-tampering",
        "reports": [
            {
                "fixture": VALID_FIXTURE.name,
                "decision": accept["decision"],
                "primary_reason_code": accept["primary_reason_code"],
                "computed_envelope_root": accept["computed_envelope_root"],
            },
            {
                "fixture": TAMPERED_FIXTURE.name,
                "decision": challenge["decision"],
                "primary_reason_code": challenge["primary_reason_code"],
                "computed_envelope_root": challenge["computed_envelope_root"],
            },
        ],
        "passed": True,
    }

    _write_json(output_dir / "accept-report.json", accept)
    _write_json(output_dir / "challenge-report.json", challenge)
    _write_json(output_dir / "demo-summary.json", summary)

    transcript = _transcript(accept, challenge)
    (output_dir / "transcript.txt").write_text(transcript, encoding="utf-8")

    if check:
        expected = EXPECTED_TRANSCRIPT.read_text(encoding="utf-8")
        if transcript != expected:
            raise AssertionError("demo transcript drifted from committed expectation")

    return transcript


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the ProofPath PoCI evidence demo")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "artifacts" / "poci-demo",
        help="Directory for portable JSON reports",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if decisions, determinism, or transcript differ from expectations",
    )
    args = parser.parse_args()

    try:
        transcript = run_demo(args.output_dir.resolve(), args.check)
    except (AssertionError, OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1

    print(transcript, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
