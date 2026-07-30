# ProofPath installable skills

## Agent Action Safety Chain

Portable ChatGPT skill for defensive AI-agent action auditing and implementation:

```text
proposal
→ ProofPath ACCEPT / HOLD / BLOCK
→ guarded execution
→ CML / LTP traces
→ durable ledger
→ verified evidence bundle
→ CI / review / merge readiness
```

- Skill source: [`agent-action-safety-chain/`](agent-action-safety-chain/)
- Mobile installation and usage: [`agent-action-safety-chain/README_RU.md`](agent-action-safety-chain/README_RU.md)
- Release ZIP: `agent-action-safety-chain.zip`
- Release tag: `agent-action-safety-chain-v1.0.0`

Build locally:

```bash
python3 scripts/build_agent_action_safety_chain_skill.py
```

## Three-Graph Agent Safety v1.1

Portable ChatGPT skill for safe personal-agent decisions.

Three truth graphs:

```text
Idea + Intent + Fact
```

Three context-control graphs:

```text
Policy + Memory + Risk
```

The v1.1 invariant is:

```text
memory informs reasoning
but never creates authority
```

- Skill source: [`three-graph-agent-safety/`](three-graph-agent-safety/)
- Mobile installation: [`three-graph-agent-safety/README_RU.md`](three-graph-agent-safety/README_RU.md)
- Legacy three-graph schema: [`three-graph-agent-safety/assets/three-graph-bundle.schema.json`](three-graph-agent-safety/assets/three-graph-bundle.schema.json)
- Personal Agent Safety v1.1 schema: [`three-graph-agent-safety/assets/personal-agent-safety-bundle.schema.json`](three-graph-agent-safety/assets/personal-agent-safety-bundle.schema.json)
- Validated example: [`three-graph-agent-safety/assets/personal-agent-safety.example.json`](three-graph-agent-safety/assets/personal-agent-safety.example.json)
- Semantic validator: [`three-graph-agent-safety/tools/validate_personal_agent_safety_bundle.py`](three-graph-agent-safety/tools/validate_personal_agent_safety_bundle.py)
- Release ZIP: `three-graph-agent-safety.zip`
- Release tag: `three-graph-agent-safety-v1.1.0`

Build and validate locally:

```bash
python3 scripts/build_three_graph_agent_safety_skill.py
```
