@echo off
title DevPilot - Build Windows Setup Installer
echo =========================================================
echo       Building DevPilot Windows Setup Installer (.exe)
echo =========================================================
echo.

:: 1. Verify dist\DevPilot exists
if not exist "dist\DevPilot\DevPilot.exe" (
    echo [1/2] Compiling PyInstaller folder distribution first...
    call build_executable.bat
) else (
    echo [1/2] Found compiled DevPilot distribution in dist\DevPilot.
)

echo.
echo [2/2] Checking for Inno Setup Compiler (ISCC)...

set "ISCC="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if exist "%LOCALAPPDATA%\Programs\Antigravity IDE\_\resources\app\node_modules\innosetup\bin\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Antigravity IDE\_\resources\app\node_modules\innosetup\bin\ISCC.exe"

if defined ISCC (
    echo Found Inno Setup Compiler at: "%ISCC%"
    echo Compiling Windows Setup Installer...
    "%ISCC%" installer.iss
    if %errorlevel% equ 0 (
        echo.
        echo =========================================================
        echo  SUCCESS: Windows Setup Installer Created!
        echo  Location: dist\DevPilot-Windows-Setup-1.0.0.exe
        echo =========================================================
    ) else (
        echo [ERROR] Inno Setup compilation failed with code %errorlevel%.
    )
) else (
    echo [INFO] Inno Setup 6 not found in standard paths.
    echo Please install Inno Setup 6 from: https://jrsoftware.org/isdl.php
)

echo.
pause
