"""The deterministic budget guardrail. Reads the live per-category budget;
proposals over the remaining allowance are flagged, never dropped.
"""

from __future__ import annotations

from conftest import make_budget

from household_agent import guardrail


def test_within_limit_when_under_remaining_budget(store):
    store.budgets["wardrobe"] = make_budget("wardrobe", 120, spent=0)
    assert guardrail.check_budget("wardrobe", 50) == "within_limit"


def test_needs_override_when_over_limit(store):
    store.budgets["wardrobe"] = make_budget("wardrobe", 120, spent=0)
    assert guardrail.check_budget("wardrobe", 200) == "needs_override"


def test_exact_remaining_is_within_limit(store):
    store.budgets["gifts"] = make_budget("gifts", 100, spent=40)
    assert guardrail.check_budget("gifts", 60) == "within_limit"


def test_one_over_remaining_needs_override(store):
    store.budgets["gifts"] = make_budget("gifts", 100, spent=40)
    assert guardrail.check_budget("gifts", 60.01) == "needs_override"


def test_spend_so_far_is_counted(store):
    store.budgets["groceries"] = make_budget("groceries", 150, spent=0)
    assert guardrail.check_budget("groceries", 50) == "within_limit"
    store.increment_budget_spent("groceries", 120)
    # 120 spent + 50 proposed = 170 > 150
    assert guardrail.check_budget("groceries", 50) == "needs_override"
