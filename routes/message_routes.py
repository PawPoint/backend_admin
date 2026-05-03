from fastapi import APIRouter, HTTPException
from models.admin_model import MessageCreate
from logic.message_logic import send_message, get_messages, get_all_conversations

router = APIRouter()


@router.post("/api/admin/messages")
async def send_message_route(body: MessageCreate):
    """Send a message between admin users."""
    try:
        result = send_message(
            sender_id=body.sender_id,
            receiver_id=body.receiver_id,
            content=body.content,
            sender_name=body.sender_name or "",
            receiver_name=body.receiver_name or "",
            sender_role=body.sender_role or "staff_admin",
        )
        return {"message": "Sent", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/admin/messages/{uid}")
async def get_messages_route(uid: str):
    """Fetch all conversations for a given admin UID."""
    try:
        conversations = get_messages(uid)
        return {"conversations": conversations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/admin/messages")
async def get_all_conversations_route():
    """Fetch all admin conversations (super admin view)."""
    try:
        conversations = get_all_conversations()
        return {"conversations": conversations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
