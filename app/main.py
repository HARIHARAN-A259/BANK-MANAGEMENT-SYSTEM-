"""
main.py — FastAPI application entry point for Cashio Security
Mounts all routers, configures Swagger UI, initialises the database.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.routers import auth, account, transactions, card, admin

# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Cashio Security API",
    description=(
        "**Cashio Security** — Advanced Bank Management System\n\n"
        "A complete REST API for managing bank accounts, transactions, ATM cards, "
        "and PDF documents.\n\n"
        "**Key features:**\n"
        "- JWT authentication with account lockout protection\n"
        "- All money stored as integer paise (no float arithmetic)\n"
        "- bcrypt-hashed passwords and PINs\n"
        "- Atomic transfers with rollback\n"
        "- Luhn-valid ATM card numbers\n"
        "- PDF receipts, statements and ATM card documents\n\n"
        "**Default admin password:** `Admin@1234` *(change via `ADMIN_PASSWORD` env var)*"
    ),
    version="1.0.0",
    contact={
        "name": "Cashio Security Support",
        "email": "support@cashiosecurity.in",
        "url": "https://cashiosecurity.in",
    },
    license_info={
        "name": "MIT",
    },
    # Swagger UI available at /docs; ReDoc at /redoc
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS — allow all origins in dev; restrict in production
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Global exception handler — catch unhandled errors cleanly
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"},
    )

# ---------------------------------------------------------------------------
# Mount routers
# ---------------------------------------------------------------------------
app.include_router(auth.router)
app.include_router(account.router)
app.include_router(transactions.router)
app.include_router(card.router)
app.include_router(admin.router)

# ---------------------------------------------------------------------------
# Startup event — initialise DB tables and seed data
# ---------------------------------------------------------------------------
@app.on_event("startup")
def on_startup():
    print("=" * 60)
    print("  CASHIO SECURITY — Advanced Bank Management System")
    print("  Starting up ... initialising database ...")
    print("=" * 60)
    init_db()
    print("[OK] Database ready.")
    print("[OK] API docs: http://127.0.0.1:8000/docs")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------------------------
@app.get("/", tags=["Health"], summary="Health check")
def root():
    """Returns a welcome message confirming the API is running."""
    return {
        "bank": "Cashio Security",
        "message": "Welcome to Cashio Security API. Visit /docs for interactive documentation.",
        "status": "running",
        "version": "1.0.0",
    }

