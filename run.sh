#!/bin/bash
#
# Pooltool Online - One-click launcher
# Just run: ./run.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "  ____             _ _              _    ___        _ _            "
echo " |  _ \ ___   ___ | | |_ ___   ___ | |  / _ \ _ __ | (_)_ __   ___ "
echo " | |_) / _ \ / _ \| | __/ _ \ / _ \| | | | | | '_ \| | | '_ \ / _ \\"
echo " |  __/ (_) | (_) | | || (_) | (_) | | | |_| | | | | | | | | |  __/"
echo " |_|   \___/ \___/|_|\__\___/ \___/|_|  \___/|_| |_|_|_|_| |_|\___|"
echo -e "${NC}"
echo ""

PYTHON_BIN="python3"
if ! command -v "$PYTHON_BIN" &> /dev/null; then
    PYTHON_BIN="python"
fi

if ! command -v "$PYTHON_BIN" &> /dev/null; then
    echo -e "${RED}Error: Python is not installed.${NC}"
    echo "Please install Python 3.10+ from https://python.org"
    exit 1
fi

if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
    echo -e "${RED}Error: Python 3.10+ is required.${NC}"
    "$PYTHON_BIN" --version || true
    echo "Please install Python 3.10+ from https://python.org"
    exit 1
fi

PYTHON_VERSION=$(
    "$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'
)
echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION detected"

if [ -f ".venv/pyvenv.cfg" ]; then
    VENV_VERSION=$(
        grep -E '^version = ' .venv/pyvenv.cfg 2>/dev/null | head -n 1 | awk '{print $3}' | cut -d. -f1-2
    )
    if [ -n "${VENV_VERSION:-}" ] && [ "$VENV_VERSION" != "$PYTHON_VERSION" ]; then
        echo -e "${YELLOW}→${NC} Recreating virtual environment (Python version changed)..."
        rm -rf .venv
    fi
fi

if [ ! -f ".venv/bin/activate" ] && [ -d ".venv" ]; then
    echo -e "${YELLOW}→${NC} Recreating virtual environment (corrupted .venv detected)..."
    rm -rf .venv
fi

if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}→${NC} Creating virtual environment..."
    "$PYTHON_BIN" -m venv .venv
    echo -e "${GREEN}✓${NC} Virtual environment created"
fi

# Activate virtual environment
echo -e "${YELLOW}→${NC} Activating virtual environment..."
source .venv/bin/activate

python -m pip install -q --upgrade pip setuptools wheel

if ! python -m poetry --version > /dev/null 2>&1; then
    echo -e "${YELLOW}→${NC} Installing Poetry..."
    python -m pip install -q --upgrade "poetry==1.8.4"
    echo -e "${GREEN}✓${NC} Poetry installed"
fi

export POETRY_VIRTUALENVS_CREATE=false
export POETRY_NO_INTERACTION=1

echo -e "${YELLOW}→${NC} Ensuring dependencies are installed..."
python -m poetry install --only main --sync
echo -e "${GREEN}✓${NC} Dependencies ready"

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}                      Starting Pooltool Online...                         ${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "Tip: Run ${YELLOW}./run.sh --fast${NC} for better performance on macOS"
echo ""

# Run the game
python -m poetry run run-pooltool "$@"
