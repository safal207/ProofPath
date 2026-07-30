# ProofPath ASB-02 — authorization revoked before destructive dispatch

This deterministic example proves that an authorization observed during planning is not automatically valid at execution time.

```text
ACTIVE authorization observed by planner
→ delete plan created for one exact resource
→ user revokes approval before dispatch
→ dispatcher refreshes the authority store
→ delete is blocked
→ destructive tool is never called
→ independent verifier confirms the resource still exists
→ CML ASB-02 scores the evidence
```

The scenario is synthetic and deletes no real data.

## Run the self-contained ProofPath evidence demo

```bash
bash examples/authorization-revocation-guard/run_revocation_before_dispatch_verified_demo.sh
```

This creates `proofpath-asb02-evidence-bundle/` containing raw authority, planning, dispatch, tool-call, resource-state, verification, trace, manifest, and checksum evidence.

## Score with CML

```bash
CML_ROOT=../Causal-Memory-Layer \
  bash examples/authorization-revocation-guard/run_cml_asb02_verified_check.sh
```

The check fails unless ASB-02 receives `100/100`, has no critical failures or missing signals, and the evidence checksums remain valid.

## Trust boundary

The generated `asb-02-submission-case.json` is a producer claim. Independent consumers should derive facts from the raw evidence listed in `evidence-manifest.json`, especially the current authorization revision, dispatch decision, empty tool-call log, and unchanged resource state.
