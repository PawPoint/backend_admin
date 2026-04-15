from pydantic import BaseModel
from typing import Optional


class AppointmentStatusUpdate(BaseModel):
    status: str  # 'approved' | 'rejected' | 'completed'
    doctor_note: Optional[str] = ""
    assigned_doctor: Optional[str] = ""
