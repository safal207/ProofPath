# Personal Agent Guard Demo Transcript

This transcript shows the local ProofPath workflow for an AI coding tool.

## Scene 1 — AI tool proposes a guarded command

User asks the coding agent:

```text
Prepare the change and publish it to main.
```

The agent prepares a shell command:

```bash
git push origin main
```

ProofPath Personal Agent Guard receives the hook payload:

```bash
printf '{"tool_name":"Bash","tool_input":{"command":"git push origin main"}}' \
  | python3 examples/personal-agent-guard/proofpath_guard.py
```

Output:

```json
{"decision": "BLOCK", "reason": "MAIN_BRANCH_PUSH_REQUIRES_APPROVAL"}
```

Interpretation:

```text
valid tool access != valid action
```

## Scene 2 — User gives a time-limited approval

User explicitly approves the scope for a short time window:

```bash
python3 examples/personal-agent-guard/proofpath_approve.py repo.push.main --ttl-minutes 10 --reason "manual demo approval"
```

Output:

```text
Approved repo.push.main until <timestamp>
```

## Scene 3 — AI tool retries the same command

The agent retries:

```bash
git push origin main
```

ProofPath receives the same hook payload again:

```bash
printf '{"tool_name":"Bash","tool_input":{"command":"git push origin main"}}' \
  | python3 examples/personal-agent-guard/proofpath_guard.py
```

Output:

```json
{"decision": "ALLOW", "reason": "APPROVAL_PRESENT"}
```

## Scene 4 — Audit trail

User inspects the audit log:

```bash
cat .proofpath/audit.jsonl
```

The audit log contains both decisions:

```text
first attempt -> BLOCK
second attempt -> ALLOW
```

## Demo message

```text
AI coding agents do not need blind trust.
They need local action boundaries.
```

## Product phrase

```text
ProofPath Personal Agent Guard is a local seatbelt for AI coding tools.
```

## Claim boundary

This demo shows a local hook workflow and audit trail.

It does not claim complete endpoint security, sandboxing, or production enforcement.
