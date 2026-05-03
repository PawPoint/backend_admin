from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from logic.admin_logic import (
    get_all_users,
    get_dashboard_stats,
    get_all_approved_appointments,
    get_all_completed_appointments,
    get_all_staff,
    create_staff_account,
    propose_reschedule,
    mark_staff_active,
    deactivate_staff,
    get_user_pets,
)
from logic.email_logic import send_verification_email

router = APIRouter()


# ── Dashboard Stats ───────────────────────────────────────────────────────────
@router.get("/api/admin/stats")
async def dashboard_stats():
    try:
        return get_dashboard_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Users ─────────────────────────────────────────────────────────────────────
@router.get("/api/admin/users")
async def list_all_users():
    try:
        return {"users": get_all_users()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/admin/users/{user_id}/pets")
async def list_user_pets(user_id: str):
    """Return all pets for a specific user."""
    try:
        pets = get_user_pets(user_id)
        return {"pets": pets}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Approved Appointments (master view) ───────────────────────────────────────
@router.get("/api/admin/appointments/approved")
async def list_approved_appointments():
    try:
        return {"appointments": get_all_approved_appointments()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Completed Appointments ─────────────────────────────────────────────────────
@router.get("/api/admin/appointments/completed")
async def list_completed_appointments():
    try:
        return {"appointments": get_all_completed_appointments()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Staff / Admins ────────────────────────────────────────────────────────────
@router.get("/api/admin/staff")
async def list_staff():
    """Return all admin accounts (doctors + nurses) from the admins collection."""
    try:
        return {"staff": get_all_staff()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class CreateStaffRequest(BaseModel):
    name: str
    email: str
    password: str
    specialty: str = "Veterinarian"
    role: str = "staff_admin"
    phone: str = ""
    bio: str = ""
    photoUrl: str = ""
    isActive: bool = False


@router.post("/api/admin/staff")
async def provision_staff(body: CreateStaffRequest, bg: BackgroundTasks):
    """Create a new Firebase Auth user and seed into the admins collection."""
    try:
        result = create_staff_account(
            name=body.name,
            email=body.email,
            password=body.password,
            specialty=body.specialty,
            role=body.role,
            phone=body.phone,
            bio=body.bio,
            photoUrl=body.photoUrl,
            isActive=body.isActive,
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        # Send verification email in the background if link exists
        v_link = result.get("verification_link")
        if v_link:
            bg.add_task(send_verification_email, body.email, body.name, v_link)

        return {"message": "Staff account created", "staff": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/admin/staff/{uid}/activate")
async def activate_staff(uid: str):
    """Mark a staff member as active."""
    try:
        result = mark_staff_active(uid)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return {"message": "Staff member activated", "staff": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/admin/staff/{uid}/deactivate")
async def deactivate_staff_route(uid: str):
    """Mark a staff member as deactivated (fire/resign)."""
    try:
        result = deactivate_staff(uid)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return {"message": "Staff member deactivated", "staff": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Propose Reschedule ────────────────────────────────────────────────────────
class ProposeRescheduleRequest(BaseModel):
    proposed_datetime: str   # ISO 8601 e.g. "2026-05-10T14:00:00"
    assigned_doctor: str = ""


@router.put("/api/admin/appointments/{user_id}/{appointment_id}/propose-reschedule")
async def propose_reschedule_route(
    user_id: str,
    appointment_id: str,
    body: ProposeRescheduleRequest,
):
    """Staff admin proposes a new date/time — sets status to reschedule_proposed."""
    try:
        result = propose_reschedule(
            user_id, 
            appointment_id, 
            body.proposed_datetime,
            assigned_doctor=body.assigned_doctor
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return {"message": "Reschedule proposed successfully", "appointment": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
