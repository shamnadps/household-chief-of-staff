"""Gifts agent: proposes a gift for an upcoming birthday/anniversary (within
GIFT_LOOKAHEAD_DAYS) that doesn't repeat a past year's gift for that person."""

from __future__ import annotations

from datetime import date

from household_agent.agents.base import build_agent, propose_batch
from household_agent.agents.schemas import ProposalItem
from household_agent.config import money
from household_agent.models import Event
from household_agent.triggers import GIFT_LOOKAHEAD_DAYS, gift_candidates, next_occurrence

SYSTEM_PROMPT = """You are the Gifts agent for a household chief-of-staff system.

You are given one or more upcoming birthdays/anniversaries and, for each, the
recipient's gift history from past years. Propose ONE gift idea per event,
within the event's stated gift_budget, that is NOT the same item as any past
gift for that person.

Ground the justification in the concrete facts you were given: the event type,
how many days away it is, and (if present) what was given in a previous year
and why this year's idea differs. Never propose an amount above the stated
gift_budget.

Set ref_id to the event's id exactly as given."""


def _format_event(e: Event, today: date) -> str:
    next_date = next_occurrence(e.month, e.day, today)
    days_away = (next_date - today).days
    history = (
        "\n".join(f"  - {g.year}: {g.item} ({money(g.price)})" for g in e.gift_history)
        or "  (none)"
    )
    return (
        f"Event: {e.type} for {e.person_name} (id={e.id})\n"
        f"Date: {next_date.isoformat()} ({days_away} days away)\n"
        f"Gift budget: {money(e.gift_budget)}\n"
        f"Past gifts:\n{history}"
    )


def build_prompt(events: list[Event], today: date) -> str:
    blocks = "\n\n".join(_format_event(e, today) for e in events)
    return (
        f"Today is {today.isoformat()}.\n\n"
        f"Events within {GIFT_LOOKAHEAD_DAYS} days:\n\n{blocks}"
    )


def propose(today: date | None = None) -> list[ProposalItem]:
    today = today or date.today()
    candidates = gift_candidates(today=today)
    if not candidates:
        return []
    agent = build_agent("gifts_agent", SYSTEM_PROMPT)
    return propose_batch(agent, build_prompt(candidates, today))
