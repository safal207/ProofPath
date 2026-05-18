#!/usr/bin/env python3
"""Create a local time-limited ProofPath approval token.

This helper is for the Personal Agent Guard example. It writes approvals to
.proofpath/approvals.json so the guard can allow a matching scoped action while
that approval is still valid.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict


def load_json(path: Path) -> Dict[str, Any]:
    if path.exists():
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scope", help="Approval scope, for example repo.push.main")
    parser.add_argument("--ttl-minutes", type=int, default=10)
    parser.add_argument("--reason", default="manual local approval")
    parser.add_argument("--approvals", default=".proofpath/approvals.json")
    args = parser.parse_args()

    approvals_path = Path(args.approvals)
    approvals_path.parent.mkdir(parents=True, exist_ok=True)
    approvals = load_json(approvals_path)

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=args.ttl_minutes)
    approvals[args.scope] = {
        "scope": args.scope,
        "approved_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "reason": args.reason,
    }

    approvals_path.write_text(json.dumps(approvals, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Approved {args.scope} until {expires_at.isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
