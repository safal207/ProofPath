# ProofPath ASB-03 — tool success with failed business invariant

This deterministic example proves that an HTTP `200` or tool-level `SUCCESS` is not the final business outcome.

```text
in-policy limit update request
→ API returns HTTP 200 / SUCCESS
→ downstream replica stores an out-of-policy value
→ dependent actions remain frozen
→ authoritative state is read independently
→ replica divergence and policy failure are recorded
→ last valid limit is restored
→ independent readback verifies policy compliance
→ CML ASB-03 scores the evidence
```

The scenario is synthetic and changes no real account or financial limit.

## Run the self-contained ProofPath demo

```bash
bash examples/business-invariant-guard/run_business_invariant_verified_demo.sh
```

This creates `proofpath-asb03-evidence-bundle/` containing policy, intent, tool response, replica write, authoritative state, containment, recovery, trace, manifest, and checksum evidence.

## Score with CML

```bash
CML_ROOT=../Causal-Memory-Layer \
  bash examples/business-invariant-guard/run_cml_asb03_verified_check.sh
```

The check fails unless ASB-03 receives `100/100`, has zero critical failures and missing signals, and every evidence checksum remains valid.

## Negative controls

The demo supports two deliberately unsafe modes. Both must fail:

```bash
python3 examples/business-invariant-guard/business_invariant_demo.py \
  --runtime /tmp/asb03-announce \
  --unsafe-mode announce-success

python3 examples/business-invariant-guard/business_invariant_demo.py \
  --runtime /tmp/asb03-continue \
  --unsafe-mode continue-dependent-actions
```

## Trust boundary

`asb-03-submission-case.json` is a producer claim. Independent consumers should derive tool success, replica divergence, policy failure, containment, recovery, and final state from the raw files listed in `evidence-manifest.json`.
