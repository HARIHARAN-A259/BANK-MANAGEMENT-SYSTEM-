"""
security.py — Password hashing, PIN hashing, password rules, JWT, Luhn
Cashio Security Bank Management System

NEVER log passwords, PINs, or full card numbers.
"""

import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt

# ---------------------------------------------------------------------------
# JWT configuration — read secret from env or fall back to a dev-only default
# ---------------------------------------------------------------------------
JWT_SECRET = os.environ.get("JWT_SECRET", "cashio-dev-secret-change-in-prod-!@#XYZ")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60          # 1 hour session


# ===========================================================================
# Password utilities
# ===========================================================================

def _password_meets_rules(password: str) -> tuple[bool, str]:
    """
    Returns (True, "") if the password satisfies all rules, else (False, reason).
    Rules: 8+ chars, at least one uppercase, one lowercase, one digit, one special char.
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit"
    if not re.search(r"[^A-Za-z0-9]", password):
        return False, "Password must contain at least one special character (!@#$%^&* etc.)"
    return True, ""


def validate_password(password: str) -> None:
    """Raise ValueError if the password does not meet complexity rules."""
    ok, reason = _password_meets_rules(password)
    if not ok:
        raise ValueError(reason)


def hash_password(password: str) -> str:
    """Hash a password with bcrypt (auto-salted). Returns the hash string."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain password matches the bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ===========================================================================
# PIN utilities
# ===========================================================================

def hash_pin(pin: str) -> str:
    """Hash a 4-digit PIN with bcrypt. Returns hash string."""
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()


def verify_pin(plain_pin: str, hashed_pin: str) -> bool:
    """Return True if plain PIN matches the bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_pin.encode(), hashed_pin.encode())
    except Exception:
        return False


# ===========================================================================
# CVV utility
# ===========================================================================

def generate_cvv() -> str:
    """Generate a random 3-digit CVV string."""
    return f"{secrets.randbelow(1000):03d}"


def hash_cvv(cvv: str) -> str:
    """Hash CVV with bcrypt."""
    return bcrypt.hashpw(cvv.encode(), bcrypt.gensalt()).decode()


def verify_cvv(plain_cvv: str, hashed_cvv: str) -> bool:
    """Return True if plain CVV matches hash."""
    try:
        return bcrypt.checkpw(plain_cvv.encode(), hashed_cvv.encode())
    except Exception:
        return False


# ===========================================================================
# JWT utilities
# ===========================================================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT. Payload is copied then expiry added."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT. Returns payload dict or None on failure."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None


# ===========================================================================
# Card utilities — Luhn algorithm
# ===========================================================================

CASHIO_BIN = "453200"   # 6-digit BIN prefix for Cashio Security cards

def _luhn_checksum(partial_15: str) -> int:
    """
    Compute Luhn check digit for a 15-digit number string.
    When appended, the resulting 16-digit number satisfies sum % 10 == 0.
    """
    digits = [int(d) for d in partial_15]
    total = 0
    for i, digit in enumerate(reversed(digits)):
        # In the final 16-digit card, position 0 (check digit) is not doubled.
        # Position 1 (first digit of reversed partial) IS doubled.
        if i % 2 == 0:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return (10 - (total % 10)) % 10


def generate_luhn_card_number() -> str:
    """
    Generate a 16-digit card number:
    - First 6 digits: Cashio Security BIN (453200)
    - Next 9 digits: random
    - Last digit: Luhn check digit
    """
    partial = CASHIO_BIN + "".join(str(secrets.randbelow(10)) for _ in range(9))
    check = _luhn_checksum(partial)
    return partial + str(check)


def luhn_valid(number: str) -> bool:
    """
    Return True if the full 16-digit card number passes Luhn check (ISO/IEC 7812).
    """
    if not number.isdigit() or len(number) != 16:
        return False
    digits = [int(d) for d in number]
    total = 0
    for i, digit in enumerate(reversed(digits)):
        if i % 2 == 1:   # double alternate digits from right
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def mask_card(card_number: str) -> str:
    """Return masked card string: '**** **** **** 4321'"""
    if not card_number or len(card_number) != 16:
        return "****************"
    last4 = card_number[-4:]
    return f"**** **** **** {last4}"


def card_number_in_groups(card_number: str) -> str:
    """Return card number formatted as '4532 0012 3456 7890'"""
    return " ".join(card_number[i:i+4] for i in range(0, 16, 4))


# ===========================================================================
# Account number generation
# ===========================================================================

def generate_account_number(counter: int) -> str:
    """
    Generate a unique 8-digit account number from an auto-incrementing counter.
    counter starts at 10000001 (8 digits guaranteed).
    """
    return str(counter).zfill(8)[:8]


# ===========================================================================
# Transaction ID generation
# ===========================================================================

def format_txn_id(counter: int) -> str:
    """Format TXN-00001 style from integer counter."""
    return f"TXN-{counter:05d}"

