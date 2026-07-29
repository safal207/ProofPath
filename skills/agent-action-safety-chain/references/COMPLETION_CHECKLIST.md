# Completion Checklist

## Scope and authority

- [ ] Target repository and runtime identified.
- [ ] Write/merge authority is explicit.
- [ ] Existing components were inventoried before adding new ones.
- [ ] Threat model and protected assets are stated.

## Implementation

- [ ] Proposal schema is explicit.
- [ ] Intent and causal-parent checks exist.
- [ ] Nonce is mandatory and atomically consumed.
- [ ] Scope and reversibility are evaluated.
- [ ] Human approval is required where appropriate.
- [ ] Secret egress uses scope plus destination checks.
- [ ] Executor is called only after ACCEPT.
- [ ] External containment boundary is documented honestly.
- [ ] Bundle IDs are path-safe and unique.

## Evidence

- [ ] Authorization and observation are separate.
- [ ] Causal findings are exported.
- [ ] Replay trace is exported.
- [ ] Durable hash-linked records exist.
- [ ] Intent/action/result/verification roles exist.
- [ ] Manifest records exact size and SHA-256.
- [ ] Independent verification detects tampering.

## Tests

- [ ] Safe action.
- [ ] Missing intent.
- [ ] Missing causal parent.
- [ ] Missing nonce.
- [ ] Nonce replay.
- [ ] Irreversible action without approval.
- [ ] Secret egress blocked.
- [ ] Approved allow-listed egress.
- [ ] Alias precedence.
- [ ] Path traversal.
- [ ] Nonce race.
- [ ] Evidence tampering.

## Delivery

- [ ] Focused tests pass.
- [ ] Repository-wide checks pass.
- [ ] CI is green.
- [ ] Review threads are resolved.
- [ ] PR is mergeable.
- [ ] Final report includes honest non-claims.
