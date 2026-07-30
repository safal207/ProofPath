# Memory Graph reference

## Purpose

The Memory Graph makes prior context reviewable without confusing it with current authority or present reality.

```text
Memory = past or retrieved context
Memory ≠ current Intent
Memory ≠ current Fact
```

## Required node fields

```text
memory_id
claim
source_type = user_statement | inferred | external_record | system_record
source_ref
recorded_at
retrieved_at
subject
scope
purpose
confidence
freshness
conflict_state
evidence_refs
authority_effect = none
```

## Freshness

```text
fresh    — still within a justified freshness window
aging    — usable only with caution or confirmation
stale    — must not drive a high-impact decision
unknown  — freshness cannot be established
```

Freshness must be derived from the domain. A delivery address may become stale quickly; a stable writing preference may change slowly.

## Conflict states

```text
clear
conflicted
superseded
```

Current explicit user instructions supersede remembered preferences.

## Permitted influence

Memory may help:

- personalize tone;
- avoid asking a question already answered;
- rank reversible options;
- recover prior project terminology;
- identify a likely file, repository, or workflow to inspect;
- make a proposal more relevant.

Memory may not authorize:

- sending or publishing;
- payments or purchases;
- deletion or destructive change;
- sharing private data;
- accepting legal or financial terms;
- changing recipients, targets, or scope;
- merging or releasing code.

## Retrieval minimization

Retrieve the narrowest context required by the present task.

Bad:

```text
User mentioned Anna → retrieve all relationship, career, location, and profile context
```

Good:

```text
User asks to reply to Anna's email → retrieve the exact email thread and current reply intent
```

## Inference boundary

An inferred preference must be labeled as inferred and carry lower confidence than a direct current statement.

```text
direct current statement > direct historical statement > inferred pattern
```

None of them become authority without current Intent when a side effect is involved.

## Memory decision rules

- stale + high impact → `HOLD`;
- conflicted + unresolved → `HOLD`;
- memory used as authority → `BLOCK`;
- unrelated sensitive retrieval → `BLOCK` or omit;
- current Intent conflicts with memory → current Intent wins;
- no provenance → exclude the Memory node.

## Negative controls

- remembered recipient used to send without current approval;
- remembered budget treated as purchase authority;
- inferred preference exposed as a fact;
- stale address used for delivery;
- unrelated private context retrieved;
- memory conflict silently ignored.
