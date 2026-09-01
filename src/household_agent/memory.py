"""Bedrock AgentCore Memory helpers.

The interactive orchestrator (``agents/orchestrator.ask``) attaches a session
manager so a family's questions and the agent's answers persist across sweeps —
short-term within a conversation, long-term as extracted preferences/facts.

``create_memory_resource`` is a one-time setup step; ``scripts/create_memory.py``
calls it and prints the id to put in ``AGENTCORE_MEMORY_ID``.
"""

from __future__ import annotations

from household_agent.config import AGENTCORE_MEMORY_ID, AWS_REGION, FAMILY_ID


def create_memory_resource(name: str = "HouseholdChiefOfStaffMemory") -> str:
    from bedrock_agentcore.memory import MemoryClient

    client = MemoryClient(region_name=AWS_REGION)
    memory = client.create_memory(
        name=name,
        description="Cross-sweep context for the household chief-of-staff agent: "
        "the family's questions, the agent's answers, and extracted preferences.",
    )
    return memory["id"]


def session_manager(session_id: str):
    """An ``AgentCoreMemorySessionManager`` bound to this family, or ``None`` when
    no memory resource is configured (local dev / tests)."""
    if not AGENTCORE_MEMORY_ID:
        return None

    from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
    from bedrock_agentcore.memory.integrations.strands.session_manager import (
        AgentCoreMemorySessionManager,
    )

    config = AgentCoreMemoryConfig(
        memory_id=AGENTCORE_MEMORY_ID,
        session_id=session_id,
        # AgentCore's actorId pattern rejects an empty segment ("::"), so a
        # single colon separates the namespace from the family id.
        actor_id=f"family:{FAMILY_ID}",
    )
    return AgentCoreMemorySessionManager(config, region_name=AWS_REGION)
