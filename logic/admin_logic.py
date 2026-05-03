from firebase_admin import firestore, auth as firebase_auth
from datetime import datetime
import os
import requests
import base64
from dotenv import load_dotenv
import stripe
from logic.email_logic import send_cancellation_email, send_verification_email


load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
paymongo_secret = os.getenv("PAYMONGO_SECRET_KEY")
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
    print("[get_all_approved_appointments] Fetching from top-level 'appointments' collection...")
    docs = db.collection("appointments").stream()
    results = []
    for doc in docs:
        data = doc.to_dict()
        status = data.get("status")
        print(f"[get_all_approved_appointments] Found doc {doc.id} | status: {status} | doctor: {data.get('doctor')} | dateTime: {data.get('dateTime')}")
        
        # Show approved, scheduled, and completed appointments on the calendar
        if status in ("approved", "scheduled", "completed"):
            results.append({"id": doc.id, **data})
    
    print(f"[get_all_approved_appointments] Returning {len(results)} appointments.")
    results.sort(key=lambda x: str(x.get("dateTime", "")), reverse=False)
    return results


def get_all_completed_appointments() -> list:
    """Fetch only completed appointments from the top-level 'appointments' collection."""
    db = get_db()
    docs = db.collection("appointments").stream()
    results = []
    for doc in docs:
        data = doc.to_dict()
        if data.get("status") == "completed":
            results.append({"id": doc.id, **data})
    results.sort(key=lambda x: str(x.get("dateTime", "")), reverse=True)
    return results


def get_all_rejected_appointments() -> list:
    """Scan all users and collect appointments with status 'rejected', 'cancelled', or 'auto_cancelled'."""
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
            if data.get("status") in ("rejected", "cancelled", "auto_cancelled"):
                results.append({
                    "id": appt.id,
                    "user_id": user_id,
                    "user_name": user_data.get("name", "Unknown"),
                    "user_email": user_data.get("email", ""),
                    **data,
                })
    results.sort(key=lambda x: str(x.get("rejected_at", x.get("cancelledAt", x.get("dateTime", "")))), reverse=True)
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
    """
    Vet cancels an appointment — ALWAYS issues a 100% full refund regardless
    of status. Writes an in-app notification to the user's Firestore subcollection
    AND sends a refund receipt email.
    """
    db = get_db()
    
    # Fetch user data for email and name
    user_doc_ref = db.collection("users").document(user_id)
    user_snapshot = user_doc_ref.get()
    user_data = user_snapshot.to_dict() or {}
    user_email = user_data.get("email")
    user_name = user_data.get("name", "Valued Customer")

    print(f"[reject_appointment] user_id: {user_id}")
    print(f"[reject_appointment] user_email: {user_email}")
    print(f"[reject_appointment] user_name: {user_name}")

    user_ref = user_doc_ref.collection("appointments").document(appointment_id)
    doc = user_ref.get()
    if not doc.exists:
        return {"error": "Appointment not found"}

    data = doc.to_dict() or {}
    amount_paid = float(data.get("amountPaidOnline", 0) or 0)
    checkout_session_id = data.get("checkoutSessionId", "")

    # ── Attempt full PayMongo refund ───────────────────────────────────────────
    paymongo_refund_id = None
    refund_status = "refund_not_needed" if amount_paid == 0 else "refund_pending"

    if amount_paid > 0 and checkout_session_id:
        try:
            auth_bytes = f"{paymongo_secret}:".encode("ascii")
            b64 = base64.b64encode(auth_bytes).decode("ascii")
            headers = {
                "accept": "application/json",
                "Content-Type": "application/json",
                "authorization": f"Basic {b64}",
            }
            session_resp = requests.get(
                f"https://api.paymongo.com/v1/checkout_sessions/{checkout_session_id}",
                headers=headers,
            )
            if session_resp.status_code == 200:
                session_data = session_resp.json()
                payment_intent_id = (
                    session_data.get("data", {})
                    .get("attributes", {})
                    .get("payment_intent", {})
                    .get("id")
                )
                if payment_intent_id:
                    pi_resp = requests.get(
                        f"https://api.paymongo.com/v1/payment_intents/{payment_intent_id}",
                        headers=headers,
                    )
                    if pi_resp.status_code == 200:
                        payments = (
                            pi_resp.json()
                            .get("data", {})
                            .get("attributes", {})
                            .get("payments", [])
                        )
                        if payments:
                            actual_payment_id = payments[0].get("id")
                            refund_resp = requests.post(
                                "https://api.paymongo.com/v1/refunds",
                                json={
                                    "data": {
                                        "attributes": {
                                            "amount": int(amount_paid * 100),
                                            "payment_id": actual_payment_id,
                                            "reason": "others",
                                            "notes": f"Vet cancelled appointment. {doctor_note}".strip(),
                                        }
                                    }
                                },
                                headers=headers,
                            )
                            if refund_resp.status_code in (200, 201):
                                paymongo_refund_id = refund_resp.json().get("data", {}).get("id")
                                refund_status = "refunded"
                            else:
                                print(f"[reject_appointment] Refund failed: {refund_resp.text}")
                                refund_status = "refund_pending"
        except Exception as e:
            print(f"[reject_appointment] Refund error: {e}")
            refund_status = "refund_pending"

    # ── Update appointment in Firestore ────────────────────────────────────────
    cancelled_at = datetime.utcnow().isoformat()
    update_payload = {
        "status": "rejected",
        "doctor_note": doctor_note,
        "rejected_at": cancelled_at,
        "cancelledBy": "vet",
        "refundStatus": refund_status,
        "refundAmount": amount_paid,
        "refundNote": "Full refund issued — appointment cancelled by vet.",
    }
    if paymongo_refund_id:
        update_payload["paymongoRefundId"] = paymongo_refund_id

    user_ref.update(update_payload)

    # ── Mirror to top-level appointments collection if present ────────────────
    top_ref = db.collection("appointments").document(appointment_id)
    if top_ref.get().exists:
        top_ref.update(update_payload)

    # ── Send Email Notification & Refund Receipt ──────────────────────────────
    if user_email and refund_status in ("refunded", "refund_pending", "refund_not_needed"):
        try:
            service = data.get("service", "your appointment")
            pet = data.get("pet", "your pet")
            appt_dt = data.get("dateTime", "")
            send_cancellation_email(
                to_email=user_email,
                user_name=user_name,
                appointment_id=appointment_id,
                service_name=service,
                pet_name=pet,
                appointment_date=appt_dt,
                amount_refunded=amount_paid,
                reason=doctor_note
            )
        except Exception as e:
            print(f"[reject_appointment] Email sending failed: {e}")
    else:
        print(f"[reject_appointment] Skipping email: user_email={user_email}, refund_status={refund_status}")

    # ── Write in-app notification to user ─────────────────────────────────────

    try:
        service = data.get("service", "your appointment")
        pet = data.get("pet", "your pet")
        appt_dt = data.get("dateTime", "")
        notif_ref = (
            db.collection("users")
            .document(user_id)
            .collection("notifications")
            .document(f"vet_cancelled_{appointment_id}")
        )
        if not notif_ref.get().exists:
            refund_line = (
                f" A full refund of ₱{amount_paid:.0f} has been initiated."
                if amount_paid > 0
                else ""
            )
            reason_line = f" Reason: {doctor_note}" if doctor_note else ""
            notif_ref.set({
                "id": f"vet_cancelled_{appointment_id}",
                "type": "appointment_cancelled",
                "title": "Appointment Cancelled by Vet 🩺",
                "body": (
                    f"Your {service} appointment for {pet} on {appt_dt[:10] if appt_dt else 'the scheduled date'} "
                    f"has been cancelled by the veterinarian.{reason_line}{refund_line}"
                ),
                "isRead": False,
                "createdAt": cancelled_at,
                "appointmentId": appointment_id,
                "service": service,
                "pet": pet,
            })
    except Exception as e:
        print(f"[reject_appointment] Notification write error: {e}")

    updated = user_ref.get()
    return {
        "id": appointment_id,
        "refund_status": refund_status,
        "refund_amount": amount_paid,
        **updated.to_dict(),
    }



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


def get_user_pets(user_id: str) -> list:
    """Fetch all pets for a specific user."""
    db = get_db()
    docs = db.collection("users").document(user_id).collection("pets").stream()
    results = []
    for doc in docs:
        data = doc.to_dict() or {}
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
    phone: str = "",
    bio: str = "",
    photoUrl: str = "",
    isActive: bool = False,
) -> dict:
    """Create a Firebase Auth user, send verification email, and seed into the admins collection."""
    db = get_db()

    # 1. Create or Update Firebase Auth account
    # NOTE: Firebase Auth only accepts http/https URLs for photo_url.
    # Base64 data URIs are stored in Firestore only.
    auth_photo_url = photoUrl if photoUrl and photoUrl.startswith("http") else None

    try:
        user = firebase_auth.get_user_by_email(email)
        uid = user.uid
        is_new = False
        # Update existing user to ensure they can log in with the new staff password
        update_kwargs = {
            "password": password,
            "display_name": name,
            "disabled": False,  # Ensure account is enabled
        }
        if auth_photo_url:
            update_kwargs["photo_url"] = auth_photo_url
        elif user.photo_url and user.photo_url.startswith("http"):
            # Keep existing valid Auth photo URL
            update_kwargs["photo_url"] = user.photo_url
        firebase_auth.update_user(uid, **update_kwargs)
    except firebase_auth.UserNotFoundError:
        create_kwargs = {
            "email": email,
            "password": password,
            "display_name": name,
            "email_verified": False,  # Must verify first
        }
        if phone:
            create_kwargs["phone_number"] = phone
        if auth_photo_url:
            create_kwargs["photo_url"] = auth_photo_url
        user = firebase_auth.create_user(**create_kwargs)
        uid = user.uid
        is_new = True

    # 2. Generate Verification Link if new
    verification_link = None
    if is_new:
        try:
            verification_link = firebase_auth.generate_email_verification_link(email)
        except Exception as e:
            print(f"[create_staff_account] Failed to generate verification: {e}")

    # 3. Seed admins collection
    doc_data = {
        "uid": uid,
        "email": email,
        "name": name,
        "role": role,
        "specialty": specialty,
        "phone": phone,
        "bio": bio,
        "photoUrl": photoUrl,
        "isActive": isActive,
        "isDeactivated": False,
        "email_verified": False if is_new else user.email_verified,
        "created_at": datetime.utcnow().isoformat(),
    }
    db.collection("admins").document(uid).set(doc_data, merge=True)
    
    return {
        "uid": uid, 
        "is_new": is_new, 
        "verification_link": verification_link,
        **doc_data
    }


def mark_staff_active(uid: str) -> dict:
    """Mark a staff member as active and verified."""
    db = get_db()
    ref = db.collection("admins").document(uid)
    if not ref.get().exists:
        return {"error": "Staff member not found"}
    
    ref.update({
        "isActive": True,
        "email_verified": True,
        "isDeactivated": False # Ensure reset if previously deactivated
    })
    return {"uid": uid, "isActive": True, "email_verified": True}


def deactivate_staff(uid: str) -> dict:
    """Deactivate a staff member (fire/resign)."""
    db = get_db()
    ref = db.collection("admins").document(uid)
    if not ref.get().exists:
        return {"error": "Staff member not found"}

    ref.update({
        "isActive": False,
        "isDeactivated": True,
        "deactivatedAt": datetime.utcnow().isoformat()
    })
    return {"uid": uid, "isActive": False, "isDeactivated": True}


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

    data = doc.to_dict() or {}
    status = data.get("status", "")
    if status in ("cancelled", "auto_cancelled", "rejected"):
        return {"error": f"Cannot collect balance for a {status} appointment."}

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
        status = data.get("status", "")
        service_name = data.get("service", "Other")

        # Skip appointments that are still pending or scheduled
        if status in ("pending", "scheduled"):
            continue

        # Case 1: User-initiated cancellation (Downpayment forfeited)
        if status in ("cancelled", "auto_cancelled"):
            # We count only the online downpayment as revenue
            gross_revenue += paid_online
            cash_collected += paid_online
            # No pending receivable for cancelled services
            if service_name:
                service_revenue[service_name] = service_revenue.get(service_name, 0.0) + paid_online
            continue

        # Case 2: Vet-initiated cancellation (Rejected)
        if status == "rejected":
            # If it's rejected, it's usually fully refunded (0 revenue)
            refund_status = data.get("refundStatus", "")
            if refund_status != "refunded":
                # Only count if for some reason it wasn't refunded
                gross_revenue += paid_online
                cash_collected += paid_online
                if service_name:
                    service_revenue[service_name] = service_revenue.get(service_name, 0.0) + paid_online
            # No pending receivable
            continue

        # Case 3: Active (Approved) or Finished (Completed)
        if total > 0:
            gross_revenue += total
            
            if pay_status == "fully_paid":
                # Entire total collected
                cash_collected += total
            else:
                # Only downpayment collected so far
                cash_collected += paid_online

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
        status = data.get("status", "")
        
        # Only include records that have payment data AND are approved/completed/cancelled
        if (not data.get("paymentMethod") and not data.get("totalPrice")) or status in ("pending", "scheduled"):
            continue
        results.append({
            "id": doc.id,
            "user_id": data.get("user_id", ""),
            "user_name": data.get("user_name", "Unknown"),
            "pet": data.get("pet", ""),
            "doctor": data.get("doctor", ""),
            "service": data.get("service", ""),
            "status": status,
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


def propose_reschedule(
    user_id: str, 
    appointment_id: str, 
    proposed_datetime: str,
    assigned_doctor: str = ""
) -> dict:
    """
    Staff admin proposes a new date/time for an appointment.

    - Status → 'reschedule_proposed'
    - Stores 'proposedDateTime' field
    - Sets 'doctor' field so we know who is proposing/assigned
    - Writes an in-app notification to the user asking them to Accept or Decline
    """
    from datetime import datetime, timezone
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
    current_status = data.get("status", "")

    if current_status in ("cancelled", "auto_cancelled", "completed", "reschedule_proposed"):
        return {"error": f"Cannot propose reschedule for appointment with status '{current_status}'"}

    now_utc = datetime.now(timezone.utc).isoformat()
    update_payload = {
        "status": "reschedule_proposed",
        "proposedDateTime": proposed_datetime,
        "rescheduledAt": now_utc,
    }
    if assigned_doctor:
        update_payload["doctor"] = assigned_doctor

    user_ref.update(update_payload)

    top_ref = db.collection("appointments").document(appointment_id)
    if top_ref.get().exists:
        top_ref.update(update_payload)

    # Write in-app notification so the user sees it
    service = data.get("service", "your appointment")
    pet = data.get("pet", "your pet")

    try:
        dt_str = proposed_datetime[:10]  # e.g. "2026-05-10"
        time_str = proposed_datetime[11:16] if len(proposed_datetime) > 10 else ""
        dt_label = f"{dt_str} at {time_str}" if time_str else dt_str
    except Exception:
        dt_label = proposed_datetime

    notif_id = f"reschedule_proposed_{appointment_id}"
    notif_ref = (
        db.collection("users")
        .document(user_id)
        .collection("notifications")
        .document(notif_id)
    )
    if not notif_ref.get().exists:
        notif_ref.set({
            "id": notif_id,
            "type": "rescheduleProposed",
            "title": "Reschedule Proposed 📅",
            "body": (
                f"The clinic has proposed a new time for your {service} appointment "
                f"for {pet}: {dt_label}. "
                f"Please open the app to Accept or Decline this new schedule."
            ),
            "isRead": False,
            "createdAt": now_utc,
            "appointmentId": appointment_id,
            "service": service,
            "pet": pet,
        })

    updated = user_ref.get()
    return {"id": appointment_id, **updated.to_dict()}
