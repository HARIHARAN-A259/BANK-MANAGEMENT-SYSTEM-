"""
db.py — Database engine, session factory, and initialisation
Cashio Security Bank Management System
"""

import os
import shutil
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# ---------------------------------------------------------------------------
# Database file path (relative to project root)
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "cashio.db")
DB_BAK_PATH = os.path.join(BASE_DIR, "cashio.db.bak")
DB_URL = f"sqlite:///{DB_PATH}"

# ---------------------------------------------------------------------------
# Engine — check_same_thread=False is required for FastAPI (multiple threads)
# ---------------------------------------------------------------------------
engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False},
    # Echo SQL to stdout in dev; set to False in production
    echo=False,
)

# Enable SQLite WAL mode for better concurrency (readers don't block writers)
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ---------------------------------------------------------------------------
# Declarative base — all ORM models inherit from this
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Dependency: yields a DB session and closes it after the request
# ---------------------------------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# backup_db() — call this before any risky schema migration or bulk write
# ---------------------------------------------------------------------------
def backup_db():
    """Copy cashio.db → cashio.db.bak for safety."""
    if os.path.exists(DB_PATH):
        shutil.copy2(DB_PATH, DB_BAK_PATH)


# ---------------------------------------------------------------------------
# init_db() — create all tables and seed initial data
# ---------------------------------------------------------------------------
def init_db():
    """
    Import models here (not at module top) to avoid circular imports.
    Creates all tables, seeds the admin account and meta counters.
    """
    from app.models import Account, Transaction, Admin, Meta  # noqa: F401
    from app.security import hash_password

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Seed meta counters if they don't exist
        for key, default_val in [("next_txn_counter", "1"), ("next_account_counter", "10000001")]:
            if not db.query(Meta).filter(Meta.key == key).first():
                db.add(Meta(key=key, value=default_val))

        # Seed admin account if it doesn't exist
        if not db.query(Admin).filter(Admin.id == 1).first():
            # Default password: Admin@1234  — change via env ADMIN_PASSWORD
            admin_password = os.environ.get("ADMIN_PASSWORD", "Admin@1234")
            db.add(Admin(id=1, password_hash=hash_password(admin_password)))
            print("[Cashio Security] Admin account created. Default password: Admin@1234")
            print("[Cashio Security] Set ADMIN_PASSWORD env variable to override.")

        db.commit()
    finally:
        db.close()

