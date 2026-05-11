# Database Migration Gate Demo

This demo shows ProofPath as a mandatory pre-execution gate for database inspection, schema migration, and production data-change workflows.

It makes ProofPath useful for DBAs, backend teams, platform engineers, SREs, and AI agents that assist with database operations.

```text
AI/DB assistant proposes database action
  -> database action context is declared
  -> ProofPath checks intent, causal parent, scope, reversibility, and approval
  -> read-only inspection continues
  -> risky schema/data actions are blocked before execution
  -> every decision is written to the audit log
```

## Core line

**Valid DB credentials should not automatically mean valid schema or data change.**

A database assistant may have valid credentials or migration-tool access. That does not mean every proposed database action should execute.

ProofPath does not replace database permissions, IAM, network controls, backups, migration tooling, or review processes. It adds an action-level decision boundary before high-risk database actions execute.

## Scenario

A DB assistant is allowed to help with inspection.

The assistant attempts three actions:

1. a safe read-only database inspection;
2. a production schema migration without explicit human approval;
3. a production data-changing action without explicit human approval.

ProofPath separates these cases:

```text
read-only database inspection       -> ACCEPT
schema migration without approval   -> BLOCK
production data change without approval -> BLOCK
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

Terminal 3: run the database scenarios.

### 1. Read-only database inspection

```bash
bash examples/database-migration-gate/db_read_inspection.sh
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
The action is read-only, scoped as inspection, and reversible.
ProofPath accepts it and forwards it to the protected API.
```

### 2. Schema migration without approval

```bash
bash examples/database-migration-gate/db_schema_migration_without_approval.sh
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
The assistant may have valid database or migration credentials.
The proposed schema migration is high-risk and lacks explicit human approval.
ProofPath blocks it before the protected API sees it.
```

### 3. Production data change without approval

```bash
bash examples/database-migration-gate/db_data_change_without_approval.sh
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
The assistant attempts a production data-changing action without explicit approval.
ProofPath blocks the action before execution.
```

## Inspect the audit trail

```bash
cat proofpath-audit.jsonl
```

Expected audit shape:

```jsonl
{"audit_id":"...","previous_hash":"GENESIS","intent_id":"intent_read_database_schema_001","causal_parent":"decision_user_requested_db_inspection","scope":"database.read.inspect","decision":"ACCEPT","reason":null,"forwarded":true,"upstream_status":200,"hash":"sha256:..."}
{"audit_id":"...","previous_hash":"sha256:...","intent_id":"intent_change_database_schema_001","causal_parent":"decision_agent_prepared_migration","scope":"database.schema.migrate","decision":"BLOCK","reason":"IRREVERSIBLE_ACTION_REQUIRES_APPROVAL","forwarded":false,"upstream_status":null,"hash":"sha256:..."}
{"audit_id":"...","previous_hash":"sha256:...","intent_id":"intent_change_production_data_001","causal_parent":"decision_agent_prepared_data_fix","scope":"database.data.mutate","decision":"BLOCK","reason":"IRREVERSIBLE_ACTION_REQUIRES_APPROVAL","forwarded":false,"upstream_status":null,"hash":"sha256:..."}
```

## Reviewer quick check

```text
1. Read-only database inspection returns ACCEPT.
2. Read-only inspection is forwarded upstream.
3. Schema migration without approval returns BLOCK.
4. Production data change without approval returns BLOCK.
5. Blocked actions are not forwarded upstream.
6. All decisions appear in the audit log.
7. Audit entries form a hash-linked chain.
```

## Suggested database action scopes

```text
database.read.inspect
database.schema.migrate
database.index.change
database.constraint.change
database.data.mutate
database.backup.restore
database.replication.change
```

## Suggested approval policy

Require explicit human approval for:

- production schema migrations;
- production data-changing actions;
- backup restore or rollback operations;
- index/constraint changes on critical tables;
- replication or failover changes;
- actions outside an approved migration window.

## What this proves

ProofPath can protect database workflows, not only generic API calls.

The important boundary is not whether the agent has credentials. The boundary is whether the proposed database action is valid in context.

## Takeaway

A valid database credential, migration token, or admin role is not the same as a valid database change.

ProofPath makes AI-assisted database operations reviewable before execution.
