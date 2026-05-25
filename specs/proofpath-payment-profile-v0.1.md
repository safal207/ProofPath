# ProofPath Payment Profile v0.1

Deterministic guard profile for `agent_payment` proposals.

Rules: validate action type, allowed assets, decimal amount/budget, required intent fields, recipient scope, recurring approvals, and write one decision record per proposal to `.proofpath/audit.jsonl`.
