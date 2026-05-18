#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

POLICY="$WORK_DIR/policy.json"
APPROVALS="$WORK_DIR/approvals.json"
AUDIT_LOG="$WORK_DIR/audit.jsonl"

python3 - "$POLICY" "$APPROVALS" "$AUDIT_LOG" <<'PY'
import json
import sys
from pathlib import Path

policy_path, approvals_path, audit_log_path = map(Path, sys.argv[1:])
policy = json.loads(Path("examples/personal-agent-guard/policy.json").read_text(encoding="utf-8"))
policy["approval_file"] = str(approvals_path)
policy["audit_log"] = str(audit_log_path)
policy_path.write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

HOOK_PAYLOAD='{"tool_name":"Bash","tool_input":{"command":"git push origin main"}}'

set +e
FIRST_OUTPUT=$(printf '%s' "$HOOK_PAYLOAD" | python3 examples/personal-agent-guard/proofpath_guard.py --policy "$POLICY")
FIRST_STATUS=$?
set -e

if [[ "$FIRST_STATUS" -ne 2 ]]; then
  echo "Expected first guarded command to exit with status 2 in generic mode, got $FIRST_STATUS" >&2
  echo "$FIRST_OUTPUT" >&2
  exit 1
fi

python3 - "$FIRST_OUTPUT" <<'PY'
import json
import sys
payload = json.loads(sys.argv[1])
assert payload["decision"] == "BLOCK", payload
assert payload["reason"] == "MAIN_BRANCH_PUSH_REQUIRES_APPROVAL", payload
PY

python3 examples/personal-agent-guard/proofpath_approve.py \
  repo.push.main \
  --ttl-minutes 10 \
  --reason "demo self-test approval" \
  --approvals "$APPROVALS" >/dev/null

SECOND_OUTPUT=$(printf '%s' "$HOOK_PAYLOAD" | python3 examples/personal-agent-guard/proofpath_guard.py --policy "$POLICY")

python3 - "$SECOND_OUTPUT" "$AUDIT_LOG" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(sys.argv[1])
assert payload["decision"] == "ALLOW", payload
assert payload["reason"] == "APPROVAL_PRESENT", payload

records = [json.loads(line) for line in Path(sys.argv[2]).read_text(encoding="utf-8").splitlines() if line.strip()]
assert len(records) == 2, records
assert records[0]["decision"] == "BLOCK", records
assert records[1]["decision"] == "ALLOW", records
assert records[0]["approval_scope"] == "repo.push.main", records
assert records[1]["approval_scope"] == "repo.push.main", records
assert records[0].get("hash"), records
assert records[1].get("hash"), records
PY

echo "Personal Agent Guard demo check passed."
