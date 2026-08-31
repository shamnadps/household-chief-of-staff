# Devpost submission — Household Chief of Staff

*Ready-to-paste text for the Agents for Humans submission form. Track:
**Everyday Agents**. Repo: https://github.com/shamnadps/household-chief-of-staff*

---

## What it does / who it's for / how it works

**Household Chief of Staff** is a background agent that carries the rolling list
of small household decisions so you don't have to hold them in your head.

Once a day it runs a **sweep** over a family's data across four areas —
kids' clothing sizes, upcoming birthdays and anniversaries, grocery reorder
cadence, and travel-wishlist prices. For anything that needs attention it
writes a specific proposal with a justification grounded in the family's real
numbers, checks the cost against that category's monthly budget, and emails
**one decision at a time**: Approve or Reject. It never buys or books anything
— approving logs a simulated transaction and moves a budget counter.

**Who it's for:** anyone running a household who loses time to a stream of
minor, judgement-light decisions that individually don't matter and together
never stop. Parents especially — the kids keep growing, the occasions keep
coming, the pantry keeps emptying.

**How it works:** a scheduled job (`triggers` → Strands agent → `guardrail` →
DynamoDB → SES) where the model's role is deliberately narrow. Plain Python
decides *whether* a category has something worth looking at and *whether* a
proposal fits the budget; the Strands agent, on Amazon Bedrock, only decides
*what to propose and how to justify it*. A second Strands surface — an
agents-as-tools orchestrator on Bedrock AgentCore Runtime with AgentCore Memory
— lets you ask the chief of staff questions ("why that gift?", "is groceries
near its budget?") and get an answer from live data.

## Features and functionality

- **Daily autonomous sweep** across wardrobe, gifts, groceries and travel.
- **Deterministic trigger rules** — sizing 90+ days stale or a season boundary
  crossed; an event within 14 days; a grocery item past its cadence; a watched
  trip at/near its target price. The agent only ever sees qualified candidates.
- **Grounded proposals** — every justification cites the actual numbers (the
  size delta and days since review, last year's gift, the days overdue, the
  live-versus-target price). The gifts agent deliberately avoids repeating a
  past year's gift for that person.
- **Deterministic budget guardrail** — runs after the model, before anything is
  written or sent. Over-budget proposals are flagged `needs_override` and still
  surfaced — never silently dropped.
- **One-click approval from email** — Approve / Reject links carry a random
  per-transaction token; clicking updates DynamoDB, moves the budget counter,
  and applies a side effect so the item stops re-qualifying.
- **Admin dashboard** — a single self-refreshing page: proposals by category
  with their justification, today's activity, items trending toward qualifying,
  recent history, and budget bars that shade in what's *pending* approval so
  you can see whether approving everything queued would go over budget.
- **Ask the chief of staff** — a Strands agents-as-tools orchestrator on
  AgentCore Runtime answers natural-language questions from live data, with
  AgentCore Memory carrying context across sweeps.
- **Infrastructure as code** — one `sam deploy`; a Docker-free build.
- **Hermetic test suite** — 19 tests, no AWS credentials needed.

## Technologies used

- **Strands Agents SDK** — four single-turn category agents using
  `structured_output`, plus an agents-as-tools orchestrator with read-only data
  tools.
- **Amazon Bedrock** (Amazon Nova family) — the reasoning + justification model.
- **Bedrock AgentCore Runtime** — hosts the agent for async background
  execution and the interactive "ask" path.
- **Bedrock AgentCore Memory** — cross-sweep context for the "ask" path.
- **AWS Lambda** — the scheduled sweep; the FastAPI approve/reject/admin
  service via Mangum.
- **Amazon API Gateway** (HTTP API) — public endpoint for the email links and
  dashboard.
- **Amazon DynamoDB** — single-table store: family, budgets, transactions,
  price history, sweep log.
- **Amazon EventBridge Scheduler** — fires the daily sweep.
- **Amazon SES** — the approval-request email (the one real external action).
- **AWS Secrets Manager** — admin password, sweep secret, SerpAPI key.
- **AWS SAM / CloudFormation** — infrastructure as code.
- Python, FastAPI, Pydantic, Mangum, pytest.

## Other data sources used

- **SerpAPI** — live current flight prices for the travel category.
- Historical price trend is **synthetic seed data** (`scripts/seed_data.py`,
  `seasonal_curve()`) standing in for a production time-series price pipeline —
  stated explicitly rather than left ambiguous.
- The demo family (members, budgets, events, groceries, wishlist) is seeded
  fixture data with all dates computed relative to "today" so every category
  has a candidate whenever the sweep is demoed.

## Findings and learnings

- **The deterministic code around the model's edges mattered more for trust
  than the model's reasoning quality.** Trigger rules before it, a budget
  guardrail after it — the agent is only as reliable as the boundaries it isn't
  allowed to reason its way out of. If an agent is going to email you spending
  decisions, it can't be allowed to talk itself into one.
- **Two Strands patterns, two jobs.** Inside the sweep, single-turn agents with
  structured output are the right tool — no loop, no wandering. For "ask the
  chief of staff", the agents-as-tools orchestrator lets the model choose which
  specialist and which data to consult. Same specialists, composed two ways.
- **DynamoDB numbers.** boto3's resource client stores numbers as `Decimal` and
  rejects `float` on write. One pair of conversion helpers at the data-layer
  boundary keeps every layer above it working in plain `int`/`float`.
- **Testing an agent pipeline offline.** The first test harness swapped the
  DynamoDB module per test; modules that had already imported it kept the stale
  reference. Fix: one fake store, reset in place. The suite now needs no AWS.
- **Email links can't be IAM-authed.** An Approve link is opened from a plain
  email; it can't carry a SigV4 signature. The real boundary is a random
  per-transaction token; the dashboard gets its own HTTP Basic Auth gate
  because it's a broader surface.
- **Docker-free Lambda packaging.** Pydantic ships a compiled wheel that must
  match the Lambda runtime. A SAM `makefile` build pinned to
  `manylinux2014_aarch64` / CPython 3.12 produces a correct package from macOS
  with no Docker — and trimming unused transitive deps took the bundle from
  241 MB to 92 MB.
