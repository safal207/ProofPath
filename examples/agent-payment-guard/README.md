# ProofPath Agent Payment Guard

ProofPath Agent Payment Guard is a local pre-execution guard for AI-agent payments.

It does not move funds. It decides whether a proposed payment has declared intent, causal authorization, recipient scope, budget scope, and required approval before any payment rail is called.

**Stablecoin rails move value. ProofPath proves the action had the right to move value.**

Run:

```bash
bash examples/agent-payment-guard/run_demo_check.sh
```
