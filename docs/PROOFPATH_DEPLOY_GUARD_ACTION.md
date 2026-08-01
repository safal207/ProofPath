# ProofPath Deploy Guard GitHub Action v0.1

The reusable Deploy Guard Action places ProofPath immediately before a production deployment boundary.

It consumes:

```text
policy JSON + action evidence JSON
```

and emits:

```text
ACCEPT / HOLD / BLOCK / CHALLENGE
+ deterministic clearance certificate
+ machine-readable outputs
+ GitHub job summary
```

The Action does not perform the deployment. It evaluates whether the supplied observable evidence satisfies the selected policy for one exact action.

## Recommended integration

Copy `examples/deploy-guard/consumer-workflow.yml` and replace the placeholder with a reviewed, full 40-character ProofPath commit SHA:

```yaml
- name: Evaluate exact deployment proposal
  id: deploy_guard
  uses: safal207/ProofPath/deploy-guard@REPLACE_WITH_FULL_40_CHARACTER_COMMIT_SHA
  with:
    policy: .proofpath/deploy-policy.json
    evidence: .proofpath/deploy-evidence.json
    certificate: proofpath-evidence/deploy-clearance.json
    mode: enforce
```

Do not use a mutable branch such as `main` for a production authorization boundary. Review the pinned code and update the pin deliberately.

The deployment step remains separate:

```yaml
- name: Deployment boundary
  if: steps.deploy_guard.outputs.decision == 'ACCEPT'
  run: echo "Insert the separately authorized deployment command here."
```

GitHub environment protection, repository permissions, cloud IAM, human approvals, and the deployment platform remain authoritative. ProofPath does not create or expand them.

## Inputs

| Input | Required | Default | Meaning |
|---|---:|---|---|
| `policy` | yes | — | Deploy Guard policy JSON inside `GITHUB_WORKSPACE` |
| `evidence` | yes | — | Exact deploy-action evidence JSON inside `GITHUB_WORKSPACE` |
| `certificate` | no | `proofpath-deploy-clearance.json` | Output certificate path inside `GITHUB_WORKSPACE` |
| `mode` | no | `enforce` | `enforce` or `observe` |

All three paths are resolved and required to remain inside `GITHUB_WORKSPACE`. Policy and evidence must already exist. The Action never downloads mutable policy or evidence from the network.

## Modes

### `enforce`

The step succeeds only for `ACCEPT`.

| Decision | Exit code | Job effect |
|---|---:|---|
| `ACCEPT` | `0` | continue |
| `HOLD` | `2` | fail |
| `BLOCK` | `3` | fail |
| `CHALLENGE` | `4` | fail |

Use this mode immediately before a deployment boundary.

### `observe`

A complete, valid certificate is reported without failing the step, including `HOLD`, `BLOCK`, and `CHALLENGE`.

Use this mode during a design-partner pilot to learn which evidence is missing or contradictory before making the gate mandatory.

`observe` is not permissive verification. Malformed input, an incomplete certificate, output injection, invalid roots, mismatched exit codes, or an unsupported assurance label still fails the Action.

## Outputs

| Output | Meaning |
|---|---|
| `decision` | `ACCEPT`, `HOLD`, `BLOCK`, or `CHALLENGE` |
| `primary-reason-code` | Primary reason, or `NONE` for `ACCEPT` |
| `clearance-root` | Root of the exact clearance certificate |
| `policy-root` | Root of the evaluated policy |
| `evidence-root` | Root of the evaluated evidence |
| `execution-allowed` | `true` only for `ACCEPT` |
| `authority-granted` | Always `false` |
| `permitted-next-transition` | Decision-specific next transition |
| `assurance-level` | `POLICY_VERIFIED` |
| `witness-level` | `SINGLE_WORKFLOW_REFERENCE` |
| `coverage` | `NOT_FINANCIALLY_COVERED` |
| `certificate-path` | Absolute generated-certificate path |

The certificate is the durable evidence object. Step outputs are convenient projections and should not replace certificate retention and verification.

## Fail-closed wrapper

The composite Action calls `deploy-guard/run_action.py`, which:

- passes all user-supplied values as argument-list elements rather than shell code;
- never uses `shell=True`, `eval`, `exec`, or `os.system`;
- constrains input and output paths to `GITHUB_WORKSPACE`;
- rejects multiline and NUL-containing values;
- checks that the verifier exit code matches the certificate decision;
- requires valid policy, evidence, and clearance roots;
- requires `execution_allowed` to be true only for `ACCEPT`;
- requires `authority_granted` to remain false;
- requires the exact v0.1 assurance, witness, and coverage labels;
- emits controlled single-line GitHub outputs;
- writes a human-readable step summary.

The wrapper runs the bundled verifier from the pinned Action checkout. It does not execute code from the policy or evidence files.

## Evidence lifecycle

A production workflow should retain the certificate even when the gate fails:

```yaml
- name: Upload clearance certificate
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: proofpath-deploy-clearance-${{ github.run_id }}
    path: proofpath-evidence/deploy-clearance.json
    if-no-files-found: error
    retention-days: 14
```

For stronger provenance, a caller with an explicitly reviewed signing policy may keyless-attest the exact certificate in a separate step. The reusable Action itself requests no signing permission and makes no independent-witness claim.

## Honest assurance boundary

Every valid v0.1 certificate preserves:

```text
Assurance: POLICY_VERIFIED
Witnesses: SINGLE_WORKFLOW_REFERENCE
Coverage: NOT_FINANCIALLY_COVERED
Authority granted: false
```

An `ACCEPT` result means only:

> The supplied observable evidence satisfied the evaluated policy for this exact deployment proposal.

It does not mean:

- the deployment was performed;
- the deployment will succeed;
- the application is vulnerability-free;
- the evidence represents objective real-world truth;
- an independent organizational quorum approved the action;
- ProofPath supplied insurance or a financial guarantee;
- new repository, cloud, or human authority was created.

## Local repository conformance

Inside ProofPath, the Action is exercised as a real local composite Action:

```yaml
uses: ./deploy-guard
```

The conformance workflow proves:

1. `ACCEPT` succeeds in `enforce` mode;
2. `HOLD`, `BLOCK`, and `CHALLENGE` are reportable in `observe` mode;
3. `HOLD` fails in `enforce` mode;
4. all certificates remain deterministic and complete;
5. no deployment command is executed;
6. the evidence artifact is bounded to 14-day retention.
