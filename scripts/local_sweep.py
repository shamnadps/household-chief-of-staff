"""Run one sweep locally against the configured DynamoDB table. Needs AWS
credentials (DynamoDB + Bedrock InvokeModel) and, for the travel category, a
SERPAPI_API_KEY.

    python scripts/local_sweep.py            # full run, sends SES email
    python scripts/local_sweep.py --dry      # no email (proposals still written)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from household_agent.sweep import run_sweep  # noqa: E402

if __name__ == "__main__":
    dry = "--dry" in sys.argv[1:]
    entry = run_sweep(send_email=not dry)
    print(
        f"sweep {entry.id}\n"
        f"  run_at:             {entry.run_at.isoformat()}\n"
        f"  categories_checked: {', '.join(entry.categories_checked)}\n"
        f"  proposals_created:  {entry.proposals_created}\n"
        f"  email:              {'skipped (--dry)' if dry else 'sent via SES'}"
    )
