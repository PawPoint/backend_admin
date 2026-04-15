from pydantic import BaseModel
from typing import Optional


class AdminLoginRequest(BaseModel):
    email: str
    password: str


class MessageCreate(BaseModel):
    sender_id: str
    receiver_id: str
    content: str
    sender_name: Optional[str] = ""
    sender_role: Optional[str] = "staff_admin"
