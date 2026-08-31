# Agents for Humans: building a household chief-of-staff with Strands Agents and Amazon Bedrock

*I wrote this post for the Agents for Humans hackathon. It covers how the
project was built and how it uses AWS. Draft — publish publicly on
builder.aws.com before the deadline, keeping "Agents for Humans" in the title.*

---

## The chore I wanted an agent to own

Running a household is a rolling list of small decisions that never stops
arriving. Have the kids outgrown last season's shoes? Is a gift sorted for the
anniversary in two weeks? Did the grocery reorder actually go out? Is now a
cheap time to book those flights?

None of these is hard. Doing them *well* means remembering what you bought last
year, checking current prices, and staying inside a budget — and that overhead
never goes away. I wanted an agent that carries the list: it watches the
family's data, decides what needs doing, writes a short justification, and
surfaces **one** decision at a time — approve or reject.

The theme of this hackathon is agents that run quietly in the background and
only ping you when there's a real decision. That's exactly the shape here.

## The shape of the system

A scheduled **sweep** runs once a day:

```
EventBridge Scheduler (daily)
  -> Sweep  (Lambda, or Bedrock AgentCore Runtime)
       triggers.py     does any category have a candidate?     [plain Python]
       Strands agent   what to propose, and why?               [Bedrock Nova Lite]
       guardrail.py    is it within the category budget?       [plain Python]
       DynamoDB        write the proposal
       Amazon SES      email: Approve / Reject
  -> link clicked
       API Gateway + Lambda (FastAPI)  validate token, update DynamoDB, move budget
```

Four categories — wardrobe, gifts, groceries, travel — each a **Strands
`Agent`** that returns a typed `ProposalBatch` via `structured_output(...)`.

## The design decision that mattered: keep the model boxed in

If an agent is going to email me spending decisions, I need to know it can't
talk itself into one. So the model never decides **whether** to act and never
decides **whether something is affordable**. Both are plain Python:

- **Before** the model — `triggers.py` decides whether a category even has a
  candidate (sizing 90+ days stale or a season boundary crossed; an event
  within 14 days; a grocery item past its cadence; a watched trip at/near its
  target price). The agent only ever sees things that already qualify.
- **After** the model — `guardrail.py` checks the proposed amount against the
  remaining budget. Over-budget proposals aren't dropped; they're flagged
  `needs_override` and emailed with a warning. The human still decides.

The Strands agent's job is deliberately narrow: given a qualified candidate and
the real data, write the proposal and a justification grounded in the actual
numbers — the size delta and days since review, last year's gift, the days
overdue, the live-versus-target price.

What I'd tell anyone building an action-taking agent: **the deterministic code
around the model's edges mattered more for trust than the model's reasoning
quality.** The agent is only as reliable as the boundaries it isn't allowed to
reason its way out of.

## Two ways Strands shows up

1. **Inside the sweep** — one single-turn agent per category, each producing
   structured output. No tools, no loop; the orchestration around them is
   deterministic on purpose.
2. **Talking to the chief of staff** — a Strands **agents-as-tools**
   orchestrator. Each specialist is wrapped as a `@tool`, alongside read-only
   tools over the family's live data and the proposal log. Ask *"why did you
   propose the hamper, and is groceries near its budget?"* and the orchestrator
   model decides which specialists and data to consult, then answers in a few
   grounded sentences. This runs on **Bedrock AgentCore Runtime**, with
   **AgentCore Memory** carrying context across sweeps.

## How it uses AWS

| Service | Role |
|---|---|
| Amazon Bedrock (Nova Lite) | reasoning + justification per category |
| Bedrock AgentCore Runtime | hosts the agent for async background work + interactive Q&A |
| Bedrock AgentCore Memory | cross-sweep context for the "ask" path |
| AWS Lambda | scheduled sweep; FastAPI approve/reject/admin (via Mangum) |
| Amazon API Gateway (HTTP API) | public endpoint for the email links + dashboard |
| Amazon DynamoDB | single-table store — family, budgets, transactions, price history, sweep log |
| Amazon EventBridge Scheduler | fires the daily sweep |
| Amazon SES | the approval email — the one real external action |
| AWS Secrets Manager | admin password, sweep secret, SerpAPI key |
| AWS SAM / CloudFormation | infrastructure as code |

Amazon Nova Lite was a good fit for the reasoning step: the value here is a
tight, grounded justification, not prose, and Nova Lite is fast and inexpensive
at one sweep a day.

## What bit me

- **DynamoDB numbers.** boto3's resource client stores numbers as `Decimal` and
  rejects `float` on write. I ended up with one pair of conversion helpers at
  the data-layer boundary (`float -> Decimal` in, `Decimal -> int/float` out)
  so nothing above it ever sees a `Decimal`.
- **Testing an agent pipeline offline.** The first version of the test harness
  swapped the DynamoDB module in `sys.modules` but recreated it per test —
  modules that had already done `from ... import table as repo` kept the old
  reference and saw an empty store. Fix: one fake store instance, reset in
  place. The suite now runs with zero AWS access.
- **Email links can't be IAM-authed.** An Approve link is opened from a plain
  email in a browser; it can't carry a SigV4 signature. The real boundary is a
  random per-transaction token in the link; the admin dashboard gets its own
  HTTP Basic Auth gate because it's a broader surface.

## Try it

Repo: https://github.com/shamnadps/household-chief-of-staff (Apache-2.0). `pytest -q` runs 19 tests with no AWS
needed; `README.md` has the `sam deploy` and AgentCore steps; `docs/TESTING.md`
is a reviewer walkthrough.

*Built for the Agents for Humans hackathon.*
