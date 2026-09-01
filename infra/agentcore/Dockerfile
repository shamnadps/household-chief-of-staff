# Bedrock AgentCore Runtime container for the Household Chief of Staff agent.
# Hosts src/household_agent/runtime.py — {"action":"sweep"} for the daily
# background job, {"action":"ask","prompt":...} for interactive Q&A with
# AgentCore Memory.
#
# AgentCore Runtime requires linux/arm64.
FROM --platform=linux/arm64 public.ecr.aws/docker/library/python:3.12-slim

WORKDIR /app

COPY infra/agentcore/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ /app/src/
ENV PYTHONPATH=/app/src

# Runtime config. Override SES_SENDER / APPROVAL_RECIPIENT / BASE_URL at build
# or deploy time; the Memory id arrives as BEDROCK_AGENTCORE_MEMORY_ID from the
# AgentCore toolkit and is read by config.py.
ENV TABLE_NAME=HouseholdAgent \
    BEDROCK_MODEL_ID=us.amazon.nova-lite-v1:0 \
    CURRENCY=GBP \
    SERPAPI_API_KEY=none

# AgentCore Runtime invokes the HTTP server the SDK starts on port 8080.
EXPOSE 8080
CMD ["python", "-m", "household_agent.runtime"]
