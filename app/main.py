"""
main.py — FastAPI application entry point for Cashio Security
Mounts all routers, configures Swagger UI, initialises the database.
"""

import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.routers import auth, account, transactions, card, admin

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
if not os.path.exists(FRONTEND_DIR):
    try:
        os.makedirs(FRONTEND_DIR, exist_ok=True)
    except OSError:
        pass

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
# Health check endpoint
# ---------------------------------------------------------------------------
@app.get("/api/health", tags=["Health"], summary="API Health Check")
def health_check():
    """Returns API health status."""
    return {
        "bank": "Cashio Security",
        "status": "online",
        "version": "1.0.0",
        "docs": "/docs",
    }

# ---------------------------------------------------------------------------
# Favicon handler
# ---------------------------------------------------------------------------
@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    fav = os.path.join(FRONTEND_DIR, "assets", "logo.png")
    if os.path.exists(fav):
        return FileResponse(fav, media_type="image/png")
    return JSONResponse(status_code=404, content={"detail": "Not found"})

# ---------------------------------------------------------------------------
# Mount Frontend Static Files
# Mounted after API routers so /auth, /account, /transactions etc. take precedence.
# Both /app-ui and root / will serve the frontend.
# ---------------------------------------------------------------------------
if os.path.exists(FRONTEND_DIR):
    app.mount("/app-ui", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend_ui")
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

