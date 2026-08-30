"""Deterministic qualification rules. The model never decides *whether* to look
at something — only *what to say* once these functions say it qualifies.
"""

from __future__ import annotations

from datetime import date, timedelta

from household_agent.data import table as repo
from household_agent.models import Event, GroceryItem, Member, WishlistItem

SEASON_BOUNDARIES = [(3, 1), (6, 1), (9, 1), (12, 1)]
WARDROBE_STALE_DAYS = 90
GIFT_LOOKAHEAD_DAYS = 14
TRAVEL_TARGET_BUFFER = 1.1


def _season_crossed(last_entry: date, today: date) -> bool:
    d = last_entry
    while d < today:
        d = d + timedelta(days=1)
        if (d.month, d.day) in SEASON_BOUNDARIES:
            return True
    return False


def next_occurrence(month: int, day: int, today: date) -> date:
    candidate = date(today.year, month, day)
    return candidate if candidate >= today else date(today.year + 1, month, day)


def wardrobe_candidates(today: date | None = None) -> list[Member]:
    today = today or date.today()
    result = []
    for m in repo.get_members():
        if not m.size_history:
            continue
        last = max(entry.date for entry in m.size_history)
        stale = (today - last).days >= WARDROBE_STALE_DAYS
        if stale or _season_crossed(last, today):
            result.append(m)
    return result


def gift_candidates(
    lookahead_days: int = GIFT_LOOKAHEAD_DAYS, today: date | None = None
) -> list[Event]:
    today = today or date.today()
    existing_this_year = {
        (tx.ref_id, tx.created_at.year)
        for tx in repo.get_transactions()
        if tx.category == "gifts"
    }
    result = []
    for e in repo.get_events():
        next_date = next_occurrence(e.month, e.day, today)
        if (next_date - today).days > lookahead_days:
            continue
        if (e.id, next_date.year) in existing_this_year:
            continue
        result.append(e)
    return result


def grocery_candidates(today: date | None = None) -> list[GroceryItem]:
    today = today or date.today()
    return [
        g
        for g in repo.get_grocery_items()
        if g.last_ordered_date + timedelta(days=g.frequency_days) <= today
    ]


def travel_candidates() -> list[WishlistItem]:
    result = []
    for w in repo.get_wishlist_items():
        if w.category != "travel" or w.status != "watching" or not w.price_history:
            continue
        latest = max(w.price_history, key=lambda p: p.date)
        if latest.price <= w.target_price * TRAVEL_TARGET_BUFFER:
            result.append(w)
    return result
