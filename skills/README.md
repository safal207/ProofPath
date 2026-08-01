# ProofPath installable skills

## Agent Action Safety Chain

Portable ChatGPT skill for defensive AI-agent action auditing and implementation:

```text
proposal
→ ProofPath ACCEPT / HOLD / BLOCK
→ guarded execution
→ causal and replay traces
→ durable evidence
→ CI / review / merge readiness
```

- Skill source: [`agent-action-safety-chain/`](agent-action-safety-chain/)
- Mobile installation: [`agent-action-safety-chain/README_RU.md`](agent-action-safety-chain/README_RU.md)
- Release ZIP: `agent-action-safety-chain.zip`
- Release tag: `agent-action-safety-chain-v1.0.0`

Build locally:

```bash
python3 scripts/build_agent_action_safety_chain_skill.py
```

## Three-Graph Agent Safety v1.2

Portable ChatGPT skill for identity-bound, capability-scoped, time-valid personal-agent decisions.

Three truth graphs:

```text
Idea + Intent + Fact
```

Six control graphs:

```text
Identity + Policy + Capability + Memory + Temporal + Risk
```

Core rule:

```text
identity proves who
capability proves can
Intent proves may
Temporal proves still valid
Fact proves happened
```

- Skill source: [`three-graph-agent-safety/`](three-graph-agent-safety/)
- Mobile installation: [`three-graph-agent-safety/README_RU.md`](three-graph-agent-safety/README_RU.md)
- Legacy schema: [`three-graph-agent-safety/assets/three-graph-bundle.schema.json`](three-graph-agent-safety/assets/three-graph-bundle.schema.json)
- Personal Agent Safety v1.1 schema: [`three-graph-agent-safety/assets/personal-agent-safety-bundle.schema.json`](three-graph-agent-safety/assets/personal-agent-safety-bundle.schema.json)
- Personal Agent Safety v1.2 schema: [`three-graph-agent-safety/assets/personal-agent-safety-v1.2-bundle.schema.json`](three-graph-agent-safety/assets/personal-agent-safety-v1.2-bundle.schema.json)
- Semantic validator: [`three-graph-agent-safety/tools/validate_personal_agent_safety_bundle.py`](three-graph-agent-safety/tools/validate_personal_agent_safety_bundle.py)
- Release ZIP: `three-graph-agent-safety.zip`
- Release tag: `three-graph-agent-safety-v1.2.0`

Build locally:

```bash
python3 scripts/build_three_graph_agent_safety_skill.py
```
