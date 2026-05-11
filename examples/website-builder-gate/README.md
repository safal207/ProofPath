# Website Builder Gate Demo

This demo shows ProofPath as a mandatory pre-execution gate for AI-assisted website building.

It moves ProofPath from a generic protected API example into a practical workflow:

```text
AI builds or edits a website
  -> proposes a file/deploy/action change
  -> ProofPath checks intent, causal parent, scope, reversibility, and approval
  -> safe actions continue
  -> risky actions are blocked before execution
  -> every decision is written to the audit log
```

## Core line

**Valid deploy access should not automatically mean valid website change.**

A website-building agent may have a valid GitHub token, deployment credential, or API key. That does not mean every proposed website change should execute.

ProofPath does not replace GitHub auth, deployment credentials, HTTPS, IAM, or CI/CD controls. It adds an action-level decision boundary before high-risk website changes execute.

## Scenario

A site-builder agent is allowed to help with a landing page.

The agent attempts three actions:

1. a safe content edit;
2. a production deployment without explicit human approval;
3. a destructive website asset change without explicit human approval.

ProofPath separates these cases:

```text
safe content edit                         -> ACCEPT
production deploy without approval        -> BLOCK
destructive asset change without approval -> BLOCK
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

Terminal 3: run the website-builder scenarios.

### 1. Safe content edit

```bash
bash examples/website-builder-gate/site_edit_headline.sh
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
The action has declared intent, causal parent, scope, and reversible classification.
ProofPath accepts the action and forwards it to the protected API.
```

### 2. Production deploy without approval

```bash
bash examples/website-builder-gate/site_deploy_production_without_approval.sh
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
The agent may have deploy credentials.
The proposed production deploy is irreversible or high-risk and lacks human approval.
ProofPath blocks it before the protected API sees it.
```

### 3. Destructive website asset change without approval

```bash
bash examples/website-builder-gate/site_destructive_asset_change_without_approval.sh
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
The agent attempts a destructive website asset change without explicit approval.
ProofPath blocks the action before execution.
```

## Inspect the audit trail

```bash
cat proofpath-audit.jsonl
```

Expected audit shape:

```jsonl
{"audit_id":"...","previous_hash":"GENESIS","intent_id":"intent_update_landing_headline_001","causal_parent":"decision_user_requested_site_copy_update","scope":"website.content.edit","decision":"ACCEPT","reason":null,"forwarded":true,"upstream_status":200,"hash":"sha256:..."}
{"audit_id":"...","previous_hash":"sha256:...","intent_id":"intent_deploy_production_001","causal_parent":"decision_agent_ready_to_deploy","scope":"website.deploy.production","decision":"BLOCK","reason":"IRREVERSIBLE_ACTION_REQUIRES_APPROVAL","forwarded":false,"upstream_status":null,"hash":"sha256:..."}
{"audit_id":"...","previous_hash":"sha256:...","intent_id":"intent_replace_public_assets_001","causal_parent":"decision_agent_cleanup_assets","scope":"website.delete","decision":"BLOCK","reason":"IRREVERSIBLE_ACTION_REQUIRES_APPROVAL","forwarded":false,"upstream_status":null,"hash":"sha256:..."}
```

## Reviewer quick check

```text
1. Safe website copy edit returns ACCEPT.
2. Safe edit is forwarded upstream.
3. Production deploy without approval returns BLOCK.
4. Destructive website asset change without approval returns BLOCK.
5. Blocked actions are not forwarded upstream.
6. All decisions appear in the audit log.
7. Audit entries form a hash-linked chain.
```

## Suggested website action scopes

```text
website.content.edit
website.asset.add
website.form.modify
website.script.add
website.env.modify
website.deploy.preview
website.deploy.production
website.delete
```

## Suggested approval policy

Require explicit human approval for:

- production deployment;
- deletion or replacement of pages/assets;
- modifying environment/secrets files;
- adding unapproved third-party scripts;
- changing payment/contact/data-collection forms;
- disabling security headers or privacy notices.

## What this proves

ProofPath can protect website-building workflows, not only generic API calls.

The important boundary is not whether the agent has credentials. The boundary is whether the proposed website action is valid in context.

## Takeaway

A valid GitHub token, deploy key, or API credential is not the same as a valid website change.

ProofPath makes AI-assisted website changes reviewable before execution.
