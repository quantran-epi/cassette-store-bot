from datetime import datetime

from pydantic import BaseModel, Field


class Customer(BaseModel):
    """Customer domain model with multi-phone and multi-address support."""

    id: int | None = None
    name: str
    phones: list[str] = Field(default_factory=list)
    addresses: list[str] = Field(default_factory=list)
    notes: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
