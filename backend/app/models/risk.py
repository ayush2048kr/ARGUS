from datetime import datetime

from pydantic import BaseModel, Field


class RiskAssessment(BaseModel):
    risk_id: str
    user_id: str
    event_id: str

    severity: str

    risk_score: float = Field(ge=0, le=100)
    behavior_deviation_score: float = Field(ge=0, le=100)
    peer_deviation_score: float = Field(ge=0, le=100)
    context_risk_score: float = Field(ge=0, le=100)
    activity_severity: float = Field(ge=0, le=100)
    evidence: list[str]
    reason: str

    created_at: datetime
    
