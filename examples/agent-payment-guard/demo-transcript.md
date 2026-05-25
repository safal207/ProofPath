# Demo transcript

```bash
$ python3 examples/agent-payment-guard/payment_guard.py examples/agent-payment-guard/payment_proposal.valid_micro_payment.json
{"decision":"ACCEPT","reason":"PAYMENT_WITHIN_SCOPE_AND_BUDGET"}

$ python3 examples/agent-payment-guard/payment_guard.py examples/agent-payment-guard/payment_proposal.over_budget.json
{"decision":"BLOCK","reason":"OVER_BUDGET"}

$ python3 examples/agent-payment-guard/payment_guard.py examples/agent-payment-guard/payment_proposal.recurring_without_approval.json
{"decision":"HOLD","reason":"RECURRING_PAYMENT_REQUIRES_APPROVAL"}
```
