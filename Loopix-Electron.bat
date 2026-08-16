@echo off
title Loopix AI Editor (Electron)
echo =========================================================
echo             Starting Loopix AI Editor (Desktop)        
echo =========================================================
echo.

:: Ensure frontend production bundle is built
if not exist "frontend\dist\index.html" (
    echo Building frontend UI bundle...
    cd frontend
    call npm run build
    cd ..
)

:: Launch Electron Desktop Process
echo Launching Loopix Electron Desktop App...
cd electron
call npx electron .
cd ..

echo.
echo Application closed.
pause
