from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from logic.admin_logic import (
    mark_balance_paid,
    get_financial_stats,
    get_all_transactions,
)

router = APIRouter()


# ── Mark OTC Balance as Paid ──────────────────────────────────────────────────
class MarkPaidBody(BaseModel):
    user_id: str
    appointment_id: str


@router.put("/api/payments/mark-paid")
async def mark_otc_balance_paid(body: MarkPaidBody):
    """Staff action: mark the remaining OTC balance as paid for an appointment."""
    try:
        result = mark_balance_paid(
            user_id=body.user_id,
            appointment_id=body.appointment_id,
        )
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return {"message": "Balance marked as paid", "appointment": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Financial Summary (super_admin) ──────────────────────────────────────────
@router.get("/api/admin/financials")
async def get_financials():
    """Return gross revenue, cash collected, and pending receivables."""
    try:
        return get_financial_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── All Transactions (super_admin) ────────────────────────────────────────────
@router.get("/api/admin/transactions")
async def list_transactions():
    """Return a flat list of all payment transactions."""
    try:
        return {"transactions": get_all_transactions()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Payment Intent (placeholder — wire to Stripe/PayPal later) ───────────────
class IntentBody(BaseModel):
    amount: float
    currency: str = "PHP"
    description: str = ""


@router.post("/api/payments/create-intent")
async def create_payment_intent(body: IntentBody):
    """
    Placeholder: In production this would talk to Stripe/PayPal,
    create a payment intent, and return a client_secret.
    """
    import uuid
    fake_secret = f"pi_{uuid.uuid4().hex}_secret_{uuid.uuid4().hex[:8]}"
    return {
        "client_secret": fake_secret,
        "amount": body.amount,
        "currency": body.currency,
        "message": "Placeholder intent — wire to Stripe/PayPal for production.",
    }
