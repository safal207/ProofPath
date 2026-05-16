# Compute Witness Market Value

Status: Draft v0.1

## One-line value proposition

ProofPath Compute Witness gives AI compute providers, agent platforms, and regulated AI teams a small, executable way to prove that a compute result was requested, scoped, causally authorized, decided, anchored to audit evidence, and linked to prior accepted evidence before it is trusted.

For a practical first deployment path, see [Compute Witness Pilot Integration Guide](compute-witness-pilot-guide.md).

## Market problem

AI systems increasingly perform multi-step actions where the final output is not enough.

A buyer may need to know:

- who requested the compute job;
- what intent and scope were declared;
- which prior decision authorized the job;
- which model, runtime, input, and output commitments were recorded;
- whether the verifier accepted or blocked the job;
- whether the receipt is anchored to audit evidence;
- whether a follow-up compute job actually depends on a prior accepted result.

Without this layer, teams can have useful outputs but weak evidence about authorization, continuity, and accountability.

## Buyer segments

### 1. AI compute marketplaces

Pain:

- customers need more than raw GPU availability;
- buyers want evidence that compute jobs followed declared policy;
- marketplaces need a neutral proof surface that can sit above different providers.

ProofPath value:

- compute receipts for each job;
- canonical audit hash verification;
- chainable evidence for multi-step workloads;
- a small conformance validator that can be run in CI.

First pilot:

```text
For every demo compute job, emit:
job_manifest.json
compute_receipt.json
audit_log.json

Then run:
python3 scripts/validate_compute_witness.py
```

### 2. Agent platforms

Pain:

- agents can call tools, APIs, or compute backends without enough provenance;
- it is hard to distinguish a useful result from a causally valid result;
- multi-step agent chains can drift from the original authorization.

ProofPath value:

- each compute/action boundary receives a manifest and receipt;
- blocked jobs explain the missing authorization or unsafe scope;
- child jobs must point to accepted parent receipts when they claim continuity;
- validator catches broken parent-to-child commitments.

First pilot:

```text
Wrap one agent workflow:
Plan -> Compute Step 1 -> Compute Step 2 -> Final Result

Attach ProofPath receipts to each compute step.
Reject or block any child step that cannot point to an accepted parent receipt.
```

### 3. Regulated AI adopters

Pain:

- internal teams need audit trails for high-impact AI workflows;
- logs often show what happened but not why it was allowed;
- compliance teams need inspectable evidence rather than vague model explanations.

ProofPath value:

- explicit intent and scope before execution;
- clear ACCEPT / HOLD / REJECT / BLOCK / AUDIT decisions;
- receipts that can be stored with audit evidence;
- narrow non-claims that make the system easier to review.

First pilot:

```text
Select one low-risk AI workflow.
Record job manifests, verifier decisions, compute receipts, and audit log entries.
Run conformance checks in CI before treating outputs as trusted evidence.
```

### 4. AI safety and evaluation teams

Pain:

- benchmarks often measure output quality but not authorization lineage;
- it is difficult to reproduce why a system was allowed to continue;
- trace and replay infrastructure needs stable evidence records.

ProofPath value:

- minimal fixtures for accepted, blocked, and chained compute jobs;
- executable conformance instead of prose-only claims;
- a bridge to replay, challenge, and causal memory layers.

First pilot:

```text
Add ProofPath Compute Witness fixtures to one evaluation harness.
Require all accepted multi-step runs to preserve parent receipt continuity.
Use broken-chain fixtures as negative test cases.
```

## What can be sold first

### Compute Witness Pilot Pack

A first commercial or grant-facing package can be narrow:

```text
1. Define a compute witness profile for one workflow.
2. Emit job manifests and compute receipts.
3. Anchor receipts to audit log entries.
4. Validate canonical SHA-256 audit hashes.
5. Validate one parent-to-child compute chain.
6. Produce a short audit packet for review.
```

Deliverables:

- integration guide;
- fixture set;
- validator output;
- audit packet example;
- short risk report showing accepted, blocked, and broken-chain cases.

## What this is not yet

This is not yet:

- a full zkML proof system;
- a GPU hardware attestation layer;
- a decentralized settlement protocol;
- a replacement for key management;
- a complete compliance platform;
- a guarantee that the model output is true.

The first value is narrower and easier to buy:

```text
ProofPath makes compute authorization and continuity inspectable.
```

## Minimum buyer-visible demo

The smallest useful market demo is:

```text
Case A: accepted compute job
  -> manifest present
  -> receipt accepted
  -> audit hash verified

Case B: blocked compute job
  -> missing causal parent
  -> receipt blocked
  -> audit hash verified

Case C: chained compute job
  -> parent accepted
  -> child causal_parent = receipt:<parent_receipt_id>
  -> child.input_hash == parent.output_hash
  -> audit chain verified
```

This can be shown in under five minutes and does not require a production integration.

## Positioning

Use this wording:

```text
ProofPath Compute Witness is an evidence layer for AI compute accountability.
It does not prove that every model output is correct.
It proves that a compute result was requested, scoped, causally authorized, decided, audit-anchored, and linked to prior accepted evidence before it is trusted.
```

Avoid this wording:

```text
ProofPath proves all AI computation.
ProofPath replaces zkML.
ProofPath guarantees model truth.
ProofPath proves GPU execution.
```

## Practical adoption ladder

```text
Level 0: Read the fixture docs.
Level 1: Run the conformance validator locally.
Level 2: Add CI conformance to a demo repo.
Level 3: Emit receipts from one agent or compute workflow.
Level 4: Validate parent-to-child compute continuity.
Level 5: Store audit packets for review.
Level 6: Add replay/challenge fixtures.
Level 7: Add optional TEE, zkML, or provider-specific attestations.
```

## Commercial wedge

The best first wedge is not broad AI governance.

The best first wedge is:

```text
Receipts and audit evidence for high-risk AI compute actions.
```

This wedge is small enough to implement, concrete enough to demo, and important enough for teams that need accountability before trusting agentic or compute-heavy workflows.
