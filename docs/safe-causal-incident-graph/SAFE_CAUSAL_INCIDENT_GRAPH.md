# SAFE Causal Incident Graph (SCIG)

**Version:** 0.1  
**Status:** Experimental proposal  
**Project:** ProofPath

SCIG is a machine-readable causal state-transition model for AI incidents and near misses. It complements incident-sharing formats and telemetry systems by connecting observed evidence to the question: **why was this action possible, which control failed, what contained the outcome, how was recovery performed, and how was the fix verified?**

## Canonical model

```text
actor
→ action
→ pre_state
→ control
→ transition
→ post_state
→ invariant
→ violation
→ cause
→ containment
→ recovery
→ verification
→ evidence
```

Every relevant object SHOULD carry or reference the following dimensions when available:

```text
phase + time + provenance + trace_reference + evidence_reference
```

This is the ProofPath canonical safety chain:

```text
state + causality + phase + transition + time + recovery + verification + evidence
```

## 1. Goals

SCIG makes an incident or near miss:

- reconstructable;
- causally explainable;
- queryable;
- reproducible;
- mechanically verifiable;
- traceable back to preserved evidence.

SCIG does not replace OpenTelemetry or an incident-sharing format. Telemetry remains the observation transport; SCIG provides the causal and verification semantics over those observations.

## 2. Core objects

### Actor

Entity capable of initiating or influencing an action, for example an AI agent, human, service, scheduler, tool, workflow, or model.

### Action

Attempted or completed operation such as a tool call, network request, credential use, filesystem write, command execution, delegation, or policy change.

### Pre-state and post-state

Observable system conditions before and after a transition.

### Control

A mechanism intended to constrain behaviour, such as authorization, sandboxing, capability policy, network filtering, approval gates, tool permissions, identity scope, or rate limits.

A control SHOULD declare its expected defensive outcome.

### Transition

A first-class state change:

```text
(pre_state, action, conditions) → post_state
```

Transitions SHOULD record `phase`, `observed_at`, and ordering information.

### Invariant

A safety property expected to remain true across a specified scope.

Example:

```text
A restricted agent MUST NOT establish an authenticated external network session.
```

Invariant result values in v0.1 are:

- `held`
- `violated`
- `unknown`

### Violation

A violation exists when an observed state or transition contradicts an invariant.

### Cause

SCIG distinguishes temporal correlation from causal contribution. v0.1 causal edge vocabulary:

- `enabled_by`
- `required`
- `triggered`
- `bypassed`
- `failed_to_prevent`
- `amplified`
- `masked`
- `recovered_by`
- `verified_by`

### Containment

Action or control that prevents an unsafe condition from expanding. Containment success does **not** imply remediation success.

### Recovery

Movement from unsafe/degraded state into an explicitly defined acceptable target state.

### Verification

Evidence-backed determination that remediation restored the intended safety property.

Preferred form:

```text
previous failing path
→ replay or equivalent test
→ unsafe transition no longer reachable
→ invariant holds
→ evidence preserved
```

### Evidence

A reference to an authoritative artifact such as a trace/span, log, policy decision, configuration snapshot, file hash, network event, human approval, test result, or attestation.

SCIG references source evidence rather than duplicating it.

## 3. Phase model

Suggested phase vocabulary:

- `planning`
- `reasoning`
- `authorization`
- `execution`
- `observation`
- `verification`
- `containment`
- `recovery`

Phase is important because an unsafe plan, unsafe authorization, and unsafe execution represent materially different control failures.

## 4. Temporal and causal ordering

Wall-clock time alone is insufficient for distributed systems. Implementations SHOULD preserve `observed_at` and MAY include:

- sequence numbers;
- trace/span parentage;
- logical clocks;
- causal parent IDs.

SCIG treats chronological order and causal order as related but distinct.

## 5. OpenTelemetry mapping

SCIG evidence and transitions MAY reference OpenTelemetry identifiers:

```json
{
  "trace_reference": {
    "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
    "span_id": "00f067aa0ba902b7"
  }
}
```

This allows existing observability systems to retain evidence while SCIG adds causal interpretation.

## 6. SAFE mapping

SCIG is designed to complement SAFE-style incident and near-miss exchange:

```text
preserved incident evidence
        ↓
SCIG causal reconstruction
        ↓
root cause / failed control
        ↓
reproducible test
        ↓
recovery + verification
        ↓
evidence-backed safety claim
```

SCIG focuses on:

- how observations relate causally;
- which transition created the unsafe state;
- which control was expected to prevent it;
- which invariant held or failed;
- what contained the outcome;
- how recovery was performed;
- how remediation was independently verified.

## 7. Query: Why was this action possible?

A conforming implementation SHOULD be able to return an evidence-backed causal path for an action or invariant violation.

Example:

```text
Agent requested external access
↓ enabled_by
Credential appeared in tool output
↓ failed_to_prevent
Capability policy evaluated incomplete context
↓
External request attempted
↓
INV-CRED-001 violated
↓ recovered_by
Credential revoked
↓ verified_by
Replay test passed
```

A useful machine-oriented abstraction is:

```text
PATH(invariant_violation ← caused_by* ← action)
```

## 8. Near-miss semantics

A near miss SHOULD preserve failed primary controls and successful secondary controls separately.

Example:

```text
INV-CRED-001 = violated
INV-NET-001  = held
```

The correct conclusion is not merely "no breach occurred". The useful reusable finding is:

```text
primary control failed + secondary containment succeeded
```

## 9. Verification rules

SCIG v0.1 verifier checks:

1. required top-level structure is present;
2. schema version is `0.1`;
3. at least one invariant exists;
4. at least one evidence object exists;
5. invariant results use the canonical vocabulary;
6. transition references pre/post states;
7. containment/recovery/verification results use explicit outcomes;
8. causal edges contain source, target, and causal type;
9. verification cannot be considered passed when recovery is absent or failed;
10. a report is emitted with invariant and lifecycle status.

## 10. Minimal output

```text
SCIG SAFE-SCIG-2026-0001
INV-CRED-001   VIOLATED
INV-NET-001    HELD
CONTAINMENT    PASSED
RECOVERY       PASSED
VERIFICATION   PASSED
RESULT         VALID
```

## 11. Non-goals

SCIG v0.1 does not define:

- a replacement for OpenTelemetry;
- a universal telemetry transport;
- confidential disclosure governance;
- vulnerability severity scoring;
- a complete policy language;
- model chain-of-thought representation.

Only externally observable and auditable system behaviour belongs in the graph.

## 12. Security principle

A safety claim without evidence is an assertion.  
A control without verification is an assumption.  
A recovered system without a reproducible test is an unverified state.

Therefore:

```text
STATE
+ CAUSE
+ TRANSITION
+ TIME
+ CONTROL
+ RECOVERY
+ VERIFICATION
+ EVIDENCE
= VERIFIABLE SAFETY CLAIM
```

## 13. Reference artifacts

- Schema: `schemas/safe-causal-incident-graph-v0.1.schema.json`
- Example: `examples/safe-near-miss.json`
- Verifier CLI: `proofpath-scig`

Run from repository root:

```bash
cargo run -p proofpath-verifier --bin proofpath-scig -- examples/safe-near-miss.json
cargo test -p proofpath-verifier --bin proofpath-scig
```
