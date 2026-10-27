
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Alert(BaseModel):
    alert_id: str = Field(min_length=1, max_length=128)
    user_id: str = Field(min_length=1, max_length=64)
    event_id: str = Field(min_length=1, max_length=128)

    risk_score: float = Field(ge=0, le=100)
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    reason: str = Field(min_length=1, max_length=2000)
    evidence: list[str] = Field(min_length=1)

    status: Literal["open", "investigating", "resolved"] = "open"
    created_at: datetime
