# ProofPath NOOA Liminal Guard

A runnable defensive integration for **NVIDIA Labs Object-Oriented Agents (NOOA)** and the ProofPath/Liminal evidence stack.

```text
NOOA capability or exported span
        ↓
ProofPath pre-execution decision
  ACCEPT / HOLD / BLOCK
        ↓ ACCEPT only
sandboxed side effect
        ↓
CML causal records and findings
LTP replay-oriented transition trace
LiminalDB-style hash-linked ledger
Ibex-style manifest and bundle verification
```

## What is implemented

- a stable wrapper around high-impact Python capabilities;
- a format-tolerant mapper for exported parent/child NOOA spans;
- declared-intent, causal-parent, scope, reversibility, approval, destination, and replay checks;
- fail-closed blocking of secret-bearing egress to a destination outside the allow-list;
- `CML-AUDIT-R3-SECRET_NET_MISSING_CHAIN` evidence for that pattern;
- no side-effect execution after `HOLD` or `BLOCK`;
- hash-linked authorization and observation records;
- CML JSONL, LTP JSONL, durable-ledger JSONL, evidence roles, manifest, and offline verification;
- deterministic synthetic fixtures and benchmark metrics.

The implementation is standard-library Python and does not require a model API key.

## Run the complete chain

From the repository root:

```bash
bash examples/nooa-liminal-guard/run_demo_check.sh
```

The command executes unit tests and six scenarios:

| Scenario | Expected |
|---|---|
| public file read | `ACCEPT` |
| irreversible delete without approval | `HOLD` |
| secret to unknown network destination | `BLOCK` + CML R3 |
| approved send to allow-listed destination | `ACCEPT` |
| missing causal parent | `BLOCK` |
| consumed nonce replay | `BLOCK` |

Generated evidence is written under:

```text
.proofpath/nooa-liminal-demo/
├── benchmark-summary.json
└── bundles/<span-id>-<decision>-<ledger-hash>/
    ├── authorization.json
    ├── cml-trace.jsonl
    ├── cml-findings.json
    ├── ltp-trace.jsonl
    ├── liminaldb-ledger.jsonl
    ├── manifest.json
    ├── bundle-verification.json
    └── evidence/
        ├── intent.json
        ├── action.json
        ├── result.json
        └── verification.json
```

## Wrap a NOOA capability

NOOA exposes ordinary Python methods as capabilities. Put the guard at the capability boundary rather than relying on an unstable internal hook:

```python
from pathlib import Path
from nooa_liminal_guard import ActionProposal, Policy, ProofPathNOOAGuard

policy = Policy.load(Path("examples/nooa-liminal-guard/policy.json"))
guard = ProofPathNOOAGuard(
    policy,
    Path(".proofpath/nooa-state"),
    Path(".proofpath/nooa-evidence"),
)

class ExternalActions:
    def send_report(self, payload: dict) -> dict:
        proposal = ActionProposal(
            trace_id="trace-123",
            span_id="span-send-1",
            parent_span_id="span-plan-1",
            agent="ReportingAgent",
            method="send_report",
            intent_id="intent-send-report",
            parent_cause="approved-task-123",
            action="network_send",
            scope="network.send",
            target="/v1/reports",
            destination="api.example.test",
            approval_ref="human_approval:ticket-42",
            nonce="nonce-send-1",
        )
        guarded = guard.execute(proposal, lambda: self._real_send(payload))
        if not guarded.decision.execution_allowed:
            return {
                "status": guarded.decision.decision,
                "reasons": list(guarded.decision.reason_codes),
            }
        return guarded.result

    def _real_send(self, payload: dict) -> dict:
        # Keep the actual network implementation inside the OS sandbox.
        return {"accepted": True}
```

A NOOA agent can hold an `ExternalActions` object as typed state and call its guarded methods. Model output remains a proposal; ProofPath controls the side-effect boundary.

## Map exported NOOA spans

NOOA publicly guarantees parent-child tracing, but this integration does not bind itself to a private database schema. The adapter accepts common export names:

```python
from nooa_liminal_guard import proposal_from_nooa_span

proposal = proposal_from_nooa_span(
    {
        "trace_id": "trace-123",
        "id": "span-send-1",
        "parent_id": "span-plan-1",
        "name": "send_report",
        "attributes": {
            "scope": "network.send",
            "destination": "api.example.test",
        },
    },
    defaults={
        "intent_id": "intent-send-report",
        "parent_cause": "approved-task-123",
        "target": "/v1/reports",
        "approval_ref": "human_approval:ticket-42",
        "nonce": "nonce-send-1",
    },
)
```

Security-critical intent fields must come from the application or authorization layer, not be guessed from model prose.

## Run in a restricted container

Build:

```bash
docker build -t proofpath-nooa-guard examples/nooa-liminal-guard
```

Run the synthetic demo with network disabled and a read-only root filesystem:

```bash
docker run --rm \
  --network none \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --tmpfs /tmp:rw,noexec,nosuid,size=32m \
  -v "$PWD/.proofpath/container-evidence:/evidence" \
  -v "$PWD/.proofpath/container-state:/state" \
  proofpath-nooa-guard
```

For a live NOOA code-execution agent, use an actual containment layer such as NVIDIA OpenShell, a container, or a VM. The Python checks in this example are policy enforcement and evidence generation, **not an OS security boundary**.

## Claim boundary

This integration proves that the included fixtures:

- are decided before the synthetic side effect;
- never execute after `HOLD` or `BLOCK`;
- produce reproducible evidence bundles;
- detect replay and the modeled secret-egress pattern.

It does not claim a completed independent security audit, universal detection, compatibility with every future NOOA trace schema, or sandbox certification.
