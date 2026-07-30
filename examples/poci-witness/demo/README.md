# PoCI v0.1 runnable evidence demo

This reviewer demo verifies one bounded action, then verifies a second envelope whose observed-result digest was substituted.

## Run

From the repository root:

```bash
python3 examples/poci-witness/run_demo.py --check
```

Expected result:

```text
PoCI v0.1 evidence demo
valid-action.accept.json -> ACCEPT (primary=None)
result-digest-mismatch.challenge.json -> CHALLENGE (primary=RESULT_DIGEST_MISMATCH)
portable reports: accept-report.json, challenge-report.json, demo-summary.json
PASS evidence accepted; tampering challenged
```

The default output directory is `artifacts/poci-demo/`. It contains the full normalized ACCEPT and CHALLENGE reports, a compact summary, and the transcript. The same files are uploaded by the PoCI GitHub Actions workflow.

## Story

```text
signed intent
  -> bounded proposal
  -> authority and causal checks
  -> execution receipt
  -> observed result
  -> witness evaluation
  -> offline ACCEPT
  -> substitute the claimed result digest
  -> offline CHALLENGE
```

See `architecture.mmd` for the diagram source.

## What this proves

- the verifier recomputes the outcome rather than trusting the embedded verdict;
- a valid fixture produces deterministic `ACCEPT` output;
- a result commitment mismatch produces `CHALLENGE` with a stable reason code;
- the reports can be generated without a running gateway or network call.

## What this does not prove

The mock scenario does not prove model truthfulness, hardware identity, witness independence, execution inside a TEE, zkML correctness, or objective real-world truth.
