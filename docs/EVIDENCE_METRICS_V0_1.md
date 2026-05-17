# Evidence Metrics v0.1

This document defines the first measurable frame for ProofPath, Compute Witness, and the connected evidence-gate stack.

It is a metrics schema and baseline template, not a claim of completed benchmark results.

## One-sentence summary

Evidence Metrics v0.1 defines how future evidence packets will report measurable action-boundary, verifier, causal-validity, trace/replay, and gate-decision results.

## Why this exists

Evidence Packet v0.1 explains what reviewers can inspect today.

Evidence Metrics v0.1 defines how those artifacts should become measurable:

```text
run demo / verifier / replay
-> collect metrics
-> emit JSON
-> summarize in reviewer report
```

The goal is to move from:

```text
we have reviewer artifacts
```

to:

```text
we have reviewer artifacts with repeatable measurements
```

## Important distinction

This document defines metrics.

It does not yet claim measured results.

Use:

```text
planned_metric / observed_value / evidence_source / run_id
```

Do not report invented numbers.

## Metrics areas

Evidence Metrics v0.1 covers seven areas:

1. ProofPath action-boundary metrics.
2. Compute Witness verifier metrics.
3. CML causal-validity metrics.
4. LTP trace / replay metrics.
5. PythiaLabs gate-decision metrics.
6. CI / reproducibility metrics.
7. Reviewer artifact completeness metrics.

## 1. ProofPath action-boundary metrics

### Purpose

Measure whether high-risk actions are blocked before execution when required evidence or approval is missing.

### Metrics

| Metric | Type | Meaning |
| --- | --- | --- |
| `actions_total` | count | Total proposed actions evaluated. |
| `actions_accepted` | count | Actions accepted and forwarded. |
| `actions_blocked` | count | Actions blocked before upstream execution. |
| `actions_audited` | count | Actions allowed or recorded for audit. |
| `unsafe_without_approval_blocked` | count | Irreversible unsafe actions blocked due to missing approval. |
| `unsafe_without_approval_false_accepts` | count | Unsafe actions incorrectly accepted. Target: zero in fixtures. |
| `safe_with_approval_false_blocks` | count | Approved safe/valid cases incorrectly blocked. |
| `decision_latency_ms_p50` | number | Median decision latency. |
| `decision_latency_ms_p95` | number | p95 decision latency. |
| `audit_records_written` | count | Number of decision records written to audit log. |
| `audit_hash_chain_valid` | boolean | Whether audit chain verification passes. |

### Evidence sources

- `examples/agent-dangerous-action/`
- `proofpath-audit.jsonl`
- gateway logs
- future `reports/action-boundary-metrics.json`

### Reviewer interpretation

Strong signal:

```text
unsafe_without_approval_blocked > 0
unsafe_without_approval_false_accepts == 0
safe_with_approval_false_blocks == 0
```

Bounded claim:

```text
The fixture demonstrates action-boundary behavior for controlled scenarios.
```

Non-claim:

```text
This does not prove all unsafe actions are blocked in production.
```

## 2. Compute Witness verifier metrics

### Purpose

Measure whether compute evidence can be verified and whether broken evidence is rejected.

### Metrics

| Metric | Type | Meaning |
| --- | --- | --- |
| `manifests_total` | count | Total job manifests checked. |
| `receipts_total` | count | Total receipts checked. |
| `valid_packets_accepted` | count | Valid evidence packets accepted. |
| `invalid_packets_rejected` | count | Broken or mismatched packets rejected. |
| `audit_hash_mismatches_detected` | count | Audit-hash mismatches detected. |
| `python_conformance_pass` | boolean | Python conformance check passes. |
| `rust_verifier_pass` | boolean | Rust verifier check passes. |
| `cross_language_agreement` | boolean | Python and Rust agree on expected fixture results. |
| `challenge_fixtures_total` | count | Total challenge fixtures inspected. |
| `challenge_fixtures_failed_as_expected` | count | Intentionally broken fixtures rejected. |

### Evidence sources

- `examples/compute-witness/`
- `conformance/compute-witness/`
- `scripts/validate_compute_witness.py`
- Rust verifier / CLI output
- future `reports/compute-witness-conformance.json`

### Reviewer interpretation

Strong signal:

```text
valid_packets_accepted > 0
invalid_packets_rejected > 0
audit_hash_mismatches_detected > 0
cross_language_agreement == true
```

Bounded claim:

```text
The current fixtures demonstrate reproducible acceptance and rejection behavior.
```

Non-claim:

```text
This is not hardware attestation, zkML, or proof that a model reasoned correctly.
```

## 3. CML causal-validity metrics

### Purpose

Measure whether causal-validity failures are detected separately from operational success.

### Metrics

| Metric | Type | Meaning |
| --- | --- | --- |
| `causal_cases_total` | count | Total causal-memory cases checked. |
| `valid_lineages_accepted` | count | Causally valid chains accepted. |
| `broken_lineages_rejected` | count | Broken or missing causal chains rejected. |
| `missing_parent_detected` | count | Missing causal parent violations detected. |
| `unmarked_gap_detected` | count | Unmarked causal gaps detected. |
| `secret_to_network_violation_detected` | count | Sensitive-to-network policy violations detected. |
| `violation_classes_covered` | count | Number of violation classes covered by fixtures. |
| `causal_reconstruction_success` | boolean | Whether causal chain reconstruction works for valid fixtures. |

### Evidence sources

- CML repository
- CML benchmark / showcase outputs
- future `reports/cml-causal-validity-results.json`

### Reviewer interpretation

Strong signal:

```text
valid_lineages_accepted > 0
broken_lineages_rejected > 0
violation_classes_covered >= 2
```

Bounded claim:

```text
CML supports causal-validity inspection for controlled fixtures.
```

Non-claim:

```text
This does not prove universal causal truth or complete policy coverage.
```

## 4. LTP trace / replay metrics

### Purpose

Measure whether traces can be inspected for continuity, anchors, drift, and replay behavior.

### Metrics

| Metric | Type | Meaning |
| --- | --- | --- |
| `traces_total` | count | Total traces inspected. |
| `traces_proceeded` | count | Traces allowed to proceed. |
| `traces_rejected` | count | Traces rejected by inspection. |
| `traces_audited` | count | Traces marked for audit. |
| `missing_anchors_detected` | count | Missing anchor failures detected. |
| `invalid_anchors_detected` | count | Invalid anchor failures detected. |
| `drift_detected` | count | Semantic or replay drift detected. |
| `replay_fidelity_rate` | number | Share of traces replaying as expected. |
| `conformance_pass` | boolean | LTP conformance suite passes. |
| `inspection_latency_ms_p95` | number | p95 trace inspection latency. |

### Evidence sources

- LTP repository
- LTP conformance fixtures
- LTP inspector outputs
- future `reports/ltp-replay-results.json`

### Reviewer interpretation

Strong signal:

```text
missing_anchors_detected > 0
conformance_pass == true
replay_fidelity_rate is reported with fixture count
```

Bounded claim:

```text
LTP supports trace/replay inspection for controlled cases.
```

Non-claim:

```text
This does not guarantee perfect replay of all real-world environments.
```

## 5. PythiaLabs gate-decision metrics

### Purpose

Measure ALLOW / BLOCK / ESCALATE behavior across deterministic evidence gates.

### Metrics

| Metric | Type | Meaning |
| --- | --- | --- |
| `gate_cases_total` | count | Total gate scenarios run. |
| `allow_count` | count | Gate decisions returning ALLOW / accepted. |
| `block_count` | count | Gate decisions returning BLOCK / rejected. |
| `escalate_count` | count | Gate decisions requiring human/operator escalation. |
| `stable_stop_reasons_total` | count | Stop reasons emitted. |
| `unexpected_stop_reasons` | count | Stop reasons outside expected fixture set. |
| `counterfactual_flips_total` | count | Cases where changing one evidence field flips decision. |
| `digest_reproducibility_pass` | boolean | Evidence digests reproduce across runs. |
| `scenario_domains_covered` | count | Domains covered: infra, banking, Web3, OTF, etc. |

### Evidence sources

- PythiaLabs repository
- infrastructure action showcase
- banking-risk showcase
- Web3 treasury showcase
- OTF reviewer path
- future `reports/pythia-gate-results.json`

### Reviewer interpretation

Strong signal:

```text
gate_cases_total > 0
block_count > 0
allow_count > 0
counterfactual_flips_total > 0
unexpected_stop_reasons == 0
```

Bounded claim:

```text
PythiaLabs demonstrates deterministic evidence-gate behavior across selected domains.
```

Non-claim:

```text
This does not prove production banking, Web3, or internet-freedom deployment.
```

## 6. CI / reproducibility metrics

### Purpose

Measure whether evidence checks are reproducible in CI and not only local demos.

### Metrics

| Metric | Type | Meaning |
| --- | --- | --- |
| `ci_runs_total` | count | CI runs considered. |
| `ci_success_count` | count | Successful CI runs. |
| `ci_failure_count` | count | Failed CI runs. |
| `formatting_pass` | boolean | Formatting check passes. |
| `clippy_pass` | boolean | Rust clippy passes. |
| `tests_pass` | boolean | Rust tests pass. |
| `compute_witness_cli_fixture_pass` | boolean | Compute Witness Rust CLI fixture passes. |
| `docs_links_checked` | boolean | Future: docs links checked. |
| `reproducible_from_clean_checkout` | boolean | Future: clean-checkout reproduction status. |

### Evidence sources

- GitHub Actions workflow runs
- PR validation summaries
- CI logs
- future `reports/ci-reproducibility.json`

### Reviewer interpretation

Strong signal:

```text
formatting_pass == true
clippy_pass == true
tests_pass == true
compute_witness_cli_fixture_pass == true
```

Bounded claim:

```text
The repo is currently passing its scripted checks.
```

Non-claim:

```text
Passing CI does not prove the system is production-secure.
```

## 7. Reviewer artifact completeness metrics

### Purpose

Measure whether the reviewer packet contains enough artifacts to inspect the claim.

### Metrics

| Metric | Type | Meaning |
| --- | --- | --- |
| `reviewer_paths_total` | count | Number of reviewer path documents. |
| `evidence_docs_total` | count | Number of evidence docs. |
| `demo_commands_documented` | count | Number of documented demo command sets. |
| `expected_outputs_documented` | count | Number of expected-output artifacts. |
| `non_claim_sections_present` | boolean | Whether non-claims are explicit. |
| `cross_repo_routes_present` | boolean | Whether CML/LTP/PythiaLabs/LS routes exist. |
| `metrics_template_present` | boolean | Whether machine-readable metrics template exists. |
| `artifact_bundle_present` | boolean | Future: whether generated artifact bundle exists. |

### Evidence sources

- `docs/EVIDENCE_PACKET_V0_1.md`
- `docs/TRC_TPU_EVIDENCE_PLAN.md`
- `docs/ECOSYSTEM_GRAPH.md`
- `docs/SUBMITTED_APPLICATION_REVIEWER_BRIDGE.md`
- `reports/evidence-metrics-template-v0.1.json`

### Reviewer interpretation

Strong signal:

```text
non_claim_sections_present == true
cross_repo_routes_present == true
metrics_template_present == true
```

Bounded claim:

```text
The reviewer evidence surface is organized and inspectable.
```

Non-claim:

```text
Completeness of documents is not equivalent to empirical validation.
```

## Machine-readable template

The baseline template lives at:

```text
reports/evidence-metrics-template-v0.1.json
```

It should be copied and filled by future runs as:

```text
reports/evidence-metrics-YYYY-MM-DD-run-N.json
```

## Reporting rule

Every numeric metric should include:

```text
value
unit
source
run_id
observed_at
status: measured | planned | not_applicable
```

If a metric has not yet been measured, report:

```json
{
  "status": "planned",
  "value": null
}
```

Do not invent values.

## Minimal v0.2 target

Evidence Packet v0.2 should include at least:

```text
[ ] ProofPath action-boundary metrics JSON.
[ ] Compute Witness verifier metrics JSON.
[ ] CI reproducibility metrics JSON.
[ ] Reviewer artifact completeness JSON.
[ ] Short Markdown summary of measured vs planned metrics.
```

Optional but stronger:

```text
[ ] CML causal-validity metrics JSON.
[ ] LTP trace/replay metrics JSON.
[ ] PythiaLabs gate-decision metrics JSON.
```

## Bottom line

Evidence Metrics v0.1 creates the measurement contract.

It is the bridge from:

```text
reviewer checklist
```

to:

```text
generated evidence packet
```

The next step is to run the demos and verifiers, then fill the template with observed values.
