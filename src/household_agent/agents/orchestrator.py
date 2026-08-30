"""The chief-of-staff orchestrator.

Two entry points, one set of specialists:

* ``run_sweep()`` — the scheduled background job. Orchestration here is
  deterministic *on purpose*: plain code decides whether a category has a
  candidate (triggers.py) and whether a proposal fits the budget
  (guardrail.py). The model's only job is the per-category "what to say" step,
  which is a Strands agent (see wardrobe.py / gifts.py / groceries.py /
  travel.py). See sweep.py for that pipeline.

* ``ask(question)`` — the interactive path exposed over Bedrock AgentCore
  Runtime. This is a real Strands *agents-as-tools* orchestrator: each
  specialist is wrapped as a tool, plus read-only tools over the family's live
  data, and the orchestrator model decides which specialist(s) to consult to
  answer a human's question ("why did you propose the hamper?", "what's
  coming up in groceries?"). AgentCore Memory keeps context across sweeps.
"""

from __future__ import annotations

import json
from datetime import date

from strands import Agent, tool

from household_agent.agents import gifts, groceries, travel, wardrobe
from household_agent.agents.model import category_model
from household_agent.data import table as repo

ORCHESTRATOR_PROMPT = """You are the Household Chief of Staff — the coordinator a
family talks to about the background work their agent does.

You have four specialists available as tools (wardrobe, gifts, groceries,
travel) and read-only tools over the family's current data and the proposal
log. When a human asks a question, consult whichever specialists and data you
need, then answer plainly in 2-4 sentences. Always ground the answer in real
numbers from the tools — never guess. You never move money or send email; you
explain and recommend. If asked to actually approve or reject something, say
that only the human can do that from the email or the dashboard."""


# ---- specialists as tools ---------------------------------------------------


@tool
def wardrobe_review(today: str | None = None) -> str:
    """Run the wardrobe specialist: proposals for kids whose sizing is stale or
    who crossed a season boundary. Returns JSON list of proposals (may be empty)."""
    d = date.fromisoformat(today) if today else None
    return json.dumps([p.model_dump() for p in wardrobe.propose(today=d)])


@tool
def gift_review(today: str | None = None) -> str:
    """Run the gifts specialist: a non-repeating gift idea for any birthday or
    anniversary within the lookahead window. Returns JSON list of proposals."""
    d = date.fromisoformat(today) if today else None
    return json.dumps([p.model_dump() for p in gifts.propose(today=d)])


@tool
def grocery_review(today: str | None = None) -> str:
    """Run the groceries specialist: reorders for items past their cadence.
    Returns JSON list of proposals."""
    d = date.fromisoformat(today) if today else None
    return json.dumps([p.model_dump() for p in groceries.propose(today=d)])


@tool
def travel_review(today: str | None = None) -> str:
    """Run the travel specialist: fetches live flight prices for watched trips
    and proposes booking any at/near target. Returns JSON list of proposals."""
    d = date.fromisoformat(today) if today else None
    return json.dumps([p.model_dump() for p in travel.propose(today=d)])


# ---- read-only data tools -------------------------------------------------


@tool
def family_snapshot() -> str:
    """Current family data: members and their latest sizes, upcoming events,
    grocery cadences, travel wishlist. JSON."""
    return json.dumps(
        {
            "members": [
                {
                    "id": m.id,
                    "name": m.name,
                    "role": m.role,
                    "latest_size": (
                        max(m.size_history, key=lambda e: e.date).__dict__
                        if m.size_history
                        else None
                    ),
                }
                for m in repo.get_members()
            ],
            "events": [
                {"id": e.id, "person": e.person_name, "type": e.type, "when": f"{e.month:02d}-{e.day:02d}"}
                for e in repo.get_events()
            ],
            "groceries": [
                {"id": g.id, "name": g.name, "every_days": g.frequency_days,
                 "last_ordered": g.last_ordered_date.isoformat()}
                for g in repo.get_grocery_items()
            ],
            "wishlist": [
                {"id": w.id, "name": w.name, "target": w.target_price, "status": w.status}
                for w in repo.get_wishlist_items()
            ],
        },
        default=str,
    )


@tool
def budget_snapshot() -> str:
    """Per-category monthly limit and amount spent so far this period. JSON."""
    return json.dumps(
        [
            {
                "category": c,
                "monthly_limit": (b := repo.get_budget(c)).monthly_limit,
                "spent_this_period": b.spent_this_period,
            }
            for c in ("wardrobe", "gifts", "groceries", "travel")
        ]
    )


@tool
def recent_proposals(limit: int = 10) -> str:
    """The most recent proposals the agent has made, newest first, with their
    status (proposed / executed / rejected) and justification. JSON."""
    txs = sorted(repo.get_transactions(), key=lambda t: t.created_at, reverse=True)[:limit]
    return json.dumps(
        [
            {
                "category": t.category,
                "description": t.description,
                "amount": t.amount,
                "status": t.status,
                "budget_status": t.budget_status,
                "justification": t.justification,
                "created_at": t.created_at.isoformat(),
            }
            for t in txs
        ]
    )


ORCHESTRATOR_TOOLS = [
    wardrobe_review,
    gift_review,
    grocery_review,
    travel_review,
    family_snapshot,
    budget_snapshot,
    recent_proposals,
]


def build_orchestrator(session_manager=None) -> Agent:
    return Agent(
        name="chief_of_staff",
        model=category_model(),
        system_prompt=ORCHESTRATOR_PROMPT,
        tools=ORCHESTRATOR_TOOLS,
        session_manager=session_manager,
    )


def ask(question: str, session_manager=None) -> str:
    """One-shot Q&A against the orchestrator. ``runtime.py`` passes an
    AgentCore Memory session manager so context carries across sweeps."""
    agent = build_orchestrator(session_manager=session_manager)
    return str(agent(question))
