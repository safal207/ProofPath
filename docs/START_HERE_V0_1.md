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

## v0.1 product path

```text
live demo
-> audit log
-> metrics collector
-> CI verification
-> reusable GitHub Action
-> downstream-style adoption example
```

## Three-minute reviewer path

1. Read the v0.1 milestone:

```text
docs/RELEASE_V0_1.md
```

2. Read the GitHub Action quickstart:

```text
docs/GITHUB_ACTION_QUICKSTART.md
```

3. Inspect the reusable action:

```text
action.yml
```

4. Inspect the metrics tools:

```text
scripts/collect_action_boundary_metrics.py
scripts/assert_action_boundary_metrics.py
```

5. Inspect the downstream-style adoption example:

```text
examples/github-action-adoption/
```

6. Inspect the reports:

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
```

The key product loop is:

```text
ProofPath audit JSONL
-> metrics JSON
-> expected-value assertions
-> CI pass / fail
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

## What v0.1 proves

Safe claim:

```text
ProofPath v0.1 demonstrates a reusable CI evidence gate for action-boundary audit metrics.
```

Stronger but still bounded claim:

```text
ProofPath v0.1 shows that an AI-agent/API action boundary can be expressed as audit logs, measured as metrics, and enforced as CI pass/fail evidence.
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
```

## Best current product phrase

```text
ProofPath is a CI evidence gate for AI-agent actions.
```

## Next milestone

```text
v0.2 = versioned release/tag + larger scenario suite + artifact uploads + latency metrics
```

## Bottom line

ProofPath v0.1 is no longer only a protocol idea or local demo.

It is a reusable product slice:

```text
audit log in
-> metrics out
-> CI pass/fail
```
