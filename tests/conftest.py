"""Test harness.

The deterministic core (triggers.py, guardrail.py, sweep.py) reaches DynamoDB
only through ``household_agent.data.table``. These tests replace that module
with an in-memory fake *before* anything imports it, so the whole suite runs
with **zero AWS access and no boto3**.
"""

from __future__ import annotations

import sys
import types
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from household_agent.models import (  # noqa: E402
    Budget,
    Event,
    GiftHistoryEntry,
    GroceryItem,
    Member,
    PriceEntry,
    SizeEntry,
    SweepLogEntry,
    Transaction,
    WishlistItem,
)


class FakeStore:
    """Mutable in-memory stand-in for the DynamoDB single table."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.members: dict[str, Member] = {}
        self.budgets: dict[str, Budget] = {}
        self.events: dict[str, Event] = {}
        self.groceries: dict[str, GroceryItem] = {}
        self.wishlist: dict[str, WishlistItem] = {}
        self.transactions: dict[str, Transaction] = {}
        self.sweeps: list[SweepLogEntry] = []

    # ---- reads
    def get_members(self):
        return list(self.members.values())

    def get_budget(self, category):
        return self.budgets[category]

    def get_events(self):
        return list(self.events.values())

    def get_grocery_items(self):
        return list(self.groceries.values())

    def get_wishlist_items(self):
        return list(self.wishlist.values())

    def get_transactions(self):
        return list(self.transactions.values())

    def get_transaction(self, tx_id):
        return self.transactions.get(tx_id)

    def get_sweep_log(self, limit=10):
        return sorted(self.sweeps, key=lambda s: s.run_at, reverse=True)[:limit]

    # ---- writes
    def create_transaction(self, category, ref_id, description, amount, justification,
                           budget_status="within_limit"):
        tx = Transaction(
            id=str(uuid.uuid4()),
            category=category,
            ref_id=ref_id,
            description=description,
            amount=amount,
            justification=justification,
            status="proposed",
            created_at=datetime.now(timezone.utc),
            approval_token="tok-" + uuid.uuid4().hex[:12],
            budget_status=budget_status,
        )
        self.transactions[tx.id] = tx
        return tx

    def update_transaction_status(self, tx_id, status):
        self.transactions[tx_id].status = status
        self.transactions[tx_id].decided_at = datetime.now(timezone.utc)

    def increment_budget_spent(self, category, amount):
        b = self.budgets[category]
        self.budgets[category] = Budget(
            category=b.category,
            monthly_limit=b.monthly_limit,
            spent_this_period=b.spent_this_period + amount,
            period_start=b.period_start,
            currency=b.currency,
        )

    def append_price_history(self, item_id, entry):
        self.wishlist[item_id].price_history.append(entry)

    def set_wishlist_status(self, item_id, status):
        self.wishlist[item_id].status = status

    def update_member_size(self, member_id, entry):
        self.members[member_id].size_history.append(entry)

    def record_gift_given(self, event_id, item, price, year):
        self.events[event_id].gift_history.append(GiftHistoryEntry(year=year, item=item, price=price))

    def mark_grocery_ordered(self, item_id, ordered_date):
        g = self.groceries[item_id]
        self.groceries[item_id] = GroceryItem(
            id=g.id, name=g.name, frequency_days=g.frequency_days,
            last_ordered_date=ordered_date, typical_price=g.typical_price,
            preferred_store=g.preferred_store, quantity=g.quantity,
        )

    def log_sweep(self, entry):
        self.sweeps.append(entry)


# One store, one fake module, installed before any test imports triggers /
# guardrail / sweep (which do `from household_agent.data import table as repo`
# at import time). The `store` fixture resets this instance *in place* so those
# already-bound references keep working.
_STORE = FakeStore()

_fake_table = types.ModuleType("household_agent.data.table")
for _name in dir(FakeStore):
    if not _name.startswith("_"):
        setattr(_fake_table, _name, getattr(_STORE, _name))
_fake_table._store = _STORE  # test hook
sys.modules["household_agent.data.table"] = _fake_table


@pytest.fixture
def store() -> FakeStore:
    """The shared in-memory store, emptied for this test."""
    _STORE.reset()
    return _STORE


# ---- small builders -------------------------------------------------------

def make_member(id, name, *, entries: list[tuple[str, float, float, float]], role="kid"):
    return Member(
        id=id, name=name, role=role, birthdate=date(2017, 1, 1),
        size_history=[
            SizeEntry(date=date.fromisoformat(d), shoe_eu=s, top_cm=t, bottom_cm=b)
            for (d, s, t, b) in entries
        ],
    )


def make_budget(category, limit, spent=0.0):
    return Budget(category=category, monthly_limit=limit, spent_this_period=spent,
                  period_start=date.today().replace(day=1))


def make_event(id, person, month, day, *, gift_budget=60.0, history=None):
    return Event(
        id=id, type="birthday", person_name=person, month=month, day=day,
        gift_budget=gift_budget,
        gift_history=[GiftHistoryEntry(**h) for h in (history or [])],
    )


def make_grocery(id, name, freq, last_ordered: str, price=3.0):
    return GroceryItem(
        id=id, name=name, frequency_days=freq,
        last_ordered_date=date.fromisoformat(last_ordered),
        typical_price=price, preferred_store="Tesco", quantity="1",
    )


def make_trip(id, name, target, latest_price, *, status="watching"):
    return WishlistItem(
        id=id, category="travel", name=name, target_price=target, member_id=None,
        price_history=[PriceEntry(date=date.today(), price=latest_price, source="simulated")],
        status=status, origin="LHR", destination="ZRH",
        depart_date=date.today().isoformat(), return_date=date.today().isoformat(),
        passengers=2,
    )
