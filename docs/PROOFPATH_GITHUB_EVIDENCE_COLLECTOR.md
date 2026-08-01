# ProofPath GitHub Evidence Collector v0.1

The GitHub Evidence Collector removes most manual JSON assembly from the Deploy Guard integration.

```text
GitHub checks + PR reviews + producer job + Actions artifact
                         ↓
             GitHub Evidence Collector
                         ↓
       explicit commit-bound trusted facts
                         ↓
             Deploy Evidence Builder
                         ↓
                  Deploy Guard
```

The Collector reads observable GitHub facts. It does not infer authority, organizational roles, insurance coverage, or the truth of external security and change-management claims.

## Collected automatically

The Collector reads the GitHub API for:

- workflow-run repository, branch, and head SHA;
- one explicitly named artifact-producing job;
- the producer job's completed/successful state;
- one exact artifact name and its GitHub-reported SHA-256 digest;
- configured check-run names on the exact source SHA;
- an optional expected GitHub App slug per check;
- the latest review state for explicitly mapped reviewers;
- review commit binding to the exact source SHA.

## Supplied explicitly

GitHub does not natively define the business meaning of these facts, so the Collector configuration preserves them without claiming to verify them:

- agent authority and scope;
- reviewer-to-role mapping such as `service-owner` or `security`;
- critical vulnerability count;
- change-ticket state;
- artifact-attestation verification result;
- expected provenance workflow and signer SHA.

The output report always states:

```text
collector_verified_authority: false
collector_verified_attestation_claim: false
collector_verified_change_ticket: false
deployment_performed: false
```

## Why producer-job binding matters

A workflow may still be running when Deploy Guard evaluates an artifact. Requiring the entire workflow run to be completed would prevent a gate from running inside that workflow.

The Collector therefore requires both:

1. the workflow run repository and `head_sha` match the proposed action;
2. the configured `artifact_job_name` matches exactly one job that is already `completed/success`.

A completed workflow run must also have conclusion `success`. An in-progress run is accepted only after its exact artifact-producing job has succeeded.

## Configuration

Schema:

```text
schemas/proofpath-github-evidence-collector-config-v0.1.schema.json
```

Example:

```json
{
  "profile_id": "proofpath.github.evidence-collector-config.v0.1",
  "artifact_job_name": "build-artifact",
  "authority": {
    "active": true,
    "expires_at": "2026-12-31T23:59:59Z",
    "scope": {
      "repositories": ["owner/repository"],
      "environments": ["production"],
      "actions": ["deploy"]
    }
  },
  "provenance": {
    "attestation_verified": true,
    "runner_environment": "github-hosted",
    "workflow": "owner/repository/.github/workflows/build.yml",
    "source_sha": "0123456789abcdef0123456789abcdef01234567",
    "signer_sha": "89abcdef0123456789abcdef0123456789abcdef"
  },
  "security": {
    "critical_vulnerabilities": 0
  },
  "approval_role_map": {
    "alice": "service-owner",
    "bob": "security"
  },
  "check_names": [
    "unit-tests",
    "security-scan"
  ],
  "check_app_allowlist": {
    "unit-tests": "github-actions",
    "security-scan": "github-actions"
  },
  "change_ticket": {
    "id": "CHG-42",
    "status": "approved",
    "commit_sha": "0123456789abcdef0123456789abcdef01234567"
  }
}
```

`provenance.source_sha` and `change_ticket.commit_sha` must equal the Action's `source-sha`. The Collector fails before output when those immutable bindings conflict.

## Review semantics

The Collector does not treat every GitHub approval as a business approval.

Only reviewers present in `approval_role_map` are considered. For each mapped actor, the Collector selects that actor's latest review. It emits an approval only when:

```text
latest review state == APPROVED
and review commit_id == source-sha
```

A stale approval, a later `CHANGES_REQUESTED`, or an unmapped reviewer does not become an approval. Missing approvals are preserved as missing facts so Deploy Guard can return `HOLD`.

## Check semantics

Only exact configured check names are emitted. An optional App slug can prevent a similarly named check from another GitHub App from being selected.

For repeated runs of the same check on the same commit and App, the latest check-run ID is selected.

Normalization:

```text
completed/success      → success
completed/failure      → failure
completed/cancelled    → cancelled
completed/timed_out    → timed_out
other or not completed → pending
missing exact check    → pending
```

Missing or pending checks remain valid evidence and normally produce a Guard `HOLD`. A failed required check normally produces `BLOCK`.

## Minimal workflow

```yaml
permissions:
  contents: read
  actions: read
  checks: read
  pull-requests: read

steps:
  - id: collect
    uses: safal207/ProofPath/deploy-guard/github-collector@REVIEWED_40_CHAR_COMMIT_SHA
    with:
      github-token: ${{ github.token }}
      config: .proofpath/github-collector.json
      artifact-run-id: ${{ github.run_id }}
      artifact-name: deployable
      source-sha: ${{ needs.build.outputs.source_sha }}
      pull-request-number: ${{ github.event.pull_request.number || 0 }}

  - id: evidence
    uses: safal207/ProofPath/deploy-guard/evidence-builder@REVIEWED_40_CHAR_COMMIT_SHA
    with:
      policy: .proofpath/deploy-policy.json
      trusted-facts: ${{ steps.collect.outputs.trusted-facts-path }}
      artifact-digest: ${{ steps.collect.outputs.artifact-digest }}
      environment: production
      agent-id: github-actions/production-deployer
      repository: ${{ steps.collect.outputs.repository }}
      source-branch: ${{ steps.collect.outputs.source-branch }}
      source-sha: ${{ steps.collect.outputs.source-sha }}

  - id: guard
    uses: safal207/ProofPath/deploy-guard@REVIEWED_40_CHAR_COMMIT_SHA
    with:
      policy: .proofpath/deploy-policy.json
      evidence: ${{ steps.evidence.outputs.evidence-path }}
      certificate: proofpath-evidence/deploy-clearance.json
      mode: enforce
```

Pin Collector, Builder, and Guard to the same reviewed full commit SHA.

## Required permissions

The Collector needs read-only access:

```yaml
permissions:
  contents: read
  actions: read
  checks: read
  pull-requests: read
```

It does not need:

- repository write access;
- an OIDC token;
- attestation write permission;
- secrets other than the scoped GitHub token used for API reads;
- cloud credentials.

## Security properties

The implementation:

- uses only Python's standard library;
- performs only authenticated HTTP `GET` requests;
- sends the token only to the HTTPS `GITHUB_API_URL` origin;
- rejects embedded URL credentials;
- constrains config, output, and report paths to `GITHUB_WORKSPACE`;
- rejects duplicate JSON keys and floating-point configuration values;
- binds run, producer job, artifact, checks, reviews, ticket, and provenance to the exact source SHA;
- does not run code from an artifact or pull-request review;
- does not download the selected artifact;
- does not deploy, merge, change IAM, or call a cloud provider.

## Honest assurance boundary

After Collector, Builder, and the current reference Guard:

```text
GitHub metadata collection: LIVE_API_BOUND
Assurance: POLICY_VERIFIED
Witnesses: SINGLE_WORKFLOW_REFERENCE
Coverage: NOT_FINANCIALLY_COVERED
Deployment performed: false
Authority granted: false
```

A stronger claim requires independently verified upstream authority/provenance and, for quorum assurance, independently owned witnesses.
