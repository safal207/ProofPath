# ProofPath Deploy Evidence Builder v0.1

The Deploy Evidence Builder converts explicit trusted workflow facts into the exact evidence profile consumed by ProofPath Deploy Guard.

```text
build and verification jobs
        ↓ explicit trusted facts
Deploy Evidence Builder
        ↓ deterministic commit-bound evidence
Deploy Guard
        ↓ ACCEPT / HOLD / BLOCK / CHALLENGE
consumer-owned deployment step
```

The builder reduces integration work. It does not replace the systems that verify tests, approvals, change tickets, artifact provenance, vulnerability counts, or agent authority.

## Why this layer exists

A deployment gate is only useful when every fact refers to the same proposed action. Manually assembled JSON makes it easy to accidentally combine:

- a current artifact with an older commit;
- a successful check from another revision;
- an approval for a superseded commit;
- a change ticket for a different release;
- a provenance statement for different bytes.

The builder fails before writing evidence when these immutable bindings conflict.

Policy deficiencies are handled differently. Missing approvals, inactive authority, pending checks, or insufficient scope remain visible facts and are passed to Deploy Guard, which returns the appropriate decision and reason codes.

## Inputs

The composite Action is located at:

```text
deploy-guard/evidence-builder
```

Required inputs:

| Input | Meaning |
|---|---|
| `policy` | Deploy Guard policy JSON |
| `trusted-facts` | Explicit upstream facts JSON |
| `artifact-digest` | Exact `sha256:<64 lowercase hex>` artifact digest |
| `environment` | Proposed target environment |
| `agent-id` | Stable identifier for the proposing automation |

Optional identity inputs:

| Input | Default |
|---|---|
| `repository` | `GITHUB_REPOSITORY` |
| `source-branch` | `GITHUB_REF_NAME` |
| `source-sha` | `GITHUB_SHA` |
| `action-id` | Deterministically derived from repo, commit, environment, and artifact |
| `evaluated-at` | Current UTC time |
| `output` | `proofpath-evidence/deploy-action-evidence.json` |

For reproducible evidence bytes, supply an explicit `evaluated-at` value captured by the trusted workflow.

## Trusted-facts contract

The facts file uses:

```json
{
  "profile_id": "proofpath.deploy.evidence-inputs.v0.1",
  "authority": {},
  "build_provenance": {},
  "checks": [],
  "security": {},
  "approvals": [],
  "change_ticket": null
}
```

The complete reference fixture is:

```text
examples/deploy-guard/trusted-facts.accept.json
```

### Facts that must be commit-bound

The builder requires the proposed `source-sha` to equal:

- `build_provenance.commit_sha`;
- every `checks[*].commit_sha`;
- every `approvals[*].commit_sha`;
- `change_ticket.commit_sha` when a ticket exists.

The proposed artifact digest must equal `build_provenance.artifact_digest`.

A conflict is treated as malformed construction, not as a policy decision. The Action exits `1` and writes no evidence file.

### Facts that remain policy inputs

The builder deliberately preserves these values without promoting them:

- `authority.active`;
- authority scope;
- `attestation_verified`;
- runner environment;
- check status;
- vulnerability count;
- approval outcome and role;
- ticket status.

Deploy Guard evaluates those values. For example:

```text
no approvals                     → HOLD
failed required test             → BLOCK
authority scope excludes repo    → BLOCK
artifact digest conflict         → builder failure before evidence
```

## Outputs

The Action exports:

```text
evidence-path
evidence-root
action-id
repository
source-branch
source-sha
artifact-digest
```

`evidence-root` uses the same domain-separated canonical JSON algorithm as Deploy Guard:

```text
sha256("proofpath:deploy-guard:v0.1:evidence\n" + canonical_json(evidence))
```

Fixed inputs, including `evaluated-at`, produce byte-identical evidence and the same root.

## Minimal integration

```yaml
- name: Build ProofPath deployment evidence
  id: evidence
  uses: safal207/ProofPath/deploy-guard/evidence-builder@REVIEWED_40_CHAR_COMMIT_SHA
  with:
    policy: .proofpath/deploy-policy.json
    trusted-facts: .proofpath/trusted-deploy-facts.json
    artifact-digest: ${{ needs.build.outputs.artifact_digest }}
    environment: production
    agent-id: github-actions/production-deployer
    source-sha: ${{ needs.build.outputs.source_sha }}
    evaluated-at: ${{ needs.verify.outputs.evaluated_at }}

- name: Evaluate ProofPath clearance
  id: guard
  uses: safal207/ProofPath/deploy-guard@REVIEWED_40_CHAR_COMMIT_SHA
  with:
    policy: .proofpath/deploy-policy.json
    evidence: ${{ steps.evidence.outputs.evidence-path }}
    certificate: proofpath-evidence/deploy-clearance.json
    mode: enforce
```

A complete downstream template is available at:

```text
examples/deploy-guard/evidence-builder-consumer-workflow.yml
```

## Where trusted facts should come from

A production consumer should construct the facts file from outputs that have already been verified by the relevant owner:

| Fact | Suggested source |
|---|---|
| Artifact digest | build output or immutable registry digest |
| Attestation result | pinned provenance verification step |
| Checks | exact commit check-suite results |
| Vulnerabilities | scanner result bound to artifact or commit |
| Approvals | protected environment or review system |
| Change ticket | change-management API or signed export |
| Authority | current authorization system |

A checked-in example file is suitable for conformance and demos, not proof of a live production state.

## GitHub pull-request SHA warning

On `pull_request` workflows, `github.sha` can refer to GitHub's synthetic merge commit. The deploy evidence must use the exact commit whose artifact, checks, approvals, and provenance were verified.

Prefer an explicit output from the trusted build job:

```yaml
source-sha: ${{ needs.build.outputs.source_sha }}
```

The builder rejects mixed commit bindings but cannot decide which commit the consumer intended.

## Safety properties

The implementation:

- uses only the Python standard library;
- rejects duplicate JSON keys and floating-point values;
- rejects multiline and NUL-containing scalar inputs;
- constrains policy, facts, and output paths to `GITHUB_WORKSPACE`;
- does not invoke a shell, network client, cloud API, or deployment command;
- never changes `execution.performed` from `false`;
- does not create authority or approvals;
- does not verify attestations by itself;
- keeps the actual deployment in a separate consumer-owned step.

## Permissions

The builder requires no GitHub write permission, OIDC token, attestation permission, secret, or network access. The reference workflow uses:

```yaml
permissions:
  contents: read
```

Upstream verification jobs may need additional read permissions depending on their source systems. Those permissions should not be granted to the builder merely for convenience.

## Pinning and evidence retention

Production consumers should:

1. pin both Builder and Guard to the same reviewed full commit SHA;
2. retain generated evidence and the clearance certificate even when enforcement fails;
3. keep deployment commands outside ProofPath Actions;
4. require `steps.guard.outputs.decision == 'ACCEPT'` at the deployment boundary.

## Honest assurance boundary

The Builder proves deterministic construction and exact internal binding of supplied facts. It does not prove that upstream facts are true.

The current Deploy Guard assurance remains:

```text
Assurance: POLICY_VERIFIED
Witnesses: SINGLE_WORKFLOW_REFERENCE
Coverage: NOT_FINANCIALLY_COVERED
Deployment performed: false
Authority granted: false
```
