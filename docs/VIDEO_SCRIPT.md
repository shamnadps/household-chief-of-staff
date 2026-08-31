# Demo video script — Household Chief of Staff

Target: **under 5 minutes**. No need to appear on camera — screen recording +
voiceover is fine. Beats below are timed; the pitch must cover **(1) the
problem, (2) who it's for, (3) why it matters**, and the video must **show the
project working end to end**.

Two ways to run the demo:
- **Deployed** (preferred, scores higher): the SAM stack + `AdminUrl`, a real
  `aws lambda invoke` of the sweep, a real SES email, a real Approve click.
- **Local** (fallback): `uvicorn household_agent.api.app:app` for the dashboard,
  `python scripts/local_sweep.py` for the sweep, dashboard Approve buttons
  instead of the email. Show the AWS console (DynamoDB items, Lambda, Bedrock)
  either way.

Before recording: `python scripts/demo_reset.py` then `python scripts/seed_data.py`
so the dashboard starts clean and every category has a candidate.

---

## 0:00–0:40 — The problem (1) + who it's for (2)

**Screen:** a title card, or a plain slide with the four category icons.

> "Running a household is a rolling list of tiny decisions that never stops.
> Have the kids outgrown their shoes? Is a gift sorted for the anniversary in
> two weeks? Did the grocery reorder go out? Is now a cheap time to book those
> flights?
>
> None of these is hard. But doing them *well* means remembering what you
> bought last year, checking current prices, and staying inside a budget — and
> that overhead never goes away. It's a permanent background tax on attention,
> and it lands hardest on parents.
>
> Household Chief of Staff is an agent that carries that list. It runs in the
> background, and it only pings you when there's a real decision to make."

## 0:40–1:15 — Why it matters (3) + the shape

**Screen:** `docs/architecture.svg`.

> "The design decision that matters is *trust*. If an agent is going to email me
> spending decisions, I need to know it can't talk itself into one.
>
> So the model never decides *whether* to act, and never decides *whether
> something is affordable*. Both of those are plain Python. Trigger rules run
> first — is anything even worth looking at? A budget guardrail runs last — does
> this fit? The Strands agent in the middle has one job: given a qualified
> candidate and the real data, write the proposal and justify it.
>
> It runs on AWS — Strands Agents on Amazon Bedrock, a daily EventBridge
> schedule, DynamoDB, SES for the email, and Bedrock AgentCore for the part you
> can talk to."

## 1:15–2:30 — Run the sweep (working demo, part 1)

**Screen:** terminal, then the AWS console.

> "Here's a sweep running."

- **Deployed:** `aws lambda invoke --function-name household-agent-sweep /dev/stdout`
- **Local:** `python scripts/local_sweep.py`

> "It checked all four categories. It found a candidate in wardrobe — Kai's shoe
> size jumped two EU sizes and it's been over 90 days since the last review —
> and one in gifts: the anniversary is 11 days out."

**Screen:** AWS console — **Bedrock** usage/metrics, then **DynamoDB** showing
the new `TXN#` items, then **CloudWatch logs** for the sweep function.

> "Every proposal is a real DynamoDB write, and every justification traces back
> to a document in that table — the size delta, the days since review, last
> year's gift."

## 2:30–3:30 — The approval email + one click (working demo, part 2)

**Screen:** the inbox.

> "One email per proposal. Category, the proposal, the amount, the reason, and
> two links."

Open the wardrobe email. Read the justification aloud.

> "The gifts one is the interesting case — last year's gift was a spa voucher,
> so the agent deliberately proposed something different: a food-and-wine
> hamper, inside the £150 budget."

Click **Approve** on the wardrobe email.

**Screen:** the JSON response, then back to DynamoDB.

> "That hit API Gateway and a Lambda, which checked the per-transaction token,
> flipped the transaction to executed, and moved the wardrobe budget counter.
> Nothing bought anything — this is a simulated execution model."

*(Local fallback: click Approve on the dashboard card instead.)*

## 3:30–4:20 — The dashboard + ask the chief of staff

**Screen:** the `/admin` dashboard.

> "One page for everything: what needs approval by category, today's activity,
> what's trending toward qualifying next, and the budgets — where the bars shade
> in what's *pending*, so you can see at a glance whether approving everything
> queued would push a category over."

**Screen:** terminal — `agentcore invoke`.

> "And because it's a Strands agents-as-tools orchestrator on AgentCore Runtime,
> I can just ask it things."

```
agentcore invoke '{"action":"ask","prompt":"Why did you propose the hamper, and is groceries near its budget?"}'
```

> "It consults the gifts specialist and the live budget and answers in a
> couple of sentences — grounded in the same real numbers. AgentCore Memory
> keeps that context across sweeps."

*(If AgentCore isn't deployed: show `orchestrator.ask(...)` run locally instead,
and say the same thing.)*

## 4:20–4:50 — Close

**Screen:** the repo, then the architecture diagram.

> "Deterministic rules on the edges, a Strands agent in the middle, one
> decision at a time. The whole thing is on GitHub — Apache-2.0, a README, and
> a test suite that runs with no AWS access.
>
> Household Chief of Staff. It watches, it decides, it justifies — and it asks
> first."

---

### Shot checklist (must appear on screen)

- [ ] Sweep running (Lambda invoke or `local_sweep.py`)
- [ ] **AWS Console: Bedrock** (model usage / metrics) — proof it runs on AWS
- [ ] **AWS Console: DynamoDB** items (`TXN#…`) appearing
- [ ] **AWS Console: Lambda** and/or CloudWatch logs for the sweep
- [ ] A real approval email (or dashboard card) with a grounded justification
- [ ] Approve click → state change visible
- [ ] The `/admin` dashboard with budget bars
- [ ] `agentcore invoke` (or local `orchestrator.ask`) answering a question
- [ ] The public GitHub repo page
