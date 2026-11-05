"""
models.py — SQLAlchemy ORM models for Cashio Security
All money columns are INTEGER (paise). Never use Float for money.
"""

from datetime import datetime
from sqlalchemy import (
    Boolean, Column, Integer, String, Text, DateTime
)
from app.db import Base


# ---------------------------------------------------------------------------
# Account model
# ---------------------------------------------------------------------------
class Account(Base):
    __tablename__ = "accounts"

    # Primary key
    account_number = Column(String(8), primary_key=True, index=True)

    # Identity
    name = Column(String(50), unique=True, nullable=False, index=True)   # lowercase username
    email = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)

    # Security
    password_hash = Column(Text, nullable=False)
    pin_hash = Column(Text, nullable=False)
    locked = Column(Boolean, default=False, nullable=False)              # locked after 3 wrong passwords
    pin_locked = Column(Boolean, default=False, nullable=False)          # locked after 3 wrong PINs
    failed_login_count = Column(Integer, default=0, nullable=False)
    pin_attempts = Column(Integer, default=0, nullable=False)

    # Balance (integer paise; ₹1 = 100 paise)
    balance = Column(Integer, default=0, nullable=False)

    # Withdraw & transfer limits (integer paise)
    withdraw_limit = Column(Integer, default=5_000_000, nullable=False)   # ₹50,000
    transfer_limit = Column(Integer, default=10_000_000, nullable=False)  # ₹1,00,000
    daily_withdraw_limit = Column(Integer, default=2_000_000, nullable=False)  # ₹20,000

    # Daily withdraw tracking
    today_withdrawn = Column(Integer, default=0, nullable=False)
    last_withdraw_date = Column(String(10), nullable=True)               # ISO date YYYY-MM-DD

    # Timestamps
    last_login = Column(String(30), nullable=True)                       # ISO datetime string
    created_at = Column(String(30), default=lambda: datetime.utcnow().isoformat())

    # Soft delete
    active = Column(Boolean, default=True, nullable=False)

    # ATM card
    card_number = Column(String(16), nullable=True)                      # 16-digit plain (masked on output)
    card_expiry = Column(String(5), nullable=True)                       # MM/YY
    card_cvv_hash = Column(Text, nullable=True)                          # bcrypt hash; CVV never stored plain
    card_status = Column(String(10), default="NONE", nullable=False)     # NONE / ACTIVE / BLOCKED


# ---------------------------------------------------------------------------
# Transaction model
# ---------------------------------------------------------------------------
class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Shared between TRANSFER_OUT + TRANSFER_IN pair
    txn_id = Column(String(12), nullable=False, index=True)              # e.g. TXN-00001

    account_number = Column(String(8), nullable=False, index=True)

    type = Column(String(20), nullable=False)
    # DEPOSIT | WITHDRAW | TRANSFER_IN | TRANSFER_OUT
    # INTEREST | CARD_ISSUE | CARD_BLOCK | CARD_UNBLOCK | CARD_DOWNLOAD | SECURITY

    amount = Column(Integer, nullable=False)                             # paise
    balance_after = Column(Integer, nullable=False)                      # paise
    timestamp = Column(String(30), default=lambda: datetime.utcnow().isoformat())
    status = Column(String(10), nullable=False)                          # SUCCESS | FAILED
    remark = Column(Text, nullable=True)


# ---------------------------------------------------------------------------
# Admin model (single row, id=1)
# ---------------------------------------------------------------------------
class Admin(Base):
    __tablename__ = "admin"

    id = Column(Integer, primary_key=True, default=1)
    password_hash = Column(Text, nullable=False)


# ---------------------------------------------------------------------------
# Meta model — persistent key/value store
# Keys used:
#   next_txn_counter      → integer, starts at 1, used for TXN-XXXXX
#   next_account_counter  → integer, used for 8-digit account numbers
# ---------------------------------------------------------------------------
class Meta(Base):
    __tablename__ = "meta"

    key = Column(String(50), primary_key=True)
    value = Column(Text, nullable=False)

