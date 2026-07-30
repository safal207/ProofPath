#!/usr/bin/env python3
"""Run deterministic conformance vectors for the OTS output classifier."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Sequence


def load_verifier(repo_root: Path):
    script = repo_root / "scripts" / "verify_ots_anchor.py"
    spec = importlib.util.spec_from_file_location("proofpath_verify_ots_anchor", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load verifier: {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: check_ots_anchor_vectors.py <manifest.json>", file=sys.stderr)
        return 2

    manifest_path = Path(args[0]).resolve()
    repo_root = Path(__file__).resolve().parents[1]
    verifier = load_verifier(repo_root)
    manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))

    failures = 0
    for case in manifest["cases"]:
        output = str(case["output"])
        stream = case.get("stream", "stdout")
        result = verifier.classify_ots_output(
            int(case["returncode"]),
            output if stream == "stdout" else "",
            output if stream == "stderr" else "",
        )
        actual = {
            "status": result.status,
            "reason": result.reason,
            "bitcoin_block_height": result.bitcoin_block_height,
            "attested_before": result.attested_before,
        }
        expected = case["expected"]

        if actual != expected:
            failures += 1
            print(f"FAIL {case['name']}")
            print("  expected:", json.dumps(expected, sort_keys=True))
            print("  actual:  ", json.dumps(actual, sort_keys=True))
        else:
            print(f"PASS {case['name']} -> {result.status}/{result.reason}")

    if failures:
        print(f"\nOTS temporal-anchor conformance failed: {failures}")
        return 1

    print(f"\nOTS temporal-anchor conformance passed: {len(manifest['cases'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
