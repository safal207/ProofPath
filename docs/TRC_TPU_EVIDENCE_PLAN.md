# TRC / TPU Evidence Plan

This document explains how Google TPU Research Cloud access can be used as a reviewer-facing evidence generator for the ProofPath / Compute Witness / evidence-gate research direction.

It is not a funding announcement, endorsement claim, or production-readiness claim.

## One-sentence summary

TRC access will be used to generate reproducible evidence artifacts for agent action-boundary experiments, not as a claim of production readiness or institutional endorsement.

## Why this matters

ProofPath and Compute Witness are about making high-risk AI/agent actions reviewable before they execute.

For grant reviewers, the next useful evidence is not only more prose. It is a reproducible experiment package:

```text
agent task
-> proposed high-risk action
-> evidence / authorization / scope / trace checks
-> ACCEPT / BLOCK / ESCALATE decision
-> audit artifact
-> replay / verifier output
-> benchmark report
```

TRC compute can support this by enabling larger or repeated agent-evaluation runs that produce measurable artifacts.

## Current role of TRC access

TRC access is best understood as a temporary compute resource for generating evidence.

It supports:

- repeated benchmark runs;
- model-assisted scenario generation;
- stress tests over larger task sets;
- artifact generation for reviewer packets;
- latency / overhead measurement under controlled workloads;
- reproducible traces and Compute Witness receipts.

It does not by itself prove that the system is production-ready, institutionally endorsed, or deployed.

## Research question

The practical research question is:

```text
Can action-boundary evidence gates reduce unsafe or unauditable agent actions
while preserving reviewability, replayability, and bounded overhead?
```

Sub-questions:

1. Can ProofPath block high-risk actions before they reach protected upstream systems?
2. Can Compute Witness make agent compute outputs reviewable through manifests, receipts, audit hashes, and challenge fixtures?
3. Can CML capture whether an action was causally valid, not only operationally successful?
4. Can LTP provide trace/replay continuity for multi-step agent behavior?
5. Can PythiaLabs express the same pattern as deterministic ALLOW / BLOCK / ESCALATE evidence gates?

## Proposed experiment tracks

### Track 1 — Dangerous action boundary

Goal:

```text
Show that high-risk agent/API actions can be blocked before execution when evidence is insufficient.
```

Example scenarios:

- delete production-like resource without human approval;
- deploy configuration change outside declared scope;
- execute irreversible action with missing causal parent;
- perform admin action with stale evidence;
- forward sensitive data without valid action context.

Artifacts:

- ProofPath gateway audit logs;
- accepted / blocked trace pairs;
- hash-chained decision records;
- expected-output fixtures;
- reviewer transcript.

Metrics:

- number of unsafe actions blocked;
- number of safe actions accepted;
- false block cases;
- false accept cases;
- decision latency;
- audit artifact completeness.

### Track 2 — Compute Witness reproducibility

Goal:

```text
Show that AI/agent compute results can be packaged as reviewable evidence.
```

Example scenarios:

- job manifest declares intent, scope, causal authorization, and commitments;
- receipt records result, hash, verifier status, and audit path;
- broken-evidence challenge fixtures intentionally fail;
- Rust verifier checks audit-hash consistency against canonical fixtures.

Artifacts:

- job manifests;
- receipts;
- audit packets;
- broken-evidence challenge fixtures;
- Python conformance output;
- Rust verifier output;
- CI regression report.

Metrics:

- verifier pass / fail rate;
- mismatch detection rate;
- fixture coverage;
- manifest completeness;
- audit-hash reproducibility;
- cross-language agreement between Python and Rust checks.

### Track 3 — Causal validity via CML

Goal:

```text
Show that actions can be operationally successful but causally invalid.
```

Example scenarios:

- missing parent authorization;
- unmarked causal gap;
- ambiguous root authority;
- secret-to-network chain without valid lineage;
- custom policy violation.

Artifacts:

- CML causal logs;
- causal chain reconstruction;
- benchmark results;
- violation-class report;
- links from action-boundary decisions to causal-validity checks.

Metrics:

- causal violation detection rate;
- violation class coverage;
- valid-chain acceptance rate;
- broken-lineage rejection rate;
- reproducibility across fixture runs.

### Track 4 — LTP trace / replay continuity

Goal:

```text
Show that multi-step agent behavior can be inspected through trace continuity and replay.
```

Example scenarios:

- supported trace accepted;
- unsupported trace rejected;
- drifted execution path marked for audit;
- missing anchor blocked;
- replay output compared against expected fixture.

Artifacts:

- LTP trace JSONL;
- replay reports;
- two-phase inspection outputs;
- conformance reports;
- audit bundle.

Metrics:

- replay fidelity;
- unsupported-path rejection rate;
- drift detection rate;
- conformance pass rate;
- inspection latency.

### Track 5 — PythiaLabs evidence-gate framing

Goal:

```text
Show the same action-boundary pattern as deterministic ALLOW / BLOCK / ESCALATE gates.
```

Example scenarios:

- infrastructure action gate;
- banking-risk action gate;
- Web3 treasury governance gate;
- OTF / internet-freedom-sensitive action gate;
- counterfactual evidence change flips decision.

Artifacts:

- deterministic gate outputs;
- stable stop reasons;
- demo transcripts;
- evidence digests;
- reviewer-facing expected output files.

Metrics:

- ALLOW / BLOCK / ESCALATE distribution;
- stop-reason stability;
- counterfactual decision flip correctness;
- digest reproducibility;
- scenario coverage.

## Reviewer-facing output package

A complete evidence package should include:

```text
reports/trc-evidence-summary.md
reports/action-boundary-metrics.json
reports/compute-witness-conformance.json
reports/cml-causal-validity-results.json
reports/ltp-replay-results.json
reports/pythia-gate-results.json
artifacts/audit-logs/*.jsonl
artifacts/receipts/*.json
artifacts/fixtures/*.json
artifacts/transcripts/*.md
```

The key reviewer question is:

```text
Can another person inspect what was proposed, why it was allowed or blocked,
and whether the result is reproducible?
```

## How this strengthens active review paths

### Schmidt / Trustworthy AI style review

Evidence value:

- deterministic oversight for agent traces;
- action-boundary experiments;
- causal memory and replayable artifacts;
- measurable failure classes.

### Google.org / AI safety or public-benefit review

Evidence value:

- open-source safety infrastructure;
- reproducible demonstrations;
- concrete public-benefit tooling path;
- reusable evidence artifacts rather than closed demos.

### OTF / internet-freedom review

Evidence value:

- review gates for sensitive automation;
- explicit ALLOW / BLOCK / ESCALATE decisions;
- open-source artifacts small teams can inspect;
- non-proprietary evidence workflow for civil-society tooling.

### OpenAI Security Grant style review

Evidence value:

- pre-execution action boundary;
- prevention of unsafe tool use before protected systems are reached;
- audit artifacts for AI-agent actions;
- challenge fixtures for broken evidence.

### NLnet / open-source infrastructure review

Evidence value:

- libre reusable components;
- reproducible local verifier paths;
- protocol-shaped evidence rather than one-off app logic;
- clear non-claims and bounded implementation scope.

## Non-claims

TRC access does not mean:

- Google endorsement;
- production deployment;
- production security validation;
- certified safety;
- regulatory compliance;
- model-provider integration;
- guaranteed performance at scale;
- solved AI alignment;
- trusted execution environment attestation;
- zkML proof of correctness;
- funding approval from any grantmaker.

The narrow claim is:

```text
TRC compute can help generate larger, repeated, and more reviewer-useful evidence artifacts for action-boundary experiments.
```

## Minimal first milestone

The first useful milestone is not a large benchmark. It is a clean reviewer packet.

Deliver:

```text
1. One ProofPath dangerous-action benchmark run.
2. One Compute Witness manifest / receipt / verifier run.
3. One CML causal-validity fixture report.
4. One LTP trace / replay fixture report.
5. One PythiaLabs ALLOW / BLOCK / ESCALATE demo report.
6. One combined summary explaining what passed, what failed, and what remains out of scope.
```

Success criterion:

```text
A reviewer can inspect the artifacts without trusting a hidden service or private notebook.
```

## Practical next steps

1. Define a fixed scenario set.
2. Run local baselines first.
3. Use TRC compute for repeated runs and model-assisted scenario generation.
4. Export all results as JSON / JSONL / Markdown artifacts.
5. Add CI or scriptable replay commands where possible.
6. Summarize results in a grant-reviewer evidence packet.

## Bottom line

TRC access is useful only if it becomes evidence.

The goal is to convert temporary compute into durable reviewer artifacts:

```text
compute resource
-> reproducible experiments
-> inspectable artifacts
-> reviewer confidence
-> stronger grant case
```
