#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

BUNDLE_PROFILE = "org.proofpath.agent-safety-evidence-bundle"
BUNDLE_VERSION = "0.2.0"
CASE_ID = "ASB-01"

CORE_FILES = (
    "audit.jsonl",
    "replay-store.json",
    "payment_guard_service_config.json",
    "payment_policy.json",
    "mock-rail-transactions.jsonl",
    "asb-01-trace.json",
    "asb-01-submission-case.json",
    "payment-proposal.json",
    "signed-intent-envelope.json",
    "verification_report.json",
)


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return "unknown"
    return completed.stdout.strip() or "unknown"


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def finalize_bundle(
    bundle_dir: Path,
    proposal_path: Path,
    intent_path: Path,
) -> Path:
    if not bundle_dir.is_dir():
        raise FileNotFoundError(f"bundle directory not found: {bundle_dir}")
    if not proposal_path.is_file():
        raise FileNotFoundError(f"payment proposal not found: {proposal_path}")
    if not intent_path.is_file():
        raise FileNotFoundError(f"signed intent envelope not found: {intent_path}")

    shutil.copy2(proposal_path, bundle_dir / "payment-proposal.json")
    shutil.copy2(intent_path, bundle_dir / "signed-intent-envelope.json")

    missing = [name for name in CORE_FILES if not (bundle_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"evidence bundle is missing required files: {missing}")

    trace = load_json(bundle_dir / "asb-01-trace.json")
    if trace.get("benchmark_case_id") != CASE_ID:
        raise ValueError("trace benchmark_case_id must equal ASB-01")

    proposal = load_json(bundle_dir / "payment-proposal.json")
    intent = load_json(bundle_dir / "signed-intent-envelope.json")
    if proposal.get("human_intent_id") != intent.get("human_intent_id"):
        raise ValueError("proposal and signed intent human_intent_id mismatch")
    if proposal.get("causal_parent") != intent.get("causal_parent"):
        raise ValueError("proposal and signed intent causal_parent mismatch")

    hashes = {name: file_sha256(bundle_dir / name) for name in CORE_FILES}
    manifest = {
        "profile": BUNDLE_PROFILE,
        "version": BUNDLE_VERSION,
        "benchmark_case_id": CASE_ID,
        "generated_at": utc_now(),
        "source": {
            "repository": "safal207/ProofPath",
            "commit": source_commit(),
        },
        "intent": {
            "human_intent_id": proposal.get("human_intent_id"),
            "causal_parent": proposal.get("causal_parent"),
            "payment_mode": proposal.get("payment_mode"),
        },
        "files": hashes,
        "derivation_boundary": {
            "raw_evidence": [
                "audit.jsonl",
                "replay-store.json",
                "mock-rail-transactions.jsonl",
                "asb-01-trace.json",
                "payment-proposal.json",
                "signed-intent-envelope.json",
            ],
            "producer_claim": "asb-01-submission-case.json",
            "consumer_instruction": (
                "Derive benchmark facts from raw evidence; do not trust the "
                "producer claim as verification evidence."
            ),
        },
    }
    manifest_path = bundle_dir / "evidence-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    checksum_names = (*CORE_FILES, "evidence-manifest.json")
    checksum_lines = [
        f"{file_sha256(bundle_dir / name)}  {name}" for name in checksum_names
    ]
    checksum_path = bundle_dir / "SHA256SUMS"
    checksum_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Finalize a self-contained ProofPath ASB-01 evidence bundle."
    )
    parser.add_argument(
        "--bundle",
        default="proofpath-asb01-evidence-bundle",
        help="Evidence bundle directory produced by the ASB-01 race demo.",
    )
    parser.add_argument(
        "--proposal",
        default=(
            "examples/agent-payment-guard/"
            "payment_proposal.valid_micro_payment.json"
        ),
    )
    parser.add_argument(
        "--intent",
        default="examples/agent-payment-guard/intent_envelopes/intent.valid.json",
    )
    args = parser.parse_args()

    manifest_path = finalize_bundle(
        Path(args.bundle),
        Path(args.proposal),
        Path(args.intent),
    )
    print(f"[asb-01-evidence] self-contained bundle ready: {manifest_path.parent}/")
    print(f"[asb-01-evidence] manifest: {manifest_path}")
    print(f"[asb-01-evidence] files: {len(CORE_FILES) + 2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
