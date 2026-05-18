# ProofPath v0.1 Product Milestone

ProofPath v0.1 is the first product milestone for a CI-verifiable action-boundary evidence gate and a local Personal Agent Guard workflow.

It turns ProofPath audit logs into machine-checkable CI evidence and shows how local AI coding tools can be wrapped with a personal approval boundary.

## One-sentence summary

```text
ProofPath v0.1 verifies whether high-impact AI-agent/API actions produced the expected BLOCK / ACCEPT / audit metrics before CI passes.
```

## Product phrase

```text
ProofPath turns action-boundary audit logs into CI-verifiable evidence.
```

## Personal workflow phrase

```text
ProofPath Personal Agent Guard is a local seatbelt for AI coding tools.
```

## What is included in v0.1

v0.1 includes the first complete product slice:

```text
live demo
-> audit log
-> metrics collector
-> CI verification
-> reusable GitHub Action
-> downstream-style adoption example
-> Personal Agent Guard local workflow
```

## Core artifacts

| Artifact | Purpose |
| --- | --- |
| `crates/proofpath-gateway/` | Rust gateway that evaluates and forwards or blocks actions. |
| `scripts/collect_action_boundary_metrics.py` | Converts audit JSONL into metrics JSON. |
| `scripts/assert_action_boundary_metrics.py` | Asserts expected metrics for CI. |
| `action.yml` | Reusable composite GitHub Action. |
| `docs/LANDING_V0_1.md` | Short landing page for v0.1 product surfaces. |
| `docs/GITHUB_ACTION_QUICKSTART.md` | Product quickstart for GitHub Action users. |
| `examples/github-action-adoption/` | Downstream-style adoption example. |
| `examples/personal-agent-guard/` | Local guard example for Claude Code / Codex-style AI coding tools. |
| `scripts/run_live_action_boundary_check.sh` | Live CI demo runner. |
| `reports/action-boundary-fixture-2026-05-17.json` | First fixture metrics baseline. |
| `reports/evidence-metrics-2026-05-17-ci-baseline.json` | First CI reproducibility baseline. |

## CI-validated evidence

The current CI validates:

```text
formatting
clippy
Rust tests
Compute Witness Rust CLI fixture
live action-boundary metrics
reusable ProofPath GitHub Action self-test
Personal Agent Guard demo self-test
```

The repository product-level check is:

```text
ProofPath audit JSONL
-> action-boundary metrics JSON
-> expected-value assertions
-> CI pass / fail
```

The personal workflow check is:

```text
AI coding tool command
-> local policy
-> scoped approval boundary
-> local audit log
```

## GitHub Action usage

A downstream repository can use ProofPath as a CI evidence gate:

```yaml
- name: Verify ProofPath action-boundary metrics
  uses: safal207/ProofPath@main
  with:
    audit-log: proofpath-audit.jsonl
    metrics-output: proofpath-action-boundary-metrics.json
    expected-actions-total: "2"
    expected-actions-blocked: "1"
    expected-actions-accepted: "1"
    expected-unsafe-without-approval-blocked: "1"
    expected-unsafe-without-approval-false-accepts: "0"
    expected-safe-with-approval-false-blocks: "0"
    expected-audit-records-written: "2"
    expected-blocked-forwarded-count: "0"
    expected-accepted-forwarded-count: "1"
    expected-audit-hash-chain-present: "true"
```

## Personal Agent Guard usage

A local user can run:

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

Relevant files:

```text
examples/personal-agent-guard/policy.json
examples/personal-agent-guard/proofpath_guard.py
examples/personal-agent-guard/proofpath_approve.py
examples/personal-agent-guard/claude-settings.example.json
examples/personal-agent-guard/codex-config.example.toml
```

## Demo story

The canonical action-boundary demo checks two actions:

```text
1. no-approval irreversible action -> BLOCK
2. approved irreversible action -> ACCEPT
```

The Personal Agent Guard demo checks a local AI-tool workflow:

```text
1. guarded local command -> BLOCK
2. scoped time-limited approval -> written
3. same command -> ALLOW
4. both decisions -> audit log
```

Expected v0.1 action-boundary metrics:

```text
actions_total = 2
actions_blocked = 1
actions_accepted = 1
unsafe_without_approval_blocked = 1
unsafe_without_approval_false_accepts = 0
safe_with_approval_false_blocks = 0
audit_records_written = 2
blocked_forwarded_count = 0
accepted_forwarded_count = 1
audit_hash_chain_present = true
```

## Reviewer interpretation

Safe claim:

```text
ProofPath v0.1 demonstrates CI-verifiable and local evidence-gate patterns for action-boundary audit metrics.
```

Stronger but still bounded claim:

```text
ProofPath v0.1 shows that an AI-agent/API action boundary can be expressed as audit logs, measured as metrics, and enforced as CI or local pass/fail evidence.
```

Do not overstate this as:

```text
ProofPath proves complete AI-agent safety.
```

That is not claimed.

## Non-claims

v0.1 does not claim:

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

## What v0.1 proves

v0.1 proves that two useful product surfaces exist:

```text
an audit log can be checked by a reusable CI action
```

and:

```text
a local AI-tool command can pass through a personal approval boundary and audit trail
```

These are the minimum useful product slices.

## Next milestones

### v0.2

```text
publish versioned GitHub release/tag
add larger action-boundary scenario suite
emit artifact uploads from CI
add latency measurement
add richer Personal Agent Guard policies
```

### v0.3

```text
add policy configuration file for hosted/API use
support multiple action profiles
add richer report summaries
add third-party/downstream repo demo
add local installer or one-command setup for personal guard
```

## Bottom line

ProofPath v0.1 is no longer only a protocol idea or local demo.

It is both:

```text
a reusable CI evidence gate for action-boundary audit metrics
```

and:

```text
a local seatbelt pattern for AI coding tools
```
