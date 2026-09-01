from datetime import datetime

from pydantic import BaseModel


class RiskAssessment(BaseModel):
    risk_id: str
    user_id: str
    event_id: str

    risk_score: float
    severity: str

    behavior_deviation_score: float
    peer_deviation_score: float
    context_risk_score: float

    activity_severity: float

    evidence: list[str]
    reason: str

    created_at: datetime
    
