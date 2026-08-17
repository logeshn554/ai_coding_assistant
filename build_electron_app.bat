@echo off
title Loopix - Build Windows Desktop Package (Electron)
echo =========================================================
echo       Building Loopix Standalone Windows Installer
echo =========================================================
echo.

:: 1. Build frontend bundle
echo [1/3] Building Frontend UI Bundle...
cd frontend
call npm run build
if %errorlevel% neq 0 (
    echo [ERROR] Frontend build failed.
    cd ..
    pause
    exit /b 1
)
cd ..

:: 2. Ensure Electron dependencies
echo [2/3] Checking Electron dependencies...
cd electron
call npm install
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install electron dependencies.
    cd ..
    pause
    exit /b 1
)

:: 3. Build Windows Executable Installer
echo [3/3] Packaging Windows NSIS Installer...
call npm run build
cd ..

echo.
echo =========================================================
echo  Build Complete!
echo  Installer output directory: dist\electron-build\
echo =========================================================
pause
