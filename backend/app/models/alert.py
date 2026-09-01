from datetime import datetime

from pydantic import BaseModel


class Alert(BaseModel):
    alert_id: str
    user_id: str
    event_id: str
    risk_score: float
    severity: str
    reason: str
    evidence: list[str]
    status: str = "open"
    created_at: datetime