"""
routers/admin.py — Admin endpoints for Cashio Security
  POST /admin/login
  GET  /admin/accounts
  POST /admin/unlock/{account_number}
  GET  /admin/total-deposits
"""

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app.dependencies import get_current_admin
from app.models import Account, Admin, Transaction
from app.schemas import (
    AdminLoginRequest, AdminLoginResponse,
    AdminAccountOut, TotalDepositsResponse,
    MessageResponse,
    paise_to_rupees,
)
from app.security import verify_password, create_access_token

router = APIRouter(prefix="/admin", tags=["Admin"])


# ---------------------------------------------------------------------------
# POST /admin/login
# ---------------------------------------------------------------------------
@router.post("/login", response_model=AdminLoginResponse, summary="Admin login")
def admin_login(req: AdminLoginRequest, db: Session = Depends(get_db)):
    """
    Admin login with password. Returns a separate admin JWT.
    Admin JWT has type='admin' in the payload.
    """
    admin = db.query(Admin).filter(Admin.id == 1).first()
    if admin is None:
        raise HTTPException(status_code=500, detail="Admin account not configured.")

    if not verify_password(req.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin password.",
        )

    token = create_access_token({"sub": "admin", "type": "admin"})
    return AdminLoginResponse(
        message="Admin login successful. Welcome to Cashio Security Admin Panel.",
        access_token=token,
        token_type="bearer",
    )


# ---------------------------------------------------------------------------
# GET /admin/accounts
# ---------------------------------------------------------------------------
@router.get(
    "/accounts",
    response_model=list[AdminAccountOut],
    summary="List all bank accounts",
)
def list_accounts(
    _: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Return all accounts (active and inactive). Admin only."""
    accounts = db.query(Account).order_by(Account.account_number).all()
    return [
        AdminAccountOut(
            account_number=a.account_number,
            name=a.name,
            email=a.email,
            phone=a.phone,
            balance_rupees=paise_to_rupees(a.balance),
            locked=a.locked,
            pin_locked=a.pin_locked,
            active=a.active,
            card_status=a.card_status,
            last_login=a.last_login,
        )
        for a in accounts
    ]


# ---------------------------------------------------------------------------
# POST /admin/unlock/{account_number}
# ---------------------------------------------------------------------------
@router.post(
    "/unlock/{account_number}",
    response_model=MessageResponse,
    summary="Unlock a locked account or PIN",
)
def unlock_account(
    account_number: str = Path(..., description="8-digit account number"),
    _: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Unlock a customer account and/or PIN that was locked due to failed attempts.
    Resets: locked, pin_locked, failed_login_count, pin_attempts.
    """
    account = db.query(Account).filter(Account.account_number == account_number).first()
    if not account:
        raise HTTPException(
            status_code=404,
            detail=f"Account {account_number} not found.",
        )

    was_locked = account.locked
    was_pin_locked = account.pin_locked

    account.locked = False
    account.pin_locked = False
    account.failed_login_count = 0
    account.pin_attempts = 0
    db.commit()

    parts = []
    if was_locked:
        parts.append("account login")
    if was_pin_locked:
        parts.append("PIN")
    if not parts:
        return MessageResponse(message=f"Account {account_number} was not locked.")

    return MessageResponse(
        message=f"Unlocked {' and '.join(parts)} for account {account_number} ({account.name})."
    )


# ---------------------------------------------------------------------------
# GET /admin/total-deposits
# ---------------------------------------------------------------------------
@router.get(
    "/total-deposits",
    response_model=TotalDepositsResponse,
    summary="Total deposits across all accounts",
)
def total_deposits(
    _: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Return the sum and count of all successful DEPOSIT transactions."""
    result = (
        db.query(
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
            func.count(Transaction.id).label("count"),
        )
        .filter(
            Transaction.type == "DEPOSIT",
            Transaction.status == "SUCCESS",
        )
        .one()
    )
    return TotalDepositsResponse(
        total_deposits_rupees=paise_to_rupees(result.total),
        total_deposits_paise=result.total,
        count=result.count,
    )

