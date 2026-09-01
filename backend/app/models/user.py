from pydantic import BaseModel


class User(BaseModel):
    user_id: str
    role: str = "analyst"
    is_active: bool = True