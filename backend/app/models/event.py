from datetime import datetime

from pydantic import BaseModel


class Event(BaseModel):
    event_id: str
    user_id: str
    timestamp: datetime
    source: str
    event_type: str
    action: str
    resource: str | None
    resource_sensitivity: str | None
    source_ip: str | None
    destination: str | None
    device_id: str
    location: str | None
    role: str | None
    department: str | None
    work_schedule: str | None
    access_level: str | None
    is_external: bool | None 