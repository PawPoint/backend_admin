"""
seed_new_admins.py
------------------
Creates the four new PawPoint admin accounts in Firebase Auth (if they don't
exist) and writes their role documents to the 'admins' Firestore collection.

Role mapping (per blueprint):
  staff_admin  → doctors  (Ji-Eun Park, Matteo Rossi)
  super_admin  → nurses   (Hana Kim,    Sofia Müller)

Run from the backend_admin directory:
    python seed_new_admins.py
"""

import firebase_admin
from firebase_admin import credentials, auth, firestore

# ── Initialize Firebase Admin ─────────────────────────────────────────────────
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-credentials.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ── Admin accounts to create ──────────────────────────────────────────────────
ADMINS = [
    {
        "email": "drji-eunpark@pawpoint.com",
        "password": "pawpointadmin_staff1",
        "name": "Dr. Ji-Eun Park",
        "role": "staff_admin",
        "specialty": "Veterinarian",
    },
    {
        "email": "drmatteorossi@pawpoint.com",
        "password": "pawpointadmin_staff2",
        "name": "Dr. Matteo Rossi",
        "role": "staff_admin",
        "specialty": "Veterinarian",
    },
    {
        "email": "nursehanakim@pawpoint.com",
        "password": "pawpointsuper_adminstaff1",
        "name": "Nurse Hana Kim",
        "role": "super_admin",
        "specialty": "Veterinary Nurse",
    },
    {
        "email": "nursesofiamuller@pawpoint.com",
        "password": "pawpointsuper_adminstaff2",
        "name": "Nurse Sofia Müller",
        "role": "super_admin",
        "specialty": "Veterinary Nurse",
    },
]


def get_or_create_user(email: str, password: str, display_name: str) -> str:
    """Return existing UID or create a new user and return the new UID."""
    try:
        user = auth.get_user_by_email(email)
        print(f"  [EXISTS] {email}  →  uid={user.uid}")
        # Update display name if missing
        if not user.display_name:
            auth.update_user(user.uid, display_name=display_name)
        return user.uid
    except auth.UserNotFoundError:
        user = auth.create_user(
            email=email,
            password=password,
            display_name=display_name,
            email_verified=True,
        )
        print(f"  [CREATED] {email}  →  uid={user.uid}")
        return user.uid


def seed():
    print("\n🌱  Seeding admin accounts...\n")
    for admin in ADMINS:
        uid = get_or_create_user(admin["email"], admin["password"], admin["name"])

        # Write / update the admins collection document
        ref = db.collection("admins").document(uid)
        ref.set(
            {
                "uid": uid,
                "email": admin["email"],
                "name": admin["name"],
                "role": admin["role"],
                "specialty": admin["specialty"],
                "created_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,  # Preserve any existing fields
        )
        role_label = "staff_admin (Doctor)" if admin["role"] == "staff_admin" else "super_admin (Nurse)"
        print(f"  [FIRESTORE] admins/{uid}  →  role='{admin['role']}'  ({role_label})\n")

    print("✅  Admin seeding complete.")
    print("\nYou can now log in with:")
    for a in ADMINS:
        print(f"   {a['email']}  /  {a['password']}  [{a['role']}]")


if __name__ == "__main__":
    seed()
