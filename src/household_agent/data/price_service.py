"""Wraps SerpAPI (read-only) behind the interface the agents use. Live current
price only — the historical trend is seeded synthetic data (see
scripts/seed_data.py). Cached in-process for CACHE_TTL_SECONDS so repeated runs
don't burn quota.
"""

from __future__ import annotations

import time
from datetime import date

import requests

from household_agent.config import CURRENCY, SERPAPI_API_KEY
from household_agent.models import PriceEntry

SERPAPI_ENDPOINT = "https://serpapi.com/search"
CACHE_TTL_SECONDS = 6 * 60 * 60

_cache: dict[str, tuple[float, PriceEntry]] = {}


def _api_key() -> str:
    if not SERPAPI_API_KEY:
        raise RuntimeError("SERPAPI_API_KEY not set in environment")
    return SERPAPI_API_KEY


def _cached(cache_key: str) -> PriceEntry | None:
    hit = _cache.get(cache_key)
    if hit and (time.time() - hit[0]) < CACHE_TTL_SECONDS:
        return hit[1]
    return None


def get_shopping_price(query: str) -> PriceEntry:
    cache_key = f"shopping:{query}"
    hit = _cached(cache_key)
    if hit:
        return hit

    resp = requests.get(
        SERPAPI_ENDPOINT,
        params={"engine": "google_shopping", "q": query, "api_key": _api_key()},
        timeout=15,
    )
    resp.raise_for_status()
    results = resp.json().get("shopping_results", [])
    if not results:
        raise RuntimeError(f"No shopping results for query: {query}")
    prices = [r["extracted_price"] for r in results if r.get("extracted_price")]
    entry = PriceEntry(date=date.today(), price=min(prices), source="serpapi")
    _cache[cache_key] = (time.time(), entry)
    return entry


def get_flight_price(
    origin: str, dest: str, depart_date: str, return_date: str, passengers: int = 1
) -> PriceEntry:
    """``passengers`` scales SerpAPI's per-adult price into a family-total figure,
    matching how ``wishlist_items.target_price`` is framed (e.g. "family of 5")."""
    cache_key = f"flight:{origin}:{dest}:{depart_date}:{return_date}:{passengers}"
    hit = _cached(cache_key)
    if hit:
        return hit

    resp = requests.get(
        SERPAPI_ENDPOINT,
        params={
            "engine": "google_flights",
            "departure_id": origin,
            "arrival_id": dest,
            "outbound_date": depart_date,
            "return_date": return_date,
            "currency": CURRENCY,
            "hl": "en",
            "type": "1",  # round trip
            "api_key": _api_key(),
        },
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    flights = data.get("best_flights", []) + data.get("other_flights", [])
    if not flights:
        raise RuntimeError(f"No flight results for {origin}->{dest}")
    prices = [f["price"] for f in flights if f.get("price")]
    entry = PriceEntry(date=date.today(), price=min(prices) * passengers, source="serpapi")
    _cache[cache_key] = (time.time(), entry)
    return entry
