---
name: Experiment feedback
description: Share results from a ProofPath community experiment
title: "Experiment feedback: "
labels: ["community", "feedback", "experiment"]
body:
  - type: markdown
    attributes:
      value: |
        Thank you for testing ProofPath.

        Useful starting point: `COMMUNITY_EXPERIMENTS.md`

  - type: dropdown
    id: level
    attributes:
      label: Experiment level
      options:
        - Level 0 — Reader feedback
        - Level 1 — Local demo run
        - Level 2 — Real model experiment
        - Level 3 — Break the model boundary
        - Level 4 — Build an integration
        - Level 5 — Protocol critique
    validations:
      required: true

  - type: textarea
    id: environment
    attributes:
      label: Environment
      description: OS, Rust version, Python version, model provider, relevant setup details.
      placeholder: "macOS / Linux / Windows, rustc --version, python --version, model used..."
    validations:
      required: false

  - type: textarea
    id: tried
    attributes:
      label: What I tried
      description: Commands, scenario, prompt, integration, or review path.
    validations:
      required: true

  - type: textarea
    id: happened
    attributes:
      label: What happened
      description: Output, logs, decisions, errors, audit records, screenshots, or transcript.
    validations:
      required: true

  - type: textarea
    id: expected
    attributes:
      label: Expected behavior
      description: What did you expect ProofPath to do?
    validations:
      required: false

  - type: textarea
    id: confusing
    attributes:
      label: What was confusing?
      description: Setup, terminology, protocol, gateway behavior, model boundary, docs, etc.
    validations:
      required: false

  - type: textarea
    id: strong
    attributes:
      label: What felt strong?
      description: What worked well or felt valuable?
    validations:
      required: false

  - type: textarea
    id: suggestions
    attributes:
      label: Suggested changes
      description: Concrete improvements to docs, protocol, verifier, gateway, examples, or roadmap.
    validations:
      required: false

  - type: textarea
    id: adoption
    attributes:
      label: Would you use this? Why / why not?
      description: Optional but very useful.
    validations:
      required: false
