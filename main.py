from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv
import os

load_dotenv()

# Initialize Firebase Admin (shared credential with main backend)
if not firebase_admin._apps:
    creds_path = "firebase-credentials.json"
    if os.path.exists(creds_path):
        try:
            cred = credentials.Certificate(creds_path)
            firebase_admin.initialize_app(cred)
            print("✅ Firebase Admin initialized successfully.")
        except Exception as e:
            print(f"❌ Error initializing Firebase Admin: {e}")
    else:
        print(f"❌ Error: {creds_path} not found. Please ensure it is provided as a Secret File on Render.")

from routes.admin_routes import router as admin_router
from routes.appointment_admin_routes import router as appt_admin_router
from routes.message_routes import router as message_router
from routes.services_routes import router as services_router
from routes.payment_routes import router as payment_router

app = FastAPI(title="PawPoint Admin API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_router,      tags=["Admin"])
app.include_router(appt_admin_router, tags=["AppointmentsAdmin"])
app.include_router(message_router,    tags=["Messages"])
app.include_router(services_router,   tags=["Services"])
app.include_router(payment_router,    tags=["Payments"])


@app.get("/")
def read_root():
    return {
        "status": "online",
        "message": "PawPoint Admin Backend is running!",
    }
