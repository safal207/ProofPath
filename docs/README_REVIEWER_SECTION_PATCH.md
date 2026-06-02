# Suggested README Patch

Add this section near the top of the ProofPath README.

```markdown
## NGI TALER reviewer path

ProofPath Agent Payment Guard was submitted to NGI TALER as an open-source auxiliary layer for privacy-preserving AI-agent payment authorization.

Start here:

- [`docs/NGI_TALER_REVIEWER_PATH.md`](docs/NGI_TALER_REVIEWER_PATH.md)
- [`docs/TALER_ALIGNMENT.md`](docs/TALER_ALIGNMENT.md)
- [`docs/AGENT_PAYMENT_GUARD_DEMO.md`](docs/AGENT_PAYMENT_GUARD_DEMO.md)
- [`docs/BUDGET_AND_MILESTONES.md`](docs/BUDGET_AND_MILESTONES.md)

Reviewer quick commands:

```bash
bash examples/agent-payment-guard/run_demo_check.sh
bash examples/agent-payment-guard/run_service_check.sh
bash examples/agent-payment-guard/run_e2e_evidence_demo.sh
bash examples/agent-payment-guard/run_mock_rail_demo.sh
```

Grant metadata:

```text
Application: 2026-08-00b
Fund: NGI TALER
Requested amount: EUR 50,000
Correct repository: https://github.com/safal207/ProofPath
```
```
