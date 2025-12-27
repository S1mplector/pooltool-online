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

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed.${NC}"
    echo "Please install Python 3.10+ from https://python.org"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION detected"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}→${NC} Creating virtual environment..."
    python3 -m venv .venv
    echo -e "${GREEN}✓${NC} Virtual environment created"
fi

# Activate virtual environment
echo -e "${YELLOW}→${NC} Activating virtual environment..."
source .venv/bin/activate

# Check if poetry is installed in venv
if ! command -v poetry &> /dev/null; then
    echo -e "${YELLOW}→${NC} Installing Poetry..."
    pip install -q --upgrade pip
    pip install -q poetry==1.8.4
    echo -e "${GREEN}✓${NC} Poetry installed"
fi

# Check if dependencies are installed (quick check for pooltool package)
if ! python -c "import pooltool" 2>/dev/null; then
    echo -e "${YELLOW}→${NC} Installing dependencies (first run, this may take a few minutes)..."
    
    # Update lock file if needed
    if [ "pyproject.toml" -nt "poetry.lock" ] 2>/dev/null; then
        echo -e "${YELLOW}→${NC} Updating lock file..."
        poetry lock --no-update 2>/dev/null || poetry lock
    fi
    
    poetry install --no-interaction
    echo -e "${GREEN}✓${NC} Dependencies installed"
else
    echo -e "${GREEN}✓${NC} Dependencies already installed"
fi

# Check for pyngrok (for internet multiplayer)
if python -c "import pyngrok" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Internet multiplayer ready (pyngrok installed)"
else
    echo -e "${YELLOW}!${NC} pyngrok not found - multiplayer will be LAN only"
    echo "  To enable internet play: pip install pyngrok"
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}                      Starting Pooltool Online...                         ${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Run the game
poetry run run-pooltool "$@"
