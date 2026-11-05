"""
routers/transactions.py — Money movement endpoints for Cashio Security
  POST /transactions/deposit
  POST /transactions/withdraw
  POST /transactions/transfer
  GET  /transactions
  GET  /transactions/mini
  GET  /transactions/{txn_id}
  GET  /transactions/counts
  GET  /transactions/failed
  GET  /transactions/{txn_id}/receipt
"""

from datetime import datetime, timezone, date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.db import get_db
from app.dependencies import get_current_user
from app.models import Account, Transaction, Meta
from app.schemas import (
    DepositRequest, WithdrawRequest, TransferRequest,
    TransactionOut, TransactionCountsResponse, MessageResponse,
    paise_to_rupees, rupees_to_paise,
)
from app.security import verify_pin, format_txn_id
from app.pdf_utils import generate_receipt_pdf

router = APIRouter(prefix="/transactions", tags=["Transactions"])

MAX_PIN_ATTEMPTS = 3


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _next_txn_id(db: Session) -> str:
    """Atomically increment and return the next TXN-XXXXX string."""
    meta = db.query(Meta).filter(Meta.key == "next_txn_counter").with_for_update().first()
    counter = int(meta.value)
    meta.value = str(counter + 1)
    return format_txn_id(counter)


def _log_txn(
    db: Session,
    account_number: str,
    txn_id: str,
    txn_type: str,
    amount_paise: int,
    balance_after_paise: int,
    txn_status: str,
    remark: str = "",
) -> Transaction:
    txn = Transaction(
        txn_id=txn_id,
        account_number=account_number,
        type=txn_type,
        amount=amount_paise,
        balance_after=balance_after_paise,
        timestamp=datetime.now(timezone.utc).isoformat(),
        status=txn_status,
        remark=remark,
    )
    db.add(txn)
    return txn


def _check_pin(account: Account, pin: str, db: Session) -> None:
    """
    Verify PIN with lockout. Raises HTTPException on wrong PIN or locked PIN.
    Resets pin_attempts on success.
    """
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
                detail=f"Wrong PIN. PIN locked after {MAX_PIN_ATTEMPTS} failed attempts. Contact admin.",
            )
        db.commit()
        remaining = MAX_PIN_ATTEMPTS - account.pin_attempts
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Wrong PIN. {remaining} attempt(s) remaining.",
        )

    account.pin_attempts = 0
    # Note: db.commit() is called by the caller after the full transaction completes


def _reset_daily_withdraw_if_needed(account: Account) -> None:
    """Reset today_withdrawn if last_withdraw_date is not today."""
    today = date.today().isoformat()
    if account.last_withdraw_date != today:
        account.today_withdrawn = 0
        account.last_withdraw_date = today


def _txn_to_out(txn: Transaction) -> TransactionOut:
    return TransactionOut(
        txn_id=txn.txn_id,
        account_number=txn.account_number,
        type=txn.type,
        amount_rupees=paise_to_rupees(txn.amount),
        balance_after_rupees=paise_to_rupees(txn.balance_after),
        timestamp=txn.timestamp,
        status=txn.status,
        remark=txn.remark,
    )


# ---------------------------------------------------------------------------
# POST /transactions/deposit
# ---------------------------------------------------------------------------
@router.post("/deposit", response_model=MessageResponse, summary="Deposit money")
def deposit(
    req: DepositRequest,
    account: Account = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deposit money into the account. No PIN required. Amount in rupees."""
    amount_paise = rupees_to_paise(req.amount)
    txn_id = _next_txn_id(db)

    try:
        account.balance += amount_paise
        _log_txn(
            db, account.account_number, txn_id,
            "DEPOSIT", amount_paise, account.balance, "SUCCESS",
            remark=req.remark or f"Deposit of {paise_to_rupees(amount_paise)}",
        )
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        # Log the failed attempt
        _log_txn(
            db, account.account_number, txn_id,
            "DEPOSIT", amount_paise, account.balance, "FAILED",
            remark=f"Deposit failed: {str(e)[:100]}",
        )
        db.commit()
        raise HTTPException(status_code=500, detail="Deposit failed due to a database error.")

    return MessageResponse(
        message=f"Deposit successful. {paise_to_rupees(amount_paise)} credited. New balance: {paise_to_rupees(account.balance)}"
    )


# ---------------------------------------------------------------------------
# POST /transactions/withdraw
# ---------------------------------------------------------------------------
@router.post("/withdraw", response_model=MessageResponse, summary="Withdraw money (PIN required)")
def withdraw(
    req: WithdrawRequest,
    account: Account = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Withdraw money. PIN required.
    Enforces:
    - Per-transaction limit (withdraw_limit)
    - Daily withdrawal limit (daily_withdraw_limit)
    - Sufficient balance
    """
    amount_paise = rupees_to_paise(req.amount)
    txn_id = _next_txn_id(db)

    # Verify PIN first (logs nothing here — validation step)
    _check_pin(account, req.pin, db)

    # Reset daily limit if it's a new day
    _reset_daily_withdraw_if_needed(account)

    # Enforce per-transaction limit
    if amount_paise > account.withdraw_limit:
        _log_txn(
            db, account.account_number, txn_id,
            "WITHDRAW", amount_paise, account.balance, "FAILED",
            remark=f"Exceeds per-txn limit of {paise_to_rupees(account.withdraw_limit)}",
        )
        db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"Amount exceeds per-transaction withdraw limit of {paise_to_rupees(account.withdraw_limit)}.",
        )

    # Enforce daily limit
    if account.today_withdrawn + amount_paise > account.daily_withdraw_limit:
        already_withdrawn = account.today_withdrawn
        _log_txn(
            db, account.account_number, txn_id,
            "WITHDRAW", amount_paise, account.balance, "FAILED",
            remark=f"Daily limit exceeded. Already withdrawn: {paise_to_rupees(already_withdrawn)}",
        )
        db.commit()
        remaining = account.daily_withdraw_limit - account.today_withdrawn
        raise HTTPException(
            status_code=400,
            detail=(
                f"Daily withdrawal limit reached. "
                f"You can withdraw up to {paise_to_rupees(remaining)} more today."
            ),
        )

    # Enforce sufficient balance
    if amount_paise > account.balance:
        _log_txn(
            db, account.account_number, txn_id,
            "WITHDRAW", amount_paise, account.balance, "FAILED",
            remark="Insufficient balance",
        )
        db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient balance. Available: {paise_to_rupees(account.balance)}",
        )

    # Debit
    try:
        account.balance -= amount_paise
        account.today_withdrawn += amount_paise
        account.last_withdraw_date = date.today().isoformat()
        _log_txn(
            db, account.account_number, txn_id,
            "WITHDRAW", amount_paise, account.balance, "SUCCESS",
            remark=req.remark or f"Withdrawal of {paise_to_rupees(amount_paise)}",
        )
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        _log_txn(
            db, account.account_number, txn_id,
            "WITHDRAW", amount_paise, account.balance, "FAILED",
            remark=f"DB error: {str(e)[:100]}",
        )
        db.commit()
        raise HTTPException(status_code=500, detail="Withdrawal failed due to a database error.")

    return MessageResponse(
        message=f"Withdrawal successful. {paise_to_rupees(amount_paise)} debited. New balance: {paise_to_rupees(account.balance)}"
    )


# ---------------------------------------------------------------------------
# POST /transactions/transfer
# ---------------------------------------------------------------------------
@router.post("/transfer", response_model=MessageResponse, summary="Transfer to another account (PIN required)")
def transfer(
    req: TransferRequest,
    account: Account = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Transfer money to another account.
    - PIN required
    - No self-transfer
    - Receiver must exist and be active
    - Enforces per-transaction transfer limit
    - ATOMIC: single DB transaction with rollback on any failure
    - Creates TRANSFER_OUT (sender) + TRANSFER_IN (receiver) sharing same TXN ID
    """
    amount_paise = rupees_to_paise(req.amount)
    txn_id = _next_txn_id(db)

    # Verify PIN
    _check_pin(account, req.pin, db)

    # No self-transfer
    if req.to_account == account.account_number:
        raise HTTPException(status_code=400, detail="You cannot transfer money to your own account.")

    # Enforce transfer limit
    if amount_paise > account.transfer_limit:
        _log_txn(
            db, account.account_number, txn_id,
            "TRANSFER_OUT", amount_paise, account.balance, "FAILED",
            remark=f"Exceeds transfer limit of {paise_to_rupees(account.transfer_limit)}",
        )
        db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"Amount exceeds per-transaction transfer limit of {paise_to_rupees(account.transfer_limit)}.",
        )

    # Receiver must exist and be active
    receiver = db.query(Account).filter(
        Account.account_number == req.to_account
    ).with_for_update().first()   # Lock receiver row for the duration of this transaction

    if receiver is None or not receiver.active:
        _log_txn(
            db, account.account_number, txn_id,
            "TRANSFER_OUT", amount_paise, account.balance, "FAILED",
            remark=f"Receiver account {req.to_account} not found or inactive",
        )
        db.commit()
        raise HTTPException(
            status_code=404,
            detail=f"Destination account {req.to_account} does not exist or is inactive.",
        )

    # Sufficient balance
    if amount_paise > account.balance:
        _log_txn(
            db, account.account_number, txn_id,
            "TRANSFER_OUT", amount_paise, account.balance, "FAILED",
            remark="Insufficient balance for transfer",
        )
        db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient balance. Available: {paise_to_rupees(account.balance)}",
        )

    # === ATOMIC TRANSFER ===
    # Both debit and credit happen inside a single DB transaction.
    # If anything fails, everything is rolled back.
    try:
        # Lock sender row
        sender = db.query(Account).filter(
            Account.account_number == account.account_number
        ).with_for_update().first()

        # Debit sender
        sender.balance -= amount_paise
        remark_out = req.remark or f"Transfer to {req.to_account}"
        _log_txn(
            db, sender.account_number, txn_id,
            "TRANSFER_OUT", amount_paise, sender.balance, "SUCCESS",
            remark=remark_out,
        )

        # Credit receiver
        receiver.balance += amount_paise
        remark_in = f"Transfer from {sender.account_number}" + (f" | {req.remark}" if req.remark else "")
        _log_txn(
            db, receiver.account_number, txn_id,
            "TRANSFER_IN", amount_paise, receiver.balance, "SUCCESS",
            remark=remark_in,
        )

        db.commit()   # ← single commit; if this fails, everything above is rolled back
    except SQLAlchemyError as e:
        db.rollback()
        # Log the failure for the sender
        _log_txn(
            db, account.account_number, txn_id,
            "TRANSFER_OUT", amount_paise, account.balance, "FAILED",
            remark=f"Atomic transfer failed: {str(e)[:100]}",
        )
        db.commit()
        raise HTTPException(status_code=500, detail="Transfer failed. No money was moved.")

    return MessageResponse(
        message=(
            f"Transfer successful. {paise_to_rupees(amount_paise)} sent to account {req.to_account}. "
            f"Your new balance: {paise_to_rupees(sender.balance)}"
        )
    )


# ---------------------------------------------------------------------------
# GET /transactions  — full history
# ---------------------------------------------------------------------------
@router.get("", response_model=List[TransactionOut], summary="Full transaction history")
def get_all_transactions(
    account: Account = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    txns = (
        db.query(Transaction)
        .filter(Transaction.account_number == account.account_number)
        .order_by(Transaction.timestamp.desc())
        .all()
    )
    return [_txn_to_out(t) for t in txns]


# ---------------------------------------------------------------------------
# GET /transactions/mini  — last 5
# ---------------------------------------------------------------------------
@router.get("/mini", response_model=List[TransactionOut], summary="Last 5 transactions")
def get_mini_statement(
    account: Account = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    txns = (
        db.query(Transaction)
        .filter(Transaction.account_number == account.account_number)
        .order_by(Transaction.timestamp.desc())
        .limit(5)
        .all()
    )
    return [_txn_to_out(t) for t in txns]


# ---------------------------------------------------------------------------
# GET /transactions/counts
# ---------------------------------------------------------------------------
@router.get("/counts", response_model=TransactionCountsResponse, summary="Transaction counts by type")
def get_transaction_counts(
    account: Account = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from sqlalchemy import func
    rows = (
        db.query(Transaction.type, func.count(Transaction.id).label("cnt"))
        .filter(
            Transaction.account_number == account.account_number,
            Transaction.status == "SUCCESS",
        )
        .group_by(Transaction.type)
        .all()
    )
    counts = {r.type: r.cnt for r in rows}
    return TransactionCountsResponse(
        deposits=counts.get("DEPOSIT", 0),
        withdrawals=counts.get("WITHDRAW", 0),
        transfers_out=counts.get("TRANSFER_OUT", 0),
        transfers_in=counts.get("TRANSFER_IN", 0),
        interest=counts.get("INTEREST", 0),
        total=sum(counts.values()),
    )


# ---------------------------------------------------------------------------
# GET /transactions/failed
# ---------------------------------------------------------------------------
@router.get("/failed", response_model=List[TransactionOut], summary="Failed transactions")
def get_failed_transactions(
    account: Account = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    txns = (
        db.query(Transaction)
        .filter(
            Transaction.account_number == account.account_number,
            Transaction.status == "FAILED",
        )
        .order_by(Transaction.timestamp.desc())
        .all()
    )
    return [_txn_to_out(t) for t in txns]


# ---------------------------------------------------------------------------
# GET /transactions/{txn_id}
# (must be defined AFTER /mini, /counts, /failed to avoid path conflicts)
# ---------------------------------------------------------------------------
@router.get("/{txn_id}", response_model=List[TransactionOut], summary="Get transaction by ID")
def get_transaction_by_id(
    txn_id: str = Path(..., description="e.g. TXN-00001"),
    account: Account = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    txns = (
        db.query(Transaction)
        .filter(
            Transaction.txn_id == txn_id,
            Transaction.account_number == account.account_number,
        )
        .all()
    )
    if not txns:
        raise HTTPException(
            status_code=404,
            detail=f"Transaction {txn_id} not found for your account.",
        )
    return [_txn_to_out(t) for t in txns]


# ---------------------------------------------------------------------------
# GET /transactions/{txn_id}/receipt
# ---------------------------------------------------------------------------
@router.get("/{txn_id}/receipt", summary="Download receipt PDF for a transaction")
def get_receipt(
    txn_id: str = Path(..., description="e.g. TXN-00001"),
    account: Account = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate and return a PDF receipt for the given transaction."""
    # Find the transaction for this account
    txn = (
        db.query(Transaction)
        .filter(
            Transaction.txn_id == txn_id,
            Transaction.account_number == account.account_number,
        )
        .order_by(Transaction.id)
        .first()
    )
    if not txn:
        raise HTTPException(
            status_code=404,
            detail=f"Transaction {txn_id} not found for your account.",
        )

    # Determine to_account for transfers
    to_account = None
    if txn.type == "TRANSFER_OUT":
        # Extract from remark or find the partner leg
        partner = (
            db.query(Transaction)
            .filter(Transaction.txn_id == txn_id, Transaction.type == "TRANSFER_IN")
            .first()
        )
        if partner:
            to_account = partner.account_number

    filepath = generate_receipt_pdf(
        txn_id=txn.txn_id,
        account_number=txn.account_number,
        holder_name=account.name,
        txn_type=txn.type,
        amount_paise=txn.amount,
        balance_after_paise=txn.balance_after,
        timestamp=txn.timestamp,
        status=txn.status,
        remark=txn.remark,
        to_account=to_account,
    )

    return FileResponse(
        path=filepath,
        media_type="application/pdf",
        filename=f"receipt_{txn_id}.pdf",
    )

