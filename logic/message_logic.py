from firebase_admin import firestore
from datetime import datetime


def get_db():
    return firestore.client()


def send_message(sender_id: str, receiver_id: str, content: str, sender_name: str = "", sender_role: str = "staff_admin") -> dict:
    """Store a message in the admin_messages collection."""
    db = get_db()
    # Conversation ID is sorted pair of user IDs for easy lookup
    conv_id = "__".join(sorted([sender_id, receiver_id]))
    msg_ref = db.collection("admin_messages").document(conv_id).collection("messages").document()
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
    """Fetch all conversations where uid is a participant."""
    db = get_db()
    convs = db.collection("admin_messages").stream()
    results = []
    for conv in convs:
        conv_id = conv.id
        if uid in conv_id.split("__"):
            msgs = (
                db.collection("admin_messages")
                .document(conv_id)
                .collection("messages")
                .order_by("timestamp")
                .stream()
            )
            conv_msgs = [{"id": m.id, **m.to_dict()} for m in msgs]
            results.append({"conversation_id": conv_id, "messages": conv_msgs})
    return results


def get_all_conversations() -> list:
    """Fetch all conversations (for super admin)."""
    db = get_db()
    convs = db.collection("admin_messages").stream()
    results = []
    for conv in convs:
        conv_id = conv.id
        msgs = (
            db.collection("admin_messages")
            .document(conv_id)
            .collection("messages")
            .order_by("timestamp")
            .stream()
        )
        conv_msgs = [{"id": m.id, **m.to_dict()} for m in msgs]
        results.append({"conversation_id": conv_id, "messages": conv_msgs})
    return results
