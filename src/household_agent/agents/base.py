"""Shared construction for the four category agents. Each is a single-turn
Strands ``Agent`` that returns a typed ``ProposalBatch`` via structured output —
no tools, no multi-turn loop; the orchestrator (see ``orchestrator.py``) is what
strings them together.
"""

from __future__ import annotations

from functools import lru_cache

from strands import Agent

from household_agent.agents.model import category_model
from household_agent.agents.schemas import ProposalBatch, ProposalItem


@lru_cache(maxsize=8)
def build_agent(name: str, system_prompt: str) -> Agent:
    return Agent(name=name, model=category_model(), system_prompt=system_prompt)


def propose_batch(agent: Agent, prompt: str) -> list[ProposalItem]:
    """Run the agent once and pull its validated proposals out."""
    result: ProposalBatch = agent.structured_output(ProposalBatch, prompt)
    return list(result.proposals)
