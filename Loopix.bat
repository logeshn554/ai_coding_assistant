@echo off
title Loopix AI Editor
echo =========================================================
echo               Starting Loopix AI Editor                
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

