"""Sends the approval-request email via Amazon SES. This is the one real
external action in an otherwise fully simulated execution model — approving a
proposal logs a mock transaction and moves a budget counter; it does not place
an order or move money.
"""

from __future__ import annotations

from urllib.parse import urlencode

import boto3

from household_agent.config import (
    APPROVAL_RECIPIENT,
    AWS_REGION,
    BASE_URL,
    SES_SENDER,
    money,
)
from household_agent.models import Transaction


def _links(tx: Transaction) -> tuple[str, str]:
    q = urlencode({"tx": tx.id, "token": tx.approval_token})
    return f"{BASE_URL}/approve?{q}", f"{BASE_URL}/reject?{q}"


def build_body(tx: Transaction) -> str:
    approve_url, reject_url = _links(tx)
    override_note = (
        "\n*** OVER BUDGET for this category this period — approving this will "
        "exceed the monthly limit. Confirm you want to override. ***\n"
        if tx.budget_status == "needs_override"
        else ""
    )
    return (
        f"Category: {tx.category.title()}\n"
        f"Proposal: {tx.description}\n"
        f"Amount: {money(tx.amount)}\n\n"
        f"Why: {tx.justification}\n"
        f"{override_note}\n"
        f"Approve: {approve_url}\n"
        f"Reject:  {reject_url}\n"
    )


def send_approval_email(tx: Transaction) -> None:
    ses = boto3.client("ses", region_name=AWS_REGION)
    ses.send_email(
        Source=SES_SENDER,
        Destination={"ToAddresses": [APPROVAL_RECIPIENT]},
        Message={
            "Subject": {
                "Data": f"[Household Agent] Approval needed: {tx.description} ({money(tx.amount)})"
            },
            "Body": {"Text": {"Data": build_body(tx)}},
        },
    )
