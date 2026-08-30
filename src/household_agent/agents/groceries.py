"""Groceries agent: proposes a reorder for items past their usual cadence, and
notes a cost-saving timing angle if there's a real one."""

from __future__ import annotations

from datetime import date, timedelta

from household_agent.agents.base import build_agent, propose_batch
from household_agent.agents.schemas import ProposalItem
from household_agent.config import money
from household_agent.models import GroceryItem
from household_agent.triggers import grocery_candidates

SYSTEM_PROMPT = """You are the Groceries agent for a household chief-of-staff system.

You are given one or more grocery items due for reorder (their usual cadence
has elapsed since last_ordered_date). Propose ONE reorder per item, at its
typical_price and quantity, from its preferred store. If you notice a genuine
cost-saving angle (a larger pack, or that the item is very overdue), mention it
briefly in the justification — but the proposal itself is the standard reorder.

Ground every justification in the concrete numbers given: item name, days
overdue, typical price, quantity, store.

Set ref_id to the grocery item's id exactly as given."""


def _format_item(g: GroceryItem, today: date) -> str:
    due_date = g.last_ordered_date + timedelta(days=g.frequency_days)
    days_overdue = (today - due_date).days
    return (
        f"Item: {g.name} (id={g.id})\n"
        f"Last ordered: {g.last_ordered_date.isoformat()}, reorder every "
        f"{g.frequency_days} days ({days_overdue} days overdue)\n"
        f"Typical price: {money(g.typical_price)} for {g.quantity}\n"
        f"Preferred store: {g.preferred_store}"
    )


def build_prompt(items: list[GroceryItem], today: date) -> str:
    blocks = "\n\n".join(_format_item(g, today) for g in items)
    return f"Today is {today.isoformat()}.\n\nGrocery items due for reorder:\n\n{blocks}"


def propose(today: date | None = None) -> list[ProposalItem]:
    today = today or date.today()
    candidates = grocery_candidates(today=today)
    if not candidates:
        return []
    agent = build_agent("groceries_agent", SYSTEM_PROMPT)
    return propose_batch(agent, build_prompt(candidates, today))
