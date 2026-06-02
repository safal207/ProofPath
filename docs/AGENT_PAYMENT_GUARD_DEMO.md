# Agent Payment Guard Demo

## Goal

This demo shows that an AI-agent payment proposal is not automatically allowed to execute.

ProofPath evaluates the proposal before execution and produces a decision with evidence.

## Core story

```text
Model output is a proposal.
Signed human intent is authorization.
Policy decides whether execution is allowed.
Evidence explains the decision.
```

## Demo scenarios

### Scenario 1 — valid signed intent

Expected result:

```text
decision: ACCEPT
execution_allowed: true
```

Reason:

- signed intent exists;
- nonce is fresh;
- payment proposal is within policy;
- recipient is allowed;
- asset is allowed;
- amount is within budget.

### Scenario 2 — replayed intent

Expected result:

```text
decision: BLOCK
reason: INTENT_REPLAYED
execution_allowed: false
```

Reason:

- the same signed envelope was already used;
- replaying it must not allow a second payment.

### Scenario 3 — policy violation

Expected result:

```text
decision: HOLD or BLOCK
execution_allowed: false
```

Reason can include:

- recipient not in scope;
- amount exceeds budget;
- asset not allowed;
- recurring approval missing;
- intent expired.

### Scenario 4 — evidence export

Expected result:

```text
evidence bundle created
audit log chain valid
offline verification OK
```

Reason:

- decisions should be portable;
- reviewers should be able to validate evidence without trusting a live server.

## Suggested commands

```bash
bash examples/agent-payment-guard/run_demo_check.sh
bash examples/agent-payment-guard/run_service_check.sh
bash examples/agent-payment-guard/run_e2e_evidence_demo.sh
bash examples/agent-payment-guard/run_mock_rail_demo.sh
```

## Expected E2E shape

```text
[e2e] step 1 — valid signed intent: ACCEPT
  decision: ACCEPT
  execution_allowed: true

[e2e] step 2 — replay same envelope: BLOCK / INTENT_REPLAYED
  decision: BLOCK
  execution_allowed: false

[e2e] step 3 — export evidence bundle
  bundle ready

[e2e] step 4 — verify bundled audit log
  audit log: OK
```

## What reviewers should inspect

- Does the replay store persist across service restarts?
- Is `BLOCK` enforced before mock payment rail execution?
- Is evidence export deterministic enough to verify?
- Are private details avoided or minimized in the evidence bundle?
- Are non-claims clearly documented?
- Is the API contract simple enough for integration?

## Deliverable target

After the grant, this demo should become a stable reference path:

```text
proposal.json
intent-envelope.json
policy.json
audit.jsonl
evidence-bundle/
proofpath verify evidence-bundle/
```

The desired reviewer experience:

```bash
proofpath evaluate proposal.json --intent intent.json --policy policy.json
proofpath export-evidence --audit .proofpath/audit.jsonl --out proofpath-evidence-bundle/
proofpath verify proofpath-evidence-bundle/
```
