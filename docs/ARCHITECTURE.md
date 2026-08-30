# Architecture

![architecture](architecture.svg)

## One-paragraph summary

A scheduled job ("the sweep") runs once a day. For each of four categories it
asks a plain-Python rule whether anything qualifies; if so, a Strands agent
backed by Amazon Bedrock (Nova Pro) writes a proposal and a justification
grounded in the family's real data; a plain-Python guardrail checks the amount
against that category's remaining monthly budget; the proposal is written to
DynamoDB and emailed via SES with Approve / Reject links. Clicking a link hits
a FastAPI service on Lambda behind API Gateway, which validates a
per-transaction token, updates DynamoDB, moves the budget counter, and applies
a small side effect so the item stops re-qualifying. Separately, a Strands
*agents-as-tools* orchestrator on Bedrock AgentCore Runtime answers questions
about what the agent did, using AgentCore Memory for continuity.

## Components

| Component | File | Responsibility |
|---|---|---|
| Scheduler | `infra/template.yaml` (`ScheduleV2`) | invoke the sweep daily (`cron(0 7 * * ? *)` UTC) |
| Sweep pipeline | `sweep.py` | orchestrate trigger → agent → guardrail → persist → notify, deterministically |
| Trigger rules | `triggers.py` | decide whether a category has a candidate — *before* any model call |
| Category agents | `agents/{wardrobe,gifts,groceries,travel}.py` | one Strands `Agent` each; `structured_output(ProposalBatch)` |
| Model factory | `agents/model.py` | `BedrockModel(model_id="us.amazon.nova-pro-v1:0", temperature=0.3)` |
| Guardrail | `guardrail.py` | `within_limit` vs `needs_override` against the live budget — *after* the model |
| Persistence | `data/table.py` | the only module that talks to DynamoDB |
| Notification | `notify.py` | Amazon SES `send_email` — the one real external action |
| HTTP surface | `api/app.py`, `api/handler.py` | `/approve` `/reject` `/admin` `/admin/api/*` `/sweep` `/healthz`; Mangum → Lambda |
| Dashboard | `api/dashboard.py` | state aggregation + a single self-refreshing HTML page |
| Side effects | `side_effects.py` | on approval, update the source record (acknowledge size, record gift, mark ordered, mark purchased) |
| Orchestrator | `agents/orchestrator.py` | agents-as-tools + read-only data tools; `ask(question)` |
| AgentCore entry | `runtime.py` | `BedrockAgentCoreApp` — `{"action":"sweep"}` / `{"action":"ask"}` |
| Memory | `memory.py` | `AgentCoreMemorySessionManager`, keyed `family::demo-family` |
| Scheduled Lambda | `scheduled.py` | AgentCore-free path to run the same `sweep.run_sweep()` |

## Data model — DynamoDB single table

Table `HouseholdAgent`, `PK` / `SK` strings, `PAY_PER_REQUEST`.

| Item | PK | SK | Notes |
|---|---|---|---|
| Family profile | `FAMILY#demo-family` | `META` | |
| Member | `FAMILY#demo-family` | `MEMBER#<id>` | `size_history` list |
| Budget | `FAMILY#demo-family` | `BUDGET#<category>` | `monthly_limit`, `spent_this_period` |
| Event | `FAMILY#demo-family` | `EVENT#<id>` | `gift_history` list |
| Grocery item | `FAMILY#demo-family` | `GROCERY#<id>` | `frequency_days`, `last_ordered_date` |
| Wishlist item | `FAMILY#demo-family` | `WISHLIST#<id>` | `price_history`; travel routing fields |
| Transaction | `FAMILY#demo-family` | `TXN#<id>` | `status`, `budget_status`, `approval_token` |
| Sweep log | `FAMILY#demo-family` | `SWEEP#<iso-ts>#<id>` | one line per run |

Listing a type is `query(PK = FAMILY#…, begins_with(SK, "<PREFIX>#"))`. A single
transaction is a `get_item` on its exact key. Numbers are stored as `Decimal`
and converted back to `int`/`float` at the module boundary.

## The trust model

Three things the model is **not allowed to do**:

1. **Decide whether to act.** `triggers.py` runs first, in plain Python. The
   agent only sees candidates that already qualify.
2. **Decide whether something is affordable.** `guardrail.py` runs after the
   agent and before anything is written or sent. Its result is recorded on the
   transaction as `budget_status`.
3. **Execute anything.** The agent returns a typed `ProposalBatch` and nothing
   else. Writing to DynamoDB, sending email, and moving the budget counter are
   all done by `sweep.py` / `api/app.py` — never by an agent.

Over-budget proposals are never dropped. They are flagged `needs_override`,
emailed with an explicit warning, and shown with a badge on the dashboard — the
human still decides.

## Security boundaries

| Endpoint | Boundary | Why |
|---|---|---|
| `GET /approve`, `GET /reject` | random per-transaction `approval_token` | opened from a plain email link, which can't carry a SigV4 signature |
| `POST /sweep` | `X-Sweep-Secret` header vs Secrets Manager | real cost + real email per call |
| `GET /admin`, `/admin/api/*` | HTTP Basic Auth vs Secrets Manager | exposes all family data + token-free approve/reject |

Secrets (`admin-password`, `sweep-secret`, `serpapi-key`) live in AWS Secrets
Manager and are injected into Lambda via `{{resolve:secretsmanager:…}}` at
deploy time. IAM policies are per-function and scoped: DynamoDB CRUD on the one
table, `bedrock:InvokeModel*` limited to `amazon.nova-*` and inference
profiles, `ses:SendEmail*`, and `secretsmanager:GetSecretValue` on the three
named secrets.

## Why AgentCore

The interactive path is hosted on Bedrock AgentCore Runtime rather than a plain
Lambda because:

- the sweep fans out to four Bedrock calls plus a live flight-price lookup —
  long-running, async work AgentCore Runtime is built for;
- **AgentCore Memory** gives the "ask the chief of staff" path short-term
  conversation context and long-term extracted preferences, keyed per family,
  without a bespoke store;
- one container artifact serves both `{"action":"sweep"}` and
  `{"action":"ask"}`.

The scheduled sweep can run on AgentCore too (point EventBridge Scheduler at a
`bedrock-agentcore:InvokeAgentRuntime` universal target); the plain
`scheduled.py` Lambda is kept so the SAM stack is self-contained and demoable
without AgentCore access.
