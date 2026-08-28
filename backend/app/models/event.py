from datetime import datetime

from pydantic import BaseModel


class Event(BaseModel):
    event_id: str
    user_id: str
    timestamp: datetime
    source: str
    event_type: str
    action: str
    resource: str
    resource_sensitivity: str
    source_ip: str
    destination: str
    device_id: str
    location: str
    role: str
    department: str
    work_schedule: str
    access_level: str
    is_external: bool