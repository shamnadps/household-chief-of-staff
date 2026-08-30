"""Deterministic qualification rules. These decide *whether* a category has a
candidate at all — before any model call. Fully hermetic (in-memory store).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from conftest import make_event, make_grocery, make_member, make_trip

from household_agent import triggers
from household_agent.models import Transaction

TODAY = date(2026, 6, 15)


def _iso(days: int) -> str:
    return (TODAY + timedelta(days=days)).isoformat()


# ---- wardrobe -----------------------------------------------------------

def test_wardrobe_qualifies_when_sizing_is_stale(store):
    store.members["kai"] = make_member("kai", "Kai", entries=[(_iso(-200), 25, 104, 98),
                                                             (_iso(-100), 27, 116, 110)])
    names = {m.name for m in triggers.wardrobe_candidates(today=TODAY)}
    assert "Kai" in names


def test_wardrobe_skips_recent_review_with_no_season_crossing(store):
    # both dates sit between the Jun 1 and Sep 1 boundaries, and <90 days apart
    store.members["mia"] = make_member(
        "mia", "Mia", entries=[("2026-07-01", 30, 120, 120)]
    )
    names = {m.name for m in triggers.wardrobe_candidates(today=date(2026, 7, 20))}
    assert "Mia" not in names


def test_wardrobe_qualifies_on_season_boundary_even_if_recent(store):
    # last entry 5 days before Jun 1 boundary, today just after -> season crossed
    just_before_june = date(2026, 5, 27)
    store.members["ada"] = make_member(
        "ada", "Ada",
        entries=[(just_before_june.isoformat(), 28, 110, 110)],
    )
    names = {m.name for m in triggers.wardrobe_candidates(today=date(2026, 6, 3))}
    assert "Ada" in names


# ---- gifts ------------------------------------------------------------

def test_gift_qualifies_within_lookahead(store):
    d = TODAY + timedelta(days=5)
    store.events["e1"] = make_event("e1", "Sam", d.month, d.day)
    people = {e.person_name for e in triggers.gift_candidates(today=TODAY)}
    assert people == {"Sam"}


def test_gift_skipped_outside_lookahead(store):
    d = TODAY + timedelta(days=40)
    store.events["e1"] = make_event("e1", "Sam", d.month, d.day)
    assert triggers.gift_candidates(today=TODAY) == []


def test_gift_deduped_when_already_proposed_this_year(store):
    d = TODAY + timedelta(days=5)
    store.events["e1"] = make_event("e1", "Sam", d.month, d.day)
    store.transactions["t1"] = Transaction(
        id="t1", category="gifts", ref_id="e1", description="book", amount=20,
        justification="x", status="proposed",
        created_at=datetime(TODAY.year, 1, 1, tzinfo=timezone.utc),
        approval_token="tok",
    )
    assert triggers.gift_candidates(today=TODAY) == []


# ---- groceries ------------------------------------------------------------

def test_grocery_qualifies_when_past_cadence(store):
    store.groceries["milk"] = make_grocery("milk", "Milk", freq=7, last_ordered=_iso(-8))
    names = {g.name for g in triggers.grocery_candidates(today=TODAY)}
    assert names == {"Milk"}


def test_grocery_skipped_when_within_cadence(store):
    store.groceries["milk"] = make_grocery("milk", "Milk", freq=14, last_ordered=_iso(-8))
    assert triggers.grocery_candidates(today=TODAY) == []


# ---- travel ------------------------------------------------------------

def test_travel_qualifies_at_or_near_target(store):
    store.wishlist["zrh"] = make_trip("zrh", "Zurich", target=1000, latest_price=1050)
    names = {w.name for w in triggers.travel_candidates()}
    assert names == {"Zurich"}


def test_travel_skipped_when_price_above_band(store):
    store.wishlist["zrh"] = make_trip("zrh", "Zurich", target=1000, latest_price=1300)
    assert triggers.travel_candidates() == []


def test_travel_skipped_when_not_watching(store):
    store.wishlist["zrh"] = make_trip("zrh", "Zurich", target=1000, latest_price=900,
                                      status="purchased")
    assert triggers.travel_candidates() == []
