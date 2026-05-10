---
name: Protocol critique
description: Critique ProofPath as a protocol or security boundary
title: "Protocol critique: "
labels: ["protocol", "feedback", "security"]
body:
  - type: markdown
    attributes:
      value: |
        Use this template for protocol-level critique.

        Suggested docs to review:
        - `specs/proofpath-http-profile-v0.1.md`
        - `specs/threat-model.md`
        - `docs/philosophy.md`

  - type: textarea
    id: summary
    attributes:
      label: Summary
      description: What is your main critique or observation?
    validations:
      required: true

  - type: textarea
    id: threat_model
    attributes:
      label: Threat model gaps
      description: What attacks, misuse cases, or system failures are missing?
    validations:
      required: false

  - type: textarea
    id: protocol_design
    attributes:
      label: Protocol design feedback
      description: Headers, decisions, reason codes, replay protection, signatures, interoperability, etc.
    validations:
      required: false

  - type: textarea
    id: standards
    attributes:
      label: Standards alignment
      description: HTTP Message Signatures, W3C Trace Context, OpenTelemetry, OAuth, API gateways, etc.
    validations:
      required: false

  - type: textarea
    id: recommendations
    attributes:
      label: Recommendations
      description: What should change first?
    validations:
      required: false
