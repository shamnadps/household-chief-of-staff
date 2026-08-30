"""Bedrock AgentCore Runtime entrypoint.

One HTTP surface, dispatched on ``payload["action"]``:

    {"action": "sweep"}                 -> run the daily background sweep
    {"action": "ask", "prompt": "..."}  -> interactive chief-of-staff Q&A
                                           (Strands agents-as-tools + AgentCore Memory)

``EventBridge Scheduler`` invokes it once a day with ``{"action": "sweep"}``;
a human (or the dashboard) invokes it with ``{"action": "ask", ...}``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from household_agent.agents.orchestrator import ask
from household_agent.memory import session_manager
from household_agent.sweep import run_sweep

app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload: dict) -> dict:
    action = (payload or {}).get("action", "ask")

    if action == "sweep":
        entry = run_sweep()
        return {
            "action": "sweep",
            "run_at": entry.run_at.isoformat(),
            "proposals_created": entry.proposals_created,
            "categories_checked": entry.categories_checked,
        }

    if action == "ask":
        prompt = (payload or {}).get("prompt", "").strip()
        if not prompt:
            return {"error": "payload.prompt is required for action 'ask'"}
        sid = (payload or {}).get("session_id") or datetime.now(timezone.utc).strftime(
            "sess-%Y%m%d%H%M%S"
        )
        return {"action": "ask", "session_id": sid, "answer": ask(prompt, session_manager(sid))}

    return {"error": f"unknown action: {action!r}"}


if __name__ == "__main__":
    app.run()
