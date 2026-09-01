# Bedrock AgentCore Runtime deployment

The interactive **"ask the chief of staff"** path — and, optionally, the daily
sweep itself — runs on **Bedrock AgentCore Runtime**, hosting
`src/household_agent/runtime.py`.

| Payload | What it does |
|---|---|
| `{"action": "sweep"}` | Runs the deterministic daily sweep (same `sweep.run_sweep()` the scheduled Lambda calls). |
| `{"action": "ask", "prompt": "..."}` | Strands *agents-as-tools* orchestrator answers a question, with **AgentCore Memory** carrying context. Pass a `session_id` in the payload to pin the memory session, or reuse the same AgentCore Runtime session id (the `-s` flag / `Runtime-Session-Id` header) — `runtime.py` falls back to it. |

## Why AgentCore here

- **Long-running / async background execution** — the sweep fans out to four
  Bedrock calls plus a live flight-price lookup; AgentCore Runtime is built for
  exactly this rather than squeezing it into a request/response Lambda.
- **AgentCore Memory** — the family's questions and the agent's answers persist
  as short-term context and extracted long-term preferences, keyed per family.
- Judging note: *"Deploying with AgentCore is a smart architectural choice and
  will strengthen your Technical Implementation score."*

## Prerequisites

- AWS account with **Bedrock model access** enabled for `amazon.nova-lite-v1:0`
  (and the `us.` cross-region inference profile) in your region.
- The **starter-toolkit CLI**: `pip install bedrock-agentcore-starter-toolkit`
  (already in this repo's venv). It prints a "no longer supported" nudge toward
  the newer `@aws/agentcore` npm CLI — but that npm CLI is a different,
  CDK-scaffold product with an incompatible workflow. The starter toolkit's
  `configure` / `deploy` is what this project uses. Set
  `AGENTCORE_SUPPRESS_RECOMMENDATION=1` to silence the nudge.
- **No Docker needed** — the default `agentcore deploy` builds the ARM64
  container in the cloud with CodeBuild. (`--local-build` / `--local` need
  Docker/Finch/Podman.)
- IAM: the deploying principal needs `bedrock-agentcore:*`, `codebuild:*`,
  `ecr:*`, `logs:*`, `iam:*` (to create the execution + CodeBuild roles), and
  `s3:*` (CodeBuild source bucket). The auto-created **runtime execution role**
  comes with Bedrock invoke + Memory + logs, but **not** app data access — add
  an inline policy granting DynamoDB CRUD on `HouseholdAgent` and `ses:SendEmail`
  (see `infra/agentcore/runtime-data-policy.json`).

## Configure + deploy (cloud build, no Docker)

```bash
export AGENTCORE_SUPPRESS_RECOMMENDATION=1 AWS_REGION=us-east-1

agentcore configure \
  -e src/household_agent/runtime.py \
  -n household_chief_of_staff \
  -rf infra/agentcore/requirements.txt \
  --disable-otel --deployment-type container \
  --region us-east-1 --non-interactive
```

`configure` auto-creates the execution role, ECR repo, CodeBuild project **and a
short-term Memory resource** (no `scripts/create_memory.py` needed), and
generates `.bedrock_agentcore/household_chief_of_staff/Dockerfile`. That
generated Dockerfile needs three edits before `deploy` (the toolkit keeps your
edits on subsequent deploys):

1. Its `CMD` is `python -m src.household_agent.runtime`, which breaks the
   package's absolute `household_agent.*` imports. Replace the tail with:
   ```dockerfile
   ENV PYTHONPATH=/app/src
   CMD ["python", "-m", "household_agent.runtime"]
   ```
2. `agentcore deploy --env` is silently dropped by this toolkit version, so bake
   the runtime config in as `ENV` lines (`SES_SENDER`, `APPROVAL_RECIPIENT`,
   `BASE_URL` are the ones without safe defaults):
   ```dockerfile
   ENV TABLE_NAME=HouseholdAgent BEDROCK_MODEL_ID=us.amazon.nova-lite-v1:0 \
       CURRENCY=GBP SERPAPI_API_KEY=none \
       SES_SENDER=<verified-sender> APPROVAL_RECIPIENT=<verified-recipient> \
       BASE_URL=<HTTP API base URL from the SAM stack>
   ```

The Memory id is injected by the toolkit as `BEDROCK_AGENTCORE_MEMORY_ID`;
`config.py` reads that (and `AGENTCORE_MEMORY_ID`) so memory wires up with no
extra env.

```bash
agentcore deploy --auto-update-on-conflict
```

`agentcore deploy` (formerly `agentcore launch --code-build`) builds the
container in CodeBuild, pushes it to ECR, creates the AgentCore Runtime, and
returns its ARN. `infra/agentcore/Dockerfile` is the reference hand-written
equivalent (`PYTHONPATH`, entrypoint and env already correct).

## Invoke

```bash
agentcore invoke '{"action":"ask","prompt":"Why did you propose the food hamper for the anniversary?"}'
agentcore invoke '{"action":"sweep"}'
```

## Point the daily schedule at AgentCore (optional)

To run the scheduled sweep on AgentCore instead of the fallback Lambda, set the
EventBridge Scheduler target to a universal `bedrock-agentcore:InvokeAgentRuntime`
call with input `{"action":"sweep"}`, and disable `SweepFunction`'s schedule in
`infra/template.yaml`. The Lambda path is kept so the SAM stack is
self-contained and demoable without AgentCore access.
