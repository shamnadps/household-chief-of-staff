# Bedrock AgentCore Runtime deployment

The interactive **"ask the chief of staff"** path — and, optionally, the daily
sweep itself — runs on **Bedrock AgentCore Runtime**, hosting
`src/household_agent/runtime.py`.

| Payload | What it does |
|---|---|
| `{"action": "sweep"}` | Runs the deterministic daily sweep (same `sweep.run_sweep()` the scheduled Lambda calls). |
| `{"action": "ask", "prompt": "...", "session_id": "..."}` | Strands *agents-as-tools* orchestrator answers a question, with **AgentCore Memory** carrying context across sweeps. |

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
- The **AgentCore CLI**: `npm install -g @aws/agentcore`
  (the older `pip install bedrock-agentcore-starter-toolkit` is deprecated and
  its `agentcore` CLI prints a deprecation notice).
- **No Docker needed** — the default `agentcore deploy` builds the ARM64
  container in the cloud with CodeBuild. (`--local-build` / `--local` need
  Docker/Finch/Podman.)
- IAM permissions to let the CLI create the execution role, CodeBuild project,
  and ECR repo it needs, plus `bedrock-agentcore:*`. The runtime's execution
  role needs: `bedrock:InvokeModel*`, DynamoDB CRUD on the `HouseholdAgent`
  table, `ses:SendEmail`, `bedrock-agentcore:*` (Memory), and
  `secretsmanager:GetSecretValue` for the SerpAPI secret.

## One-time: create the Memory resource

```bash
python scripts/create_memory.py          # prints AGENTCORE_MEMORY_ID
```

## Configure + deploy (cloud build, no Docker)

```bash
# from the repo root
agentcore configure \
  --entrypoint src/household_agent/runtime.py \
  --name household-chief-of-staff \
  --requirements-file infra/agentcore/requirements.txt \
  --region us-east-1

agentcore deploy \
  --env TABLE_NAME=HouseholdAgent \
  --env BEDROCK_MODEL_ID=us.amazon.nova-lite-v1:0 \
  --env CURRENCY=GBP \
  --env AGENTCORE_MEMORY_ID=<from create_memory.py> \
  --env SES_SENDER=<verified-sender> \
  --env APPROVAL_RECIPIENT=<verified-recipient> \
  --env BASE_URL=<HTTP API base URL from the SAM stack> \
  --env SERPAPI_API_KEY=<key>
```

`agentcore deploy` (formerly `agentcore launch --code-build`) builds the
container in CodeBuild, pushes it to ECR, creates the AgentCore Runtime, and
returns its ARN. The hand-written `infra/agentcore/Dockerfile` is kept for
reference and for `agentcore deploy --local-build`.

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
