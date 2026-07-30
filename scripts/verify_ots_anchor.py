#!/usr/bin/env python3
"""Verify a Bitcoin OpenTimestamps sidecar for exact target bytes.

This adapter invokes the official ``ots`` CLI. It deliberately fails closed:
a URL, a proof filename, exit code 0, or a success-looking string alone is not
enough. The result is promoted to TEMPORALLY_ANCHORED only when the verifier
exits successfully and reports exactly one Bitcoin block attestation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

SUCCESS_RE = re.compile(
    r"Success!\s+Bitcoin block\s+(?P<height>[1-9][0-9]*)\s+"
    r"attests existence as of\s+(?P<time>[^\r\n]+)",
    re.IGNORECASE,
)
PENDING_RE = re.compile(
    r"(Pending confirmation in Bitcoin blockchain|PendingAttestation)",
    re.IGNORECASE,
)
UNKNOWN_RE = re.compile(r"Unknown Attestation", re.IGNORECASE)


@dataclass(frozen=True)
class Classification:
    status: str
    reason: str
    bitcoin_block_height: int | None = None
    attested_before: str | None = None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def classify_ots_output(returncode: int, stdout: str, stderr: str) -> Classification:
    """Classify official-client output without upgrading weak evidence.

    A successful process must contain exactly one Bitcoin success attestation.
    Pending output is kept pending. Conflicting or ambiguous output fails closed.
    """

    combined = "\n".join(part for part in (stdout, stderr) if part)
    successes = list(SUCCESS_RE.finditer(combined))

    if PENDING_RE.search(combined):
        if successes:
            return Classification("INVALID", "CONFLICTING_PENDING_AND_CONFIRMED")
        return Classification("PENDING", "BITCOIN_CONFIRMATION_PENDING")

    if UNKNOWN_RE.search(combined):
        return Classification("INVALID", "UNKNOWN_ATTESTATION")

    if returncode != 0:
        return Classification("INVALID", "VERIFIER_EXIT_NONZERO")

    if len(successes) == 0:
        return Classification("INVALID", "NO_BITCOIN_ATTESTATION")

    if len(successes) != 1:
        heights = {match.group("height") for match in successes}
        if len(heights) > 1:
            return Classification("INVALID", "CONFLICTING_BITCOIN_ATTESTATIONS")
        return Classification("INVALID", "AMBIGUOUS_MULTIPLE_ATTESTATIONS")

    match = successes[0]
    return Classification(
        "TEMPORALLY_ANCHORED",
        "BITCOIN_ATTESTATION_VERIFIED",
        bitcoin_block_height=int(match.group("height")),
        attested_before=match.group("time").strip(),
    )


def run_verifier(
    target: Path,
    proof: Path,
    *,
    ots_bin: str = "ots",
    bitcoin_node: str | None = None,
    timeout_seconds: int = 120,
) -> dict:
    """Run ``ots verify`` against exact copies of target and proof."""

    if not target.is_file():
        return result_envelope(
            target,
            proof,
            Classification("INVALID", "TARGET_NOT_FOUND"),
            verifier={"binary": ots_bin, "executed": False},
        )
    if not proof.is_file():
        return result_envelope(
            target,
            proof,
            Classification("INVALID", "PROOF_NOT_FOUND"),
            verifier={"binary": ots_bin, "executed": False},
        )

    target_hash = sha256_file(target)
    proof_hash = sha256_file(proof)

    resolved_binary = shutil.which(ots_bin)
    if resolved_binary is None:
        return result_envelope(
            target,
            proof,
            Classification("UNAVAILABLE", "OTS_CLIENT_NOT_FOUND"),
            target_hash=target_hash,
            proof_hash=proof_hash,
            verifier={"binary": ots_bin, "executed": False},
        )

    with tempfile.TemporaryDirectory(prefix="proofpath-ots-") as temp_dir:
        temp_root = Path(temp_dir)
        temp_target = temp_root / "payload"
        temp_proof = temp_root / "payload.ots"
        shutil.copyfile(target, temp_target)
        shutil.copyfile(proof, temp_proof)

        command: list[str] = [resolved_binary]
        if bitcoin_node:
            command.extend(["--bitcoin-node", bitcoin_node])
        command.extend(["verify", temp_proof.name])

        try:
            completed = subprocess.run(
                command,
                cwd=temp_root,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return result_envelope(
                target,
                proof,
                Classification("UNAVAILABLE", "VERIFIER_TIMEOUT"),
                target_hash=target_hash,
                proof_hash=proof_hash,
                verifier={
                    "binary": resolved_binary,
                    "executed": True,
                    "command": command,
                    "timeout_seconds": timeout_seconds,
                    "stdout": exc.stdout or "",
                    "stderr": exc.stderr or "",
                },
            )
        except OSError as exc:
            return result_envelope(
                target,
                proof,
                Classification("UNAVAILABLE", "VERIFIER_EXECUTION_ERROR"),
                target_hash=target_hash,
                proof_hash=proof_hash,
                verifier={
                    "binary": resolved_binary,
                    "executed": False,
                    "error": str(exc),
                },
            )

    classification = classify_ots_output(
        completed.returncode, completed.stdout, completed.stderr
    )
    return result_envelope(
        target,
        proof,
        classification,
        target_hash=target_hash,
        proof_hash=proof_hash,
        verifier={
            "binary": resolved_binary,
            "executed": True,
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "output_sha256": "sha256:"
            + hashlib.sha256(
                (completed.stdout + "\n" + completed.stderr).encode("utf-8")
            ).hexdigest(),
        },
    )


def result_envelope(
    target: Path,
    proof: Path,
    classification: Classification,
    *,
    target_hash: str | None = None,
    proof_hash: str | None = None,
    verifier: dict,
) -> dict:
    return {
        "schema": "proofpath.temporal-anchor.ots.v0.1",
        "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "subject": {
            "path": str(target),
            "content_hash": target_hash,
        },
        "proof": {
            "path": str(proof),
            "media_type": "application/vnd.opentimestamps.ots",
            "content_hash": proof_hash,
        },
        "verification": asdict(classification),
        "temporal_precedence_proven": classification.status
        == "TEMPORALLY_ANCHORED",
        "verifier": verifier,
    }


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify an OpenTimestamps proof for exact target bytes."
    )
    parser.add_argument("target", type=Path)
    parser.add_argument("proof", type=Path)
    parser.add_argument("--ots-bin", default="ots")
    parser.add_argument("--bitcoin-node")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = run_verifier(
        args.target,
        args.proof,
        ots_bin=args.ots_bin,
        bitcoin_node=args.bitcoin_node,
        timeout_seconds=args.timeout_seconds,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)

    status = result["verification"]["status"]
    return 0 if status == "TEMPORALLY_ANCHORED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
