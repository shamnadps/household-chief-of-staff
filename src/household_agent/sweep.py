"""The daily sweep pipeline. Deterministic by design:

    for each category:
        candidates = triggers.<category>_candidates()      # plain code
        proposals  = agents.<category>.propose()            # Strands agent — the
                                                            # only model call
        for each proposal:
            status = guardrail.check_budget(...)            # plain code
            tx     = table.create_transaction(...)          # persist
            notify.send_approval_email(tx)                  # SES

The model proposes; this module decides what gets written and sent. Category
agents never touch DynamoDB or SES.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone

from household_agent.agents import gifts, groceries, travel, wardrobe
from household_agent.data import table as repo
from household_agent.guardrail import check_budget
from household_agent.models import Category, SweepLogEntry
from household_agent.notify import send_approval_email

log = logging.getLogger(__name__)

CATEGORY_AGENTS = {
    "wardrobe": wardrobe,
    "gifts": gifts,
    "groceries": groceries,
    "travel": travel,
}


def run_sweep(today: date | None = None, *, send_email: bool = True) -> SweepLogEntry:
    today = today or date.today()
    categories_checked: list[str] = []
    proposals_created = 0

    for category, agent_module in CATEGORY_AGENTS.items():
        categories_checked.append(category)
        for proposal in agent_module.propose(today=today):
            status = check_budget(category, proposal.amount)
            tx = repo.create_transaction(
                category=category,  # type: ignore[arg-type]
                ref_id=proposal.ref_id,
                description=proposal.description,
                amount=proposal.amount,
                justification=proposal.justification,
                budget_status=status,
            )
            if send_email:
                # A failed send (SES unverified, throttled) must not abort the
                # sweep — the proposal is already persisted and visible on the
                # dashboard; the email is a notification, not the source of truth.
                try:
                    send_approval_email(tx)
                except Exception:  # noqa: BLE001
                    log.exception("SES send failed for transaction %s; continuing", tx.id)
            proposals_created += 1

    entry = SweepLogEntry(
        id=str(uuid.uuid4()),
        run_at=datetime.now(timezone.utc),
        proposals_created=proposals_created,
        categories_checked=categories_checked,
    )
    repo.log_sweep(entry)
    return entry
