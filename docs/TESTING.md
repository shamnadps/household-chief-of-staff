# Testing — reviewer walkthrough

Two ways to see this working: the automated suite (offline, 30 seconds) and a
live run on AWS.

## 1. Automated tests — no AWS needed

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

Expected: **19 passed**. An in-memory fake replaces `household_agent.data.table`
before anything imports it (`tests/conftest.py`), so the suite needs no AWS
credentials, no boto3, and no Bedrock access.

| File | Covers |
|---|---|
| `test_guardrail.py` | budget guardrail: within-limit vs `needs_override`, exact-boundary, spend-so-far counted |
| `test_triggers.py` | qualification rules: wardrobe staleness + season crossing, gift lookahead + same-year dedupe, grocery cadence, travel target band + status |
| `test_sweep.py` | pipeline wiring: guardrail status recorded on the transaction, over-budget proposal still persisted, sweep logged (category agents stubbed) |

What is deterministic and tested: `trigger → propose → guardrail → persist`. The
model's justification *text* varies run to run; the decisions around it do not.

## 2. Live run on AWS

### One-time

1. Enable Bedrock model access for `amazon.nova-pro-v1:0` in your region.
2. Verify an SES sender address (and a recipient, if your account is in the SES
   sandbox).
3. `sam build --template infra/template.yaml && sam deploy --guided …`
   (parameters in the main README).
4. `python scripts/seed_data.py` — writes the demo family into DynamoDB, with
   all dates relative to today so every category has a candidate.

### Run a sweep

```bash
aws lambda invoke --function-name household-agent-sweep /dev/stdout
```

Expected: up to four proposals written to DynamoDB, each with a `budget_status`,
and one SES email per proposal with Approve / Reject links. The anniversary gift
proposal will deliberately avoid last year's seeded "Spa voucher".

### Approve / reject

- From the email: click **Approve** — the link hits API Gateway → Lambda, which
  validates the per-transaction token, flips the transaction to `executed`,
  increments `BUDGET#<category>.spent_this_period`, and applies the side effect.
- From the dashboard: open the `AdminUrl` output (HTTP Basic Auth,
  `admin` / your `AdminPasswordValue`), then use the Approve / Reject buttons.
  The budget bars shade in what is *pending*, so you can see whether approving
  everything queued would push a category over budget.

### Interactive "ask" path (AgentCore)

```bash
python scripts/create_memory.py          # once — prints AGENTCORE_MEMORY_ID
# configure + launch per infra/agentcore/README.md
agentcore invoke '{"action":"ask","prompt":"Why did you propose that gift, and is groceries near its budget?"}'
```

The orchestrator consults the relevant specialist tools and the live budget,
and answers in a few sentences grounded in real numbers.

### Reset between demo runs

```bash
python scripts/demo_reset.py    # clears transactions + sweep log, keeps seed data
python scripts/seed_data.py     # full reset incl. budgets
```

## Teardown

```bash
sam delete --stack-name household-agent
```
