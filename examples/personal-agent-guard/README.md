# ProofPath Personal Agent Guard

Personal Agent Guard is a local ProofPath example for AI coding tools such as Claude Code and Codex-style CLIs.

It is designed for the personal workflow:

```text
AI coding tool proposes a high-impact command
-> local ProofPath guard checks policy
-> guard allows or blocks
-> decision is written to .proofpath/audit.jsonl
-> optional time-limited approval can allow the next attempt
```

## Why this exists

ProofPath v0.1 already works as a CI evidence gate.

This example makes ProofPath useful locally, before enterprise integration:

```text
my AI coding tool
-> my local action boundary
-> my audit log
```

## Files

```text
policy.json
proofpath_guard.py
proofpath_approve.py
claude-settings.example.json
codex-config.example.toml
demo-transcript.md
run_demo_check.sh
```

## Quick local demo

From the repository root:

```bash
rm -rf .proofpath
printf '{"tool_name":"Bash","tool_input":{"command":"git push origin main"}}' \
  | python3 examples/personal-agent-guard/proofpath_guard.py
```

Expected result:

```json
{"decision": "BLOCK", "reason": "MAIN_BRANCH_PUSH_REQUIRES_APPROVAL"}
```

Create a time-limited approval:

```bash
python3 examples/personal-agent-guard/proofpath_approve.py repo.push.main --ttl-minutes 10
```

Run the same hook payload again:

```bash
printf '{"tool_name":"Bash","tool_input":{"command":"git push origin main"}}' \
  | python3 examples/personal-agent-guard/proofpath_guard.py
```

Expected result:

```json
{"decision": "ALLOW", "reason": "APPROVAL_PRESENT"}
```

Inspect the audit trail:

```bash
cat .proofpath/audit.jsonl
```

## Claude Code example

Copy or adapt:

```text
examples/personal-agent-guard/claude-settings.example.json
```

The example uses a `PreToolUse` hook for Bash-style tool calls.

## Codex-style example

Copy or adapt:

```text
examples/personal-agent-guard/codex-config.example.toml
```

The example shows `PreToolUse` and `PermissionRequest` style hook entries.

## Self-test

```bash
bash examples/personal-agent-guard/run_demo_check.sh
```

The self-test verifies:

```text
first guarded command -> BLOCK
approval token written
second guarded command -> ALLOW
audit log contains both decisions
```

## Claim boundary

This is a personal local guard example.

It does not claim:

```text
production endpoint enforcement
complete agent security
full sandboxing
formal verification
```

It demonstrates a practical user-facing ProofPath workflow:

```text
AI tool command
-> local policy
-> approval boundary
-> audit trail
```
