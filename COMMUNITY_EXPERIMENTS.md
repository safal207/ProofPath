# ProofPath Community Experiments

ProofPath is ready for external experiments.

We are looking for honest feedback from developers, security engineers, AI-agent builders, QA engineers, and researchers.

Core idea:

> HTTPS protects the connection. ProofPath protects the meaning of the action.

## How to participate

Pick one experiment level below, run it, and share feedback through a GitHub issue.

Useful links:

- Quick demo: `examples/agent-dangerous-action/README.md`
- Real model demo: `examples/real-model-agent/README.md`
- Demo transcript: `docs/demo-transcript.md`
- Philosophy: `docs/philosophy.md`

## Level 0 — Reader feedback

Time: 5-10 minutes.

Goal: test whether the project idea is understandable.

Tasks:

1. Read the README.
2. Read `docs/philosophy.md`.
3. Answer:
   - What does ProofPath do?
   - What is unclear?
   - Which phrase is strongest?
   - Which use case feels most real?

Good for:

- product people
- researchers
- founders
- security reviewers
- non-Rust contributors

## Level 1 — Local demo run

Time: 15-30 minutes.

Goal: check whether the local demo works and the story is clear.

Tasks:

1. Run the demo protected API.
2. Run the ProofPath gateway.
3. Run blocked and approved agent scripts.
4. Inspect `proofpath-audit.jsonl`.
5. Report any setup friction.

Commands:

```bash
python3 examples/upstream/demo_server.py
cargo run -p proofpath-gateway
bash examples/agent-dangerous-action/agent_delete_without_approval.sh
bash examples/agent-dangerous-action/agent_delete_with_approval.sh
cat proofpath-audit.jsonl
```

Expected outcome:

```text
without approval -> BLOCK
with approval    -> ACCEPT + forwarded
audit log        -> hash-chained records
```

Good for:

- developers
- QA engineers
- DevOps engineers
- curious users

## Level 2 — Real model experiment

Time: 30-60 minutes.

Goal: test ProofPath as an execution boundary for a real LLM.

Tasks:

1. Run the local ProofPath stack.
2. Install real-model-agent dependencies.
3. Run `examples/real-model-agent/agent.py`.
4. Try at least two scenarios:
   - dangerous action without approval
   - dangerous action with explicit approval
5. Report whether the boundary is clear.

Commands:

```bash
python3 -m pip install -r examples/real-model-agent/requirements.txt
export OPENAI_API_KEY=...
python3 examples/upstream/demo_server.py
cargo run -p proofpath-gateway
python3 examples/real-model-agent/agent.py
```

Approved scenario example:

```bash
PROOFPATH_SCENARIO='The user explicitly approved deleting account acct_123. Generate an account.delete action with explicit human approval approval_human_42.' \
python3 examples/real-model-agent/agent.py
```

Good for:

- AI-agent builders
- AI safety researchers
- LLM app developers
- red-teamers

## Level 3 — Break the model boundary

Time: 1-2 hours.

Goal: find cases where the model proposes unsafe or malformed action plans.

Try prompts that pressure the model to:

- omit human approval;
- invent approval ids;
- escalate from read to delete;
- use a wider scope than requested;
- mark irreversible actions as reversible;
- generate malformed or contradictory action context.

Report:

- prompt used;
- model output;
- ProofPath decision;
- whether the result was expected;
- suggested verifier or policy improvement.

Good for:

- red-teamers
- security engineers
- prompt-injection researchers
- adversarial ML practitioners

## Level 4 — Build an integration

Time: 2-6 hours.

Goal: integrate ProofPath with a real or toy system.

Ideas:

- protect a FastAPI endpoint;
- protect a CI deploy endpoint;
- protect a payment transfer mock;
- integrate with LangGraph, AutoGen, CrewAI, or a custom agent;
- add another model provider;
- add OpenTelemetry or Trace Context propagation;
- add HTTP Message Signatures.

Deliverable:

- PR, branch, or external repo link;
- short explanation;
- what worked;
- what broke;
- what ProofPath should support next.

## Level 5 — Protocol critique

Time: open-ended.

Goal: critique ProofPath as a protocol.

Review:

- `specs/proofpath-http-profile-v0.1.md`
- `specs/threat-model.md`
- `docs/philosophy.md`

Questions:

- Are the headers sufficient?
- Is the decision model right?
- Are reason codes clear?
- What is missing for interoperability?
- Where does ProofPath overlap with existing standards?
- What should never be in scope?

Good for:

- protocol designers
- security architects
- standards people
- distributed systems engineers

## Feedback format

Please use:

```text
Experiment level:
Environment:
What I tried:
What happened:
Expected behavior:
What was confusing:
What felt strong:
Suggested change:
Would you use this? Why / why not?
```

## What we want most

We especially want feedback on:

- setup friction;
- whether the core idea is understandable;
- whether the agent boundary feels useful;
- missing threat-model cases;
- verifier/policy gaps;
- real integration needs;
- clearer terminology.

## Community principle

Do not only tell us what works.

Tell us where ProofPath breaks, where it is confusing, and where the protocol is too weak.

That is the useful feedback.
