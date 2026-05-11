# ProofPath reviewer summary

## One-line summary

ProofPath is a defensive pre-execution gateway that prevents valid AI-agent/API credentials from becoming unsafe, unaudited, or irreversible actions.

## Problem

AI agents increasingly interact with code repositories, infrastructure, APIs, financial workflows, CI/CD systems, and other security-sensitive tools. In many systems, once an agent has valid credentials or tool access, an action can execute immediately.

That is not enough for high-risk actions.

A request can be authenticated and still be unsafe. An AI agent may have valid credentials while attempting to delete data, modify infrastructure, push unsafe code, trigger a financial workflow, or perform an irreversible administrative action outside the intended scope.

Existing controls such as HTTPS, OAuth, IAM, API keys, and ordinary infrastructure security remain necessary. But they mostly answer whether a connection, credential, or broad permission is valid. They do not always answer whether this specific proposed action is safe, scoped, reversible, approved, and auditable.

ProofPath focuses on that execution boundary.

## Security model

ProofPath adds an action-level decision layer before a request reaches the protected upstream API.

It asks:

- What is the declared intent?
- What is the causal parent or prior authorization context?
- What scope is being used?
- Is the action reversible, compensatable, or irreversible?
- Does the action require human approval?
- Should the gateway allow, hold, reject, block, or audit the action?
- Can the decision be reviewed later?

The core principle is:

> Valid credentials should not automatically mean valid action.

ProofPath is not a replacement for HTTPS, OAuth, IAM, API keys, or ordinary infrastructure security. It is an additional action-level security and audit layer.

## What exists today

The current repository contains a runnable prototype with:

- a Rust verifier crate;
- an Axum gateway;
- a minimal HTTP action-context profile;
- checks for intent, causal parent, scope, reversibility, and human approval;
- upstream forwarding only after a ProofPath decision;
- blocking of unsafe irreversible actions before they reach the protected API;
- hash-chained JSONL audit logging;
- a protected demo endpoint;
- dangerous-action demo material;
- real-model-agent demo material;
- community experiment levels for external review.

The implementation is intentionally small and auditable. The goal is to demonstrate the security boundary clearly before expanding integrations.

## Why this matters for AI-agent cybersecurity

As tool-using models become more capable, a major failure mode shifts from:

> the model said something wrong

to:

> the system executed something unsafe.

This is especially relevant when AI agents can access:

- developer tools;
- cloud APIs;
- CI/CD pipelines;
- infrastructure scripts;
- financial or administrative workflows;
- governance or public-sector systems;
- production APIs.

ProofPath helps reduce the risk that valid API credentials or AI-agent tool access become unsafe, unaudited, or irreversible actions.

## What is intentionally out of scope

ProofPath does not claim to fully understand human intent.

It does not replace transport security, identity systems, IAM, OAuth, API keys, sandboxing, runtime monitoring, or secure software development practices.

It does not claim that a single gateway can solve all AI-agent safety or cybersecurity problems.

Instead, ProofPath focuses on one narrow and important boundary: action-level pre-execution checks for high-risk AI-agent/API actions.

## Current limitations

The current version is a prototype. Known limitations include:

- the action-context profile is early and may change;
- policy configuration is still minimal;
- integrations with agent frameworks are not yet mature;
- demos are intentionally small;
- audit-log verification needs more tooling;
- threat-model coverage should be expanded;
- usability for external developers needs more testing.

These limitations are part of the planned work and are documented explicitly to keep the project reviewable and conservative.

## Near-term roadmap

Near-term work should focus on:

1. hardening the ProofPath HTTP action-context profile;
2. improving the Rust verifier and Axum gateway;
3. adding stronger policy configuration;
4. expanding ACCEPT, HOLD, BLOCK, and AUDIT examples;
5. adding conformance fixtures and negative tests;
6. improving audit-log integrity and replay verification;
7. documenting integration patterns for AI-agent toolchains and CI workflows;
8. publishing a clearer threat model;
9. collecting feedback from developers and security researchers.

## Relationship to PythiaLabs

PythiaLabs is the broader evidence-gate framework.

ProofPath is a separate runnable reference prototype focused on action-level security enforcement for high-risk AI-agent/API actions.

The two projects are related in security philosophy, but ProofPath should be reviewed as its own concrete implementation: a small gateway that makes high-risk actions more constrained, auditable, and reviewable before execution.
