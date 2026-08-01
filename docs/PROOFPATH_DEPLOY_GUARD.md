# ProofPath Deploy Guard v0.1

ProofPath Deploy Guard is the first product-shaped **Assured Action** demo.

It evaluates whether an AI coding or cloud agent may perform one specific production deployment. The output is a deterministic, signed clearance certificate with one of four decisions:

| Decision | Meaning | Next transition |
|---|---|---|
| `ACCEPT` | Required observable evidence satisfies policy | `DEPLOY_TO_PRODUCTION` |
| `HOLD` | Evidence is incomplete or still pending | `WAIT_FOR_REQUIRED_EVIDENCE` |
| `BLOCK` | A policy, authority, or safety requirement failed | `REPAIR_POLICY_OR_SAFETY_FAILURE` |
| `CHALLENGE` | Two claimed facts conflict and require investigation | `INVESTIGATE_CONFLICTING_EVIDENCE` |

## Ninety-second demo

```bash
python3 scripts/verify_proofpath_deploy_guard.py \
  examples/deploy-guard/deploy-policy.json \
  examples/deploy-guard/deploy.accept.json \
  --pretty
```

The four committed scenarios demonstrate the full decision space:

```text
deploy.accept.json
→ ACCEPT
→ exact commit, approvals, successful checks, verified artifact provenance

deploy.hold-missing-approval.json
→ HOLD
→ one of two required approvals is absent

deploy.block-tests-failed.json
→ BLOCK
→ a required integration check failed

deploy.challenge-artifact-mismatch.json
→ CHALLENGE
→ the proposed artifact digest conflicts with build provenance
```

The GitHub Actions demo generates all four certificates, keyless-attests the exact `ACCEPT` certificate and the demo manifest, and uploads the evidence bundle.

## What is verified

The policy gate checks observable facts:

- repository, branch, environment, and action allowlists;
- active, unexpired, action-scoped authority;
- commit-bound approvals and required approval roles;
- commit-bound required checks;
- critical-vulnerability threshold;
- approved, commit-bound change ticket;
- artifact and commit agreement with build provenance;
- verified artifact attestation;
- GitHub-hosted runner requirement;
- confirmation that the deployment has not already been performed.

ProofPath does **not** claim to reveal or prove a model's private chain of thought.

## Clearance certificate

The certificate commits to:

```text
action identity
policy root
evidence root
decision and findings
clearance root
permitted next transition
assurance and coverage labels
```

Every v0.1 certificate is explicit about its current assurance boundary:

```text
Assurance: POLICY_VERIFIED
Witnesses: SINGLE_WORKFLOW_REFERENCE
Coverage:  NOT_FINANCIALLY_COVERED
```

`authority_granted` is always `false`. An `ACCEPT` decision means the supplied evidence satisfies the evaluated policy for the exact action; it does not create new authority or authorize unrelated actions.

## Decision precedence

Deploy Guard is fail-closed:

```text
CHALLENGE > BLOCK > HOLD > ACCEPT
```

For example, an artifact mismatch remains `CHALLENGE` even if a test also failed and an approval is missing. Conflicting evidence must not be hidden behind an ordinary policy failure.

## Product path

This reference demo maps directly to the commercial product ladder:

1. **ProofPath Guard** — local policy gate and signed journal.
2. **ProofPath Quorum** — independent external witnesses.
3. **ProofPath Bonded** — bonded operators and dispute handling.
4. **ProofPath Covered** — financial coverage only through an appropriate licensed partner.

The v0.1 demo implements the first layer. The existing PoCI external-witness and admission work provides the technical path to the second.

## Safety boundary

This workflow:

- does not deploy to production;
- does not call a cloud provider;
- does not modify IAM;
- does not merge code;
- does not provide insurance or a financial guarantee;
- does not claim organizationally independent quorum;
- signs the decision artifact, not the deployment itself.

A production integration should place the gate immediately before the deployment boundary and independently verify the certificate attestation, exact action fields, policy version, and `execution_allowed` value.
