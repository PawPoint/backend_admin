from fastapi import APIRouter, HTTPException
from models.appointment_admin_model import AppointmentStatusUpdate
from logic.admin_logic import (
    get_all_pending_appointments,
    get_all_rejected_appointments,
    approve_appointment,
    reject_appointment,
    cancel_appointment_by_admin,
    complete_appointment,
)

router = APIRouter()


@router.get("/api/admin/appointments/pending")
async def list_pending_appointments():
    """Fetch all pending/scheduled appointments across all users."""
    try:
        appts = get_all_pending_appointments()
        return {"appointments": appts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/admin/appointments/rejected")
async def list_rejected_appointments():
    """Fetch all rejected appointments across all users."""
    try:
        appts = get_all_rejected_appointments()
        return {"appointments": appts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/admin/appointments/{user_id}/{appointment_id}/approve")
async def approve_appointment_route(
    user_id: str, appointment_id: str, body: AppointmentStatusUpdate
):
    """Approve an appointment — copies it to the top-level collection."""
    try:
        result = approve_appointment(
            user_id,
            appointment_id,
            doctor_note=body.doctor_note or "",
            assigned_doctor=body.assigned_doctor or "",
        )
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return {"message": "Appointment approved", "appointment": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/admin/appointments/{user_id}/{appointment_id}/reject")
async def reject_appointment_route(
    user_id: str, appointment_id: str, body: AppointmentStatusUpdate
):
    """Reject an appointment."""
    try:
        result = reject_appointment(user_id, appointment_id, doctor_note=body.doctor_note or "")
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return {"message": "Appointment rejected", "appointment": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/admin/appointments/{user_id}/{appointment_id}/complete")
async def complete_appointment_route(user_id: str, appointment_id: str):
    """Mark an appointment as completed."""
    try:
        result = complete_appointment(user_id, appointment_id)
        return {"message": "Appointment completed", "appointment": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/admin/appointments/{user_id}/{appointment_id}/cancel")
async def cancel_appointment_by_admin_route(user_id: str, appointment_id: str, body: AppointmentStatusUpdate):
    """Admin cancels an appointment."""
    try:
        result = cancel_appointment_by_admin(
            user_id, appointment_id, reason=body.doctor_note or ""
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return {"message": "Appointment cancelled by admin", "appointment": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
