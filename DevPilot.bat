@echo off
title DevPilot AI Editor
echo =========================================================
echo               Starting DevPilot AI Editor                
echo =========================================================
echo.

:: Ensure frontend production bundle exists
if not exist "frontend\dist\index.html" (
    echo Building frontend bundle...
    cd frontend
    call npm run build
    cd ..
)

:: Launch standalone Electron desktop application (no browser)
cd electron
call npx electron .
cd ..

