"""The sweep pipeline: trigger -> agent -> guardrail -> persist -> (email).

The per-category agents (the only model calls) are stubbed here so the test is
deterministic and offline; what's exercised is the pipeline wiring — guardrail
result recorded on the transaction, over-budget still persisted, sweep logged.
"""

from __future__ import annotations

from datetime import date

import pytest

from conftest import make_budget

from household_agent import sweep
from household_agent.agents.schemas import ProposalItem


@pytest.fixture(autouse=True)
def _budgets(store):
    store.budgets["wardrobe"] = make_budget("wardrobe", 120, spent=0)
    store.budgets["gifts"] = make_budget("gifts", 100, spent=90)
    store.budgets["groceries"] = make_budget("groceries", 150, spent=0)
    store.budgets["travel"] = make_budget("travel", 500, spent=0)
    return store


@pytest.fixture(autouse=True)
def _stub_agents(monkeypatch):
    monkeypatch.setattr(
        sweep.wardrobe, "propose",
        lambda today=None: [ProposalItem(ref_id="kai", description="Shoes + 2 tops",
                                         amount=68, justification="grew EU 25->27")],
    )
    monkeypatch.setattr(
        sweep.gifts, "propose",
        lambda today=None: [ProposalItem(ref_id="anniv", description="Food & wine hamper",
                                         amount=95, justification="not last year's spa voucher")],
    )
    monkeypatch.setattr(sweep.groceries, "propose", lambda today=None: [])
    monkeypatch.setattr(sweep.travel, "propose", lambda today=None: [])
    monkeypatch.setattr(sweep, "send_approval_email", lambda tx: None)


def test_sweep_creates_transactions_with_guardrail_status(_budgets):
    entry = sweep.run_sweep(today=date(2026, 6, 15), send_email=False)

    assert entry.proposals_created == 2
    assert entry.categories_checked == ["wardrobe", "gifts", "groceries", "travel"]

    txs = {t.category: t for t in _budgets.get_transactions()}
    assert txs["wardrobe"].budget_status == "within_limit"
    # gifts: 90 spent + 95 proposed = 185 > 100 -> flagged, still created
    assert txs["gifts"].budget_status == "needs_override"
    assert txs["gifts"].status == "proposed"


def test_sweep_is_logged(_budgets):
    sweep.run_sweep(today=date(2026, 6, 15), send_email=False)
    log = _budgets.get_sweep_log()
    assert len(log) == 1
    assert log[0].proposals_created == 2


def test_over_budget_proposal_is_not_dropped(_budgets):
    sweep.run_sweep(today=date(2026, 6, 15), send_email=False)
    gifts_txs = [t for t in _budgets.get_transactions() if t.category == "gifts"]
    assert len(gifts_txs) == 1  # created despite being over budget
