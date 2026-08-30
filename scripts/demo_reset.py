"""Clear a demo run: delete every transaction and sweep-log item, leaving the
seeded family / budgets / events / groceries / wishlist untouched. Run this
before recording so the dashboard starts clean, then trigger one sweep.

    python scripts/demo_reset.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from household_agent.data import table as repo  # noqa: E402

if __name__ == "__main__":
    n_tx = repo.delete_by_prefix("TXN#")
    n_sweep = repo.delete_by_prefix("SWEEP#")
    print(f"Deleted {n_tx} transactions and {n_sweep} sweep-log entries.")
    print("Budgets are NOT reset here — re-run scripts/seed_data.py for a full reset.")
