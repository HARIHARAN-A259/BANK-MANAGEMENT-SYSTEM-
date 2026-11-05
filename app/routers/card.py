"""
routers/card.py — ATM card endpoints for Cashio Security
  POST /card/issue
  POST /card/download
  POST /card/block
  POST /card/unblock
"""

import os
from datetime import datetime, timezone, date
from dateutil.relativedelta import relativedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_current_user
from app.models import Account, Transaction, Meta
from app.schemas import (
    CardIssueRequest, CardIssueResponse,
    CardActionRequest, MessageResponse,
    paise_to_rupees,
)
from app.security import (
    generate_luhn_card_number, luhn_valid,
    generate_cvv, hash_cvv, verify_cvv,
    verify_pin, format_txn_id,
    mask_card, card_number_in_groups,
)
from app.pdf_utils import generate_card_pdf

router = APIRouter(prefix="/card", tags=["ATM Card"])

MAX_PIN_ATTEMPTS = 3


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _next_txn_id(db: Session) -> str:
    meta = db.query(Meta).filter(Meta.key == "next_txn_counter").with_for_update().first()
    counter = int(meta.value)
    meta.value = str(counter + 1)
    return format_txn_id(counter)


def _log_txn(db, account_number, txn_id, txn_type, balance, remark=""):
    txn = Transaction(
        txn_id=txn_id,
        account_number=account_number,
        type=txn_type,
        amount=0,                   # Card events have no monetary amount
        balance_after=balance,
        timestamp=datetime.now(timezone.utc).isoformat(),
        status="SUCCESS",
        remark=remark,
    )
    db.add(txn)


def _check_pin(account: Account, pin: str, db: Session) -> None:
    if account.pin_locked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PIN is locked. Contact admin to unlock.",
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
            detail=f"Wrong PIN. {remaining} attempt(s) remaining.",
        )
    account.pin_attempts = 0


def _card_expiry_str() -> str:
    """Return expiry date 5 years from today in MM/YY format."""
    exp = date.today().replace(year=date.today().year + 5)
    return exp.strftime("%m/%y")


# ---------------------------------------------------------------------------
# POST /card/issue
# ---------------------------------------------------------------------------
@router.post("/issue", response_model=CardIssueResponse, summary="Issue a new ATM debit card")
def issue_card(
    req: CardIssueRequest,
    account: Account = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Issue a Cashio Security debit card.
    - Only one active card per account
    - 16-digit Luhn-valid number with Cashio Security BIN prefix
    - Expiry: 5 years from today (MM/YY)
    - CVV: 3 digits, stored as bcrypt hash, returned ONCE here
    - PIN required
    """
    # Verify PIN
    _check_pin(account, req.pin, db)
    db.commit()  # commit pin_attempts reset

    # Only one active card at a time
    if account.card_status == "ACTIVE":
        raise HTTPException(
            status_code=400,
            detail=(
                f"An active card is already issued for this account "
                f"(masked: {mask_card(account.card_number)}). "
                "Block it before issuing a new one."
            ),
        )

    # Generate card details
    card_number = generate_luhn_card_number()
    expiry = _card_expiry_str()
    cvv = generate_cvv()
    cvv_hash = hash_cvv(cvv)
    holder_name = account.name.upper()

    # Save to account
    account.card_number = card_number
    account.card_expiry = expiry
    account.card_cvv_hash = cvv_hash
    account.card_status = "ACTIVE"

    # Log card issue event
    txn_id = _next_txn_id(db)
    _log_txn(db, account.account_number, txn_id, "CARD_ISSUE", account.balance,
             remark=f"Card issued. Masked: {mask_card(card_number)}")
    db.commit()

    return CardIssueResponse(
        message="Debit card issued successfully. Save your CVV — it will not be shown again.",
        card_masked=mask_card(card_number),
        card_expiry=expiry,
        cvv=cvv,          # Returned ONCE; CVV is never stored in plain text
        holder_name=holder_name,
    )


# ---------------------------------------------------------------------------
# POST /card/download
# ---------------------------------------------------------------------------
@router.post("/download", summary="Download ATM card PDF (PIN required)")
def download_card(
    req: CardActionRequest,
    account: Account = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Download an ATM card PDF showing full card number (front + back).
    - PIN required
    - Blocked cards are refused
    - Logs CARD_DOWNLOAD in transactions
    """
    if account.card_status == "NONE":
        raise HTTPException(status_code=400, detail="No card has been issued for this account.")

    if account.card_status == "BLOCKED":
        raise HTTPException(
            status_code=403,
            detail="Card is blocked. Unblock the card before downloading.",
        )

    # Verify PIN
    _check_pin(account, req.pin, db)
    db.commit()  # commit pin_attempts reset

    # Generate PDF with FULL card number (owner only, PIN verified above)
    filepath = generate_card_pdf(
        account_number=account.account_number,
        card_number=account.card_number,          # Full 16-digit (shown in PDF only)
        card_expiry=account.card_expiry,
        holder_name=account.name.upper(),
        cvv="***",    # CVV is NOT shown in the PDF — it was shown once at issue
    )

    # Log card download
    txn_id = _next_txn_id(db)
    _log_txn(db, account.account_number, txn_id, "CARD_DOWNLOAD", account.balance,
             remark=f"Card PDF downloaded. Masked: {mask_card(account.card_number)}")
    db.commit()

    return FileResponse(
        path=filepath,
        media_type="application/pdf",
        filename=f"cashio_card_{account.account_number}.pdf",
    )


# ---------------------------------------------------------------------------
# POST /card/block
# ---------------------------------------------------------------------------
@router.post("/block", response_model=MessageResponse, summary="Block the active card")
def block_card(
    req: CardActionRequest,
    account: Account = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Block an active ATM card. PIN required."""
    if account.card_status == "NONE":
        raise HTTPException(status_code=400, detail="No card has been issued for this account.")

    if account.card_status == "BLOCKED":
        raise HTTPException(status_code=400, detail="Card is already blocked.")

    # Verify PIN
    _check_pin(account, req.pin, db)

    account.card_status = "BLOCKED"

    txn_id = _next_txn_id(db)
    _log_txn(db, account.account_number, txn_id, "CARD_BLOCK", account.balance,
             remark=f"Card blocked. Masked: {mask_card(account.card_number)}")
    db.commit()

    return MessageResponse(
        message=f"Card {mask_card(account.card_number)} has been blocked. Contact support or unblock online."
    )


# ---------------------------------------------------------------------------
# POST /card/unblock
# ---------------------------------------------------------------------------
@router.post("/unblock", response_model=MessageResponse, summary="Unblock a blocked card")
def unblock_card(
    req: CardActionRequest,
    account: Account = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Unblock a blocked ATM card. PIN required."""
    if account.card_status == "NONE":
        raise HTTPException(status_code=400, detail="No card has been issued for this account.")

    if account.card_status == "ACTIVE":
        raise HTTPException(status_code=400, detail="Card is already active.")

    # Verify PIN
    _check_pin(account, req.pin, db)

    account.card_status = "ACTIVE"

    txn_id = _next_txn_id(db)
    _log_txn(db, account.account_number, txn_id, "CARD_UNBLOCK", account.balance,
             remark=f"Card unblocked. Masked: {mask_card(account.card_number)}")
    db.commit()

    return MessageResponse(
        message=f"Card {mask_card(account.card_number)} has been unblocked and is now active."
    )

