
@echo off
title Cashio Security Bank Management System
echo ====================================================================
echo   CASHIO SECURITY - ADVANCED BANK MANAGEMENT SYSTEM
echo ====================================================================
echo.
echo Starting backend server on http://127.0.0.1:8000 ...
echo The frontend is automatically served at http://127.0.0.1:8000/
echo Swagger documentation is at http://127.0.0.1:8000/docs
echo.
echo Press Ctrl+C in this window to stop the server anytime.
echo ====================================================================
echo.

cd /d "%~dp0"

py -m uvicorn app.main:app --reload --port 8000
if errorlevel 1 (
    python -m uvicorn app.main:app --reload --port 8000
)

pause

