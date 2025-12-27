@echo off
REM Pooltool Online - One-click launcher for Windows
REM Just double-click this file or run: run.bat

cd /d "%~dp0"

echo.
echo   ____             _ _              _    ___        _ _            
echo  ^|  _ \ ___   ___ ^| ^| ^|_ ___   ___ ^| ^|  / _ \ _ __ ^| ^(_)_ __   ___ 
echo  ^| ^|_) / _ \ / _ \^| ^| __/ _ \ / _ \^| ^| ^| ^| ^| ^| '_ \^| ^| ^| '_ \ / _ \
echo  ^|  __/ (_) ^| (_) ^| ^| ^|^| (_) ^| (_) ^| ^| ^| ^|_^| ^| ^| ^| ^| ^| ^| ^| ^| ^|  __/
echo  ^|_^|   \___/ \___/^|_^|\__\___/ \___/^|_^|  \___/^|_^| ^|_^|_^|_^|_^| ^|_^|\___^|
echo.

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

echo [OK] Python detected

REM Create virtual environment if it doesn't exist
if not exist ".venv" (
    echo [..] Creating virtual environment...
    python -m venv .venv
    echo [OK] Virtual environment created
)

REM Activate virtual environment
echo [..] Activating virtual environment...
call .venv\Scripts\activate.bat

REM Check if poetry is installed
poetry --version >nul 2>&1
if errorlevel 1 (
    echo [..] Installing Poetry...
    pip install -q --upgrade pip
    pip install -q poetry==1.8.4
    echo [OK] Poetry installed
)

REM Check if dependencies are installed
python -c "import pooltool" >nul 2>&1
if errorlevel 1 (
    echo [..] Installing dependencies (first run, this may take a few minutes)...
    poetry install --no-interaction
    echo [OK] Dependencies installed
) else (
    echo [OK] Dependencies already installed
)

echo.
echo ======================================================================
echo                      Starting Pooltool Online...                      
echo ======================================================================
echo.

REM Run the game
poetry run run-pooltool %*
