"""
routers/auth.py — Authentication endpoints for Cashio Security
  POST /auth/register
  POST /auth/login
  POST /auth/logout
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app.models import Account, Meta
from app.schemas import (
    RegisterRequest, RegisterResponse,
    LoginRequest, LoginResponse,
    MessageResponse,
)
from app.security import (
    validate_password, hash_password, verify_password,
    hash_pin,
    create_access_token,
    generate_account_number,
)
from app.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

MAX_LOGIN_ATTEMPTS = 3


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------
@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new bank account",
)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """
    Create a new Cashio Security bank account.
    - name must be 3–30 lowercase letters
    - password must be 8+ chars with upper, lower, digit and special char
    - pin must be exactly 4 digits
    Returns the new 8-digit account number.
    """
    # Validate password complexity
    try:
        validate_password(req.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Ensure username is not already taken (case-insensitive)
    if db.query(Account).filter(func.lower(Account.name) == func.lower(req.name.strip())).first():
        raise HTTPException(
            status_code=400,
            detail=f"Username '{req.name}' is already taken. Choose a different name.",
        )

    # Generate unique account number from meta counter
    meta = db.query(Meta).filter(Meta.key == "next_account_counter").first()
    counter = int(meta.value)
    account_number = generate_account_number(counter)
    meta.value = str(counter + 1)

    # Create account
    new_account = Account(
        account_number=account_number,
        name=req.name,
        password_hash=hash_password(req.password),
        pin_hash=hash_pin(req.pin),
        email=req.email,
        phone=req.phone,
        address=req.address,
        balance=0,
        active=True,
        locked=False,
        pin_locked=False,
        failed_login_count=0,
        pin_attempts=0,
        card_status="NONE",
    )
    db.add(new_account)
    db.commit()
    db.refresh(new_account)

    return RegisterResponse(
        message="Account created successfully. Welcome to Cashio Security!",
        account_number=account_number,
        name=req.name,
    )


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------
@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Login and receive a JWT token",
)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate with username and password.
    - 3 consecutive wrong passwords → account locked (persisted in DB)
    - Returns JWT access token valid for 60 minutes
    - Returns last login timestamp
    """
    account = db.query(Account).filter(func.lower(Account.name) == func.lower(req.name.strip())).first()

    # Generic error (do not reveal whether user exists)
    auth_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid username or password.",
    )

    if account is None:
        raise auth_error

    # Check if soft-deleted
    if not account.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated.",
        )

    # Check if already locked
    if account.locked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Account is locked due to too many failed login attempts. "
                "Please contact admin to unlock."
            ),
        )

    # Verify password
    if not verify_password(req.password, account.password_hash):
        account.failed_login_count += 1
        if account.failed_login_count >= MAX_LOGIN_ATTEMPTS:
            account.locked = True
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Account locked after {MAX_LOGIN_ATTEMPTS} failed attempts. "
                    "Contact admin to unlock."
                ),
            )
        db.commit()
        remaining = MAX_LOGIN_ATTEMPTS - account.failed_login_count
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid password. {remaining} attempt(s) remaining before lockout.",
        )

    # Successful login — reset counter, update last_login
    prev_login = account.last_login
    account.failed_login_count = 0
    account.last_login = datetime.now(timezone.utc).isoformat()
    db.commit()

    # Issue JWT
    token = create_access_token({"sub": account.account_number, "type": "user"})

    return LoginResponse(
        message="Login successful. Welcome to Cashio Security!",
        access_token=token,
        token_type="bearer",
        account_number=account.account_number,
        name=account.name,
        last_login=prev_login,
    )


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------
@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout (client should discard token)",
)
def logout(_: Account = Depends(get_current_user)):
    """
    Logout endpoint. JWT is stateless — the client must discard the token.
    Returns a confirmation message.
    """
    return MessageResponse(message="Logged out successfully. Have a great day!")

