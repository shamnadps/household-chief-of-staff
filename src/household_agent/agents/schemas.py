"""Typed proposal shape the category agents must return. Strands converts this
Pydantic model into the Bedrock tool spec used for structured output.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProposalItem(BaseModel):
    ref_id: str = Field(
        description="The source record's id, copied verbatim from the input "
        "(member id / event id / grocery item id / wishlist item id)."
    )
    description: str = Field(description="One line: what to buy or book.")
    amount: float = Field(description="Estimated cost in the family's currency.", ge=0)
    justification: str = Field(
        description="2-3 sentences grounded only in the numbers given — the size "
        "delta and days since review, the days until the event and last year's "
        "gift, the days overdue, or the live vs target price."
    )


class ProposalBatch(BaseModel):
    proposals: list[ProposalItem] = Field(
        default_factory=list,
        description="One proposal per qualified candidate. Omit a candidate "
        "entirely rather than proposing something weak.",
    )
