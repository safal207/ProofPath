# PoCI External Submission Admission v0.1

This layer turns the external witness SDK output into a safe, reviewable GitHub pull-request protocol.

## Purpose

An independently owned repository can recompute the PoCI transition space, keyless-attest its exact response bytes, and submit the resulting evidence to ProofPath without receiving write, merge, execution, or authorization authority.

The admission path is:

```text
external owner repository
        ↓ independent workflow
response.json + submission.json + provenance.json
        ↓ pull request data only
trusted ProofPath pull_request_target workflow
        ↓ exact Sigstore verification
external domain admission
        ↓ organizational-independence verifier
ACCEPT or fail closed
```

## Files submitted

The external pull request must change exactly three files in one directory:

```text
external-submissions/<domain-id>/response.json
external-submissions/<domain-id>/submission.json
external-submissions/<domain-id>/provenance.json
```

No additional source code, workflow, documentation, executable, or generated file is accepted in that pull request.

The files come from the artifact produced by the reference external witness workflow:

- `external-operator-response.json` → `response.json`
- `external-operator-submission.json` → `submission.json`
- `provenance.json` → `provenance.json`

## External operator steps

1. Use a repository owned by a GitHub owner or organization other than `safal207`.
2. Copy the SDK, challenge, and reference workflow from the external witness kit.
3. Place the workflow at `.github/workflows/proofpath-external-witness.yml`.
4. Review every pinned ProofPath commit and signer identity.
5. Run the workflow manually.
6. Download the workflow artifact.
7. Copy the three required JSON subjects into one `external-submissions/<domain-id>/` folder in a fork or branch.
8. Open a pull request against a ProofPath branch containing the trusted admission workflow.

## Trusted intake boundary

`.github/workflows/poci-external-submission-admission.yml` uses `pull_request_target` deliberately.

It:

- checks out only `github.event.pull_request.base.sha`;
- never checks out the external PR head;
- accepts exactly three JSON files;
- downloads those files through the GitHub Contents API as data;
- never executes code from the external repository;
- verifies the external repository, owner, workflow, source SHA, signer SHA, OIDC issuer, and runner environment;
- proves the workflow source commit is an ancestor of the PR head;
- re-runs `gh attestation verify` from ProofPath;
- verifies challenge, response, submission, consensus, graph coverage, transition-cell count, and all self-roots;
- rejects duplicate domain, repository, or workflow identities;
- runs the organizational-independence verifier on the updated domain set.

Permissions are limited to:

```yaml
contents: read
pull-requests: write
```

The write permission is used only to post the verification result on the pull request.

## Decisions

### ACCEPT

The external owner, repository, signer workflow, source ancestry, attestation, response bytes, and all six graph roots are independently verified. The resulting three-domain governance set also evaluates to `ACCEPT`.

### BLOCK

The evidence is structurally invalid, the owner is not independent, identity fields disagree, source ancestry is unverified, the attestation is missing, authority is claimed, or an existing domain identity is reused.

### CHALLENGE

A committed root, response subject digest, nested response, or consensus coordinate differs from the pinned challenge.

## Provenance contract

`proofpath.poci.external-operator-provenance.v0.1` binds:

- external repository;
- repository owner;
- signer workflow;
- workflow source SHA;
- signer workflow SHA;
- GitHub Actions OIDC issuer;
- denial of self-hosted runners;
- exact response subject SHA-256.

The provenance document is not trusted by itself. ProofPath uses its values as constraints in an independent `gh attestation verify` invocation.

## Bootstrap limitation

A `pull_request_target` workflow is loaded from the pull request base branch. Therefore PR #205 can validate the verifier and workflow security, but the live external intake endpoint becomes active only after this trusted workflow reaches the branch targeted by an external submission.

No external operator repository owned by another account is currently connected to this session. The conformance workflow therefore emits a signed readiness `HOLD`, not a fabricated external `ACCEPT`.

## Authority boundary

Admission adds a verification domain only. It does not:

- merge the external pull request;
- authorize an agent action;
- grant execution permission;
- grant repository access;
- transfer governance control;
- make the external witness a ProofPath maintainer.
