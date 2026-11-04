
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.risk_level import get_severity_from_score


class RiskAssessment(BaseModel):
    risk_id: str = Field(min_length=1, max_length=128)
    user_id: str = Field(min_length=1, max_length=64)
    event_id: str = Field(min_length=1, max_length=128)

    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    risk_score: float = Field(ge=0, le=100)
    behavior_deviation_score: float = Field(ge=0, le=100)
    peer_deviation_score: float = Field(ge=0, le=100)
    context_risk_score: float = Field(ge=0, le=100)
    activity_severity: float = Field(ge=0, le=100)

    evidence: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=2000)

    created_at: datetime

    @model_validator(mode="after")
    def validate_severity_matches_score(self):
        expected_severity = get_severity_from_score(self.risk_score)

        if self.severity != expected_severity:
            raise ValueError(
                f"Severity must be {expected_severity} "
                f"for risk score {self.risk_score}"
            )

        return self
