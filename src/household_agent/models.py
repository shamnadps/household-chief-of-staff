"""Domain model. Plain dataclasses — the same shapes the GCP build used, kept
storage-agnostic so triggers/guardrail/agents never see DynamoDB details.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal, Optional

Category = Literal["wardrobe", "gifts", "groceries", "travel"]
TransactionStatus = Literal["proposed", "approved", "rejected", "executed"]
WishlistStatus = Literal["watching", "proposed", "approved", "rejected", "purchased"]


@dataclass
class SizeEntry:
    date: date
    shoe_eu: float
    top_cm: float
    bottom_cm: float


@dataclass
class Member:
    id: str
    name: str
    role: Literal["parent", "kid"]
    birthdate: date
    size_history: list[SizeEntry] = field(default_factory=list)
    preferences: dict = field(default_factory=dict)  # colors, brands, interests


@dataclass
class Budget:
    category: Category
    monthly_limit: float
    spent_this_period: float
    period_start: date
    currency: str = "GBP"


@dataclass
class GiftHistoryEntry:
    year: int
    item: str
    price: float


@dataclass
class Event:
    id: str
    type: Literal["birthday", "anniversary"]
    person_name: str
    month: int
    day: int
    gift_budget: float
    gift_history: list[GiftHistoryEntry] = field(default_factory=list)


@dataclass
class GroceryItem:
    id: str
    name: str
    frequency_days: int
    last_ordered_date: date
    typical_price: float
    preferred_store: str
    quantity: str


@dataclass
class PriceEntry:
    date: date
    price: float
    source: str  # "simulated" | "serpapi"


@dataclass
class WishlistItem:
    id: str
    category: Literal["wardrobe", "travel"]
    name: str
    target_price: float
    member_id: Optional[str]
    price_history: list[PriceEntry] = field(default_factory=list)
    status: WishlistStatus = "watching"
    # travel-only fields, used to drive the live flight lookup
    origin: Optional[str] = None
    destination: Optional[str] = None
    depart_date: Optional[str] = None
    return_date: Optional[str] = None
    passengers: Optional[int] = None


@dataclass
class Transaction:
    id: str
    category: Category
    ref_id: str
    description: str
    amount: float
    justification: str
    status: TransactionStatus
    created_at: datetime
    approval_token: str
    budget_status: str = "within_limit"  # "within_limit" | "needs_override"
    decided_at: Optional[datetime] = None


@dataclass
class SweepLogEntry:
    id: str
    run_at: datetime
    proposals_created: int
    categories_checked: list[str]
