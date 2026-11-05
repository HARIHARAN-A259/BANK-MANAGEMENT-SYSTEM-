"""
routers/account.py — Account management endpoints for Cashio Security
  GET  /account/details
  GET  /account/profile
  PUT  /account/profile
  POST /account/reset-password
  PUT  /account/username
  DELETE /account
  GET  /account/balance
  POST /account/interest
  GET  /account/statement
"""

from datetime import datetime, timezone, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_current_user
from app.models import Account, Transaction, Meta
from app.schemas import (
    AccountDetails, ProfileResponse, ProfileUpdateRequest,
    ResetPasswordRequest, ResetPinRequest, UsernameUpdateRequest, DeleteAccountRequest,
    BalanceResponse, InterestRequest, MessageResponse,
    paise_to_rupees, rupees_to_paise,
)
from app.security import (
    validate_password, hash_password, verify_password,
    hash_pin, verify_pin,
    mask_card, format_txn_id,
)
from app.pdf_utils import generate_statement_pdf

router = APIRouter(prefix="/account", tags=["Account"])


def _next_txn_id(db: Session) -> str:
    """Atomically increment and return the next TXN ID."""
    meta = db.query(Meta).filter(Meta.key == "next_txn_counter").with_for_update().first()
    counter = int(meta.value)
    meta.value = str(counter + 1)
    return format_txn_id(counter)


def _log_txn(db, account_number, txn_id, txn_type, amount_paise, balance_after, status, remark=""):
    txn = Transaction(
        txn_id=txn_id,
        account_number=account_number,
        type=txn_type,
        amount=amount_paise,
        balance_after=balance_after,
        timestamp=datetime.now(timezone.utc).isoformat(),
        status=status,
        remark=remark,
    )
    db.add(txn)


def _check_pin(account: Account, pin: str, db: Session) -> None:
    """Verify PIN; increment attempts and lock if needed. Raises HTTPException on failure."""
    MAX_PIN_ATTEMPTS = 3

    if account.pin_locked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PIN is locked due to too many wrong attempts. Contact admin.",
        )

    if not verify_pin(pin, account.pin_hash):
        account.pin_attempts += 1
        if account.pin_attempts >= MAX_PIN_ATTEMPTS:
            account.pin_locked = True
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Wrong PIN. PIN locked after {MAX_PIN_ATTEMPTS} failed attempts.",
            )
        db.commit()
        remaining = MAX_PIN_ATTEMPTS - account.pin_attempts
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Wrong PIN. {remaining} attempt(s) remaining before PIN lockout.",
        )

    # Correct PIN — reset counter
    account.pin_attempts = 0
    db.commit()


# ---------------------------------------------------------------------------
# GET /account/details
# ---------------------------------------------------------------------------
@router.get("/details", response_model=AccountDetails, summary="Get full account details")
def get_account_details(
    account: Account = Depends(get_current_user),
):
    return AccountDetails(
        account_number=account.account_number,
        name=account.name,
        email=account.email,
        phone=account.phone,
        address=account.address,
        balance_rupees=paise_to_rupees(account.balance),
        locked=account.locked,
        pin_locked=account.pin_locked,
        active=account.active,
        last_login=account.last_login,
        card_status=account.card_status,
        card_masked=mask_card(account.card_number) if account.card_number else None,
        card_expiry=account.card_expiry,
        withdraw_limit_rupees=paise_to_rupees(account.withdraw_limit),
        transfer_limit_rupees=paise_to_rupees(account.transfer_limit),
        daily_withdraw_limit_rupees=paise_to_rupees(account.daily_withdraw_limit),
    )


# ---------------------------------------------------------------------------
# GET /account/profile
# ---------------------------------------------------------------------------
@router.get("/profile", response_model=ProfileResponse, summary="Get contact profile")
def get_profile(account: Account = Depends(get_current_user)):
    return ProfileResponse(
        name=account.name,
        email=account.email,
        phone=account.phone,
        address=account.address,
    )


# ---------------------------------------------------------------------------
# PUT /account/profile
# ---------------------------------------------------------------------------
@router.put("/profile", response_model=ProfileResponse, summary="Update contact profile")
def update_profile(
    req: ProfileUpdateRequest,
    account: Account = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if req.email is not None:
        account.email = req.email
    if req.phone is not None:
        account.phone = req.phone
    if req.address is not None:
        account.address = req.address
    db.commit()
    db.refresh(account)
    return ProfileResponse(
        name=account.name,
        email=account.email,
        phone=account.phone,
        address=account.address,
    )


# ---------------------------------------------------------------------------
# POST /account/reset-password
# ---------------------------------------------------------------------------
@router.post("/reset-password", response_model=MessageResponse, summary="Change password")
def reset_password(
    req: ResetPasswordRequest,
    account: Account = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Verify old password
    if not verify_password(req.old_password, account.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")

    # Validate new password rules
    try:
        validate_password(req.new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Prevent reuse of old password
    if verify_password(req.new_password, account.password_hash):
        raise HTTPException(status_code=400, detail="New password must be different from the current password.")

    account.password_hash = hash_password(req.new_password)
    account.failed_login_count = 0   # reset lockout counter on password change
    db.commit()
    return MessageResponse(message="Password changed successfully.")


# ---------------------------------------------------------------------------
# POST /account/reset-pin
# ---------------------------------------------------------------------------
@router.post("/reset-pin", response_model=MessageResponse, summary="Change transaction PIN")
def reset_pin(
    req: ResetPinRequest,
    account: Account = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update 4-digit transaction PIN. Verifies old PIN with lockout defense."""
    _check_pin(account, req.old_pin, db)

    if req.old_pin == req.new_pin:
        raise HTTPException(status_code=400, detail="New PIN must be different from current PIN.")

    account.pin_hash = hash_pin(req.new_pin)
    account.pin_attempts = 0
    db.commit()
    return MessageResponse(message="Transaction PIN changed successfully.")


# ---------------------------------------------------------------------------
# PUT /account/username
# ---------------------------------------------------------------------------
@router.put("/username", response_model=MessageResponse, summary="Change username")
def update_username(
    req: UsernameUpdateRequest,
    account: Account = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Verify password before allowing username change
    if not verify_password(req.password, account.password_hash):
        raise HTTPException(status_code=401, detail="Password is incorrect.")

    # Check if new name is already taken
    if db.query(Account).filter(Account.name == req.new_name).first():
        raise HTTPException(status_code=400, detail=f"Username '{req.new_name}' is already taken.")

    account.name = req.new_name
    db.commit()
    return MessageResponse(message=f"Username changed to '{req.new_name}' successfully.")


# ---------------------------------------------------------------------------
# DELETE /account
# ---------------------------------------------------------------------------
@router.delete("/", response_model=MessageResponse, summary="Soft-delete account")
def delete_account(
    req: DeleteAccountRequest,
    account: Account = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Soft-delete the account. Requires password + PIN + the literal string 'DELETE'.
    Sets active=False; account data is preserved in DB.
    """
    # Verify password
    if not verify_password(req.password, account.password_hash):
        raise HTTPException(status_code=401, detail="Password is incorrect.")

    # Verify PIN (uses lockout logic)
    _check_pin(account, req.pin, db)

    account.active = False
    db.commit()
    return MessageResponse(message="Account deactivated successfully. Contact support to reactivate.")


# ---------------------------------------------------------------------------
# GET /account/balance
# ---------------------------------------------------------------------------
@router.get("/balance", response_model=BalanceResponse, summary="Get current balance")
def get_balance(account: Account = Depends(get_current_user)):
    return BalanceResponse(
        account_number=account.account_number,
        balance_rupees=paise_to_rupees(account.balance),
        balance_paise=account.balance,
    )


# ---------------------------------------------------------------------------
# POST /account/interest
# ---------------------------------------------------------------------------
@router.post("/interest", response_model=MessageResponse, summary="Apply interest to balance")
def apply_interest(
    req: InterestRequest,
    account: Account = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Apply an interest rate (0.01%–15%) to the current balance.
    Interest amount is rounded to nearest paisa (integer).
    PIN required.
    """
    # Verify PIN
    _check_pin(account, req.pin, db)

    if account.balance == 0:
        raise HTTPException(status_code=400, detail="Balance is zero; no interest to apply.")

    # Calculate interest in paise (integer arithmetic)
    # interest = balance * rate / 100 — rounded to nearest paisa
    interest_paise = round(account.balance * req.rate / 100)
    if interest_paise <= 0:
        raise HTTPException(status_code=400, detail="Calculated interest rounds to zero paise. Use a higher rate.")

    account.balance += interest_paise
    txn_id = _next_txn_id(db)
    _log_txn(
        db, account.account_number, txn_id,
        "INTEREST", interest_paise, account.balance, "SUCCESS",
        remark=f"Interest @ {req.rate}% = {paise_to_rupees(interest_paise)}",
    )
    db.commit()

    return MessageResponse(
        message=(
            f"Interest applied: {paise_to_rupees(interest_paise)} at {req.rate}%. "
            f"New balance: {paise_to_rupees(account.balance)}"
        )
    )


# ---------------------------------------------------------------------------
# GET /account/statement
# ---------------------------------------------------------------------------
@router.get("/statement", summary="Download account statement PDF")
def get_statement(
    from_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    account: Account = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate and download an account statement PDF.
    Optional query params: from_date, to_date (YYYY-MM-DD).
    """
    query = db.query(Transaction).filter(
        Transaction.account_number == account.account_number,
        Transaction.status == "SUCCESS",
    )

    if from_date:
        query = query.filter(Transaction.timestamp >= from_date)
    if to_date:
        # Include entire to_date day
        query = query.filter(Transaction.timestamp <= to_date + "T23:59:59")

    transactions = query.order_by(Transaction.timestamp).all()

    filepath = generate_statement_pdf(
        account_number=account.account_number,
        holder_name=account.name,
        email=account.email,
        transactions=transactions,
        from_date=from_date,
        to_date=to_date,
        current_balance_paise=account.balance,
    )

    return FileResponse(
        path=filepath,
        media_type="application/pdf",
        filename=f"statement_{account.account_number}.pdf",
    )

