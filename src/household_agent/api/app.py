"""FastAPI service for the human-facing surface. Deployed to AWS Lambda behind
an API Gateway HTTP API (see api/handler.py + infra/template.yaml); also runs
locally with ``uvicorn household_agent.api.app:app``.

Routes
------
POST /sweep                 run the daily sweep now (gated by X-Sweep-Secret)
GET  /approve               approval link from the email (per-transaction token)
GET  /reject                rejection link from the email
GET  /admin                 dashboard page (HTTP Basic Auth)
GET  /admin/api/state       JSON the dashboard renders (Basic Auth)
POST /admin/api/decide      dashboard approve/reject action (Basic Auth)
GET  /healthz               liveness

Why the service is public: /approve and /reject are opened from a plain email
link, which cannot carry an IAM SigV4 signature. Their real security boundary
is the random per-transaction ``approval_token``. /sweep has real cost and
sends real email, so it is gated by a shared secret header. /admin exposes all
family data plus token-free approve/reject, so it gets its own gate: HTTP Basic
Auth against ADMIN_USERNAME / ADMIN_PASSWORD.
"""

from __future__ import annotations

import secrets as _secrets

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from household_agent.api import dashboard
from household_agent.config import ADMIN_PASSWORD, ADMIN_USERNAME, SWEEP_SECRET
from household_agent.data import table as repo
from household_agent.models import Transaction
from household_agent.side_effects import apply_execution_side_effect
from household_agent.sweep import run_sweep

app = FastAPI(title="household-agent")
_basic = HTTPBasic()


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


# --------------------------------------------------------------------- sweep


@app.post("/sweep")
def sweep(x_sweep_secret: str | None = Header(default=None)) -> dict:
    if not SWEEP_SECRET or not x_sweep_secret or not _secrets.compare_digest(
        x_sweep_secret, SWEEP_SECRET
    ):
        raise HTTPException(status_code=403, detail="invalid or missing sweep secret")
    entry = run_sweep()
    return {
        "run_at": entry.run_at.isoformat(),
        "proposals_created": entry.proposals_created,
        "categories_checked": entry.categories_checked,
    }


# ----------------------------------------------------------- approve / reject


def _execute_approval(tx: Transaction) -> None:
    repo.update_transaction_status(tx.id, "executed")
    repo.increment_budget_spent(tx.category, tx.amount)
    apply_execution_side_effect(tx)


def _execute_rejection(tx: Transaction) -> None:
    repo.update_transaction_status(tx.id, "rejected")


def _validate(tx_id: str, token: str) -> Transaction:
    tx = repo.get_transaction(tx_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="transaction not found")
    if not _secrets.compare_digest(tx.approval_token, token):
        raise HTTPException(status_code=403, detail="invalid token")
    if tx.status != "proposed":
        raise HTTPException(status_code=409, detail=f"transaction already {tx.status}")
    return tx


@app.get("/approve")
def approve(tx: str, token: str) -> dict:
    transaction = _validate(tx, token)
    _execute_approval(transaction)
    return {"status": "executed", "tx": transaction.id}


@app.get("/reject")
def reject(tx: str, token: str) -> dict:
    transaction = _validate(tx, token)
    _execute_rejection(transaction)
    return {"status": "rejected", "tx": transaction.id}


# ----------------------------------------------------------------- admin


def _require_admin(credentials: HTTPBasicCredentials = Depends(_basic)) -> None:
    ok = (
        bool(ADMIN_PASSWORD)
        and _secrets.compare_digest(credentials.username, ADMIN_USERNAME)
        and _secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    )
    if not ok:
        raise HTTPException(
            status_code=401, detail="unauthorized", headers={"WWW-Authenticate": "Basic"}
        )


@app.get("/admin", response_class=HTMLResponse)
def admin_page(_: None = Depends(_require_admin)) -> str:
    return dashboard.DASHBOARD_HTML


@app.get("/admin/api/state")
def admin_state(_: None = Depends(_require_admin)) -> JSONResponse:
    return JSONResponse(dashboard.get_dashboard_state())


@app.post("/admin/api/decide")
def admin_decide(tx: str, action: str, _: None = Depends(_require_admin)) -> dict:
    if action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")
    transaction = repo.get_transaction(tx)
    if transaction is None:
        raise HTTPException(status_code=404, detail="transaction not found")
    if transaction.status != "proposed":
        raise HTTPException(status_code=409, detail=f"transaction already {transaction.status}")
    if action == "approve":
        _execute_approval(transaction)
        return {"status": "executed", "tx": transaction.id}
    _execute_rejection(transaction)
    return {"status": "rejected", "tx": transaction.id}
