# Build plan & progress — Household Chief of Staff (AWS)

> Single source of truth for this build. Update the **Status** column on every
> change. Legend: `[ ]` todo · `[~]` in progress · `[x]` done · `[!]` blocked.

**Hackathon:** Agents for Humans (AWS) — Devpost. Deadline **2026-09-15 03:00 GMT+3**.
**Track:** Everyday Agents.
**Repo target:** public GitHub, Apache-2.0 (license visible in repo *About*).
**Prior art:** GCP "Household Chief of Staff" at `../../google-cloud/household-agent`
(ported, not copied — services swapped, orchestration rebuilt Strands-native).

---

## 1. Locked decisions

| Decision | Value |
|---|---|
| Agent framework | **Strands Agents SDK** (`strands-agents`) — required by rules |
| Reasoning model | **Amazon Nova Pro** (`us.amazon.nova-pro-v1:0`) via Amazon Bedrock |
| Background execution | **Bedrock AgentCore Runtime** (`runtime.py` entrypoint) |
| Cross-session context | **Bedrock AgentCore Memory** (`memory.py`) |
| Data store | **Amazon DynamoDB** single-table |
| Scheduled trigger | **Amazon EventBridge Scheduler** (daily) |
| Email | **Amazon SES** (approval request — the one real external action) |
| Secrets | **AWS Secrets Manager** + Lambda env vars |
| Approve/Reject/Admin HTTP | **API Gateway + AWS Lambda** (FastAPI + Mangum) |
| IaC | **AWS SAM** (`infra/template.yaml`) |
| Region | `us-west-2` |
| Categories | Wardrobe, Gifts, Groceries, Travel (same as GCP, rebuilt) |
| License | Apache-2.0 |

---

## 2. Requirements traceability (from the rules)

| Requirement | Where satisfied | Status |
|---|---|---|
| New AI agent built with **Strands Agents SDK** | `agents/*`, `sweep.py`, `orchestrator.py` | [x] |
| Handles routine/repetitive tasks **in the background** | daily sweep via EventBridge → AgentCore Runtime | [x] |
| **Surfaces only when there's a real decision** | SES approval email + admin dashboard; nothing auto-approved | [x] |
| Track selected (Everyday Agents) | submission form + README | [ ] |
| **AgentCore** deployment (strengthens Technical Impl.) | `runtime.py`, `infra/template.yaml` | [~] |
| Text description (what/who/how) | README + Devpost description | [ ] |
| **Public** code repo URL | GitHub (create + push) | [ ] |
| All source, assets, setup instructions to run | repo + README "Setup" | [~] |
| **MIT/Apache license visible in repo About** | `LICENSE` (Apache-2.0) + GitHub About | [~] |
| README | `README.md` | [ ] |
| **Architecture Diagram** | `docs/architecture.svg` + embedded in README | [ ] |
| Demo video ≤ 5 min (working demo + problem/who/why) | recorded separately | [ ] |
| AWS Builder ID | submission form | [ ] |
| (Optional) Live demo link | API Gateway URL of `/admin` + AgentCore | [ ] |
| Bonus: `builder.aws.com` post, "Agents for Humans" in title | `docs/BUILD_JOURNAL.md` → publish | [ ] |

---

## 3. Build checklist

### Phase A — Core agent + domain (DONE)
- [x] `config.py`, `models.py`
- [x] `data/table.py` — DynamoDB single-table access point
- [x] `data/price_service.py` — SerpAPI wrapper
- [x] `triggers.py` — deterministic qualification rules
- [x] `guardrail.py` — budget enforcement (plain code; `needs_override` never dropped)
- [x] `side_effects.py` — post-approval record updates
- [x] `agents/model.py` — BedrockModel factory (Nova Pro)
- [x] `agents/schemas.py` — Pydantic `ProposalBatch`
- [x] `agents/base.py` — `build_agent` + `propose_batch` (structured output)
- [x] `agents/{wardrobe,gifts,groceries,travel}.py` — one Strands Agent each
- [x] `agents/orchestrator.py` — agents-as-tools orchestrator + read-only data tools
- [x] `sweep.py` — deterministic pipeline
- [x] `notify.py` — SES send
- [x] `memory.py` — AgentCore Memory session manager
- [x] `runtime.py` — AgentCore Runtime entrypoint (`sweep` / `ask`)
- [x] syntax check passes

### Phase B — Approve/Reject/Admin HTTP  (`src/household_agent/api/`)  [x] done
- [x] `api/dashboard.py` — state aggregation + dashboard HTML (ported; currency symbol now injected, over-budget badge added)
- [x] `api/app.py` — FastAPI: `/approve` `/reject` `/admin` `/admin/api/state` `/admin/api/decide` `/sweep`(gated) `/healthz`
- [x] `api/handler.py` — Mangum adapter (`handler = Mangum(app, lifespan="off")`)
- [x] fix `money(0)[0]` wart in `agents/wardrobe.py` (use `config.CURRENCY`)
- [x] syntax check passes

### Phase C — Infrastructure  (`infra/`)  [x] done
- [x] `infra/template.yaml` — SAM
  - [x] DynamoDB table `HouseholdAgent` (PK/SK, PAY_PER_REQUEST, PITR)
  - [x] Lambda `ApiFunction` (FastAPI via Mangum) + `AWS::Serverless::HttpApi` (proxy `/{proxy+}` + `/`)
  - [x] Lambda `SweepFunction` for the scheduled sweep (AgentCore path documented as the alt)
  - [x] EventBridge Scheduler — `ScheduleV2` event, `cron(0 7 * * ? *)` UTC → `SweepFunction`
  - [x] SES — `SesSenderAddress` / `ApprovalRecipient` params (verified out of band; noted in README)
  - [x] Secrets Manager: `household-agent/admin-password`, `/sweep-secret`, `/serpapi-key` from NoEcho params, injected via `{{resolve:secretsmanager:...}}`
  - [x] IAM: per-function inline policies (DynamoDBCrudPolicy, `bedrock:InvokeModel*` scoped to `amazon.nova-*` + inference-profile, `ses:SendEmail*`, `secretsmanager:GetSecretValue` scoped)
  - [x] Outputs: `ApiBaseUrl`, `AdminUrl`, `TableName`, `SweepFunctionName`
- [x] `src/requirements.txt` (Lambda runtime deps — SAM builds from `../src/`)
- [x] `src/household_agent/scheduled.py` — plain Lambda handler for the daily sweep
- [x] `infra/agentcore/` — `Dockerfile` (arm64), `requirements.txt`, `README.md` (`agentcore configure`/`launch`/`invoke`)
- [ ] `samconfig` documented in README (not committed) — deferred to Phase F
- [ ] `sam validate` — deferred to Phase H (needs SAM CLI)

### Phase D — Scripts  (`scripts/`)  [x] done
- [x] `scripts/seed_data.py` — write demo family into DynamoDB (dates relative to today; via `table.put_*` helpers)
- [x] `scripts/create_memory.py` — create AgentCore Memory, print id
- [x] `scripts/demo_reset.py` — clear `TXN#`/`SWEEP#` items via `table.delete_by_prefix`
- [x] `scripts/local_sweep.py` — run one sweep locally (`--dry` skips SES)
- [x] added `table.put_family/put_member/put_budget/put_event/put_grocery_item/put_wishlist_item/delete_by_prefix`
- [x] syntax check passes

### Phase E — Tests  (`tests/`)  [x] done
- [x] `tests/conftest.py` — in-memory fake `table` module installed in `sys.modules` before imports; `store` fixture resets in place; small builders
- [x] `tests/test_guardrail.py` — within-limit vs needs_override, exact-boundary, spent-total math (5 tests)
- [x] `tests/test_triggers.py` — wardrobe stale/season/skip, gift lookahead+dedupe, grocery cadence, travel target/band/status (11 tests)
- [x] `tests/test_sweep.py` — pipeline with fake table + stubbed agents: guardrail status recorded, over-budget not dropped, sweep logged (3 tests)
- [x] **`pytest` green: 19 passed, zero cloud access, no boto3/strands needed for guardrail+triggers**
- [x] `.venv` created; full `requirements.txt` installed; all 24 modules import clean

### Phase F — Docs  [x] done
- [x] `README.md` — what/who/how, architecture diagram embed, AWS services table, repo layout, setup (local + SAM deploy + AgentCore), testing, teardown, Apache-2.0
- [x] `docs/ARCHITECTURE.md` — components table, DynamoDB data model, trust model, security boundaries, why AgentCore
- [x] `docs/architecture.svg` — hand-authored, well-formed, renders on GitHub (deterministic=green / model=blue / AWS=cream)
- [x] `docs/TESTING.md` — reviewer walkthrough (offline suite + live AWS run + AgentCore ask)

### Phase G — Bonus  [x] draft done
- [x] `docs/BUILD_JOURNAL.md` — `builder.aws.com` post drafted, "Agents for Humans" in title, "built for this hackathon" language included. **User to publish before deadline + paste the GitHub URL in.**

### Phase H — Verification  [~] in progress
- [x] `py_compile` all (src + scripts + tests) — OK
- [x] `pytest` green — 19 passed, hermetic
- [x] `sam validate --lint` — **valid** (fixed: ApiFunction↔HttpApi circular dep via `BaseUrl` param two-step deploy; `SerpApiKeyValue` default `"none"`)
- [x] all 24 runtime modules import under `.venv`
- [x] `git init` + history built as 12 logical conventional commits on `main` (scaffold → data → triggers/guardrail → agents → orchestrator → sweep/runtime → api → infra → scripts → tests → docs)
- [ ] **push to public GitHub** — needs user (repo create + `git remote add` + `git push`); set About description, confirm Apache-2.0 shows, add topics (`strands-agents`, `amazon-bedrock`, `agentcore`, `ai-agent`)
- [ ] **deploy to AWS** — needs user (Bedrock model access, SES verify, `sam deploy` two-step, `agentcore launch`)
- [ ] re-check §2 — see updated statuses below

---

## 4. Working context (don't lose this)

- **Package:** `household_agent` under `src/` (`pyproject.toml` sets `pythonpath=["src"]`).
- **Local Python:** 3.14 on this machine; target runtime Python 3.11+ (Lambda/AgentCore).
- **DynamoDB keys:** `PK = FAMILY#demo-family`, `SK` prefixes `MEMBER# BUDGET# EVENT# GROCERY# WISHLIST# TXN# SWEEP#`. Numbers stored as `Decimal` (helpers in `data/table.py`).
- **Currency:** GBP (London demo family), configurable via `CURRENCY`.
- **Model id:** `us.amazon.nova-pro-v1:0` (inference profile). Override via `BEDROCK_MODEL_ID`.
- **AgentCore Runtime payload contract:** `{"action":"sweep"}` (EventBridge) / `{"action":"ask","prompt":"...","session_id":"..."}` (interactive).
- **Deterministic-skeleton thesis (carry into README/journal):** triggers decide *whether*, guardrail decides *affordable*, model only decides *what to say*. This is the trust story and maps to "Architectural Discipline".
- **Two Strands surfaces:** (1) per-category structured-output agents inside the deterministic sweep; (2) agents-as-tools orchestrator for interactive Q&A over AgentCore Runtime + Memory.
- **GCP reference files:** `../../google-cloud/household-agent/app/*` (do not modify; source of truth for ported logic + demo seed data).
- **Open question:** whether the scheduled sweep runs as its own Lambda calling `sweep.run_sweep()` directly, or EventBridge invokes AgentCore Runtime with `{"action":"sweep"}`. Leaning: AgentCore Runtime for both (single deploy artifact, matches "AgentCore deployment" bonus); keep a thin `SweepFunction` Lambda as documented fallback.
- **SES sandbox:** sender + recipient must be verified for the demo; note in README.
- **Not doing:** real payments/bookings; multi-tenant; Lyria/Polly music (GCP-only bonus, no equivalent ask here) — optional Polly narration only if time.

---

## 5. Change log

- 2026-08-30 — Phase A complete (core agent, domain, data layer, Strands agents, orchestrator, sweep, AgentCore runtime). Plan file created. Starting Phase B.
- 2026-08-30 — Phases B, C, D, E complete.
  - B: `api/dashboard.py` (ported, currency injected, over-budget badge), `api/app.py` (FastAPI: approve/reject/admin/sweep/healthz), `api/handler.py` (Mangum).
  - C: `infra/template.yaml` (SAM — DynamoDB, HttpApi+ApiFunction, SweepFunction+ScheduleV2, Secrets Manager, scoped IAM, outputs); `src/requirements.txt`; `scheduled.py`; `infra/agentcore/` (Dockerfile arm64 + requirements + README).
  - D: `scripts/seed_data.py`, `create_memory.py`, `demo_reset.py`, `local_sweep.py`; `table.put_*` + `delete_by_prefix` helpers.
  - E: `tests/` — 19 passing, hermetic (fake table module). `.venv` built with full requirements; all 24 modules import OK.
- 2026-08-30 — Phases F, G, H (local) complete.
  - F: `README.md`, `docs/ARCHITECTURE.md`, `docs/TESTING.md`, `docs/architecture.svg`.
  - G: `docs/BUILD_JOURNAL.md` drafted (builder.aws.com bonus post).
  - H: `py_compile` + `pytest` (19) green; `sam validate --lint` valid after fixing a circular ApiFunction↔HttpApi dep (`BaseUrl` param, two-step deploy) and an empty-secret lint (`SerpApiKeyValue` default `none`). Git history rebuilt as 12 logical commits.
  - Remaining (user): push to public GitHub; deploy (Bedrock model access, SES verify, `sam deploy` x2, `agentcore launch`); demo video; Devpost form + AWS Builder ID; publish the build journal.
