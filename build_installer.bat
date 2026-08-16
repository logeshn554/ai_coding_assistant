@echo off
title Loopix - Build Windows Setup Installer
echo =========================================================
echo       Building Loopix Windows Setup Installer (.exe)
echo =========================================================
echo.

:: 1. Verify dist\Loopix exists
if not exist "dist\Loopix\Loopix.exe" (
    echo [1/2] Compiling PyInstaller folder distribution first...
    call build_executable.bat
) else (
    echo [1/2] Found compiled Loopix distribution in dist\Loopix.
)

echo.
echo [2/2] Compiling Windows Setup Installer with Inno Setup...

set "ISCC="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"

if defined ISCC (
    echo Using Inno Setup Compiler: "%ISCC%"
    "%ISCC%" installer.iss
) else (
    echo Inno Setup not found in standard paths, using automated npx bundle...
    call npx -y innosetup installer.iss
)

if exist "dist_installer\Loopix-Windows-Setup-1.0.0.exe" (
    copy /y "dist_installer\Loopix-Windows-Setup-1.0.0.exe" "dist\Loopix-Windows-Setup-1.0.0.exe" >nul
)

if exist "dist\Loopix-Windows-Setup-1.0.0.exe" (
    echo.
    echo =========================================================
    echo  SUCCESS: Full VS Code-Style Setup Installer Created!
    echo  Location: dist\Loopix-Windows-Setup-1.0.0.exe
    echo =========================================================
) else (
    echo [ERROR] Setup installer compilation failed.
)

echo.
pause
