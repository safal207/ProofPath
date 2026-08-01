# Identity Graph

## Purpose

The Identity Graph proves who the principal, actor, and executor are at the evaluated boundary. It does not grant action authority.

```text
identity evidence
→ subject binding
→ delegation binding
→ assurance assessment
→ current / stale / mismatched
```

## Required attributes

```text
subject_id
actor_type
issuer
authenticated_at
assurance_level
credential_ref
audience
delegated_by
current
authority_effect = none
```

## Roles

- **principal** — the person or application whose Intent is authoritative;
- **actor** — the entity requesting or directing the action;
- **executor** — the agent, service, tool, or runtime that would perform it;
- **delegate** — an executor operating under an evidenced delegation chain.

One identity may fill multiple roles, but the bundle must say so explicitly.

## Invariants

1. Identity evidence is not authorization.
2. The evaluated principal must match the current Intent principal.
3. The selected executor must be current and bound to the selected Capability.
4. Delegation cannot expand scope, target, maximum effect, or validity.
5. A changed session, credential, actor, executor, or audience invalidates the previous decision.
6. Unknown identity or unknown delegation fails closed for high-impact actions.
7. Identity nodes require evidence and an authentication timestamp.

## Common mismatches

```text
IDENTITY_INTENT_MISMATCH
IDENTITY_ASSURANCE_INSUFFICIENT
DELEGATION_CHAIN_BROKEN
IDENTITY_CHANGED_AFTER_EVALUATION
IDENTITY_AUDIENCE_MISMATCH
EXECUTOR_IDENTITY_UNKNOWN
```

## Dispatch revalidation

Immediately before dispatch confirm:

```text
same principal
same actor
same executor
same credential/session lineage
same audience
identity still current
delegation still valid
```

If not, return `HOLD` or `BLOCK` and rebuild the affected graphs.
