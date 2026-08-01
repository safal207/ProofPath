# Capability Graph

## Purpose

The Capability Graph records what the verified executor can technically do. It is separate from Intent and Policy.

```text
Capability available ≠ Capability authorized
```

A tool being installed, enabled, authenticated, or reachable never creates permission to use it.

## Required attributes

```text
capability_id
provider
action
target_scope
status
bound_subject_id
valid_from
expires_at
reversibility
authority_effect = none
```

Allowed states:

```text
ENABLED
DISABLED
REVOKED
UNKNOWN
```

## Invariants

1. The selected Capability must match the proposed action and target.
2. It must be bound to the verified executor identity.
3. Its target scope must fit inside current Intent and Policy.
4. It must be enabled and temporally valid at dispatch.
5. Capability substitution requires a fresh alignment and risk evaluation.
6. Technical ability never expands user authority.
7. Revoked, expired, unbound, or unknown capability blocks high-impact dispatch.

## Capability minimization

Prefer the narrowest capability that can satisfy the Intent:

```text
draft_text
before
send_message

read_status
before
create_or_delete

repository_comment
before
repository_write
```

A broader capability is not safer merely because it is convenient.

## Common mismatches

```text
CAPABILITY_AUTHORITY_LEAK
CAPABILITY_REVOKED
CAPABILITY_SCOPE_MISMATCH
CAPABILITY_IDENTITY_MISMATCH
CAPABILITY_SUBSTITUTED
CAPABILITY_EXPIRED
CAPABILITY_ACTION_MISMATCH
CAPABILITY_TARGET_MISMATCH
```

## Recovery

Recovery must use an authorized, identity-bound, temporally valid capability. Do not use a broader emergency tool unless current Intent and Policy explicitly authorize it.
