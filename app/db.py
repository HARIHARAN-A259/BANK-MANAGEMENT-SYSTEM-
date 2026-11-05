"""
db.py — Database engine, session factory, and initialisation
Cashio Security Bank Management System
"""

import os
import shutil
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# ---------------------------------------------------------------------------
# Database URL and file path configuration
# Supports local SQLite, Vercel /tmp SQLite, and DATABASE_URL (PostgreSQL/MySQL/etc.)
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    # Some platforms (e.g. Heroku, Neon, Supabase) provide "postgres://", which SQLAlchemy 1.4+ requires as "postgresql://"
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    DB_URL = DATABASE_URL
    DB_PATH = None
    DB_BAK_PATH = None
else:
    # On Vercel, serverless filesystem /var/task is read-only; use writable /tmp
    if os.environ.get("VERCEL"):
        DB_PATH = "/tmp/cashio.db"
        DB_BAK_PATH = "/tmp/cashio.db.bak"
    else:
        DB_PATH = os.path.join(BASE_DIR, "cashio.db")
        DB_BAK_PATH = os.path.join(BASE_DIR, "cashio.db.bak")
    DB_URL = f"sqlite:///{DB_PATH}"

# ---------------------------------------------------------------------------
# Engine — check_same_thread=False is required for SQLite with multi-threaded FastAPI
# ---------------------------------------------------------------------------
is_sqlite = DB_URL.startswith("sqlite")

engine_kwargs = {"echo": False}
if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DB_URL, **engine_kwargs)

# Enable SQLite WAL mode for better concurrency (readers don't block writers)
if is_sqlite:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
        except Exception:
            pass
        finally:
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
    if DB_PATH and DB_BAK_PATH and os.path.exists(DB_PATH):
        try:
            shutil.copy2(DB_PATH, DB_BAK_PATH)
        except OSError:
            pass


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

        # Seed default admin account only if explicitly requested via SEED_DEFAULT_ADMIN=true
        if os.environ.get("SEED_DEFAULT_ADMIN") == "true" and not db.query(Admin).first():
            admin_password = os.environ.get("ADMIN_PASSWORD", "Admin@1234")
            db.add(Admin(id=1, username="admin", password_hash=hash_password(admin_password)))
            print("[Cashio Security] Default admin created: admin / Admin@1234")

        db.commit()
    finally:
        db.close()

