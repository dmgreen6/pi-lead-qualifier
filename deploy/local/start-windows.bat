@echo off
title PI Lead Qualifier

echo ===================================
echo    PI Lead Qualifier
echo ===================================
echo.

REM Navigate to the project root (two directories up from deploy\local)
cd /d "%~dp0..\.."

REM Check if .env exists
if not exist ".env" (
    echo No configuration found. Starting setup wizard...
    python setup\app.py
    exit /b
)

REM Install dependencies if needed
if not exist "venv" (
    echo Installing dependencies...
    python -m venv venv
    call venv\Scripts\activate
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate
)

REM Start the qualifier
echo Starting PI Lead Qualifier...
echo Dashboard: http://localhost:8080
echo.
echo Press Ctrl+C to stop
echo.

python run_local.py

pause
