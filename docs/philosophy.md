# ProofPath Philosophy

## Core line

**HTTPS protects the connection. ProofPath protects the meaning of the action.**

## What this means

A system can be technically secure and still perform the wrong action.

A valid token, encrypted channel, or authenticated request proves something important, but incomplete:

- the connection may be protected;
- the identity may be known;
- the request may be well-formed.

But that still does not prove:

- the action reflects a valid intent;
- the action was causally authorized;
- the action is within scope;
- the action is safe given its consequences;
- the action can be audited after the fact.

ProofPath exists for this missing layer.

## The shift

Traditional API security often asks:

> Who are you, and are you allowed to call this endpoint?

ProofPath asks:

> Why is this action happening, what intent does it serve, what authorized it, and can we prove that later?

## Agentic systems

This matters especially for AI-agent systems.

An AI agent may hold a valid token and use a valid HTTPS connection. But a valid connection does not prove that the agent understood the human intent correctly.

ProofPath treats critical actions as causal events, not just API calls.

## Operating principle

Accepted actions move forward.

Dangerous actions stop.

Every decision leaves a proof trail.
