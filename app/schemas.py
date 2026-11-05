"""
schemas.py — Pydantic request and response models for Cashio Security
All money values exposed to users are in RUPEES (float display only for readability).
All money stored internally is INTEGER PAISE.
"""

from typing import Optional, List
from pydantic import BaseModel, EmailStr, field_validator, model_validator
import re


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def paise_to_rupees(paise: int) -> str:
    """Convert integer paise to formatted rupee string e.g. '₹1,234.56'"""
    rupees = paise / 100
    return f"₹{rupees:,.2f}"

def rupees_to_paise(rupees: float) -> int:
    """Convert rupee float input to integer paise, rounding to nearest paisa."""
    return round(rupees * 100)


# ---------------------------------------------------------------------------
# Auth schemas
# ---------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    name: str
    password: str
    pin: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_must_be_letters_and_spaces(cls, v: str) -> str:
        cleaned = v.strip()
        if not re.fullmatch(r"[a-zA-Z ]{3,30}", cleaned) or len(cleaned) < 3:
            raise ValueError("Username must be 3–30 letters (both uppercase and lowercase letters and spaces are allowed)")
        return cleaned

    @field_validator("pin")
    @classmethod
    def pin_must_be_4_digits(cls, v: str) -> str:
        if not re.fullmatch(r"\d{4}", v):
            raise ValueError("PIN must be exactly 4 digits")
        return v


class RegisterResponse(BaseModel):
    message: str
    account_number: str
    name: str


class LoginRequest(BaseModel):
    name: str
    password: str


class LoginResponse(BaseModel):
    message: str
    access_token: str
    token_type: str = "bearer"
    account_number: str
    name: str
    last_login: Optional[str]


class AdminLoginRequest(BaseModel):
    username: Optional[str] = None
    password: str


class AdminRegisterRequest(BaseModel):
    username: str = "admin"
    password: str

    @field_validator("username")
    @classmethod
    def username_format(cls, v: str) -> str:
        cleaned = v.strip()
        if not re.fullmatch(r"[a-zA-Z0-9_]{3,30}", cleaned):
            raise ValueError("Admin username must be 3–30 alphanumeric characters")
        return cleaned


class AdminLoginResponse(BaseModel):
    message: str
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Account schemas
# ---------------------------------------------------------------------------
class AccountDetails(BaseModel):
    account_number: str
    name: str
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    balance_rupees: str
    locked: bool
    pin_locked: bool
    active: bool
    last_login: Optional[str]
    card_status: str
    card_masked: Optional[str]       # e.g. "**** **** **** 4321"
    card_expiry: Optional[str]
    withdraw_limit_rupees: str
    transfer_limit_rupees: str
    daily_withdraw_limit_rupees: str


class ProfileResponse(BaseModel):
    name: str
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]


class ProfileUpdateRequest(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def phone_format(cls, v):
        if v and not re.fullmatch(r"\d{10}", v):
            raise ValueError("Phone must be exactly 10 digits")
        return v


class ResetPasswordRequest(BaseModel):
    old_password: str
    new_password: str
    confirm_password: str

    @model_validator(mode="after")
    def passwords_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("new_password and confirm_password do not match")
        return self


class ResetPinRequest(BaseModel):
    old_pin: str
    new_pin: str
    confirm_pin: str

    @field_validator("old_pin", "new_pin", "confirm_pin")
    @classmethod
    def pin_must_be_4_digits(cls, v: str) -> str:
        if not re.fullmatch(r"\d{4}", v):
            raise ValueError("PIN must be exactly 4 digits")
        return v

    @model_validator(mode="after")
    def pins_match(self):
        if self.new_pin != self.confirm_pin:
            raise ValueError("new_pin and confirm_pin do not match")
        return self


class UsernameUpdateRequest(BaseModel):
    new_name: str
    password: str

    @field_validator("new_name")
    @classmethod
    def name_format(cls, v: str) -> str:
        cleaned = v.strip()
        if not re.fullmatch(r"[a-zA-Z ]{3,30}", cleaned) or len(cleaned) < 3:
            raise ValueError("Username must be 3–30 letters (both uppercase and lowercase letters and spaces are allowed)")
        return cleaned


class DeleteAccountRequest(BaseModel):
    password: str
    pin: str
    confirm: str                     # Must equal the string "DELETE"

    @field_validator("confirm")
    @classmethod
    def confirm_delete(cls, v: str) -> str:
        if v != "DELETE":
            raise ValueError('confirm field must be exactly the text "DELETE"')
        return v


class BalanceResponse(BaseModel):
    account_number: str
    balance_rupees: str
    balance_paise: int


# ---------------------------------------------------------------------------
# Transaction schemas
# ---------------------------------------------------------------------------
class DepositRequest(BaseModel):
    amount: float                    # Input in rupees; we convert to paise server-side
    remark: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Amount must be greater than 0")
        if v > 1_000_000:
            raise ValueError("Single deposit cannot exceed ₹10,00,000")
        # Validate no more than 2 decimal places
        if round(v, 2) != v:
            raise ValueError("Amount can have at most 2 decimal places")
        return v


class WithdrawRequest(BaseModel):
    amount: float
    pin: str
    remark: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Amount must be greater than 0")
        if round(v, 2) != v:
            raise ValueError("Amount can have at most 2 decimal places")
        return v

    @field_validator("pin")
    @classmethod
    def pin_format(cls, v: str) -> str:
        if not re.fullmatch(r"\d{4}", v):
            raise ValueError("PIN must be exactly 4 digits")
        return v


class TransferRequest(BaseModel):
    to_account: str
    amount: float
    pin: str
    remark: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Amount must be greater than 0")
        if round(v, 2) != v:
            raise ValueError("Amount can have at most 2 decimal places")
        return v

    @field_validator("pin")
    @classmethod
    def pin_format(cls, v: str) -> str:
        if not re.fullmatch(r"\d{4}", v):
            raise ValueError("PIN must be exactly 4 digits")
        return v

    @field_validator("to_account")
    @classmethod
    def to_account_format(cls, v: str) -> str:
        if not re.fullmatch(r"\d{8}", v):
            raise ValueError("to_account must be an 8-digit account number")
        return v


class InterestRequest(BaseModel):
    rate: float                      # percentage, e.g. 5.0 means 5%
    pin: str
    remark: Optional[str] = None

    @field_validator("rate")
    @classmethod
    def rate_in_range(cls, v: float) -> float:
        if not (0.01 <= v <= 15.0):
            raise ValueError("Interest rate must be between 0.01% and 15%")
        return v

    @field_validator("pin")
    @classmethod
    def pin_format(cls, v: str) -> str:
        if not re.fullmatch(r"\d{4}", v):
            raise ValueError("PIN must be exactly 4 digits")
        return v


class TransactionOut(BaseModel):
    txn_id: str
    account_number: str
    type: str
    amount_rupees: str
    balance_after_rupees: str
    timestamp: str
    status: str
    remark: Optional[str]

    model_config = {"from_attributes": True}


class TransactionCountsResponse(BaseModel):
    deposits: int
    withdrawals: int
    transfers_out: int
    transfers_in: int
    interest: int
    total: int


# ---------------------------------------------------------------------------
# Card schemas
# ---------------------------------------------------------------------------
class CardIssueRequest(BaseModel):
    pin: str

    @field_validator("pin")
    @classmethod
    def pin_format(cls, v: str) -> str:
        if not re.fullmatch(r"\d{4}", v):
            raise ValueError("PIN must be exactly 4 digits")
        return v


class CardIssueResponse(BaseModel):
    message: str
    card_masked: str                 # "**** **** **** 4321"
    card_expiry: str                 # "MM/YY"
    cvv: str                         # Returned ONCE; not stored plain
    holder_name: str


class CardActionRequest(BaseModel):
    pin: str

    @field_validator("pin")
    @classmethod
    def pin_format(cls, v: str) -> str:
        if not re.fullmatch(r"\d{4}", v):
            raise ValueError("PIN must be exactly 4 digits")
        return v


# ---------------------------------------------------------------------------
# Admin schemas
# ---------------------------------------------------------------------------
class AdminAccountOut(BaseModel):
    account_number: str
    name: str
    email: Optional[str]
    phone: Optional[str]
    balance_rupees: str
    locked: bool
    pin_locked: bool
    active: bool
    card_status: str
    last_login: Optional[str]

    model_config = {"from_attributes": True}


class TotalDepositsResponse(BaseModel):
    total_deposits_rupees: str
    total_deposits_paise: int
    count: int


# ---------------------------------------------------------------------------
# Generic response
# ---------------------------------------------------------------------------
class MessageResponse(BaseModel):
    message: str

