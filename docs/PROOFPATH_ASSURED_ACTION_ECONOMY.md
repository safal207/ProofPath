# ProofPath Assured Action Economy v0.1

ProofPath Assured Action Economy turns independent verification into paid, reproducible work without introducing a token, custody, insurance, or automatic money movement.

```text
funded verification job
        ↓ fixed-rate independent assignments
witness commit
        ↓
witness reveal
        ↓ exact quorum or honest dissent
challenge window and disputes
        ↓
deterministic settlement receipt
        ↓
external payment provider
```

The billable unit is an **Assured Action verification job**. The customer pays to have one exact action clearance independently recomputed. Witnesses are paid for valid verification work, not for producing an `ACCEPT` verdict.

## Core economic rule

If all assigned witnesses correctly commit, reveal, and agree that an action must be `BLOCK`, the verification job is fulfilled and their payout plan becomes ready.

```text
action verdict:       BLOCK
economy decision:     ACCEPT
settlement state:     READY_FOR_EXTERNAL_PAYMENT_REQUEST
```

This separates the safety outcome from the work contract. A network that pays only for action approval creates an incentive to approve unsafe actions.

## Protocol entities

### Verification Job

The job binds:

- one exact Assured Action clearance root;
- client account and risk class;
- fixed customer charge in integer minor currency units;
- platform fee and dispute reserve;
- exact witness payouts;
- quorum and independence thresholds;
- challenge window;
- explicit lack of financial coverage;
- an external payment-provider boundary;
- a deterministic job root.

Money values are integers. Floating-point values are rejected.

### Witness Assignment

Each assignment binds:

- witness identity;
- independent control domain;
- verifier implementation identity;
- fixed payout;
- upstream operator-admission receipt root.

The v0.1 contract uses `FIXED_RATE_NO_AUCTION`. It deliberately does not implement lowest-bid selection, which would reward underpriced verification and encourage a race to the bottom.

For `L2_SENSITIVE`, the contract requires at least:

```text
3 witnesses
3 independent control domains
2 verifier implementations
```

Higher risk classes increase those thresholds.

### Commitment and Reveal

Before seeing another result, every witness commits to:

```text
job id
witness id
action verdict
action clearance root
evidence root
operator admission receipt root
private nonce
```

The commitment is:

```text
sha256(
  "proofpath:assured-action-economy:v0.1:commitment\n"
  + canonical_json(commitment_payload)
)
```

The later reveal must reproduce the commitment exactly. Substitution produces `CHALLENGE`, not a lower-severity settlement error.

### Dispute

Any open dispute locks settlement. A resolved or rejected dispute remains in the signed bundle history but does not block payment readiness.

The evaluator never slashes an operator. Honest dissent produces:

```text
HOLD / ECONOMY_WITNESS_DISSENT_REQUIRES_REVIEW
slashing_performed: false
```

Objective slashing rules, bonds, appeal evidence, and an authorized capital holder require a later Bonded profile.

### Settlement Receipt

The deterministic receipt contains:

- action consensus, separate from the economy decision;
- exact payout allocation;
- budget-conservation result;
- observed independence and implementation diversity;
- decision and stable reason code;
- payment readiness and next transition;
- bundle, job, and settlement roots;
- explicit non-claims about money movement and coverage.

Every receipt states:

```text
external_payment_authority_granted: false
payment_execution_performed: false
slashing_performed: false
coverage: NOT_FINANCIALLY_COVERED
```

`READY_FOR_EXTERNAL_PAYMENT_REQUEST` means only that the deterministic plan may be submitted to a separately authorized payment provider. It is not proof that funds were captured, held, transferred, or received.

## Decision model

Precedence remains fail-closed:

```text
CHALLENGE > BLOCK > HOLD > ACCEPT
```

| Decision | Meaning | Example |
| --- | --- | --- |
| `ACCEPT` | Verification work and challenge conditions are complete | Exact quorum, conserved budget, closed window |
| `HOLD` | More evidence or review is required | Missing reveal, honest dissent, open dispute |
| `BLOCK` | The commercial contract is invalid | Budget does not conserve, false independence |
| `CHALLENGE` | A committed identity or result was substituted | Commitment, clearance, or admission-root mismatch |

The action consensus has its own `ACCEPT / HOLD / BLOCK / CHALLENGE` verdict. It does not control witness compensation by itself.

## Example unit economics

The committed reference job charges `$100.00`:

```text
$54.00  three witness payouts
$16.00  dispute reserve
$30.00  ProofPath platform fee
-------
$100.00 exact allocation
```

These are conformance values, not a promise of market pricing. The important invariant is:

```text
sum(witness payouts)
+ platform fee
+ dispute reserve
= customer charge
```

Any one-unit mismatch produces `BLOCK / ECONOMY_BUDGET_NOT_CONSERVED`.

## Run the reference job

```bash
python3 scripts/evaluate_assured_action_economy.py \
  examples/assured-action-economy/deploy-quorum.accept.json \
  --pretty
```

Expected result:

```text
decision: ACCEPT
action verdict: ACCEPT
witnesses: 3
control domains: 3
implementations: 2
allocation conserved: true
settlement state: READY_FOR_EXTERNAL_PAYMENT_REQUEST
payment executed: false
coverage: NOT_FINANCIALLY_COVERED
```

Focused tests:

```bash
python3 -m unittest tests.test_assured_action_economy -v
```

## Trust boundary

The evaluator verifies the internal economy bundle. It does not independently query GitHub, Sigstore, banks, payment processors, company registries, or cloud providers.

`admission_receipt_root` must refer to an upstream receipt produced by the external-witness admission path. A production coordinator must verify the exact admission receipt and attestation before constructing the economy bundle.

The evaluator does not prove:

- beneficial-owner independence;
- objective external-world truth;
- availability of customer funds;
- legal authority to transmit money;
- receipt of payment by a witness;
- insurance or loss coverage;
- correctness of every verifier implementation.

It does prove that the supplied contract, commitments, reveals, independence labels, allocation, dispute state, and action binding produce one deterministic settlement plan.

## Product path

```text
Deploy Evidence Builder
        ↓
Deploy Guard clearance
        ↓
PoCI external witness admission receipts
        ↓
Assured Action Economy v0.1
        ↓
external fiat payout pilot
        ↓
Bonded Proof after real loss and dispute data exists
        ↓
Covered Proof only through an appropriate licensed partner
```

The first commercial pilot can therefore use ordinary contracts and monthly fiat payouts while the protocol produces deterministic settlement receipts. No native token is required.
