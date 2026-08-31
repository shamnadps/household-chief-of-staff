"""Environment-driven configuration. Every value has a local-dev default so the
package imports cleanly without AWS; production values come from Lambda /
AgentCore environment variables and Secrets Manager (see infra/template.yaml).
"""

from __future__ import annotations

import os

AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")

# Amazon Nova Lite — the reasoning model behind each category agent. Overridable
# so the same code runs against a cheaper/faster model in tests or a different
# region's inference profile.
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.amazon.nova-lite-v1:0")

# DynamoDB single-table store.
TABLE_NAME = os.environ.get("TABLE_NAME", "HouseholdAgent")

# One hard-coded demo family — the app is single-tenant by design (see README).
FAMILY_ID = os.environ.get("FAMILY_ID", "demo-family")
CURRENCY = os.environ.get("CURRENCY", "GBP")
CURRENCY_SYMBOL = {"GBP": "£", "USD": "$", "EUR": "€"}.get(CURRENCY, "")

# Bedrock AgentCore Memory — persistent cross-sweep context for the family.
AGENTCORE_MEMORY_ID = os.environ.get("AGENTCORE_MEMORY_ID", "")

# SES.
SES_SENDER = os.environ.get("SES_SENDER", "household-agent@example.com")
APPROVAL_RECIPIENT = os.environ.get("APPROVAL_RECIPIENT", "you@example.com")

# Public base URL of the approve/reject/admin API, used to build email links.
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8080")

# Gates.
SWEEP_SECRET = os.environ.get("SWEEP_SECRET", "")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

# External price data.
SERPAPI_API_KEY = os.environ.get("SERPAPI_API_KEY", "")


def money(amount: float) -> str:
    """Format an amount in the configured currency, e.g. ``£120.00``."""
    return f"{CURRENCY_SYMBOL}{amount:,.2f}"
