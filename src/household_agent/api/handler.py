"""AWS Lambda entrypoint for the FastAPI service. API Gateway (HTTP API) proxies
every request here; Mangum adapts the ASGI app to the Lambda event/response
shape.

    infra/template.yaml -> Handler: household_agent.api.handler.handler
"""

from __future__ import annotations

from mangum import Mangum

from household_agent.api.app import app

handler = Mangum(app, lifespan="off")
