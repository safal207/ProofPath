# ProofPath v0.1 Landing

ProofPath v0.1 has two practical product surfaces:

```text
1. CI evidence gate for repositories
2. Personal Agent Guard for local AI coding tools
```

## One sentence

```text
ProofPath turns action-boundary audit logs into CI-verifiable evidence.
```

## Personal workflow sentence

```text
ProofPath Personal Agent Guard is a local seatbelt for AI coding tools.
```

## Surface 1 — CI evidence gate

Use ProofPath in GitHub Actions to verify action-boundary metrics from an audit JSONL file.

Path:

```text
action.yml
docs/GITHUB_ACTION_QUICKSTART.md
examples/github-action-adoption/
```

Flow:

```text
ProofPath audit JSONL
-> metrics JSON
-> expected-value assertions
-> CI pass / fail
```

## Surface 2 — Personal Agent Guard

Use ProofPath locally with Claude Code / Codex-style AI coding tools.

Path:

```text
examples/personal-agent-guard/
```

Flow:

```text
AI coding tool proposes a command
-> local ProofPath guard checks policy
-> BLOCK / ALLOW decision
-> optional time-limited approval
-> local audit log
```

## Why this matters

AI agents and automated tools can hold valid credentials while still needing a separate action-level check.

ProofPath adds that action boundary:

```text
valid credential
  != valid action
  != valid scope
  != valid reversibility
  != valid approval
```

## Demo paths

### Repository / CI demo

```text
examples/github-action-adoption/
```

### Local personal guard demo

```text
examples/personal-agent-guard/
```

Run:

```bash
bash examples/personal-agent-guard/run_demo_check.sh
```

Expected self-test path:

```text
first guarded command -> BLOCK
approval token written
second guarded command -> ALLOW
audit log contains both decisions
```

## Claim boundary

ProofPath v0.1 demonstrates reusable evidence gates and local guard examples.

It does not claim:

```text
production endpoint enforcement
complete prevention coverage
formal verification
regulatory compliance
full sandboxing
```

## Best current public framing

```text
ProofPath is an action-boundary evidence layer for AI agents and automated tools.
```

## Best current personal framing

```text
Use AI coding agents faster, but with a local action boundary.
```
