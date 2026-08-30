"""The single DynamoDB access point. Nothing outside this module talks to
DynamoDB directly.

Single-table design on ``TABLE_NAME``:

    PK                       SK                         item
    FAMILY#<family>          META                       family profile
    FAMILY#<family>          MEMBER#<id>                member + size_history
    FAMILY#<family>          BUDGET#<category>          per-category budget
    FAMILY#<family>          EVENT#<id>                 birthday / anniversary
    FAMILY#<family>          GROCERY#<id>               recurring grocery item
    FAMILY#<family>          WISHLIST#<id>              travel / wardrobe wishlist
    FAMILY#<family>          TXN#<id>                   proposed / decided transaction
    FAMILY#<family>          SWEEP#<ts>#<id>            one sweep-run log line

Listing a type is ``query(PK, begins_with(SK, "<PREFIX>#"))``; a single
transaction is a ``get_item`` on its exact key.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from functools import lru_cache
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

from household_agent.config import AWS_REGION, FAMILY_ID, TABLE_NAME
from household_agent.models import (
    Budget,
    Category,
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

PK = f"FAMILY#{FAMILY_ID}"


@lru_cache(maxsize=1)
def _table():
    return boto3.resource("dynamodb", region_name=AWS_REGION).Table(TABLE_NAME)


# ---------------------------------------------------------------- (de)serialise


def _num(v: Any) -> Any:
    """DynamoDB stores numbers as Decimal; hand plain int/float back to callers."""
    if isinstance(v, Decimal):
        return int(v) if v % 1 == 0 else float(v)
    if isinstance(v, list):
        return [_num(x) for x in v]
    if isinstance(v, dict):
        return {k: _num(x) for k, x in v.items()}
    return v


def _put(sk: str, body: dict) -> None:
    item = {"PK": PK, "SK": sk, **body}
    _table().put_item(Item=_to_dynamo(item))


def _to_dynamo(obj: Any) -> Any:
    """floats -> Decimal (DynamoDB rejects float); recurse into dict/list."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, list):
        return [_to_dynamo(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_dynamo(v) for k, v in obj.items()}
    return obj


def _d(value: str) -> date:
    return date.fromisoformat(value)


def _query_prefix(prefix: str) -> list[dict]:
    resp = _table().query(
        KeyConditionExpression=Key("PK").eq(PK) & Key("SK").begins_with(prefix)
    )
    items = resp.get("Items", [])
    while "LastEvaluatedKey" in resp:
        resp = _table().query(
            KeyConditionExpression=Key("PK").eq(PK) & Key("SK").begins_with(prefix),
            ExclusiveStartKey=resp["LastEvaluatedKey"],
        )
        items.extend(resp.get("Items", []))
    return [_num(i) for i in items]


# ---------------------------------------------------------------------- members


def get_members() -> list[Member]:
    out = []
    for d in _query_prefix("MEMBER#"):
        out.append(
            Member(
                id=d["SK"].split("#", 1)[1],
                name=d["name"],
                role=d["role"],
                birthdate=_d(d["birthdate"]),
                size_history=[
                    SizeEntry(
                        date=_d(e["date"]),
                        shoe_eu=e["shoe_eu"],
                        top_cm=e["top_cm"],
                        bottom_cm=e["bottom_cm"],
                    )
                    for e in d.get("size_history", [])
                ],
                preferences=d.get("preferences", {}),
            )
        )
    return out


def update_member_size(member_id: str, entry: SizeEntry) -> None:
    _table().update_item(
        Key={"PK": PK, "SK": f"MEMBER#{member_id}"},
        UpdateExpression="SET size_history = list_append(size_history, :e)",
        ExpressionAttributeValues={
            ":e": _to_dynamo(
                [
                    {
                        "date": entry.date.isoformat(),
                        "shoe_eu": entry.shoe_eu,
                        "top_cm": entry.top_cm,
                        "bottom_cm": entry.bottom_cm,
                    }
                ]
            )
        },
    )


# ---------------------------------------------------------------------- budgets


def get_budget(category: Category) -> Budget:
    d = _num(
        _table().get_item(Key={"PK": PK, "SK": f"BUDGET#{category}"})["Item"]
    )
    return Budget(
        category=category,
        monthly_limit=d["monthly_limit"],
        spent_this_period=d["spent_this_period"],
        period_start=_d(d["period_start"]),
        currency=d.get("currency", "GBP"),
    )


def increment_budget_spent(category: Category, amount: float) -> None:
    _table().update_item(
        Key={"PK": PK, "SK": f"BUDGET#{category}"},
        UpdateExpression="SET spent_this_period = spent_this_period + :a",
        ExpressionAttributeValues={":a": Decimal(str(amount))},
    )


# ----------------------------------------------------------------------- events


def get_events() -> list[Event]:
    out = []
    for d in _query_prefix("EVENT#"):
        out.append(
            Event(
                id=d["SK"].split("#", 1)[1],
                type=d["type"],
                person_name=d["person_name"],
                month=d["month"],
                day=d["day"],
                gift_budget=d["gift_budget"],
                gift_history=[
                    GiftHistoryEntry(year=g["year"], item=g["item"], price=g["price"])
                    for g in d.get("gift_history", [])
                ],
            )
        )
    return out


def record_gift_given(event_id: str, item: str, price: float, year: int) -> None:
    _table().update_item(
        Key={"PK": PK, "SK": f"EVENT#{event_id}"},
        UpdateExpression="SET gift_history = list_append(gift_history, :g)",
        ExpressionAttributeValues={
            ":g": _to_dynamo([{"year": year, "item": item, "price": price}])
        },
    )


# -------------------------------------------------------------------- groceries


def get_grocery_items() -> list[GroceryItem]:
    out = []
    for d in _query_prefix("GROCERY#"):
        out.append(
            GroceryItem(
                id=d["SK"].split("#", 1)[1],
                name=d["name"],
                frequency_days=d["frequency_days"],
                last_ordered_date=_d(d["last_ordered_date"]),
                typical_price=d["typical_price"],
                preferred_store=d["preferred_store"],
                quantity=d["quantity"],
            )
        )
    return out


def mark_grocery_ordered(item_id: str, ordered_date: date) -> None:
    _table().update_item(
        Key={"PK": PK, "SK": f"GROCERY#{item_id}"},
        UpdateExpression="SET last_ordered_date = :d",
        ExpressionAttributeValues={":d": ordered_date.isoformat()},
    )


# --------------------------------------------------------------------- wishlist


def get_wishlist_items() -> list[WishlistItem]:
    out = []
    for d in _query_prefix("WISHLIST#"):
        out.append(
            WishlistItem(
                id=d["SK"].split("#", 1)[1],
                category=d["category"],
                name=d["name"],
                target_price=d["target_price"],
                member_id=d.get("member_id"),
                price_history=[
                    PriceEntry(date=_d(p["date"]), price=p["price"], source=p["source"])
                    for p in d.get("price_history", [])
                ],
                status=d.get("status", "watching"),
                origin=d.get("origin"),
                destination=d.get("destination"),
                depart_date=d.get("depart_date"),
                return_date=d.get("return_date"),
                passengers=d.get("passengers"),
            )
        )
    return out


def append_price_history(item_id: str, entry: PriceEntry) -> None:
    _table().update_item(
        Key={"PK": PK, "SK": f"WISHLIST#{item_id}"},
        UpdateExpression="SET price_history = list_append(price_history, :p)",
        ExpressionAttributeValues={
            ":p": _to_dynamo(
                [{"date": entry.date.isoformat(), "price": entry.price, "source": entry.source}]
            )
        },
    )


def set_wishlist_status(item_id: str, status: str) -> None:
    _table().update_item(
        Key={"PK": PK, "SK": f"WISHLIST#{item_id}"},
        UpdateExpression="SET #s = :s",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": status},
    )


# ------------------------------------------------------------------ transactions


def create_transaction(
    category: Category,
    ref_id: str,
    description: str,
    amount: float,
    justification: str,
    budget_status: str = "within_limit",
) -> Transaction:
    tx_id = str(uuid.uuid4())
    token = secrets.token_urlsafe(24)
    now = datetime.now(timezone.utc)
    _put(
        f"TXN#{tx_id}",
        {
            "category": category,
            "ref_id": ref_id,
            "description": description,
            "amount": amount,
            "justification": justification,
            "status": "proposed",
            "budget_status": budget_status,
            "created_at": now.isoformat(),
            "decided_at": None,
            "approval_token": token,
        },
    )
    return Transaction(
        id=tx_id,
        category=category,
        ref_id=ref_id,
        description=description,
        amount=amount,
        justification=justification,
        status="proposed",
        created_at=now,
        approval_token=token,
        budget_status=budget_status,
    )


def _tx_from_item(d: dict) -> Transaction:
    d = _num(d)
    return Transaction(
        id=d["SK"].split("#", 1)[1],
        category=d["category"],
        ref_id=d["ref_id"],
        description=d["description"],
        amount=d["amount"],
        justification=d["justification"],
        status=d["status"],
        created_at=datetime.fromisoformat(d["created_at"]),
        approval_token=d["approval_token"],
        budget_status=d.get("budget_status", "within_limit"),
        decided_at=datetime.fromisoformat(d["decided_at"]) if d.get("decided_at") else None,
    )


def get_transaction(tx_id: str) -> Transaction | None:
    item = _table().get_item(Key={"PK": PK, "SK": f"TXN#{tx_id}"}).get("Item")
    return _tx_from_item(item) if item else None


def get_transactions() -> list[Transaction]:
    return [_tx_from_item(d) for d in _query_prefix("TXN#")]


def update_transaction_status(tx_id: str, status: str) -> None:
    _table().update_item(
        Key={"PK": PK, "SK": f"TXN#{tx_id}"},
        UpdateExpression="SET #s = :s, decided_at = :t",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": status,
            ":t": datetime.now(timezone.utc).isoformat(),
        },
    )


# --------------------------------------------------------------------- sweep log


def log_sweep(entry: SweepLogEntry) -> None:
    _put(
        f"SWEEP#{entry.run_at.isoformat()}#{entry.id}",
        {
            "run_at": entry.run_at.isoformat(),
            "proposals_created": entry.proposals_created,
            "categories_checked": entry.categories_checked,
        },
    )


def get_sweep_log(limit: int = 10) -> list[SweepLogEntry]:
    rows = _query_prefix("SWEEP#")
    rows.sort(key=lambda d: d["run_at"], reverse=True)
    return [
        SweepLogEntry(
            id=d["SK"].rsplit("#", 1)[1],
            run_at=datetime.fromisoformat(d["run_at"]),
            proposals_created=d["proposals_created"],
            categories_checked=d["categories_checked"],
        )
        for d in rows[:limit]
    ]


# ------------------------------------------------------- seeding / maintenance
# Used by scripts/ only, so raw writes still go through this one module.


def put_family(name: str, timezone: str) -> None:
    _put("META", {"name": name, "timezone": timezone})


def put_member(member_id: str, body: dict) -> None:
    _put(f"MEMBER#{member_id}", body)


def put_budget(category: str, body: dict) -> None:
    _put(f"BUDGET#{category}", body)


def put_event(event_id: str, body: dict) -> None:
    _put(f"EVENT#{event_id}", body)


def put_grocery_item(item_id: str, body: dict) -> None:
    _put(f"GROCERY#{item_id}", body)


def put_wishlist_item(item_id: str, body: dict) -> None:
    _put(f"WISHLIST#{item_id}", body)


def delete_by_prefix(prefix: str) -> int:
    """Delete every item whose SK begins with ``prefix`` (e.g. ``TXN#``).
    Used by scripts/demo_reset.py to clear a demo run without touching seed data."""
    rows = _query_prefix(prefix)
    with _table().batch_writer() as batch:
        for r in rows:
            batch.delete_item(Key={"PK": r["PK"], "SK": r["SK"]})
    return len(rows)
