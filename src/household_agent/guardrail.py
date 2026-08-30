"""Budget enforcement. Deterministic — never delegated to model judgment.

The agent proposes an amount; this runs *after* it and *before* anything is
written or emailed. Over-budget proposals are never silently dropped — they are
flagged ``needs_override`` and still surfaced to the human.
"""

from __future__ import annotations

from typing import Literal

from household_agent.data import table as repo
from household_agent.models import Category

GuardrailResult = Literal["within_limit", "needs_override"]


def check_budget(category: Category, amount: float) -> GuardrailResult:
    budget = repo.get_budget(category)
    if budget.spent_this_period + amount <= budget.monthly_limit:
        return "within_limit"
    return "needs_override"
