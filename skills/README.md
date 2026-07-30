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

## Three-Graph Agent Safety

Portable ChatGPT skill that separates agent reasoning, user authority, and observed reality:

```text
Idea Graph
+ Intent Graph
+ Fact Graph
→ alignment and mismatch detection
→ containment and recovery
→ independent verification
→ SAFE_COMPLETION
```

- Skill source: [`three-graph-agent-safety/`](three-graph-agent-safety/)
- Mobile installation and usage: [`three-graph-agent-safety/README_RU.md`](three-graph-agent-safety/README_RU.md)
- Machine-readable bundle schema: [`three-graph-agent-safety/assets/three-graph-bundle.schema.json`](three-graph-agent-safety/assets/three-graph-bundle.schema.json)
- Release ZIP: `three-graph-agent-safety.zip`
- Release tag: `three-graph-agent-safety-v1.0.0`

Build locally:

```bash
python3 scripts/build_three_graph_agent_safety_skill.py
```
