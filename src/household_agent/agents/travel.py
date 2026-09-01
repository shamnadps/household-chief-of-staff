"""Travel agent: fetches one live current price per watched trip (one SerpAPI
call each), appends it to price_history, then proposes booking any trip now at
or near its target price."""

from __future__ import annotations

from datetime import date

from household_agent.agents.base import build_agent, propose_batch
from household_agent.agents.schemas import ProposalItem
from household_agent.config import LIVE_PRICING_ENABLED, money
from household_agent.data import table as repo
from household_agent.data.price_service import get_flight_price
from household_agent.models import WishlistItem
from household_agent.triggers import travel_candidates

SYSTEM_PROMPT = """You are the Travel agent for a household chief-of-staff system.

You are given one or more trips from the family's travel wishlist whose latest
price is at or near the target for that route. Propose ONE booking per trip, at
its latest known price.

Ground every justification in the concrete numbers given: the route, the target
price, the latest price and how it compares to the target and to the seasonal
low, and the travel dates. State plainly that the current price is live and the
historical trend is a seeded approximation if that distinction matters to your
reasoning.

Set ref_id to the wishlist item's id exactly as given."""


def _refresh_live_prices() -> None:
    if not LIVE_PRICING_ENABLED:
        return  # no SerpAPI key: fall back to the seeded price history
    for item in repo.get_wishlist_items():
        if item.category != "travel" or item.status != "watching":
            continue
        if not (item.origin and item.destination and item.depart_date and item.return_date):
            continue
        entry = get_flight_price(
            item.origin,
            item.destination,
            item.depart_date,
            item.return_date,
            passengers=item.passengers or 1,
        )
        repo.append_price_history(item.id, entry)


def _format_item(w: WishlistItem) -> str:
    history = sorted(w.price_history, key=lambda p: p.date)
    latest = history[-1] if history else None
    if not latest:
        return f"Trip: {w.name} (id={w.id})\nNo price history."
    return (
        f"Trip: {w.name} (id={w.id})\n"
        f"Route: {w.origin} -> {w.destination}, {w.depart_date} to {w.return_date}, "
        f"{w.passengers} passengers\n"
        f"Target price: {money(w.target_price)}\n"
        f"Latest price: {money(latest.price)} on {latest.date.isoformat()} "
        f"(source: {latest.source})"
    )


def build_prompt(items: list[WishlistItem], today: date) -> str:
    blocks = "\n\n".join(_format_item(w) for w in items)
    return f"Today is {today.isoformat()}.\n\nTrips near their target price:\n\n{blocks}"


def propose(today: date | None = None) -> list[ProposalItem]:
    today = today or date.today()
    _refresh_live_prices()
    candidates = travel_candidates()
    if not candidates:
        return []
    agent = build_agent("travel_agent", SYSTEM_PROMPT)
    return propose_batch(agent, build_prompt(candidates, today))
