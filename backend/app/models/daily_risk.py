
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.risk_level import get_severity_from_score


class DailyRisk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(min_length=1, max_length=64)
    date: date

    behavioral_deviation_score: float | None = Field(default=None, ge=0, le=100)
    baseline_status: str

    peer_deviation_score: float | None = Field(default=None, ge=0, le=100)
    peer_deviation_status: str

    role: str | None = None
    ldap_domain: str | None = None

    context_event_count: int | None = Field(default=None, ge=0)
    context_match_status: str
    context_risk_score: float | None = Field(default=None, ge=0, le=100)
    context_status: str
    context_explanation: str
    context_peer_count: int = Field(default=0, ge=0)

    risk_score: float | None = Field(default=None, ge=0, le=100)
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL", "UNAVAILABLE"]
    risk_status: Literal["scored", "insufficient_evidence"]

    components_used: str
    risk_explanation: str
    peer_score_scope: str

    @model_validator(mode="after")
    def validate_risk_consistency(self):
        if self.risk_status == "insufficient_evidence":
            if self.risk_score is not None:
                raise ValueError("Unavailable risk must not have a score")
            if self.risk_level != "UNAVAILABLE":
                raise ValueError("Unavailable risk must use UNAVAILABLE level")
        else:
            if self.risk_score is None:
                raise ValueError("Scored risk must have a score")

            expected = get_severity_from_score(self.risk_score)
            if self.risk_level != expected:
                raise ValueError("Risk level does not match risk score")

        return self
