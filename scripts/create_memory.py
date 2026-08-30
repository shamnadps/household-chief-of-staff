"""Create the Bedrock AgentCore Memory resource the interactive orchestrator
uses, and print its id. One-time setup — put the printed value in
``AGENTCORE_MEMORY_ID`` (Lambda env / AgentCore launch env / .env).

    python scripts/create_memory.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from household_agent.memory import create_memory_resource  # noqa: E402

if __name__ == "__main__":
    memory_id = create_memory_resource()
    print(memory_id)
    print(
        "\nSet this as AGENTCORE_MEMORY_ID for the AgentCore Runtime "
        "(see infra/agentcore/README.md)."
    )
