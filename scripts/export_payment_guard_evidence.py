#!/usr/bin/env python3
"""Export a portable Agent Payment Guard evidence bundle.

Usage
-----
    python3 scripts/export_payment_guard_evidence.py --out proofpath-evidence-bundle/

Optional overrides
------------------
    --audit-path          .proofpath/audit.jsonl
    --replay-store-path   .proofpath/replay-store.json
    --config              examples/agent-payment-guard/payment_guard_service_config.json
    --policy              examples/agent-payment-guard/payment_policy.json

Behavior
--------
- Creates --out directory if it does not exist.
- Existing --out directory is overwritten (files are replaced; extra files
  already present are left in place).
- Missing audit file -> exits with error.
- Missing replay-store -> exports an empty {} store with a warning.
- Hash-chain verification is run during export; hash_chain_valid=false does
  NOT abort the export, but is recorded in verification_report.json.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Hash-chain verification (inline, no subprocess)
# ---------------------------------------------------------------------------

def canonical_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_record_hash(record: Dict[str, Any]) -> str:
    payload = dict(record)
    payload.pop("hash", None)
    return "sha256:" + sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def verify_hash_chain(audit_path: Path) -> Tuple[bool, str, int]:
    """Return (valid, message, record_count)."""
    if not audit_path.exists():
        return False, f"audit file not found: {audit_path}", 0

    lines = [line for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return True, "audit log is empty", 0

    expected_previous = "GENESIS"
    for idx, line in enumerate(lines, start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            return False, f"line {idx}: JSON decode error: {exc}", idx - 1

        prev = record.get("previous_hash", "")
        if prev != expected_previous:
            return (
                False,
                f"line {idx}: previous_hash mismatch (expected {expected_previous!r}, got {prev!r})",
                idx - 1,
            )

        stored_hash = record.get("hash", "")
        computed_hash = compute_record_hash(record)
        if stored_hash != computed_hash:
            return (
                False,
                f"line {idx}: hash mismatch (stored {stored_hash!r}, computed {computed_hash!r})",
                idx - 1,
            )

        expected_previous = stored_hash

    return True, f"chain valid ({len(lines)} records)", len(lines)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def load_replay_store_safe(path: Path) -> Tuple[Dict[str, Any], bool]:
    """Return (store_dict, was_present)."""
    if not path.exists():
        return {}, False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return (data if isinstance(data, dict) else {}), True
    except (json.JSONDecodeError, OSError):
        return {}, True


def export_bundle(
    audit_path: Path,
    replay_store_path: Path,
    config_path: Path,
    policy_path: Path,
    out_dir: Path,
) -> int:
    """Build the evidence bundle. Returns exit code (0 = success, 1 = error)."""

    # --- validate required inputs ---
    if not audit_path.exists():
        print(f"[export] ERROR: audit file not found: {audit_path}", file=sys.stderr)
        return 1

    if not config_path.exists():
        print(f"[export] ERROR: config file not found: {config_path}", file=sys.stderr)
        return 1

    if not policy_path.exists():
        print(f"[export] ERROR: policy file not found: {policy_path}", file=sys.stderr)
        return 1

    # --- create output directory ---
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- hash-chain verification ---
    chain_valid, chain_msg, record_count = verify_hash_chain(audit_path)
    if not chain_valid:
        print(f"[export] WARNING: hash chain invalid: {chain_msg}", file=sys.stderr)
    else:
        print(f"[export] hash chain: {chain_msg}")

    # --- replay store ---
    replay_store, replay_present = load_replay_store_safe(replay_store_path)
    if not replay_present:
        print(
            f"[export] WARNING: replay-store not found at {replay_store_path}; "
            "exporting empty store",
            file=sys.stderr,
        )

    # --- copy files ---
    copied: List[str] = []

    def _copy(src: Path, dest_name: str) -> None:
        dest = out_dir / dest_name
        shutil.copy2(src, dest)
        copied.append(dest_name)
        print(f"[export] copied  {src}  ->  {dest}")

    _copy(audit_path, "audit.jsonl")
    _copy(config_path, "payment_guard_service_config.json")
    _copy(policy_path, "payment_policy.json")

    # replay-store: copy if present, else write empty
    replay_dest = out_dir / "replay-store.json"
    if replay_present and replay_store_path.exists():
        shutil.copy2(replay_store_path, replay_dest)
    else:
        replay_dest.write_text(json.dumps({}, indent=2), encoding="utf-8")
    copied.append("replay-store.json")
    print(f"[export] copied  {replay_store_path}  ->  {replay_dest}")

    # --- verification report ---
    report: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "bundle_type": "agent-payment-guard-evidence",
        "audit_records_count": record_count,
        "replay_store_nonces": len(replay_store),
        "hash_chain_valid": chain_valid,
        "hash_chain_message": chain_msg,
        "source_files": {
            "audit": str(audit_path),
            "replay_store": str(replay_store_path),
            "config": str(config_path),
            "policy": str(policy_path),
        },
        "copied_files": copied + ["verification_report.json"],
    }
    report_path = out_dir / "verification_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[export] wrote   {report_path}")

    print(f"\n[export] bundle ready: {out_dir}/")
    print(f"         records : {record_count}")
    print(f"         nonces  : {len(replay_store)}")
    print(f"         chain   : {'OK' if chain_valid else 'INVALID'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export Agent Payment Guard evidence bundle.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 scripts/export_payment_guard_evidence.py --out proofpath-evidence-bundle/\n"
            "  python3 scripts/verify_audit_log.py proofpath-evidence-bundle/audit.jsonl\n"
        ),
    )
    parser.add_argument("--out", required=True, metavar="DIR",
                        help="Output directory for the evidence bundle (created if absent, overwritten if present).")
    parser.add_argument("--audit-path", default=".proofpath/audit.jsonl", metavar="PATH")
    parser.add_argument("--replay-store-path", default=".proofpath/replay-store.json", metavar="PATH")
    parser.add_argument("--config",
                        default="examples/agent-payment-guard/payment_guard_service_config.json",
                        metavar="PATH")
    parser.add_argument("--policy",
                        default="examples/agent-payment-guard/payment_policy.json",
                        metavar="PATH")
    args = parser.parse_args()

    return export_bundle(
        audit_path=Path(args.audit_path),
        replay_store_path=Path(args.replay_store_path),
        config_path=Path(args.config),
        policy_path=Path(args.policy),
        out_dir=Path(args.out),
    )


if __name__ == "__main__":
    raise SystemExit(main())
