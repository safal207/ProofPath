# ProofPath v0.1 Reviewer Checklist

This checklist gives reviewers a short, evidence-oriented path through ProofPath v0.1.

Use it after reading:

```text
docs/START_HERE_V0_1.md
docs/reviewer-runbook.md
```

## Core claim to check

```text
ProofPath turns action-boundary audit logs into CI-verifiable evidence.
```

More concretely:

```text
valid credential
  != valid action
  != valid scope
  != valid reversibility
  != valid approval
```

## 1. Repository orientation

Check:

- `README.md`
- `docs/START_HERE_V0_1.md`
- `docs/LANDING_V0_1.md`
- `docs/RELEASE_V0_1.md`

Reviewer question:

```text
Can I understand what ProofPath is in less than five minutes?
```

Expected answer:

```text
ProofPath is a pre-execution action boundary and evidence gate for high-risk AI-agent/API actions.
```

## 2. Clean-checkout reproduction

Run or inspect:

```text
docs/reviewer-runbook.md
```

Reviewer question:

```text
Can I reproduce the core behavior from a clean checkout?
```

Expected evidence:

```text
unsafe irreversible action without approval -> BLOCK
approved irreversible action -> ACCEPT
blocked action -> not forwarded
accepted action -> forwarded
proofpath-audit.jsonl -> contains both decisions
```

## 3. Conformance fixture contract

Run:

```bash
python3 scripts/check_conformance_fixtures.py conformance/manifest.json
```

Reviewer question:

```text
Are the expected verifier decisions executable rather than only described in prose?
```

Expected evidence:

```text
ProofPath conformance fixtures passed: 8
```

## 4. Audit-log integrity inspection

After running a demo, run:

```bash
python3 scripts/verify_audit_log.py proofpath-audit.jsonl
```

Reviewer question:

```text
Can I inspect whether the local audit JSONL chain is structurally intact?
```

Expected evidence:

```text
first_previous_hash=GENESIS
last_hash=sha256:...
```

Important boundary:

```text
This detects local chain breakage or payload modification.
It does not replace secure append-only storage, signing, timestamping, or regulatory-grade audit infrastructure.
```

## 5. Metrics and CI evidence gate

Inspect:

```text
action.yml
scripts/collect_action_boundary_metrics.py
scripts/assert_action_boundary_metrics.py
docs/GITHUB_ACTION_QUICKSTART.md
```

Reviewer question:

```text
Can an audit log become a CI pass/fail evidence artifact?
```

Expected evidence:

```text
ProofPath audit JSONL
-> metrics JSON
-> expected-value assertions
-> CI pass / fail
```

## 6. Personal Agent Guard path

Inspect or run:

```bash
bash examples/personal-agent-guard/run_demo_check.sh
```

Reviewer question:

```text
Does ProofPath also demonstrate a local AI coding-tool approval boundary?
```

Expected evidence:

```text
first guarded command -> BLOCK
approval token written
second guarded command -> ALLOW
audit log contains both decisions
```

## 7. Non-claims check

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

Reviewer question:

```text
Are the claims bounded and honest?
```

Expected answer:

```text
Yes. v0.1 is a local/demo/CI evidence layer, not a production compliance claim.
```

## Final reviewer summary

A positive v0.1 review should be able to say:

```text
ProofPath provides a reproducible local action-boundary demo, an executable conformance fixture runner, a local audit hash-chain verifier, and a reusable GitHub Action that turns audit logs into CI-verifiable metrics.
```

A conservative v0.1 review should also say:

```text
The system is early and fixture-oriented. It still needs production hardening, stronger storage guarantees, broader scenario coverage, latency measurement, and real-world integrations.
```

## Bottom line

```text
ProofPath v0.1 is not yet a full production security platform.
It is a compact evidence machine for action-boundary review.
```
