# Evidence Packet v0.1

This packet gives reviewers a compact route through the current inspectable evidence for ProofPath, Compute Witness, and the connected evidence-gate stack.

It is designed around one question:

```text
What can a reviewer inspect or run today?
```

## One-sentence summary

Evidence Packet v0.1 turns the ecosystem from a set of claims into a small checklist of inspectable artifacts.

## Core claim

High-risk AI/agent actions should not be trusted only because a model produced them, a tool call exists, or credentials are valid.

They should pass through reviewable evidence gates before execution:

```text
proposed action
+ declared intent
+ causal authorization
+ scope
+ reversibility
+ evidence freshness
+ trace continuity
-> ACCEPT / BLOCK / ESCALATE / AUDIT
-> reviewable artifact
```

## What this packet is

This packet is a map of present evidence, not a claim of production maturity.

It separates:

```text
claim
-> current artifact
-> expected result
-> what this supports
-> what it does not prove
```

## Fast reviewer path

A reviewer can inspect the current evidence in this order:

1. ProofPath dangerous-action boundary.
2. Compute Witness manifest / receipt / verifier path.
3. CML causal-validity support layer.
4. LTP trace / replay support layer.
5. PythiaLabs ALLOW / BLOCK / ESCALATE gate surface.
6. LS / Liminal Stack reviewer packet.
7. TRC / TPU evidence plan for future larger artifact generation.

## Evidence item 1 — ProofPath dangerous action boundary

### Claim

Valid credentials are not enough. A high-risk action should be blocked before execution when evidence or approval is missing.

### Current artifact

- Demo: [`examples/agent-dangerous-action/README.md`](../examples/agent-dangerous-action/README.md)
- Gateway: [`crates/proofpath-gateway`](../crates/proofpath-gateway)
- Audit log pattern: hash-chained JSONL decisions
- Reviewer summary: [`reviewer-summary.md`](reviewer-summary.md)

### Local commands

```bash
python3 examples/upstream/demo_server.py
cargo run -p proofpath-gateway
bash examples/agent-dangerous-action/agent_delete_without_approval.sh
bash examples/agent-dangerous-action/agent_delete_with_approval.sh
cat proofpath-audit.jsonl
```

### Expected result

```text
unsafe irreversible delete without approval -> BLOCK
same action with explicit human approval -> ACCEPT
both decisions are written to audit log
```

### What this supports

- ProofPath can sit before a protected upstream API.
- It can block unsafe irreversible actions before forwarding.
- It can distinguish valid credentials from valid action context.
- It can produce auditable decision records.

### What it does not prove

- production security;
- production identity management;
- complete prevention of unsafe AI behavior;
- formal verification of all possible action paths.

## Evidence item 2 — Compute Witness verifier path

### Claim

AI/agent compute results should be packaged as reviewable evidence, not accepted as opaque outputs.

### Current artifact

- Grant reviewer path: [`COMPUTE_WITNESS_GRANT_REVIEWER_PATH.md`](COMPUTE_WITNESS_GRANT_REVIEWER_PATH.md)
- Reviewer quickstart: [`examples/compute-witness/README.md`](../examples/compute-witness/README.md)
- Python conformance fixtures
- Rust verifier adapter and CLI
- Audit-hash verification
- Broken-evidence challenge fixtures
- CI regression check: Compute Witness Rust CLI fixture

### Local inspection path

Start here:

```text
examples/compute-witness/README.md#reviewer-quickstart
```

Then inspect:

```text
job manifest
-> receipt
-> audit packet
-> verifier output
-> challenge fixture
```

### Expected result

```text
valid evidence packet -> verifier accepts
mismatched or broken evidence -> verifier rejects
canonical audit hash remains reproducible
```

### What this supports

- Compute evidence can be represented as manifests and receipts.
- Broken evidence can be detected through fixtures.
- Rust and Python paths can agree on audit-hash expectations.
- Reviewers can inspect artifacts without trusting a hidden service.

### What it does not prove

- trusted hardware attestation;
- zkML correctness;
- GPU/TPU execution proof;
- full model-truthfulness guarantees;
- production deployment readiness.

## Evidence item 3 — CML causal-validity support layer

### Claim

An action can be operationally successful while still being causally invalid.

### Current external artifact

CML repository:

```text
https://github.com/safal207/Causal-Memory-Layer
```

Relevant reviewer route:

```text
CML README
-> LS Grant Reviewer Packet 2026
-> ProofPath ecosystem graph
```

### What to inspect

- causal logs;
- valid vs broken causal chains;
- causal violation classes;
- benchmark / showcase outputs;
- why-allowed reasoning.

### Expected result

```text
valid causal lineage -> accepted / explainable
missing or broken causal parent -> violation detected
```

### What this supports

- ProofPath action boundaries can be connected to causal-validity checks.
- The ecosystem can distinguish execution success from causal authorization.
- Reviewers can inspect why an action was allowed, not only what happened.

### What it does not prove

- universal causal truth;
- complete policy coverage;
- production authorization integration;
- legal accountability by itself.

## Evidence item 4 — LTP trace / replay support layer

### Claim

Multi-step agent behavior should be traceable and replayable enough to detect drift, missing anchors, or unsupported execution paths.

### Current external artifact

LTP repository:

```text
https://github.com/safal207/L-THREAD-Liminal-Thread-Secure-Protocol-LTP-
```

Relevant reviewer route:

```text
LTP README
-> LS Grant Reviewer Packet 2026
-> ProofPath ecosystem graph
```

### What to inspect

- trace / replay examples;
- two-phase semantic inspection;
- anchor validation;
- drift detection;
- conformance fixtures;
- SDK tests.

### Expected result

```text
supported trace with anchors -> proceed / audit
missing or invalid anchor -> reject / block
semantic drift -> audit / block depending on policy
```

### What this supports

- ProofPath decisions can be placed inside a broader trace/replay model.
- Reviewers can inspect continuity, not only final output.
- Agent behavior can be regression-tested through trace fixtures.

### What it does not prove

- perfect replay of all real-world environments;
- full semantic equivalence across all models;
- production observability integration;
- final compliance certification.

## Evidence item 5 — PythiaLabs ALLOW / BLOCK / ESCALATE gate surface

### Claim

The same action-boundary pattern can be expressed as deterministic evidence gates for multiple high-risk domains.

### Current external artifact

PythiaLabs repository:

```text
https://github.com/safal207/pythiaLabs
```

Relevant reviewer docs:

```text
docs/PYTHIALABS_ONE_PAGE_SUMMARY.md
docs/OTF_REVIEWER_PATH.md
docs/PROOFPATH_CONTINUATION_FOR_REVIEWERS.md
```

### What to inspect

- infrastructure action gate;
- banking-risk action gate;
- Web3 treasury governance gate;
- OTF / internet-freedom reviewer path;
- deterministic stop reasons;
- evidence digests;
- counterfactual decision flips.

### Expected result

```text
sufficient evidence + valid context -> ALLOW
missing evidence / unsafe context -> BLOCK
uncertain or sensitive case -> ESCALATE
```

### What this supports

- Evidence gates are not limited to one demo.
- The pattern can be mapped to infrastructure, financial, governance, and internet-freedom-sensitive workflows.
- PythiaLabs provides the application-facing surface while ProofPath / Compute Witness provide the current executable evidence continuation.

### What it does not prove

- production banking integration;
- production cybersecurity protection;
- on-chain enforcement;
- legal or regulatory compliance;
- certified internet-freedom deployment.

## Evidence item 6 — LS / Liminal Stack reviewer route

### Claim

The connected repositories form a coherent evidence stack rather than isolated demos.

### Current external artifact

LS repository:

```text
https://github.com/safal207/LS
```

Key reviewer document:

```text
docs/GRANT_REVIEWER_PACKET_2026.md
```

### What to inspect

- broad reviewer packet;
- ecosystem route;
- mapping from submitted applications to current executable evidence;
- LS / ProofPath / PythiaLabs / CML / LTP roles.

### Expected result

```text
submitted application surface
-> reviewer packet
-> executable evidence hub
-> support-layer repositories
```

### What this supports

- Reviewers entering from different grants can find the same evidence core.
- The system has a clear role map.
- Older application names and newer executable work are connected.

### What it does not prove

- that all repositories are equally mature;
- that every roadmap item is implemented;
- that the stack is already a deployable product.

## Evidence item 7 — TRC / TPU evidence plan

### Claim

TRC access should be converted into durable reviewer artifacts, not treated as a standalone credential.

### Current artifact

- TRC / TPU evidence plan: [`TRC_TPU_EVIDENCE_PLAN.md`](TRC_TPU_EVIDENCE_PLAN.md)

### What to inspect

- proposed experiment tracks;
- metrics;
- artifact package structure;
- non-claims;
- mapping to Schmidt / Google.org / OTF / OpenAI / NLnet review paths.

### Expected future result

```text
TRC compute
-> repeated experiment runs
-> metrics JSON
-> audit logs
-> receipts
-> replay reports
-> reviewer summary
```

### What this supports

- TRC can become evidence-generation infrastructure.
- The next milestone is measurable and artifact-driven.
- Compute access is tied to reproducible reviewer outputs.

### What it does not prove

- Google endorsement;
- funding approval;
- production readiness;
- institutional validation;
- solved model safety.

## Minimal evidence checklist

A reviewer-friendly v0.1 evidence checklist should contain:

```text
[ ] ProofPath dangerous action demo produces BLOCK and ACCEPT cases.
[ ] ProofPath audit log records the decisions.
[ ] Compute Witness valid fixture verifies.
[ ] Compute Witness broken fixture fails.
[ ] CML demonstrates at least one causal-validity violation.
[ ] LTP demonstrates at least one trace/replay or anchor-inspection case.
[ ] PythiaLabs demonstrates ALLOW / BLOCK / ESCALATE behavior.
[ ] LS reviewer packet explains the ecosystem route.
[ ] TRC plan explains how larger evidence artifacts will be generated.
```

## Recommended reviewer interpretation

Strong interpretation:

```text
The project already has inspectable, runnable, and cross-linked evidence artifacts for action-boundary safety.
```

Bounded interpretation:

```text
The project is not yet production infrastructure, but it has a coherent evidence path and reproducible demo surface.
```

Weak interpretation to avoid:

```text
The project claims to solve all AI safety or production security problems.
```

That is not the claim.

## Non-claims

Evidence Packet v0.1 does not claim:

- production deployment;
- institutional endorsement;
- certified security;
- regulatory compliance;
- complete AI alignment;
- trusted execution attestation;
- zkML proof of correctness;
- guaranteed prevention of all unsafe actions;
- finished product maturity;
- that all roadmap components are implemented.

The narrow claim is:

```text
There is now a small, inspectable, cross-repository evidence path for high-risk AI/agent action boundaries.
```

## Next evidence milestone

The next milestone should be an actual generated artifact bundle:

```text
reports/evidence-packet-v0.2.md
reports/action-boundary-metrics.json
reports/compute-witness-conformance.json
reports/cml-causal-validity-results.json
reports/ltp-replay-results.json
reports/pythia-gate-results.json
artifacts/audit-logs/*.jsonl
artifacts/receipts/*.json
artifacts/transcripts/*.md
```

That would move the stack from:

```text
reviewer routes + demo commands
```

to:

```text
reviewer routes + generated evidence bundle
```

## Bottom line

Evidence Packet v0.1 is the first compact reviewer checklist.

It does not ask reviewers to believe the whole vision.

It asks them to inspect a small set of artifacts that already show the core pattern:

```text
high-risk action
-> evidence boundary
-> decision
-> audit artifact
-> replay / verification path
```