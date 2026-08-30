"""Wardrobe agent: proposes a capsule purchase for kids whose sizing data is
stale or who've crossed a season boundary (per triggers.py)."""

from __future__ import annotations

from datetime import date

from household_agent.agents.base import build_agent, propose_batch
from household_agent.agents.schemas import ProposalItem
from household_agent.config import CURRENCY
from household_agent.models import Member
from household_agent.triggers import wardrobe_candidates

SYSTEM_PROMPT = """You are the Wardrobe agent for a household chief-of-staff system.

You are given the size history of one or more kids whose sizing data is due for
review (over 90 days stale, or a season boundary has passed since the last
entry). For each kid, propose ONE purchase: shoes and/or clothing sized for
their most recent measurements, appropriate for the upcoming season.

Ground every justification in the concrete numbers you were given — cite the
actual size change (e.g. "grew from EU 30 to EU 32") and the actual number of
days since the last review. Never invent a size, a date, or a price that wasn't
implied by the data. Estimate a reasonable amount for a small capsule (shoes +
a couple of clothing pieces) for one child, informed by their stated
colour/brand preferences if given.

Set ref_id to the member's id exactly as given. If nothing genuinely warrants a
purchase for a child, omit them — do not propose out of obligation."""


def _format_member(m: Member, today: date) -> str:
    history = sorted(m.size_history, key=lambda e: e.date)
    lines = [
        f"- {e.date.isoformat()}: shoe EU {e.shoe_eu}, top {e.top_cm}cm, bottom {e.bottom_cm}cm"
        for e in history
    ]
    last = history[-1].date if history else None
    days_stale = (today - last).days if last else None
    prefs = m.preferences or {}
    return (
        f"Child: {m.name} (id={m.id})\n"
        f"Size history:\n" + "\n".join(lines) + "\n"
        f"Days since last review: {days_stale}\n"
        f"Preferences: colors={prefs.get('colors', [])}, brands={prefs.get('brands', [])}, "
        f"interests={prefs.get('interests', [])}"
    )


def build_prompt(members: list[Member], today: date) -> str:
    blocks = "\n\n".join(_format_member(m, today) for m in members)
    return (
        f"Today is {today.isoformat()}. All amounts in {CURRENCY}.\n\n"
        f"Children due for wardrobe review:\n\n{blocks}"
    )


def propose(today: date | None = None) -> list[ProposalItem]:
    today = today or date.today()
    candidates = wardrobe_candidates(today=today)
    if not candidates:
        return []
    agent = build_agent("wardrobe_agent", SYSTEM_PROMPT)
    return propose_batch(agent, build_prompt(candidates, today))
