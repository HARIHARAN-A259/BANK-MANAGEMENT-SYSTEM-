"""
dependencies.py — FastAPI Depends helpers for Cashio Security
Provides: get_current_user, get_current_admin
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Account, Admin
from app.security import decode_access_token

# ---------------------------------------------------------------------------
# OAuth2 token locations — FastAPI reads Bearer token from Authorization header
# ---------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
admin_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/login")


# ---------------------------------------------------------------------------
# get_current_user — dependency for all protected user endpoints
# ---------------------------------------------------------------------------
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Account:
    """
    Decode the JWT and return the Account object.
    Raises 401 if token is invalid/expired.
    Raises 403 if the account is locked or inactive.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    account_number: str = payload.get("sub")
    token_type: str = payload.get("type", "user")

    if account_number is None or token_type != "user":
        raise credentials_exception

    account = db.query(Account).filter(
        Account.account_number == account_number
    ).first()

    if account is None:
        raise credentials_exception

    # Soft-deleted accounts cannot access the API
    if not account.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated. Contact support.",
        )

    # Locked accounts cannot access the API (they must contact admin)
    if account.locked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is locked due to too many failed login attempts. Contact admin.",
        )

    return account


# ---------------------------------------------------------------------------
# get_current_admin — dependency for all /admin/* endpoints
# ---------------------------------------------------------------------------
def get_current_admin(
    token: str = Depends(admin_oauth2_scheme),
    db: Session = Depends(get_db),
) -> Admin:
    """
    Decode the JWT and confirm it is an admin token.
    Raises 401 if token is invalid/expired or not an admin token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired admin token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    token_type: str = payload.get("type", "user")
    if token_type != "admin":
        raise credentials_exception

    admin = db.query(Admin).filter(Admin.id == 1).first()
    if admin is None:
        raise credentials_exception

    return admin

