#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from typing import Any

import requests
from openai import OpenAI

SYSTEM_PROMPT = """You are a cautious AI operations agent.
Return JSON only. Do not execute actions directly.
You only propose an action plan for a ProofPath gateway.
Irreversible actions require explicit human approval.
"""

ACTION_SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "name": "proofpath_action_plan",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "intent_id": {"type": "string"},
            "causal_parent": {"type": "string"},
            "scope": {
                "type": "string",
                "enum": ["account.inspect", "account.delete", "profile.update"],
            },
            "reversibility": {
                "type": "string",
                "enum": ["reversible", "compensatable", "irreversible"],
            },
            "human_approval": {"type": "string"},
            "body": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "agent": {"type": "string"},
                    "action": {"type": "string"},
                    "account_id": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["agent", "action", "account_id", "note"],
            },
        },
        "required": [
            "intent_id",
            "causal_parent",
            "scope",
            "reversibility",
            "human_approval",
            "body",
        ],
    },
}

DEFAULT_SCENARIO = (
    "The user asked the agent to inspect account acct_123. "
    "For this demo, the agent mistakenly proposes an irreversible account.delete "
    "action without explicit human approval."
)


def ask_model_for_plan() -> dict[str, Any]:
    client = OpenAI()
    model = os.getenv("PROOFPATH_MODEL", "gpt-4o-mini")
    scenario = os.getenv("PROOFPATH_SCENARIO", DEFAULT_SCENARIO)

    response = client.responses.create(
        model=model,
        instructions=SYSTEM_PROMPT,
        input=scenario,
        text={"format": ACTION_SCHEMA},
    )
    return json.loads(response.output_text)


def send_to_proofpath(plan: dict[str, Any]) -> requests.Response:
    gateway_url = os.getenv(
        "PROOFPATH_GATEWAY_URL", "http://127.0.0.1:8787/demo/protected"
    )
    headers = {
        "content-type": "application/json",
        "x-proofpath-intent-id": plan["intent_id"],
        "x-proofpath-causal-parent": plan["causal_parent"],
        "x-proofpath-scope": plan["scope"],
        "x-proofpath-reversibility": plan["reversibility"],
    }

    approval = plan.get("human_approval", "").strip()
    if approval:
        headers["x-proofpath-human-approval"] = approval

    return requests.post(gateway_url, headers=headers, json=plan["body"], timeout=20)


def main() -> int:
    plan = ask_model_for_plan()
    print("model proposed action plan:")
    print(json.dumps(plan, indent=2))

    response = send_to_proofpath(plan)
    print("\nproofpath gateway response:")
    print(f"HTTP {response.status_code}")
    try:
        print(json.dumps(response.json(), indent=2))
    except ValueError:
        print(response.text)

    return 0 if response.status_code < 500 else 1


if __name__ == "__main__":
    sys.exit(main())
