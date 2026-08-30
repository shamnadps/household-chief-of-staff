"""Per-category side effects applied when a transaction is approved and
executed — updates the source record so it stops re-qualifying on the next
sweep. Deterministic, no model involved.
"""

from __future__ import annotations

from datetime import date

from household_agent.data import table as repo
from household_agent.models import SizeEntry, Transaction


def _acknowledge_wardrobe(tx: Transaction) -> None:
    members = {m.id: m for m in repo.get_members()}
    member = members.get(tx.ref_id)
    if not member or not member.size_history:
        return
    last = max(member.size_history, key=lambda e: e.date)
    repo.update_member_size(
        tx.ref_id,
        SizeEntry(
            date=date.today(),
            shoe_eu=last.shoe_eu,
            top_cm=last.top_cm,
            bottom_cm=last.bottom_cm,
        ),
    )


def _record_gift(tx: Transaction) -> None:
    repo.record_gift_given(
        event_id=tx.ref_id, item=tx.description, price=tx.amount, year=tx.created_at.year
    )


def _mark_grocery_ordered(tx: Transaction) -> None:
    repo.mark_grocery_ordered(tx.ref_id, date.today())


def _mark_travel_purchased(tx: Transaction) -> None:
    repo.set_wishlist_status(tx.ref_id, "purchased")


_HANDLERS = {
    "wardrobe": _acknowledge_wardrobe,
    "gifts": _record_gift,
    "groceries": _mark_grocery_ordered,
    "travel": _mark_travel_purchased,
}


def apply_execution_side_effect(tx: Transaction) -> None:
    _HANDLERS[tx.category](tx)
