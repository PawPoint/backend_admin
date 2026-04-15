"""
seed_admin_roles.py
-------------------
One-time script to stamp the correct Firestore role fields onto the two
pre-created admin accounts:

  superadmin@pawpoint.com  →  role: "super_admin"
  staffadmin@pawpoint.com  →  role: "staff_admin"

Run from the backend_admin directory:
    python seed_admin_roles.py

Make sure firebase-credentials.json is present (same one used by main.py).
"""

import firebase_admin
from firebase_admin import credentials, firestore

# ── Initialize Firebase Admin ─────────────────────────────────────────────────
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-credentials.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ── Admin accounts to seed ────────────────────────────────────────────────────
ADMINS = [
    {
        "uid": "JqvuhfEo8baJblJEl8qW1smm3KC3",
        "email": "superadmin@pawpoint.com",
        "name": "Super Admin",
        "role": "super_admin",
    },
    {
        "uid": "7qzW8QlSXgZRZU0cV8BmDkDQehz2",
        "email": "staffadmin@pawpoint.com",
        "name": "Staff Admin",
        "role": "staff_admin",
    },
]


def seed():
    for admin in ADMINS:
        uid = admin["uid"]
        ref = db.collection("users").document(uid)
        doc = ref.get()

        if doc.exists:
            # Only update the role (preserve everything else)
            ref.update({"role": admin["role"]})
            print(f"[UPDATED] {admin['email']}  →  role='{admin['role']}'")
        else:
            # Create the document from scratch
            ref.set({
                "uid": uid,
                "email": admin["email"],
                "name": admin["name"],
                "role": admin["role"],
                "phone": "",
                "address": "",
                "created_at": firestore.SERVER_TIMESTAMP,
            })
            print(f"[CREATED] {admin['email']}  →  role='{admin['role']}'")

    print("\n✅  Role seeding complete.")


if __name__ == "__main__":
    seed()
