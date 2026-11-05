@echo off
title Cashio Security Bank Management System
echo ============================================================
echo   CASHIO SECURITY - ADVANCED BANK MANAGEMENT SYSTEM
echo ============================================================
echo.
echo Starting server on http://127.0.0.1:8080
echo Swagger docs: http://127.0.0.1:8080/docs
echo Press Ctrl+C in this window to stop the server.
echo.
cd /d "%~dp0"
python -m uvicorn app.main:app --reload --port 8080
pause