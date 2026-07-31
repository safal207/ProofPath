# PoCI Organizational Independence Gate v0.1

This layer distinguishes technical federation from independent organizational governance.

ProofPath and `ibex-agent-verification` already use different repositories, commits, workflows, runners, artifacts, graph recomputation paths, and Sigstore identities. Both repositories are currently controlled by the same GitHub owner. They therefore count as two technical domains but only one organizational owner.

## Decision rule

The current policy requires:

- at least three admitted governance domains;
- at least two distinct repository owners or organizations;
- at least one owner different from the ProofPath producer owner;
- at least three distinct signer workflows;
- a verified keyless attestation for every admitted domain;
- exact agreement on the pinned PoCI consensus.

The pinned consensus includes:

```text
round
source digest
graph-set identity
PoCI envelope identity
causal graph root
intent graph root
authority graph root
state-transition graph root
evidence graph root
time-continuity graph root
transition-cell root
multi-graph root
```

## Outcomes

### `ACCEPT`

All policy thresholds are satisfied, every domain is attested, repository and workflow identities are unique, at least one domain has a different owner, and every domain commits the exact same PoCI consensus.

### `HOLD`

The supplied evidence is internally consistent, but an external organizational dependency is still missing. The current live configuration intentionally produces `HOLD` because ProofPath and Ibex have one controlling GitHub owner.

A `HOLD` emits a deterministic `proofpath.poci.external-operator-challenge.v0.1` bundle. The bundle can be consumed without write access to ProofPath.

### `BLOCK`

The governance evidence is malformed or structurally unsafe. Examples include duplicate repositories, duplicate workflows, owner/repository mismatch, missing attestation verification, or incomplete graph coverage.

### `CHALLENGE`

The evidence is well formed but contradicts the pinned truth boundary. Examples include a substituted graph root or a same-owner domain claiming organizational independence.

Decision precedence is:

```text
CHALLENGE > BLOCK > HOLD > ACCEPT
```

## External operator protocol

An independent operator should:

1. fetch the attested producer or federation evidence;
2. verify the producer keyless attestation;
3. check out the exact pinned producer commit;
4. independently recompute all six graph roots and transition cells;
5. compare the source, envelope, graph set, consensus, transition-cell, and multi-graph roots;
6. emit a portable external-operator response from a repository owned by another user or organization;
7. keyless-attest the exact response bytes;
8. provide the response and its attestation verification evidence for admission.

The expected response profile is:

```text
proofpath.poci.external-operator-response.v0.1
```

Required fields are listed inside the generated challenge bundle.

## Why owner diversity is explicit

Repository separation is useful but insufficient. One account can create many repositories, workflows, runners, and signatures. Those artifacts prove different technical execution paths, not different governance authority.

This gate therefore counts both:

- technical domains: repository and workflow identities;
- governance domains: distinct repository owners or organizations.

A same-owner consumer remains valuable evidence and is preserved. It simply cannot satisfy the organizational-independence threshold by itself.

## Current live state

```text
technical domains: 2
repositories: 2
workflows: 2
controlling owners: 1
external owners: 0
decision: HOLD
next transition: AWAIT_EXTERNAL_OPERATOR
```

The readiness workflow treats this expected `HOLD` as a successful, honest evaluation. It attests both the readiness report and the external-operator challenge.

## Security boundary

The challenge bundle:

- does not grant repository access;
- does not grant merge authority;
- does not grant execution authority;
- does not make an external response trusted automatically;
- does not replace independent attestation verification;
- does not accept approximate or majority graph agreement.

Admission remains fail closed and requires exact consensus equality.
