#!/bin/bash
# PI Lead Qualifier - Mac Start Script

echo "==================================="
echo "   PI Lead Qualifier"
echo "==================================="
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Navigate to the project root (two directories up from deploy/local)
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed."
    echo "Please install Python from python.org"
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "No configuration found. Starting setup wizard..."
    python3 setup/app.py
    exit 0
fi

# Install dependencies if needed
if [ ! -d "venv" ]; then
    echo "Installing dependencies..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Start the qualifier
echo "Starting PI Lead Qualifier..."
echo "Dashboard: http://localhost:8080"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python3 run_local.py
