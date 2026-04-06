@echo off
REM Erome Scraper - Startup Script
REM Starts the FastAPI server on http://localhost:8000

echo ========================================
echo   Erome Scraper v3.0.0
echo   FastAPI + Web UI
echo ========================================
echo.

REM Check for virtual environment
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Check for dependencies
python -c "import fastapi" 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

echo.
echo Starting server on http://localhost:8000
echo Press Ctrl+C to stop
echo.

python -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload