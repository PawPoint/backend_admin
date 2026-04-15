from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from logic.admin_logic import (
    get_all_users,
    get_dashboard_stats,
    get_all_approved_appointments,
    get_all_staff,
    create_staff_account,
)

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


# ── Approved Appointments (master view) ───────────────────────────────────────
@router.get("/api/admin/appointments/approved")
async def list_approved_appointments():
    try:
        return {"appointments": get_all_approved_appointments()}
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


@router.post("/api/admin/staff")
async def provision_staff(body: CreateStaffRequest):
    """Create a new Firebase Auth user and seed into the admins collection."""
    try:
        result = create_staff_account(
            name=body.name,
            email=body.email,
            password=body.password,
            specialty=body.specialty,
            role=body.role,
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return {"message": "Staff account created", "staff": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
