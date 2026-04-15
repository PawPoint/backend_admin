from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from logic.admin_logic import (
    get_all_services,
    create_service,
    update_service,
    delete_service,
)

router = APIRouter()


class ServiceBody(BaseModel):
    name: str
    price: float
    description: str = ""


# ── List All Services ─────────────────────────────────────────────────────────
@router.get("/api/admin/services")
async def list_services():
    try:
        return {"services": get_all_services()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Create Service ────────────────────────────────────────────────────────────
@router.post("/api/admin/services")
async def add_service(body: ServiceBody):
    try:
        result = create_service(
            name=body.name,
            price=body.price,
            description=body.description,
        )
        return {"message": "Service created", "service": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Update Service ────────────────────────────────────────────────────────────
@router.put("/api/admin/services/{service_id}")
async def edit_service(service_id: str, body: ServiceBody):
    try:
        result = update_service(
            service_id=service_id,
            name=body.name,
            price=body.price,
            description=body.description,
        )
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return {"message": "Service updated", "service": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Delete Service ────────────────────────────────────────────────────────────
@router.delete("/api/admin/services/{service_id}")
async def remove_service(service_id: str):
    try:
        result = delete_service(service_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return {"message": "Service deleted", "id": service_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
