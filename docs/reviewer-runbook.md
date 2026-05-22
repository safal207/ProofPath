# ProofPath Reviewer Runbook

This runbook gives reviewers a single clean-checkout path from clone to observable ProofPath behavior.

It focuses on the current v0.1 evidence boundary:

```text
valid credential
  != valid action
  != valid scope
  != valid reversibility
  != valid approval
```

The goal is not to prove production security. The goal is to reproduce the core ProofPath claim locally: high-risk actions can be evaluated before execution, unsafe actions can be blocked before the protected API sees them, approved actions can be forwarded, and every decision can be written into a hash-linked audit log.

## Prerequisites

Use a machine with:

- Git;
- Rust and Cargo;
- Python 3;
- Bash;
- a terminal environment such as Linux, macOS, WSL, or Git Bash.

No external cloud service is required for the local demo path.

## 1. Clean checkout

```bash
git clone https://github.com/safal207/ProofPath.git
cd ProofPath
```

Start from a clean audit log:

```bash
rm -f proofpath-audit.jsonl proofpath-action-boundary-metrics.json
```

## 2. Build and test the Rust workspace

```bash
cargo test --workspace
```

Expected result:

```text
Rust workspace tests pass.
```

If this fails, stop here and inspect the compiler or test output first. The demo path assumes the workspace builds locally.

## 3. Start the protected upstream demo API

Open Terminal 1:

```bash
python3 examples/upstream/demo_server.py
```

Keep this process running.

Expected result:

```text
The demo protected API starts and waits for requests.
```

## 4. Start the ProofPath gateway

Open Terminal 2:

```bash
cargo run -p proofpath-gateway
```

Keep this process running.

Expected result:

```text
The ProofPath gateway starts and waits for requests.
```

If the command reports that a port is already in use, stop the old process or run the demo in a fresh terminal session.

## 5. Run the AI-agent dangerous-action demo

Open Terminal 3.

First run the irreversible delete attempt without human approval:

```bash
bash examples/agent-dangerous-action/agent_delete_without_approval.sh
```

Expected HTTP result:

```text
HTTP/1.1 403 Forbidden
```

Expected ProofPath decision:

```json
{
  "forwarded": false,
  "proofpath": {
    "decision": "BLOCK",
    "reason": "IRREVERSIBLE_ACTION_REQUIRES_APPROVAL"
  }
}
```

Meaning:

```text
The request may have a valid API path, but the proposed irreversible action lacks required approval.
ProofPath blocks it before the protected upstream API receives it.
```

Now run the same dangerous action with explicit approval:

```bash
bash examples/agent-dangerous-action/agent_delete_with_approval.sh
```

Expected HTTP result:

```text
HTTP/1.1 200 OK
```

Expected ProofPath decision:

```json
{
  "forwarded": true,
  "upstream_status": 200,
  "proofpath": {
    "decision": "ACCEPT"
  }
}
```

Meaning:

```text
The action has declared intent, causal parent, scope, reversibility classification, and explicit human approval.
ProofPath accepts it and forwards it to the protected API.
```

## 6. Inspect the dangerous-action audit log

```bash
cat proofpath-audit.jsonl
```

Expected shape:

```jsonl
{"audit_id":"...","previous_hash":"GENESIS","intent_id":"intent_inspect_account_001","causal_parent":"decision_user_requested_inspection","scope":"account.delete","decision":"BLOCK","reason":"IRREVERSIBLE_ACTION_REQUIRES_APPROVAL","forwarded":false,"upstream_status":null,"hash":"sha256:..."}
{"audit_id":"...","previous_hash":"sha256:...","intent_id":"intent_delete_account_approved_001","causal_parent":"decision_human_approved_delete","scope":"account.delete","decision":"ACCEPT","reason":null,"forwarded":true,"upstream_status":200,"hash":"sha256:..."}
```

Quick decision check without `jq`:

```bash
python3 - <<'PY'
import json
from pathlib import Path
records = [json.loads(line) for line in Path('proofpath-audit.jsonl').read_text().splitlines() if line.strip()]
for record in records:
    print(record['decision'], record['forwarded'], record.get('reason'))
assert records[0]['previous_hash'] == 'GENESIS'
assert records[0]['decision'] == 'BLOCK'
assert records[0]['forwarded'] is False
assert records[1]['decision'] == 'ACCEPT'
assert records[1]['forwarded'] is True
assert records[1]['previous_hash'] == records[0]['hash']
print('dangerous-action audit checks passed')
PY
```

Expected result:

```text
BLOCK False IRREVERSIBLE_ACTION_REQUIRES_APPROVAL
ACCEPT True None
dangerous-action audit checks passed
```

## 7. Optional: collect and assert action-boundary metrics

The reusable GitHub Action uses these same scripts internally. From the local audit file, generate metrics:

```bash
python3 scripts/collect_action_boundary_metrics.py \
  --input proofpath-audit.jsonl \
  --output proofpath-action-boundary-metrics.json \
  --run-id local-reviewer-dangerous-action
```

Inspect the metrics:

```bash
cat proofpath-action-boundary-metrics.json
```

Assert the expected two-action baseline:

```bash
python3 scripts/assert_action_boundary_metrics.py \
  --metrics proofpath-action-boundary-metrics.json \
  --expected-actions-total 2 \
  --expected-actions-blocked 1 \
  --expected-actions-accepted 1 \
  --expected-unsafe-without-approval-blocked 1 \
  --expected-unsafe-without-approval-false-accepts 0 \
  --expected-safe-with-approval-false-blocks 0 \
  --expected-audit-records-written 2 \
  --expected-blocked-forwarded-count 0 \
  --expected-accepted-forwarded-count 1 \
  --expected-audit-hash-chain-present true
```

Expected result:

```text
ProofPath action-boundary metrics passed.
```

## 8. Run the CI/CD deploy-gate demo

Reset the audit log so the CI/CD scenario has its own three-record trail:

```bash
rm -f proofpath-audit.jsonl
```

Keep the upstream demo server and ProofPath gateway running from Terminal 1 and Terminal 2.

Run a safe preview deployment:

```bash
bash examples/cicd-deploy-gate/cicd_preview_deploy.sh
```

Expected result:

```text
HTTP/1.1 200 OK
ProofPath decision: ACCEPT
forwarded: true
```

Run a production deploy without approval:

```bash
bash examples/cicd-deploy-gate/cicd_production_deploy_without_approval.sh
```

Expected result:

```text
HTTP/1.1 403 Forbidden
ProofPath decision: BLOCK
reason: IRREVERSIBLE_ACTION_REQUIRES_APPROVAL
forwarded: false
```

Run an approved production rollback:

```bash
bash examples/cicd-deploy-gate/cicd_approved_rollback.sh
```

Expected result:

```text
HTTP/1.1 200 OK
ProofPath decision: ACCEPT
forwarded: true
```

## 9. Inspect the CI/CD audit log

```bash
cat proofpath-audit.jsonl
```

Expected audit shape:

```jsonl
{"audit_id":"...","previous_hash":"GENESIS","intent_id":"intent_preview_deploy_001","causal_parent":"decision_pr_checks_passed","scope":"cicd.preview.deploy","decision":"ACCEPT","reason":null,"forwarded":true,"upstream_status":200,"hash":"sha256:..."}
{"audit_id":"...","previous_hash":"sha256:...","intent_id":"intent_production_deploy_001","causal_parent":"decision_agent_ready_to_release","scope":"cicd.production.deploy","decision":"BLOCK","reason":"IRREVERSIBLE_ACTION_REQUIRES_APPROVAL","forwarded":false,"upstream_status":null,"hash":"sha256:..."}
{"audit_id":"...","previous_hash":"sha256:...","intent_id":"intent_approved_production_rollback_001","causal_parent":"decision_human_approved_rollback","scope":"cicd.production.rollback","decision":"ACCEPT","reason":null,"forwarded":true,"upstream_status":200,"hash":"sha256:..."}
```

Quick CI/CD audit check:

```bash
python3 - <<'PY'
import json
from pathlib import Path
records = [json.loads(line) for line in Path('proofpath-audit.jsonl').read_text().splitlines() if line.strip()]
for record in records:
    print(record['scope'], record['decision'], record['forwarded'], record.get('reason'))
assert len(records) == 3
assert records[0]['previous_hash'] == 'GENESIS'
assert records[0]['scope'] == 'cicd.preview.deploy'
assert records[0]['decision'] == 'ACCEPT'
assert records[0]['forwarded'] is True
assert records[1]['scope'] == 'cicd.production.deploy'
assert records[1]['decision'] == 'BLOCK'
assert records[1]['forwarded'] is False
assert records[2]['scope'] == 'cicd.production.rollback'
assert records[2]['decision'] == 'ACCEPT'
assert records[2]['forwarded'] is True
assert records[1]['previous_hash'] == records[0]['hash']
assert records[2]['previous_hash'] == records[1]['hash']
print('cicd audit checks passed')
PY
```

Expected result:

```text
cicd.preview.deploy ACCEPT True None
cicd.production.deploy BLOCK False IRREVERSIBLE_ACTION_REQUIRES_APPROVAL
cicd.production.rollback ACCEPT True None
cicd audit checks passed
```

## 10. What this verifies

This runbook verifies that, in the local demo fixture:

1. the Rust workspace can build and test;
2. an unsafe irreversible action without approval returns `BLOCK`;
3. a blocked action is not forwarded upstream;
4. an approved irreversible action returns `ACCEPT`;
5. an accepted action is forwarded upstream;
6. the CI/CD demo distinguishes preview deploy, unapproved production deploy, and approved rollback;
7. every decision is written to `proofpath-audit.jsonl`;
8. audit records contain a hash-linked chain.

## 11. What this does not verify yet

This clean-checkout runbook does not prove:

- production security;
- regulatory compliance;
- protection against every unsafe action class;
- production key management;
- trusted execution environment attestation;
- GPU or hardware identity;
- zkML correctness;
- model truthfulness;
- latency or throughput under load;
- full replay or dispute resolution across all related repositories.

Those are future hardening and research layers. The current claim is narrower and testable:

```text
ProofPath can reproduce an action-boundary fixture where unsafe high-risk actions are blocked before upstream execution, approved actions are forwarded, and the decisions are auditable.
```

## 12. Stop local services

When finished, stop the upstream demo server and ProofPath gateway with `Ctrl-C` in their terminals.
