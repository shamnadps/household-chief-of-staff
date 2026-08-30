"""Plain AWS Lambda handler for the daily sweep — the deployable fallback for
running the background job without Bedrock AgentCore Runtime.

EventBridge Scheduler invokes this once a day (see infra/template.yaml). It
calls the exact same ``sweep.run_sweep()`` the AgentCore Runtime entrypoint
(``runtime.py``) calls for ``{"action": "sweep"}`` — one code path, two hosts.
"""

from __future__ import annotations

from household_agent.sweep import run_sweep


def handler(event: dict | None = None, context: object | None = None) -> dict:
    entry = run_sweep()
    return {
        "run_at": entry.run_at.isoformat(),
        "proposals_created": entry.proposals_created,
        "categories_checked": entry.categories_checked,
    }
