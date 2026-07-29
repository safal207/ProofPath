---
name: agent-action-safety-chain
description: Audits and completes defensive AI-agent action chains across repositories and workflows. Use when the user asks to inspect agent security, causal traces, approval lineage, replay protection, dangerous tool calls, sandbox boundaries, GitHub repositories, CI evidence, or to build a full proposal-to-guard-to-execution-to-audit-to-evidence chain. Works with NOOA, Codex, Claude Code, LangGraph, AutoGen, CrewAI, MCP, custom agents, and provider-neutral tool-calling systems.
license: MIT
compatibility: Best with GitHub access and code execution. Can operate in audit-only mode from pasted files or repository links. Live side effects require an external sandbox or VM.
metadata:
  author: safal207
  version: "1.0.0"
  source-project: ProofPath
---

# Agent Action Safety Chain

Build or audit a defensive, evidence-first chain for AI-agent actions.

## Core invariant

Treat every model output as a **proposal**, never as authorization.

```text
agent proposal
→ authority and policy evaluation
→ ACCEPT / HOLD / BLOCK
→ side effect only after ACCEPT
→ observation separate from authorization
→ causal and replay traces
→ durable evidence
→ independent verification
```

## Activate this skill when

Use this skill when the user asks to:

- audit an AI-agent repository or tool-calling workflow;
- detect unsafe, unsupported, drifting, or irreversible actions;
- add intent, causal-parent, approval, scope, nonce, replay, or secret-egress checks;
- connect an agent runtime to ProofPath, CML, LTP, LiminalDB, or evidence bundles;
- build a complete guarded execution chain;
- inspect CI, review comments, failures, and merge readiness;
- turn an existing safety concept into runnable code, tests, documentation, and a PR.

Do not activate for ordinary code review with no agent/action/security component.

## Operating modes

Infer the narrowest mode that satisfies the request.

1. **Audit only** — inspect and report; do not write.
2. **Plan** — produce architecture, gaps, risks, and ordered implementation steps.
3. **Implement** — create a branch and code only when the user explicitly asks to build, fix, or complete.
4. **Validate** — run tests, inspect CI, review findings, and repair failures.
5. **Merge** — merge only when the user explicitly asks to merge, finish end-to-end, or otherwise clearly authorizes completion through merge.

Never silently expand audit-only work into repository writes.

## Required workflow

### 1. Resolve the target

Identify the repository or files, agent/runtime, side-effect boundary, protected assets, expected output, and whether writes are authorized. When connected GitHub data can resolve ambiguity, inspect it before asking questions.

### 2. Inventory before inventing

Search the target and related repositories for existing policy engines, guards, gateways, trace formats, causal records, replay stores, ledgers, evidence manifests, sandbox adapters, CI workflows, threat models, tests, and reviewer paths. Prefer integration over creating another protocol or repository.

### 3. Model the action proposal

Require an explicit proposal containing at least:

```text
trace_id
span_id
parent_span_id
agent
method
intent_id
parent_cause
action
scope
target
reversibility
approval_ref
nonce
contains_secret
destination
metadata
```

Security-critical values must come from the application or authority layer, not be guessed from model prose.

### 4. Evaluate before execution

Apply these checks:

1. `intent_id` exists.
2. `parent_cause` exists.
3. `nonce` exists and has not been consumed.
4. `scope` is allowed.
5. Irreversible or configured high-trust actions have human approval.
6. Network operations use scope as the primary signal, not only action-name matching.
7. Secret-bearing egress targets an allowed destination and has valid lineage.
8. Action arguments are bound to a digest when practical.
9. Unsafe bundle identifiers cannot escape the evidence root.
10. Unknown high-impact actions fail closed.

Decision meanings:

- `ACCEPT` — executor may run.
- `HOLD` — structurally valid but waiting for approval or revalidation.
- `BLOCK` — malformed, unauthorized, replayed, out of scope, or risk-denied.

`HOLD` and `BLOCK` must produce `side_effect_executed=false`.

### 5. Execute safely

Before invoking the executor:

- consume the nonce atomically;
- record the authorization decision;
- keep the actual executor inside an external sandbox, container, VM, or equivalent containment layer;
- do not describe an in-process policy check as a sandbox;
- preserve evidence if nonce consumption or executor execution fails.

### 6. Record independent evidence layers

Keep these dimensions separate:

```text
authorization
observation
response integrity
causal audit
continuity decision
```

Export, where applicable:

- ProofPath authorization decision;
- CML-compatible causal records and findings;
- LTP-style replay trace;
- LiminalDB-style hash-linked ledger handoff;
- intent/action/result/verification evidence roles;
- exact manifest with byte size and SHA-256;
- independent bundle-verification result.

Use unique bundle directories so retries or replays cannot overwrite earlier evidence.

### 7. Test negative paths first

At minimum cover:

- safe reversible action → `ACCEPT`;
- irreversible action without approval → `HOLD`;
- missing intent → `BLOCK`;
- missing causal parent → `BLOCK`;
- missing nonce → `BLOCK`;
- consumed nonce → `BLOCK / INTENT_REPLAYED`;
- secret egress to unknown destination → `BLOCK` plus causal finding;
- approved egress to allow-listed destination → `ACCEPT`;
- alias precedence uses real span data before defaults;
- path traversal in `span_id` cannot escape evidence root;
- nonce race preserves evidence and does not execute the side effect;
- tampered evidence fails verification.

No test may read a real secret, exfiltrate data, or perform an offensive action.

### 8. Validate the whole chain

Run focused unit tests, repository-wide tests, formatting and linting, CI workflows, evidence-bundle verification, and review-thread inspection.

Measure:

```text
total cases
matched decisions
detection rate
false positives
false negatives
evidence completeness
executed cases
replay stability
```

Never generalize synthetic fixture results into production security guarantees.

### 9. Review and finish

Before completion:

- inspect all unresolved review threads;
- verify each finding against current code;
- fix valid issues;
- explain briefly why invalid findings were skipped;
- rerun relevant checks;
- confirm mergeability;
- merge only under the selected operating mode.

## Output contract

During work, report only meaningful checkpoints:

```text
Status
What changed
Evidence
Open risk
Next action
```

At completion include the repository and PR, merge status and commit, files/components added, tests and CI results, measured benchmark values, resolved security findings, and honest non-claims.

See [architecture reference](references/ARCHITECTURE.md), [threat catalog](references/THREAT_CATALOG.md), and [completion checklist](references/COMPLETION_CHECKLIST.md).

## Hard boundaries

- Defensive use only.
- Do not create exploit payloads, credential theft, persistence, evasion, or real exfiltration.
- Do not use real secrets in fixtures.
- Do not claim official vendor integration or endorsement without evidence.
- Do not claim production certification, universal detection, or sandbox containment from an in-process guard.
- Do not merge failing or unreviewed code merely to satisfy “finish.”
- Do not invent test, CI, benchmark, or review results.
