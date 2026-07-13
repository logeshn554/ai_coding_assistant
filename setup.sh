#!/bin/bash
set -e

echo "=============================================="
echo "DevPilot Setup - Unix"
echo "=============================================="

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed. Please install Python 3.11+."
    exit 1
fi

# Create Virtual Environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
else
    echo "Virtual environment already exists."
fi

# Install Python requirements
echo "Installing backend requirements..."
source venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt

# Check for Node/NPM
if ! command -v npm &> /dev/null; then
    echo "[WARNING] npm is not installed. Please install Node.js and npm to run the frontend."
else
    echo "Installing frontend dependencies..."
    cd frontend
    npm install
    cd ..
fi

echo "=============================================="
echo "Setup Complete! Run 'npm start' or 'make dev' to start."
echo "=============================================="
