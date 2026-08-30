"""Write the demo family into DynamoDB. Re-running overwrites the same item
keys, so it is safe to run repeatedly while iterating.

All dates are computed relative to ``today`` at run time (never hard-coded) so
the wardrobe / gift / grocery / travel triggers reliably fire whenever the
sweep is demoed, regardless of the day.

    python scripts/seed_data.py
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from household_agent.data import table as repo  # noqa: E402

TODAY = date.today()


def offset(days: int) -> str:
    return (TODAY + timedelta(days=days)).isoformat()


def seasonal_curve(base_price: float, cheap_months: list[int]) -> list[dict]:
    """12 monthly synthetic price points ending today, cheaper in cheap_months."""
    points = []
    for i in range(11, -1, -1):
        d = TODAY.replace(day=1) - timedelta(days=30 * i)
        factor = 0.85 if d.month in cheap_months else 1.05
        points.append(
            {"date": d.isoformat(), "price": round(base_price * factor, 2), "source": "simulated"}
        )
    return points


def seed() -> None:
    repo.put_family("Demo Family", "Europe/London")

    members = {
        "elena": {
            "name": "Elena", "role": "parent", "birthdate": "1990-04-14",
            "size_history": [],
            "preferences": {"colors": ["teal", "olive"], "brands": [], "interests": ["hiking"]},
        },
        "marcus": {
            "name": "Marcus", "role": "parent", "birthdate": "1988-11-02",
            "size_history": [],
            "preferences": {"colors": ["navy"], "brands": [], "interests": ["cycling"]},
        },
        "priya": {
            "name": "Priya", "role": "kid", "birthdate": "2017-03-12",
            "size_history": [
                {"date": offset(-190), "shoe_eu": 32, "top_cm": 128, "bottom_cm": 128},
                {"date": offset(-100), "shoe_eu": 33, "top_cm": 134, "bottom_cm": 134},
            ],
            "preferences": {"colors": ["purple"], "brands": [], "interests": ["drawing"]},
        },
        "maya": {
            "name": "Maya", "role": "kid", "birthdate": "2017-11-05",
            "size_history": [
                {"date": offset(-185), "shoe_eu": 30, "top_cm": 122, "bottom_cm": 122},
                {"date": offset(-95), "shoe_eu": 31, "top_cm": 128, "bottom_cm": 128},
            ],
            "preferences": {"colors": ["yellow"], "brands": [], "interests": ["football"]},
        },
        "kai": {
            "name": "Kai", "role": "kid", "birthdate": "2021-06-20",
            "size_history": [
                {"date": offset(-200), "shoe_eu": 25, "top_cm": 104, "bottom_cm": 98},
                {"date": offset(-110), "shoe_eu": 27, "top_cm": 116, "bottom_cm": 110},
            ],
            "preferences": {"colors": ["red"], "brands": [], "interests": ["dinosaurs"]},
        },
    }
    for member_id, data in members.items():
        repo.put_member(member_id, data)

    budgets = {"wardrobe": 120, "gifts": 100, "groceries": 150, "travel": 500}
    period_start = TODAY.replace(day=1).isoformat()
    for category, limit in budgets.items():
        repo.put_budget(
            category,
            {
                "monthly_limit": limit,
                "spent_this_period": 0,
                "period_start": period_start,
                "currency": "GBP",
            },
        )

    events = {
        "anniversary-elena-marcus": {
            "type": "anniversary", "person_name": "Elena & Marcus",
            "month": (TODAY + timedelta(days=11)).month,
            "day": (TODAY + timedelta(days=11)).day,
            "gift_budget": 150,
            "gift_history": [{"year": TODAY.year - 1, "item": "Spa voucher", "price": 90}],
        },
        "birthday-priya": {"type": "birthday", "person_name": "Priya", "month": 3, "day": 12, "gift_budget": 60, "gift_history": []},
        "birthday-maya": {"type": "birthday", "person_name": "Maya", "month": 11, "day": 5, "gift_budget": 60, "gift_history": []},
        "birthday-kai": {"type": "birthday", "person_name": "Kai", "month": 6, "day": 20, "gift_budget": 50, "gift_history": []},
        "birthday-elena": {"type": "birthday", "person_name": "Elena", "month": 4, "day": 14, "gift_budget": 80, "gift_history": []},
        "birthday-marcus": {"type": "birthday", "person_name": "Marcus", "month": 11, "day": 2, "gift_budget": 80, "gift_history": []},
    }
    for event_id, data in events.items():
        repo.put_event(event_id, data)

    groceries = {
        "milk": {"name": "Milk", "frequency_days": 7, "last_ordered_date": offset(-8), "typical_price": 4.50, "preferred_store": "Tesco", "quantity": "4 pints"},
        "bread": {"name": "Bread", "frequency_days": 5, "last_ordered_date": offset(-6), "typical_price": 2.20, "preferred_store": "Tesco", "quantity": "2 loaves"},
        "kids-fruit-snacks": {"name": "Kids' fruit snacks", "frequency_days": 10, "last_ordered_date": offset(-4), "typical_price": 6.00, "preferred_store": "Tesco", "quantity": "1 box"},
        "toilet-paper": {"name": "Toilet paper", "frequency_days": 30, "last_ordered_date": offset(-35), "typical_price": 12.00, "preferred_store": "Costco", "quantity": "1 pack"},
        "pasta-rice": {"name": "Pasta & rice staples", "frequency_days": 21, "last_ordered_date": offset(-10), "typical_price": 15.00, "preferred_store": "Tesco", "quantity": "mixed"},
        "coffee": {"name": "Coffee", "frequency_days": 14, "last_ordered_date": offset(-20), "typical_price": 8.50, "preferred_store": "Tesco", "quantity": "1 bag"},
    }
    for item_id, data in groceries.items():
        repo.put_grocery_item(item_id, data)

    wishlist = {
        "switzerland-trip": {
            "category": "travel",
            "name": "Switzerland winter family trip (flights, London-Zurich)",
            "target_price": 1450, "member_id": None,
            "price_history": seasonal_curve(1300, cheap_months=[1, 11]),
            "status": "watching",
            "origin": "LHR", "destination": "ZRH",
            "depart_date": offset(84), "return_date": offset(91), "passengers": 5,
        },
        "bali-trip": {
            "category": "travel",
            "name": "Bali family holiday (flights, London-Denpasar)",
            "target_price": 3200, "member_id": None,
            "price_history": seasonal_curve(2900, cheap_months=[2, 9]),
            "status": "watching",
            "origin": "LHR", "destination": "DPS",
            "depart_date": offset(23), "return_date": offset(33), "passengers": 5,
        },
    }
    for item_id, data in wishlist.items():
        repo.put_wishlist_item(item_id, data)

    print(f"Seeded demo family into DynamoDB, dates relative to today = {TODAY.isoformat()}")


if __name__ == "__main__":
    seed()
