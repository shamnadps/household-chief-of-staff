"""Shared Bedrock model factory. One place to swap Amazon Nova Lite for another
model or region.
"""

from __future__ import annotations

from functools import lru_cache

from strands.models import BedrockModel

from household_agent.config import AWS_REGION, BEDROCK_MODEL_ID


@lru_cache(maxsize=1)
def category_model() -> BedrockModel:
    # Low temperature: the value here is a grounded justification, not prose.
    return BedrockModel(
        model_id=BEDROCK_MODEL_ID,
        region_name=AWS_REGION,
        temperature=0.3,
    )
