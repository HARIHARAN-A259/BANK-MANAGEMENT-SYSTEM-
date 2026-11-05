"""
tests/conftest.py — pytest fixtures for Cashio Security
Uses an in-memory SQLite database with StaticPool so all connections and threads
share the exact same database.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import Account, Transaction, Admin, Meta
from app.security import hash_password, hash_pin, create_access_token

# ---------------------------------------------------------------------------
# In-memory SQLite engine for tests with StaticPool
# ---------------------------------------------------------------------------
TEST_DB_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function", autouse=True)
def setup_test_db():
    """Create all tables before each test, seed data, and drop after."""
    Base.metadata.create_all(bind=test_engine)
    db = TestSessionLocal()
    try:
        # Seed meta counters
        db.add(Meta(key="next_txn_counter", value="1"))
        db.add(Meta(key="next_account_counter", value="10000001"))
        # Seed admin account
        db.add(Admin(id=1, password_hash=hash_password("Admin@1234")))
        db.commit()
    finally:
        db.close()

    yield

    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    """Yield a test DB session."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    """
    FastAPI TestClient with the real app pointing to the in-memory SQLite DB.
    Overrides get_db.
    """
    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helper: create a test account directly in the DB
# ---------------------------------------------------------------------------
def make_account(
    db,
    name="testuser",
    password="Test@1234",
    pin="1234",
    balance=100_000,      # ₹1,000 in paise
    account_number="10000001",
) -> Account:
    acc = Account(
        account_number=account_number,
        name=name,
        password_hash=hash_password(password),
        pin_hash=hash_pin(pin),
        balance=balance,
        active=True,
        locked=False,
        pin_locked=False,
        failed_login_count=0,
        pin_attempts=0,
        card_status="NONE",
        withdraw_limit=5_000_000,
        transfer_limit=10_000_000,
        daily_withdraw_limit=2_000_000,
        today_withdrawn=0,
    )
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc


def get_token(account_number: str) -> str:
    """Generate a valid JWT for a test account."""
    return create_access_token({"sub": account_number, "type": "user"})


def get_admin_token() -> str:
    """Generate a valid admin JWT."""
    return create_access_token({"sub": "admin", "type": "admin"})
