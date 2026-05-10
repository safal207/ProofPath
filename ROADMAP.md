# ProofPath Roadmap

ProofPath is currently in early protocol design. The roadmap is intentionally small and implementation-oriented.

## Phase 0: Protocol foundation

Goal: make the idea precise enough for reviewers and contributors.

- [ ] Define ProofPath HTTP Profile v0.1.
- [ ] Define required and optional headers.
- [ ] Define decision outcomes and reason codes.
- [ ] Define minimal conformance fixtures.
- [ ] Define threat model.
- [ ] Define signed request context profile.

## Phase 1: Minimal verifier

Goal: validate ProofPath request context without building a full gateway yet.

- [ ] Implement Rust data types for ProofPath headers.
- [ ] Parse request metadata into a verifier input model.
- [ ] Validate required fields.
- [ ] Validate reversibility values.
- [ ] Validate decision output shape.
- [ ] Return structured JSON decisions.
- [ ] Add unit tests for valid and invalid cases.

## Phase 2: Gateway MVP

Goal: protect a sample API with a ProofPath-aware gateway.

- [ ] Build Axum-based reverse proxy.
- [ ] Add policy checks for scope and reversibility.
- [ ] Add append-only JSONL audit log.
- [ ] Add request/response examples.
- [ ] Add demo: irreversible action without approval is blocked.
- [ ] Add demo: approved action is accepted.

## Phase 3: Signatures and replay protection

Goal: make ProofPath context tamper-evident.

- [ ] Support HTTP Message Signatures for critical headers.
- [ ] Add request digest support.
- [ ] Add nonce/timestamp validation.
- [ ] Add replay cache for critical scopes.
- [ ] Add conformance fixtures for invalid signatures and replayed requests.

## Phase 4: Agentic web integrations

Goal: make ProofPath useful for AI-agent workflows.

- [ ] Define AI-agent action envelope.
- [ ] Add example with agent tool call.
- [ ] Add example with CI/CD deployment gate.
- [ ] Add example with payment-like irreversible action.
- [ ] Add CLI inspector for traces.

## Phase 5: Community and standardization

Goal: move from prototype to ecosystem.

- [ ] Publish design note: Why HTTPS is not enough for AI agents.
- [ ] Create contribution guide.
- [ ] Add good-first-issue tasks.
- [ ] Add security policy.
- [ ] Start collecting feedback from security, API gateway, and AI safety communities.
