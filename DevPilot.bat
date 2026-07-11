@echo off
title DevPilot AI Editor Launcher
echo ===================================================
echo               Starting DevPilot AI Editor          
echo ===================================================
echo.

:: Launch desktop runner using virtual environment python
echo Launching DevPilot Desktop Application...
".\venv\Scripts\python" backend/desktop_run.py

echo.
echo Application stopped.
pause
