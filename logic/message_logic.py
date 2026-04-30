from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from datetime import datetime


def get_db():
    return firestore.client()


def send_message(sender_id: str, receiver_id: str, content: str, sender_name: str = "", sender_role: str = "staff_admin") -> dict:
    """Store a message in the admin_messages collection."""
    db = get_db()
    # Conversation ID is sorted pair of user IDs for easy lookup
    conv_id = "__".join(sorted([sender_id, receiver_id]))
    
    # 1. Update/Create the Parent Conversation Document for easy querying
    conv_ref = db.collection("admin_messages").document(conv_id)
    conv_metadata = {
        "participants": [sender_id, receiver_id],
        "last_message": content,
        "updated_at": datetime.utcnow().isoformat(),
    }
    conv_ref.set(conv_metadata, merge=True)

    # 2. Add the actual message to the subcollection
    msg_ref = conv_ref.collection("messages").document()
    data = {
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "sender_name": sender_name,
        "sender_role": sender_role,
        "content": content,
        "timestamp": datetime.utcnow().isoformat(),
        "read": False,
    }
    msg_ref.set(data)
    return {"id": msg_ref.id, **data}


def get_messages(uid: str) -> list:
    """Fetch all conversations where uid is a participant (Static fallback)."""
    db = get_db()
    # Query by participants array
    convs = db.collection("admin_messages").where(filter=FieldFilter("participants", "array_contains", uid)).stream()
    results = []
    for conv in convs:
        data = conv.to_dict()
        msgs = (
            db.collection("admin_messages")
            .document(conv.id)
            .collection("messages")
            .order_by("timestamp")
            .stream()
        )
        conv_msgs = [{"id": m.id, **m.to_dict()} for m in msgs]
        results.append({
            "conversation_id": conv.id, 
            "messages": conv_msgs,
            **data
        })
    # Sort results by updated_at
    results.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return results


def get_all_conversations() -> list:
    """Fetch all admin conversations (for super admin - Static fallback)."""
    db = get_db()
    convs = db.collection("admin_messages").order_by("updated_at", direction=firestore.Query.DESCENDING).stream()
    results = []
    for conv in convs:
        data = conv.to_dict()
        msgs = (
            db.collection("admin_messages")
            .document(conv.id)
            .collection("messages")
            .order_by("timestamp")
            .stream()
        )
        conv_msgs = [{"id": m.id, **m.to_dict()} for m in msgs]
        results.append({
            "conversation_id": conv.id, 
            "messages": conv_msgs,
            **data
        })
    return results
