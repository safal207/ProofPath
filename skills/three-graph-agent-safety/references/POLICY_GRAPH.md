# Policy Graph reference

## Purpose

The Policy Graph captures external rules separately from user Intent.

```text
Intent answers: what did the user authorize?
Policy answers: what rules allow, deny, or constrain it?
```

## Required node fields

```text
policy_id
revision
issuer
valid_from
valid_until
rule_id
condition
effect
precedence
evidence_refs
```

Effects:

```text
ALLOW
DENY
CONSTRAIN
REQUIRE_APPROVAL
```

## Invariants

- A policy cannot create user Intent.
- A permissive policy plus missing Intent still yields `HOLD` or `BLOCK`.
- A mandatory denial overrides an otherwise valid proposal.
- Policy revision must be refreshed at the execution boundary for mutable high-impact rules.
- Conflicting rules require explicit precedence.
- Unknown policy state is not implicit allow.

## Common policy sources

- application policy;
- organization security policy;
- account limits;
- consent and privacy rules;
- communication rules;
- repository branch protection;
- payment or spending limits;
- jurisdictional or contractual constraints.

## Decision rules

```text
intent missing + policy allow = HOLD
intent current + policy deny = BLOCK
intent current + policy require approval + approval missing = HOLD
intent current + policy constrain + proposal outside constraint = BLOCK
policy unavailable for high-impact action = HOLD
```

## Negative controls

- stale policy revision;
- lower-precedence allow overriding mandatory deny;
- policy allow treated as user consent;
- missing policy silently interpreted as allow;
- recovery bypassing the original policy.
