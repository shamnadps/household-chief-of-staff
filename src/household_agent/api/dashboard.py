"""Admin dashboard: one page showing everything the admin needs to monitor and
act on — proposals awaiting approval by category, today's activity, items
trending toward qualifying, recent history, and budgets with pending-approval
shading. Aggregation only; HTTP wiring (routes, Basic Auth) lives in app.py.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from household_agent.config import CURRENCY_SYMBOL
from household_agent.data import table as repo
from household_agent.models import Category, Event, GroceryItem, Member, Transaction, WishlistItem
from household_agent.triggers import next_occurrence

WARDROBE_UPCOMING_MIN_DAYS = 60
GIFT_UPCOMING_MAX_DAYS = 60
GROCERY_UPCOMING_WITHIN_DAYS = 7
TRAVEL_UPCOMING_MAX_MULTIPLIER = 1.4
CATEGORIES: list[Category] = ["wardrobe", "gifts", "groceries", "travel"]


def _tx_to_dict(tx: Transaction) -> dict:
    return {
        "id": tx.id,
        "category": tx.category,
        "ref_id": tx.ref_id,
        "description": tx.description,
        "amount": tx.amount,
        "justification": tx.justification,
        "status": tx.status,
        "budget_status": tx.budget_status,
        "created_at": tx.created_at.isoformat(),
        "decided_at": tx.decided_at.isoformat() if tx.decided_at else None,
    }


def _wardrobe_upcoming(members: list[Member], today: date) -> list[dict]:
    result = []
    for m in members:
        if not m.size_history:
            continue
        last = max(entry.date for entry in m.size_history)
        days_stale = (today - last).days
        if WARDROBE_UPCOMING_MIN_DAYS <= days_stale < 90:
            result.append({"member_id": m.id, "name": m.name, "days_since_review": days_stale})
    return result


def _gift_upcoming(events: list[Event], today: date, already_active_ids: set[str]) -> list[dict]:
    result = []
    for e in events:
        if e.id in already_active_ids:
            continue
        next_date = next_occurrence(e.month, e.day, today)
        days_away = (next_date - today).days
        if 14 < days_away <= GIFT_UPCOMING_MAX_DAYS:
            result.append(
                {
                    "event_id": e.id,
                    "person_name": e.person_name,
                    "type": e.type,
                    "date": next_date.isoformat(),
                    "days_away": days_away,
                }
            )
    return result


def _grocery_upcoming(items: list[GroceryItem], today: date) -> list[dict]:
    result = []
    for g in items:
        due = g.last_ordered_date + timedelta(days=g.frequency_days)
        days_until_due = (due - today).days
        if 0 < days_until_due <= GROCERY_UPCOMING_WITHIN_DAYS:
            result.append({"item_id": g.id, "name": g.name, "due_in_days": days_until_due})
    return result


def _travel_upcoming(items: list[WishlistItem]) -> list[dict]:
    result = []
    for w in items:
        if w.category != "travel" or w.status != "watching" or not w.price_history:
            continue
        latest = max(w.price_history, key=lambda p: p.date)
        lower = w.target_price * 1.1
        upper = w.target_price * TRAVEL_UPCOMING_MAX_MULTIPLIER
        if lower < latest.price <= upper:
            result.append(
                {
                    "item_id": w.id,
                    "name": w.name,
                    "latest_price": latest.price,
                    "target_price": w.target_price,
                }
            )
    return result


def _budgets_summary(needs_approval: list[Transaction]) -> list[dict]:
    pending_by_category: dict[str, float] = {}
    for t in needs_approval:
        pending_by_category[t.category] = pending_by_category.get(t.category, 0) + t.amount

    result = []
    for category in CATEGORIES:
        b = repo.get_budget(category)
        result.append(
            {
                "category": category,
                "monthly_limit": b.monthly_limit,
                "spent_this_period": b.spent_this_period,
                "pending_total": pending_by_category.get(category, 0),
                "currency": b.currency,
            }
        )
    return result


def get_dashboard_state(today: date | None = None) -> dict:
    today = today or date.today()

    all_tx = repo.get_transactions()
    needs_approval = sorted(
        (t for t in all_tx if t.status == "proposed"), key=lambda t: t.created_at, reverse=True
    )
    todays = sorted(
        (t for t in all_tx if t.created_at.astimezone().date() == today),
        key=lambda t: t.created_at,
        reverse=True,
    )
    completed = sorted(
        (t for t in all_tx if t.status in ("executed", "rejected")),
        key=lambda t: t.decided_at or t.created_at,
        reverse=True,
    )[:25]

    active_gift_ids = {
        t.ref_id for t in all_tx if t.category == "gifts" and t.status == "proposed"
    }

    members = repo.get_members()
    events = repo.get_events()
    groceries = repo.get_grocery_items()
    wishlist = repo.get_wishlist_items()
    sweep_log = repo.get_sweep_log(limit=10)

    return {
        "generated_at": datetime.now().isoformat(),
        "currency_symbol": CURRENCY_SYMBOL,
        "budgets": _budgets_summary(needs_approval),
        "needs_approval": [_tx_to_dict(t) for t in needs_approval],
        "today": [_tx_to_dict(t) for t in todays],
        "upcoming": {
            "wardrobe": _wardrobe_upcoming(members, today),
            "gifts": _gift_upcoming(events, today, active_gift_ids),
            "groceries": _grocery_upcoming(groceries, today),
            "travel": _travel_upcoming(wishlist),
        },
        "completed": [_tx_to_dict(t) for t in completed],
        "sweep_log": [
            {
                "id": s.id,
                "run_at": s.run_at.isoformat(),
                "proposals_created": s.proposals_created,
                "categories_checked": s.categories_checked,
            }
            for s in sweep_log
        ],
    }


DASHBOARD_HTML = """<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Household Chief of Staff — Admin</title>
<style>
  :root {
    color-scheme: light;
    --bg: #f7f8fa; --surface: #ffffff; --surface-2: #fbfcfd;
    --border: #e9ebef; --border-strong: #dfe2e7;
    --text: #1b1f24; --text-soft: #3b424c; --muted: #737b86;
    --shadow-sm: 0 1px 2px rgba(20,28,40,.05);
    --shadow: 0 1px 3px rgba(20,28,40,.06), 0 8px 24px -12px rgba(20,28,40,.10);
    --wardrobe: #7c3aed; --wardrobe-bg: #f4effe;
    --gifts: #db2777;   --gifts-bg: #fdeef5;
    --groceries: #15803d; --groceries-bg: #e7f6ec;
    --travel: #2563eb;  --travel-bg: #e8f0fe;
    --ok: #15803d; --bad: #d1242f; --warn: #b45309;
  }
  * { box-sizing: border-box; }
  html { -webkit-text-size-adjust: 100%; }
  body {
    font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    margin: 0; font-size: 14px; line-height: 1.5;
    background: var(--bg); color: var(--text); -webkit-font-smoothing: antialiased;
  }
  .wrap { max-width: 1120px; margin: 0 auto; padding: 40px 28px 80px; }
  header { display: flex; align-items: flex-start; justify-content: space-between;
           flex-wrap: wrap; gap: 16px; margin-bottom: 28px; }
  h1 { font-size: 25px; font-weight: 800; margin: 0; letter-spacing: -0.02em; }
  .meta { color: var(--muted); font-size: 13px; margin-top: 6px; }
  .meta .dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%;
               background: var(--ok); margin-right: 6px; vertical-align: 1px;
               box-shadow: 0 0 0 3px rgba(21,128,61,.14); }
  .stats { display: flex; gap: 10px; flex-wrap: wrap; }
  .stat { background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
          padding: 10px 16px; box-shadow: var(--shadow-sm); min-width: 104px; }
  .stat .n { font-size: 22px; font-weight: 800; line-height: 1.15; letter-spacing: -0.02em;
             font-variant-numeric: tabular-nums; }
  .stat .l { font-size: 10.5px; color: var(--muted); text-transform: uppercase;
             letter-spacing: .06em; font-weight: 600; margin-top: 2px; }
  .stat.attn { border-color: #f3c9cc; background: linear-gradient(#fff, #fef6f6); }
  .stat.attn .n { color: var(--bad); }
  section { background: var(--surface); border: 1px solid var(--border); border-radius: 16px;
            padding: 24px; box-shadow: var(--shadow-sm); margin-bottom: 20px; }
  section h2 { font-size: 12px; text-transform: uppercase; letter-spacing: .07em;
               color: var(--muted); margin: 0 0 18px; font-weight: 700;
               display: flex; align-items: center; gap: 9px; }
  section h2 .count { background: var(--text); color: #fff; font-size: 11px;
                       font-weight: 700; padding: 2px 8px; border-radius: 20px; letter-spacing: 0; }
  .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  @media (max-width: 860px) { .two-col { grid-template-columns: 1fr; } }
  .budgets { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
  @media (max-width: 860px) { .budgets { grid-template-columns: repeat(2, 1fr); } }
  .budget-card { border: 1px solid var(--border); border-radius: 13px; padding: 16px;
                 background: var(--surface-2); }
  .budget-card .top { display: flex; justify-content: space-between; align-items: baseline;
                      margin-bottom: 12px; gap: 6px; }
  .budget-card .cat { padding: 3px 7px; }
  .budget-card .amount { font-size: 12.5px; white-space: nowrap; }
  .budget-card .figs { font-size: 12px; color: var(--muted); margin-top: 9px; }
  .bar { height: 8px; border-radius: 99px; background: #edeff2; overflow: hidden; position: relative; }
  .bar .fill { height: 100%; border-radius: 99px; }
  .bar .pending-fill { height: 100%; opacity: .30; position: absolute; top: 0;
                        border-left: 2px solid var(--surface-2); }
  .card { border: 1px solid var(--border); border-radius: 13px; padding: 16px 18px;
          margin-bottom: 12px; border-left-width: 3px; transition: box-shadow .15s, border-color .15s; }
  .card:hover { box-shadow: var(--shadow); border-color: var(--border-strong); }
  .card:last-child { margin-bottom: 0; }
  .row { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }
  .cat { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .05em;
         padding: 4px 9px; border-radius: 999px; white-space: nowrap; }
  .amount { font-weight: 800; font-variant-numeric: tabular-nums; letter-spacing: -0.01em; }
  .desc { margin: 10px 0 5px; font-size: 14.5px; font-weight: 600; color: var(--text); }
  .just { font-size: 13px; color: var(--text-soft); margin: 0 0 4px; line-height: 1.55; }
  .empty { color: var(--muted); font-size: 13.5px; padding: 8px 2px; }
  .over { color: var(--warn); font-weight: 600; font-size: 12px; margin-top: 6px; }
  .actions { margin-top: 14px; display: flex; gap: 9px; }
  button { border: none; border-radius: 9px; padding: 9px 18px; font-size: 13px; font-weight: 600;
           font-family: inherit; cursor: pointer; transition: filter .12s, transform .05s; }
  button:hover { filter: brightness(.94); }
  button:active { transform: scale(.98); }
  .approve { background: var(--ok); color: #fff; }
  .reject { background: var(--bad); color: #fff; }
  button:disabled { opacity: .4; cursor: default; filter: none; }
  .status { font-size: 10.5px; font-weight: 700; padding: 4px 10px; border-radius: 999px;
            text-transform: uppercase; letter-spacing: .04em; }
  .status-executed { background: var(--groceries-bg); color: var(--ok); }
  .status-rejected { background: var(--gifts-bg); color: var(--bad); }
  .status-proposed { background: #eef1f4; color: var(--muted); }
  .small { font-size: 11.5px; color: var(--muted); margin-top: 4px; }
  .list-row { display: flex; align-items: center; justify-content: space-between; gap: 12px;
              padding: 11px 0; border-bottom: 1px solid var(--border); font-size: 13.5px; }
  .list-row:last-child { border-bottom: none; }
  .list-row .left { display: flex; align-items: center; gap: 10px; min-width: 0; }
  .list-row .name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .list-row .right { color: var(--muted); font-size: 12.5px; white-space: nowrap;
                     font-variant-numeric: tabular-nums; }
  .cat-wardrobe { background: var(--wardrobe-bg); color: var(--wardrobe); }
  .cat-gifts { background: var(--gifts-bg); color: var(--gifts); }
  .cat-groceries { background: var(--groceries-bg); color: var(--groceries); }
  .cat-travel { background: var(--travel-bg); color: var(--travel); }
  .card.cat-border-wardrobe { border-left-color: var(--wardrobe); }
  .card.cat-border-gifts { border-left-color: var(--gifts); }
  .card.cat-border-groceries { border-left-color: var(--groceries); }
  .card.cat-border-travel { border-left-color: var(--travel); }
  .skel { color: var(--muted); font-size: 13.5px; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <h1>Household Chief of Staff</h1>
      <div class="meta"><span class="dot"></span><span id="meta">connecting…</span></div>
    </div>
    <div class="stats" id="stats"></div>
  </header>
  <section><h2>Budgets this period</h2><div id="budgets" class="skel">loading…</div></section>
  <section><h2>Needs approval <span class="count" id="na-count">0</span></h2>
    <div id="needs-approval" class="skel">loading…</div></section>
  <div class="two-col">
    <section><h2>Today</h2><div id="today" class="skel">loading…</div></section>
    <section><h2>Upcoming</h2><div id="upcoming" class="skel">loading…</div></section>
  </div>
  <section><h2>Completed</h2><div id="completed" class="skel">loading…</div></section>
  <section><h2>Sweep log</h2><div id="sweep-log" class="skel">loading…</div></section>
</div>
<script>
let SYM = "£";
const fmt = (n) => SYM + Number(n).toFixed(2);
const when = (iso) => new Date(iso).toLocaleString([], {dateStyle: "medium", timeStyle: "short"});
const ago = (iso) => {
  const s = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return Math.floor(s/60) + "m ago";
  return Math.floor(s/3600) + "h ago";
};
function txCard(t, actionable) {
  const over = t.budget_status === "needs_override"
    ? `<div class="over">Over budget — approving exceeds the monthly limit</div>` : "";
  const actions = actionable ? `
    <div class="actions">
      <button class="approve" onclick="decide('${t.id}','approve',this)">Approve</button>
      <button class="reject" onclick="decide('${t.id}','reject',this)">Reject</button>
    </div>` : `<span class="status status-${t.status}">${t.status}</span>`;
  return `<div class="card cat-border-${t.category}" id="tx-${t.id}">
    <div class="row"><span class="cat cat-${t.category}">${t.category}</span><span class="amount">${fmt(t.amount)}</span></div>
    <div class="desc">${t.description}</div>
    <div class="just">${t.justification}</div>
    ${over}
    <div class="small">${when(t.created_at)}</div>
    ${actions}
  </div>`;
}
function renderList(id, items, actionable) {
  const el = document.getElementById(id);
  if (!items.length) { el.className = "empty"; el.textContent = "Nothing here."; return; }
  el.className = ""; el.innerHTML = items.map(t => txCard(t, actionable)).join("");
}
function renderBudgets(budgets) {
  const el = document.getElementById("budgets");
  el.className = "budgets";
  el.innerHTML = budgets.map(b => {
    const spentPct = Math.min(100, (b.spent_this_period / b.monthly_limit) * 100);
    const pendingPct = Math.min(100 - spentPct, (b.pending_total / b.monthly_limit) * 100);
    const overSpent = b.spent_this_period > b.monthly_limit;
    const overIfApproved = !overSpent && b.spent_this_period + b.pending_total > b.monthly_limit;
    const fillColor = overSpent ? "var(--bad)" : `var(--${b.category})`;
    const pendColor = overIfApproved ? "var(--warn)" : `var(--${b.category})`;
    let note;
    if (b.pending_total <= 0) note = "nothing pending";
    else if (overIfApproved) note = `<span style="color:var(--warn);font-weight:600">${fmt(b.pending_total)} pending · over budget if all approved</span>`;
    else note = `${fmt(b.pending_total)} pending approval`;
    return `<div class="budget-card">
      <div class="top">
        <span class="cat cat-${b.category}">${b.category}</span>
        <span class="amount" style="${overSpent ? 'color:var(--bad)' : ''}">${fmt(b.spent_this_period)}<span style="color:var(--muted);font-weight:400"> / ${fmt(b.monthly_limit)}</span></span>
      </div>
      <div class="bar">
        <div class="fill" style="width:${spentPct}%;background:${fillColor}"></div>
        <div class="pending-fill" style="left:${spentPct}%;width:${pendingPct}%;background:${pendColor}"></div>
      </div>
      <div class="figs">${note}</div>
    </div>`;
  }).join("");
}
function renderUpcoming(u) {
  const el = document.getElementById("upcoming");
  const rows = [];
  u.wardrobe.forEach(w => rows.push(`<div class="list-row"><div class="left"><span class="cat cat-wardrobe">wardrobe</span><span class="name">${w.name}</span></div><span class="right">${w.days_since_review}d since review</span></div>`));
  u.gifts.forEach(g => rows.push(`<div class="list-row"><div class="left"><span class="cat cat-gifts">gifts</span><span class="name">${g.person_name} · ${g.type}</span></div><span class="right">in ${g.days_away}d</span></div>`));
  u.groceries.forEach(g => rows.push(`<div class="list-row"><div class="left"><span class="cat cat-groceries">groceries</span><span class="name">${g.name}</span></div><span class="right">due in ${g.due_in_days}d</span></div>`));
  u.travel.forEach(t => rows.push(`<div class="list-row"><div class="left"><span class="cat cat-travel">travel</span><span class="name">${t.name}</span></div><span class="right">${fmt(t.latest_price)} / target ${fmt(t.target_price)}</span></div>`));
  if (!rows.length) { el.className = "empty"; el.textContent = "Nothing trending toward a proposal yet."; return; }
  el.className = ""; el.innerHTML = rows.join("");
}
function renderSweepLog(entries) {
  const el = document.getElementById("sweep-log");
  if (!entries.length) { el.className = "empty"; el.textContent = "No sweeps logged yet."; return; }
  el.className = "";
  el.innerHTML = entries.map(s => `<div class="list-row">
    <div class="left"><span class="name">${when(s.run_at)}</span></div>
    <span class="right">${s.categories_checked.length} categories · ${s.proposals_created} proposals</span>
  </div>`).join("");
}
function renderCompleted(items) {
  const el = document.getElementById("completed");
  if (!items.length) { el.className = "empty"; el.textContent = "Nothing decided yet."; return; }
  el.className = "";
  el.innerHTML = items.map(t => `<div class="list-row">
    <div class="left"><span class="cat cat-${t.category}">${t.category}</span><span class="name">${t.description}</span></div>
    <span class="right"><span class="status status-${t.status}">${t.status}</span> ${fmt(t.amount)}</span>
  </div>`).join("");
}
function renderStats(data) {
  const el = document.getElementById("stats");
  const upcomingCount = Object.values(data.upcoming).reduce((n, l) => n + l.length, 0);
  const pendingTotal = data.needs_approval.reduce((n, t) => n + t.amount, 0);
  el.innerHTML = `
    <div class="stat${data.needs_approval.length ? ' attn' : ''}"><div class="n">${data.needs_approval.length}</div><div class="l">Need approval</div></div>
    <div class="stat"><div class="n">${fmt(pendingTotal)}</div><div class="l">Pending total</div></div>
    <div class="stat"><div class="n">${data.today.length}</div><div class="l">Today</div></div>
    <div class="stat"><div class="n">${upcomingCount}</div><div class="l">Upcoming</div></div>
  `;
}
async function decide(tx, action, btn) {
  btn.closest(".actions").querySelectorAll("button").forEach(b => b.disabled = true);
  const res = await fetch(`/admin/api/decide?tx=${tx}&action=${action}`, { method: "POST" });
  if (!res.ok) { alert("Failed: " + (await res.text())); }
  await load();
}
async function load() {
  const res = await fetch("/admin/api/state");
  if (res.status === 401) { document.body.innerHTML = "<p style='padding:24px'>Unauthorized.</p>"; return; }
  const data = await res.json();
  SYM = data.currency_symbol || "£";
  document.getElementById("meta").textContent = "Live · updated " + ago(data.generated_at);
  renderStats(data);
  renderBudgets(data.budgets);
  document.getElementById("na-count").textContent = data.needs_approval.length;
  renderList("needs-approval", data.needs_approval, true);
  renderList("today", data.today, false);
  renderUpcoming(data.upcoming);
  renderCompleted(data.completed);
  renderSweepLog(data.sweep_log);
}
load();
setInterval(load, 20000);
</script>
</body>
</html>
"""
