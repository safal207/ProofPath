# CI/CD Deploy Gate Demo

This demo shows ProofPath as a mandatory pre-execution gate for CI/CD, release, and production deployment workflows.

It makes ProofPath useful for DevOps teams, release managers, platform engineers, SREs, and AI coding agents that can trigger deployment actions.

```text
AI/DevOps assistant proposes CI/CD action
  -> deploy or release action context is declared
  -> ProofPath checks intent, causal parent, scope, reversibility, and approval
  -> safe preview actions continue
  -> risky production actions are blocked before execution
  -> approved emergency rollback can proceed
  -> every decision is written to the audit log
```

## Core line

**Valid CI credentials should not automatically mean valid production deploy.**

A DevOps assistant may have a valid GitHub token, deploy key, CI token, or release credential. That does not mean every proposed deploy/release action should execute.

ProofPath does not replace branch protection, CI checks, deployment credentials, GitHub Actions environments, release managers, or deployment tooling. It adds an action-level decision boundary before high-risk deployment actions execute.

## Scenario

A DevOps assistant is allowed to create preview deployments.

The assistant attempts three actions:

1. a safe preview deployment;
2. a production deployment without explicit human approval;
3. an approved production rollback.

ProofPath separates these cases:

```text
preview deployment                     -> ACCEPT
production deploy without approval      -> BLOCK
approved production rollback            -> ACCEPT
```

## Run

Terminal 1: start the demo protected API.

```bash
python3 examples/upstream/demo_server.py
```

Terminal 2: start the ProofPath gateway.

```bash
cargo run -p proofpath-gateway
```

Terminal 3: run the CI/CD scenarios.

### 1. Preview deploy

```bash
bash examples/cicd-deploy-gate/cicd_preview_deploy.sh
```

Expected result:

```text
HTTP/1.1 200 OK
```

```json
{
  "forwarded": true,
  "proofpath": {
    "decision": "ACCEPT"
  }
}
```

Meaning:

```text
The action is scoped as preview deploy and reversible.
ProofPath accepts it and forwards it to the protected API.
```

### 2. Production deploy without approval

```bash
bash examples/cicd-deploy-gate/cicd_production_deploy_without_approval.sh
```

Expected result:

```text
HTTP/1.1 403 Forbidden
```

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
The assistant may have valid CI or deployment credentials.
The proposed production deployment is high-risk and lacks explicit human approval.
ProofPath blocks it before the protected API sees it.
```

### 3. Approved production rollback

```bash
bash examples/cicd-deploy-gate/cicd_approved_rollback.sh
```

Expected result:

```text
HTTP/1.1 200 OK
```

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
The rollback is high-risk, but it carries explicit human approval.
ProofPath accepts it and forwards it to the protected API.
```

## Inspect the audit trail

```bash
cat proofpath-audit.jsonl
```

Expected audit shape:

```jsonl
{"audit_id":"...","previous_hash":"GENESIS","intent_id":"intent_preview_deploy_001","causal_parent":"decision_pr_checks_passed","scope":"cicd.preview.deploy","decision":"ACCEPT","reason":null,"forwarded":true,"upstream_status":200,"hash":"sha256:..."}
{"audit_id":"...","previous_hash":"sha256:...","intent_id":"intent_production_deploy_001","causal_parent":"decision_agent_ready_to_release","scope":"cicd.production.deploy","decision":"BLOCK","reason":"IRREVERSIBLE_ACTION_REQUIRES_APPROVAL","forwarded":false,"upstream_status":null,"hash":"sha256:..."}
{"audit_id":"...","previous_hash":"sha256:...","intent_id":"intent_approved_production_rollback_001","causal_parent":"decision_human_approved_rollback","scope":"cicd.production.rollback","decision":"ACCEPT","reason":null,"forwarded":true,"upstream_status":200,"hash":"sha256:..."}
```

## Reviewer quick check

```text
1. Preview deploy returns ACCEPT.
2. Preview deploy is forwarded upstream.
3. Production deploy without approval returns BLOCK.
4. Blocked production deploy is not forwarded upstream.
5. Approved production rollback returns ACCEPT.
6. All decisions appear in the audit log.
7. Audit entries form a hash-linked chain.
```

## Suggested CI/CD action scopes

```text
cicd.preview.deploy
cicd.staging.deploy
cicd.production.deploy
cicd.production.rollback
cicd.release.publish
cicd.workflow.modify
cicd.checks.bypass
```

## Suggested approval policy

Require explicit human approval for:

- production deployment;
- production rollback;
- release publishing;
- CI/CD workflow modifications;
- bypassing required checks;
- deployment after failed or missing tests;
- changing protected deployment environments.

## What this proves

ProofPath can protect deployment workflows, not only generic API calls.

The important boundary is not whether the agent has a token. The boundary is whether the proposed deployment action is valid in context.

## Takeaway

A valid CI token, deploy key, or release credential is not the same as a valid production deployment.

ProofPath makes AI-assisted CI/CD operations reviewable before execution.
