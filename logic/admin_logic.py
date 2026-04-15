from firebase_admin import firestore, auth as firebase_auth
from datetime import datetime


def get_db():
    return firestore.client()


# ══════════════════════════════════════════════════════════════════════════════
#  APPOINTMENTS
# ══════════════════════════════════════════════════════════════════════════════

def get_all_pending_appointments() -> list:
    """Scan all users and collect appointments with status 'pending' or 'scheduled'."""
    db = get_db()
    users_ref = db.collection("users").stream()
    results = []
    for user_doc in users_ref:
        user_data = user_doc.to_dict() or {}
        user_id = user_doc.id
        appts = (
            db.collection("users")
            .document(user_id)
            .collection("appointments")
            .stream()
        )
        for appt in appts:
            data = appt.to_dict()
            if data.get("status") in ("pending", "scheduled"):
                results.append({
                    "id": appt.id,
                    "user_id": user_id,
                    "user_name": user_data.get("name", "Unknown"),
                    "user_email": user_data.get("email", ""),
                    **data,
                })
    results.sort(key=lambda x: str(x.get("dateTime", "")), reverse=False)
    return results


def get_all_approved_appointments() -> list:
    """Fetch appointments from the top-level 'appointments' collection (approved/completed)."""
    db = get_db()
    docs = db.collection("appointments").stream()
    results = []
    for doc in docs:
        data = doc.to_dict()
        results.append({"id": doc.id, **data})
    results.sort(key=lambda x: str(x.get("dateTime", "")), reverse=False)
    return results


def approve_appointment(
    user_id: str,
    appointment_id: str,
    doctor_note: str = "",
    assigned_doctor: str = "",
) -> dict:
    """Approve an appointment: update user sub-collection + mirror to top-level."""
    db = get_db()
    user_ref = (
        db.collection("users")
        .document(user_id)
        .collection("appointments")
        .document(appointment_id)
    )
    doc = user_ref.get()
    if not doc.exists:
        return {"error": "Appointment not found"}

    data = doc.to_dict()
    data["status"] = "approved"
    data["doctor_note"] = doctor_note
    if assigned_doctor:
        data["doctor"] = assigned_doctor
    data["approved_at"] = datetime.utcnow().isoformat()
    data["user_id"] = user_id

    user_ref.update({
        "status": "approved",
        "doctor_note": doctor_note,
        "approved_at": data["approved_at"],
    })

    top_ref = db.collection("appointments").document(appointment_id)
    top_ref.set(data)

    return {"id": appointment_id, **data}


def reject_appointment(
    user_id: str, appointment_id: str, doctor_note: str = ""
) -> dict:
    """Reject an appointment."""
    db = get_db()
    user_ref = (
        db.collection("users")
        .document(user_id)
        .collection("appointments")
        .document(appointment_id)
    )
    doc = user_ref.get()
    if not doc.exists:
        return {"error": "Appointment not found"}

    user_ref.update({
        "status": "rejected",
        "doctor_note": doctor_note,
        "rejected_at": datetime.utcnow().isoformat(),
    })

    updated = user_ref.get()
    return {"id": appointment_id, **updated.to_dict()}


def complete_appointment(user_id: str, appointment_id: str) -> dict:
    """Mark an appointment as completed in both collections.
    Blocked if the appointment still has a remaining balance (Phase 3 rule).
    """
    db = get_db()
    user_ref = (
        db.collection("users")
        .document(user_id)
        .collection("appointments")
        .document(appointment_id)
    )
    doc = user_ref.get()
    if not doc.exists:
        return {"error": "Appointment not found"}

    data = doc.to_dict() or {}
    balance = data.get("balanceRemaining", 0)
    payment_method = data.get("paymentMethod", "")
    # Only enforce the balance check when Phase-3 payment fields exist
    if payment_method and float(balance or 0) > 0:
        return {"error": "Cannot complete appointment: outstanding balance of ₱{:.2f}".format(float(balance))}

    user_ref.update({"status": "completed"})

    top_ref = db.collection("appointments").document(appointment_id)
    if top_ref.get().exists:
        top_ref.update({"status": "completed"})

    updated = user_ref.get()
    return {"id": appointment_id, **updated.to_dict()}


# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD STATS
# ══════════════════════════════════════════════════════════════════════════════

def get_dashboard_stats() -> dict:
    """Aggregate stats for the super admin dashboard."""
    db = get_db()

    users = list(db.collection("users").stream())
    total_users = len(users)

    # Doctors/staff live in the 'admins' collection, not 'users'
    admins = list(db.collection("admins").stream())
    doctors = sum(
        1 for a in admins if (a.to_dict() or {}).get("role") == "staff_admin"
    )

    approved = list(db.collection("appointments").stream())
    total_approved = len(approved)
    total_completed = sum(
        1 for a in approved if (a.to_dict() or {}).get("status") == "completed"
    )

    pending_count = 0
    for user_doc in users:
        uid = user_doc.id
        appts = (
            db.collection("users").document(uid).collection("appointments").stream()
        )
        for appt in appts:
            if (appt.to_dict() or {}).get("status") in ("pending", "scheduled"):
                pending_count += 1

    from collections import defaultdict
    monthly = defaultdict(int)
    for a in approved:
        data = a.to_dict() or {}
        dt_raw = data.get("dateTime", "")
        try:
            dt = datetime.fromisoformat(str(dt_raw)[:19])
            key = dt.strftime("%b")
            monthly[key] += 1
        except Exception:
            pass

    return {
        "total_users": total_users,
        "total_doctors": doctors,
        "total_approved": total_approved,
        "total_completed": total_completed,
        "total_pending": pending_count,
        "monthly_appointments": dict(monthly),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  USERS
# ══════════════════════════════════════════════════════════════════════════════

def get_all_users() -> list:
    """Fetch all registered users from the users collection."""
    db = get_db()
    docs = db.collection("users").stream()
    results = []
    for doc in docs:
        data = doc.to_dict() or {}
        data.pop("password", None)
        results.append({"id": doc.id, **data})
    return results


# ══════════════════════════════════════════════════════════════════════════════
#  STAFF / ADMINS
# ══════════════════════════════════════════════════════════════════════════════

def get_all_staff() -> list:
    """Fetch all admin accounts from the 'admins' Firestore collection."""
    db = get_db()
    docs = db.collection("admins").stream()
    results = []
    for doc in docs:
        data = doc.to_dict() or {}
        data.pop("password", None)
        results.append({"id": doc.id, **data})
    return results


def create_staff_account(
    name: str,
    email: str,
    password: str,
    specialty: str = "Veterinarian",
    role: str = "staff_admin",
) -> dict:
    """Create a Firebase Auth user and seed into the admins collection."""
    db = get_db()

    # 1. Create Firebase Auth account
    try:
        user = firebase_auth.get_user_by_email(email)
        uid = user.uid
    except firebase_auth.UserNotFoundError:
        user = firebase_auth.create_user(
            email=email,
            password=password,
            display_name=name,
            email_verified=True,
        )
        uid = user.uid

    # 2. Seed admins collection
    doc_data = {
        "uid": uid,
        "email": email,
        "name": name,
        "role": role,
        "specialty": specialty,
        "created_at": datetime.utcnow().isoformat(),
    }
    db.collection("admins").document(uid).set(doc_data, merge=True)
    return {"uid": uid, **doc_data}


# ══════════════════════════════════════════════════════════════════════════════
#  SERVICES & PRICING
# ══════════════════════════════════════════════════════════════════════════════

def get_all_services() -> list:
    """Fetch all clinic services from Firestore."""
    db = get_db()
    docs = db.collection("services").stream()
    results = []
    for doc in docs:
        data = doc.to_dict() or {}
        results.append({"id": doc.id, **data})
    results.sort(key=lambda x: x.get("name", ""))
    return results


def create_service(name: str, price: float, description: str = "") -> dict:
    """Add a new service to Firestore."""
    db = get_db()
    ref = db.collection("services").document()
    data = {
        "name": name,
        "price": price,
        "description": description,
        "created_at": datetime.utcnow().isoformat(),
    }
    ref.set(data)
    return {"id": ref.id, **data}


def update_service(
    service_id: str, name: str, price: float, description: str = ""
) -> dict:
    """Update an existing service."""
    db = get_db()
    ref = db.collection("services").document(service_id)
    if not ref.get().exists:
        return {"error": "Service not found"}
    updates = {
        "name": name,
        "price": price,
        "description": description,
        "updated_at": datetime.utcnow().isoformat(),
    }
    ref.update(updates)
    return {"id": service_id, **updates}


def delete_service(service_id: str) -> dict:
    """Delete a service from Firestore."""
    db = get_db()
    ref = db.collection("services").document(service_id)
    if not ref.get().exists:
        return {"error": "Service not found"}
    ref.delete()
    return {"id": service_id, "deleted": True}


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 3 — PAYMENTS & FINANCIALS
# ══════════════════════════════════════════════════════════════════════════════

def mark_balance_paid(user_id: str, appointment_id: str) -> dict:
    """Staff OTC action: set balanceRemaining→0 and paymentStatus→fully_paid."""
    db = get_db()
    user_ref = (
        db.collection("users")
        .document(user_id)
        .collection("appointments")
        .document(appointment_id)
    )
    doc = user_ref.get()
    if not doc.exists:
        return {"error": "Appointment not found"}

    updates = {
        "balanceRemaining": 0.0,
        "paymentStatus": "fully_paid",
        "otc_paid_at": datetime.utcnow().isoformat(),
    }
    user_ref.update(updates)

    # Mirror to top-level appointments collection if present
    top_ref = db.collection("appointments").document(appointment_id)
    if top_ref.get().exists:
        top_ref.update(updates)

    updated = user_ref.get()
    return {"id": appointment_id, **updated.to_dict()}


def get_financial_stats() -> dict:
    """Aggregate financial KPIs from the appointments collection."""
    db = get_db()
    docs = list(db.collection("appointments").stream())

    gross_revenue = 0.0
    cash_collected = 0.0
    pending_receivables = 0.0
    service_revenue: dict = {}

    for doc in docs:
        data = doc.to_dict() or {}
        total = float(data.get("totalPrice", 0) or 0)
        paid_online = float(data.get("amountPaidOnline", 0) or 0)
        balance = float(data.get("balanceRemaining", 0) or 0)
        pay_status = data.get("paymentStatus", "")
        service_name = data.get("service", "Other")

        if total > 0:
            gross_revenue += total
            cash_collected += paid_online + (total - balance if pay_status == "fully_paid" else 0)
            if balance > 0:
                pending_receivables += balance

            if service_name:
                service_revenue[service_name] = service_revenue.get(service_name, 0.0) + total

    return {
        "gross_revenue": round(gross_revenue, 2),
        "cash_collected": round(cash_collected, 2),
        "pending_receivables": round(pending_receivables, 2),
        "service_revenue": service_revenue,
    }


def get_all_transactions() -> list:
    """Return a flat list of all appointment payment records."""
    db = get_db()
    docs = db.collection("appointments").stream()
    results = []
    for doc in docs:
        data = doc.to_dict() or {}
        # Only include records that have payment data
        if not data.get("paymentMethod") and not data.get("totalPrice"):
            continue
        results.append({
            "id": doc.id,
            "user_name": data.get("user_name", "Unknown"),
            "service": data.get("service", ""),
            "dateTime": str(data.get("dateTime", "")),
            "totalPrice": float(data.get("totalPrice", 0) or 0),
            "amountPaidOnline": float(data.get("amountPaidOnline", 0) or 0),
            "balanceRemaining": float(data.get("balanceRemaining", 0) or 0),
            "paymentStatus": data.get("paymentStatus", "pending"),
            "paymentMethod": data.get("paymentMethod", ""),
            "transactionId": data.get("transactionId", ""),
        })
    results.sort(key=lambda x: x["dateTime"], reverse=True)
    return results
