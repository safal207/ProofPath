# Budget and Milestones

## Grant request

```text
Requested amount: EUR 50,000
Fund: NGI TALER
Project: ProofPath Agent Payment Guard
```

## Budget summary

| Area | Amount |
|---|---:|
| Engineering | EUR 32,000 |
| Cryptographic design and review | EUR 6,000 |
| Testing and reproducibility | EUR 4,000 |
| Documentation and examples | EUR 4,000 |
| Community and integration work | EUR 3,000 |
| Hosting and CI infrastructure | EUR 1,000 |
| **Total** | **EUR 50,000** |

## Assumed rates

| Role | Rate |
|---|---:|
| Open-source engineering | EUR 40/hour |
| Security / cryptography review | EUR 60/hour |
| Documentation and integration | EUR 35/hour |

These are planning rates for grant budgeting.

Final distribution can be adapted to NLnet contracting and review feedback.

## Milestone 1 — Specification and threat model

Duration: 1 month

Budget: EUR 8,000

Deliverables:

- payment proposal schema;
- signed intent envelope draft;
- threat model for AI-agent payment authorization;
- non-claims document;
- updated reviewer path.

Acceptance checks:

- schemas are public;
- threat model is readable by reviewers;
- clear distinction between proposal, authorization, policy, and payment execution.

## Milestone 2 — Core guard engine

Duration: 2 months

Budget: EUR 14,000

Deliverables:

- policy evaluation engine;
- signed-intent validation;
- freshness and expiry checks;
- nonce replay protection;
- deterministic decision output.

Acceptance checks:

- valid intent returns `ACCEPT`;
- replay returns `BLOCK / INTENT_REPLAYED`;
- invalid policy returns `HOLD` or `BLOCK`;
- tests cover main decision paths.

## Milestone 3 — Evidence and verification

Duration: 2 months

Budget: EUR 12,000

Deliverables:

- hash-chained audit log;
- portable evidence bundle format;
- offline verifier;
- deterministic fixtures;
- documentation for privacy-aware evidence.

Acceptance checks:

- evidence can be exported;
- evidence can be verified offline;
- tampered evidence fails verification;
- unnecessary personal data is avoided.

## Milestone 4 — CLI, API, and integration path

Duration: 2 months

Budget: EUR 10,000

Deliverables:

- CLI commands for evaluate/export/verify;
- OpenAPI contract updates;
- mock payment rail demo;
- GNU Taler integration notes;
- example integration with an AI-agent workflow.

Acceptance checks:

- local reviewer can run end-to-end demo;
- blocked proposals never reach mock rail;
- accepted proposals are visibly forwarded;
- integration notes identify where a GNU Taler adapter would connect.

## Milestone 5 — Documentation and community review

Duration: 1 month

Budget: EUR 6,000

Deliverables:

- reviewer documentation;
- developer quickstart;
- demo transcript;
- issue templates;
- community feedback round;
- final report.

Acceptance checks:

- new developer can understand the project in under 10 minutes;
- reviewer can run demo with copy-paste commands;
- limitations and next steps are explicit.

## Total timeline

```text
Month 1: specification and threat model
Months 2-3: core guard engine
Months 4-5: evidence and verification
Months 6-7: CLI/API/integration path
Month 8: documentation and community review
```

## Public outputs

The grant will produce:

- source code;
- schemas;
- CLI;
- examples;
- evidence fixtures;
- documentation;
- threat model;
- demo scripts;
- integration notes.

All outputs are intended to be released under a free/open-source license compatible with NLnet requirements.

## Success definition

The project is successful if an independent reviewer can:

1. clone the repository;
2. run the demo;
3. see a valid payment proposal accepted;
4. see a replay blocked;
5. export an evidence bundle;
6. verify the evidence offline;
7. understand how this can later integrate with GNU Taler-style payment flows.
