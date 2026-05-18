# Start Here: ProofPath v0.1

ProofPath v0.1 is a CI-verifiable action-boundary evidence gate for AI-agent/API audit logs.

## One sentence

```text
ProofPath turns action-boundary audit logs into CI-verifiable evidence.
```

## What to understand first

AI agents and automated systems may hold valid credentials while still needing a separate check before a high-impact action is executed.

ProofPath adds a pre-execution action boundary:

```text
valid credential
  != valid action
  != valid scope
  != valid reversibility
  != valid approval
```

## Two practical product surfaces

ProofPath v0.1 now has two practical surfaces:

| Surface | Path | What it gives you |
| --- | --- | --- |
| CI evidence gate | `action.yml`, `docs/GITHUB_ACTION_QUICKSTART.md`, `examples/github-action-adoption/` | Turn audit logs into CI-verifiable metrics and pass/fail checks. |
| Personal Agent Guard | `examples/personal-agent-guard/` | Add a local approval boundary and audit log around Claude Code / Codex-style AI coding tools. |

## v0.1 product path

```text
live demo
-> audit log
-> metrics collector
-> CI verification
-> reusable GitHub Action
-> downstream-style adoption example
-> Personal Agent Guard local workflow
```

## Three-minute reviewer path

1. Read the v0.1 landing page:

```text
docs/LANDING_V0_1.md
```

2. Read the v0.1 milestone:

```text
docs/RELEASE_V0_1.md
```

3. Read the GitHub Action quickstart:

```text
docs/GITHUB_ACTION_QUICKSTART.md
```

4. Inspect the reusable action:

```text
action.yml
```

5. Inspect the metrics tools:

```text
scripts/collect_action_boundary_metrics.py
scripts/assert_action_boundary_metrics.py
```

6. Inspect the downstream-style adoption example:

```text
examples/github-action-adoption/
```

7. Inspect the Personal Agent Guard example:

```text
examples/personal-agent-guard/
```

8. Inspect the reports:

```text
reports/action-boundary-fixture-2026-05-17.md
reports/evidence-metrics-2026-05-17-ci-baseline.md
```

## What CI verifies

The Rust workflow currently verifies:

```text
formatting
clippy
Rust tests
Compute Witness Rust CLI fixture
live action-boundary metrics
reusable ProofPath GitHub Action self-test
Personal Agent Guard demo self-test
```

The key repository product loop is:

```text
ProofPath audit JSONL
-> metrics JSON
-> expected-value assertions
-> CI pass / fail
```

The key personal workflow loop is:

```text
AI coding tool command
-> local policy
-> scoped approval boundary
-> local audit log
```

## Minimal GitHub Action usage

```yaml
- name: Verify ProofPath action-boundary metrics
  uses: safal207/ProofPath@main
  with:
    audit-log: proofpath-audit.jsonl
    metrics-output: proofpath-action-boundary-metrics.json
    expected-actions-total: "2"
    expected-actions-blocked: "1"
    expected-actions-accepted: "1"
```

## Minimal Personal Agent Guard usage

```bash
bash examples/personal-agent-guard/run_demo_check.sh
```

Expected path:

```text
first guarded command -> BLOCK
approval token written
second guarded command -> ALLOW
audit log contains both decisions
```

## What v0.1 proves

Safe claim:

```text
ProofPath v0.1 demonstrates reusable CI and local evidence-gate patterns for action-boundary audit metrics.
```

Stronger but still bounded claim:

```text
ProofPath v0.1 shows that an AI-agent/API action boundary can be expressed as audit logs, measured as metrics, and enforced as CI or local pass/fail evidence.
```

## What v0.1 does not prove

ProofPath v0.1 does not claim:

```text
production security certification
complete prevention coverage
formal verification
regulatory compliance
external production adoption
large-scenario benchmark coverage
latency benchmark coverage
full sandboxing
```

## Best current product phrase

```text
ProofPath is a CI evidence gate for AI-agent actions.
```

## Best current personal phrase

```text
ProofPath Personal Agent Guard is a local seatbelt for AI coding tools.
```

## Next milestone

```text
v0.2 = versioned release/tag + larger scenario suite + artifact uploads + latency metrics + richer local guard policies
```

## Bottom line

ProofPath v0.1 is no longer only a protocol idea or local demo.

It now has two working product paths:

```text
audit log in
-> metrics out
-> CI pass/fail
```

and:

```text
AI tool command
-> local guard
-> approval boundary
-> audit trail
```
