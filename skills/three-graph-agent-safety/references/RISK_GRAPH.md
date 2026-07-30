# Risk Graph reference

## Purpose

The Risk Graph makes possible harm, uncertainty, and mitigation explicit.

```text
Risk assessment informs the gate.
Risk assessment does not authorize the action.
```

## Required structure

```text
hazard
affected asset or person
causal path
likelihood
impact
detectability
reversibility
uncertainty
mitigation
residual likelihood
residual impact
residual tier
escalation threshold
```

## Recommended dimensions

- authorization;
- financial;
- privacy;
- security;
- reputational;
- operational;
- safety;
- secondary harm;
- irreversibility.

## Tiers

```text
low
moderate
high
critical
unknown
```

Unknown is not equivalent to low.

## Gate rules

- critical residual risk → `BLOCK` or human escalation;
- high residual risk → normally `HOLD`;
- unknown risk for an irreversible action → `HOLD`;
- moderate risk may `ACCEPT` only with current Intent, Policy allowance, and concrete mitigation;
- low risk never substitutes for missing Intent.

## Mitigation quality

A mitigation must map to a causal path.

Weak:

```text
be careful
```

Strong:

```text
require current recipient confirmation before send
bind request to intent_id and idempotency_key
perform authoritative readback before success
```

## Recovery risk

Create a second Risk branch for containment and recovery:

```text
original harm
→ proposed containment
→ possible secondary harm
→ smallest reversible alternative
```

## Negative controls

- risk omitted for irreversible action;
- critical risk accepted;
- uncertainty rounded down;
- mitigation claimed but not enforced;
- recovery risk ignored;
- low risk used as permission.
