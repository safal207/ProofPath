# Model guardrail bypass is not an action-security boundary

If guardrails can be removed from the model, guardrails must move to the action boundary.

ProofPath does not need to prove that a model is safe. It verifies whether a proposed action is authorized before execution.

## Threat summary

Model-level refusal behavior is useful but fragile as a sole security control. In deployed systems, safety behavior can be removed, bypassed, degraded, or lost after deployment, especially when a model is open-weight, fine-tuned, proxied through intermediaries, or swapped for another model.

ProofPath explicitly assumes model behavior may be untrusted, partially compromised, or operationally changed over time.

## Boundary failure pattern

```text
model says action is OK
  -> agent runtime trusts model output
  -> tool/API/payment action executes
  -> no independent action authorization exists
```

Failure:

```text
model output was treated as permission
```

## ProofPath boundary pattern

```text
model proposes action
  -> ProofPath checks declared intent
  -> ProofPath checks causal parent
  -> ProofPath checks scope
  -> ProofPath checks approval/reversibility/risk
  -> ACCEPT / HOLD / BLOCK
  -> only ACCEPT reaches protected upstream
```

## Core invariants

```text
model output is a proposal, not authorization
valid model response != valid action
valid credential != valid action
valid tool access != valid execution permission
```

## Examples of protected action boundaries

ProofPath-style action authorization can protect boundaries such as:

- code execution;
- production deployment;
- database mutation;
- infrastructure change;
- payment proposal;
- data export;
- account or permission change.

## Non-claims

ProofPath does not claim:

```text
to make models safe
to prevent all harmful model outputs
to detect all jailbreaks
to replace model alignment
to replace sandboxing, IAM, endpoint security, or monitoring
to provide production certification in v0.1
```

## Relationship to existing demos

This threat note aligns with repository examples that demonstrate external action-boundary checks:

- [Dangerous action demo](../../examples/agent-dangerous-action/)
- [Personal Agent Guard demo](../../examples/personal-agent-guard/)
- [Agent payment guard demo](../../examples/agent-payment-guard/) *(if/when available)*
