@echo off
echo ==============================================
echo DevPilot Setup - Windows
echo ==============================================

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH. Please install Python 3.11+.
    exit /b 1
)

:: Create Virtual Environment
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
) else (
    echo Virtual environment already exists.
)

:: Install Python requirements
echo Installing backend requirements...
call .\venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r backend/requirements.txt

:: Check for Node/NPM
npm --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] npm is not installed or not in PATH. Please install Node.js and npm to run the frontend.
) else (
    echo Installing frontend dependencies...
    cd frontend
    npm install
    cd ..
)

echo ==============================================
echo Setup Complete! Run 'npm start' or 'make dev' to start.
echo ==============================================
