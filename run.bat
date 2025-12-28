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
set "PYTHON="

REM Prefer the Python Launcher (py.exe) if present
py -3 --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON=py -3"
) else (
    python --version >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON=python"
    )
)

if "%PYTHON%"=="" (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

%PYTHON% -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.10+ is required.
    %PYTHON% --version
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

echo [OK] Python detected

REM Create virtual environment if it doesn't exist
if not exist ".venv" (
    echo [..] Creating virtual environment...
    %PYTHON% -m venv .venv
    echo [OK] Virtual environment created
)

REM Recreate venv if activation script is missing (corrupted venv)
if not exist ".venv\Scripts\activate.bat" (
    echo [..] Recreating virtual environment (corrupted .venv detected)...
    rmdir /s /q ".venv"
    %PYTHON% -m venv .venv
)

REM Activate virtual environment
echo [..] Activating virtual environment...
call .venv\Scripts\activate.bat

python -m pip install -q --upgrade pip setuptools wheel

REM Check if poetry is installed
python -m poetry --version >nul 2>&1
if errorlevel 1 (
    echo [..] Installing Poetry...
    python -m pip install -q --upgrade poetry==1.8.4
    echo [OK] Poetry installed
)

set "POETRY_VIRTUALENVS_CREATE=false"
set "POETRY_NO_INTERACTION=1"

echo [..] Ensuring dependencies are installed...
python -m poetry install --only main --sync
if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    echo If this is your first run, please make sure you have a working internet connection.
    pause
    exit /b 1
)
echo [OK] Dependencies ready

echo.
echo ======================================================================
echo                      Starting Pooltool Online...                      
echo ======================================================================
echo.

REM Run the game
python -m poetry run run-pooltool %*

REM Keep window open if launched by double-click
if errorlevel 1 (
    echo.
    echo [ERROR] Pooltool exited with an error.
    pause
)
