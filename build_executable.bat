@echo off
title DevPilot AI Editor - Exe Builder
echo =========================================================
echo       Building DevPilot AI Editor Windows Executable
echo =========================================================
echo.

:: 1. Build frontend production assets
echo [1/4] Building Frontend UI Bundle...
cd frontend
call npm run build
if %errorlevel% neq 0 (
    echo [ERROR] Frontend build failed.
    cd ..
    pause
    exit /b 1
)
cd ..

:: 2. Generate Icon
echo [2/4] Generating DevPilot Icon...
.\venv\Scripts\python -c "import os; from PIL import Image, ImageDraw; os.makedirs('assets', exist_ok=True); img = Image.new('RGBA', (256, 256), (0,0,0,0)); d = ImageDraw.Draw(img); d.rounded_rectangle([8,8,248,248], radius=48, fill=(15,23,42,255), outline=(59,130,246,255), width=6); d.polygon([(60,128),(105,75),(115,85),(80,128),(115,171),(105,181)], fill=(56,189,248,255)); d.polygon([(196,128),(151,75),(141,85),(176,128),(141,171),(151,181)], fill=(56,189,248,255)); d.polygon([(128,65),(145,128),(128,191),(111,128)], fill=(168,85,247,255)); d.ellipse([120,120,136,136], fill=(255,255,255,255)); img.save('assets/devpilot.ico', format='ICO', sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])"

:: 3. Run PyInstaller
echo [3/4] Compiling Windows Executable (.exe) with PyInstaller...
.\venv\Scripts\pyinstaller --noconfirm devpilot.spec
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller compilation failed.
    pause
    exit /b 1
)

:: 4. Create Desktop Shortcut
echo [4/4] Creating Windows Desktop Shortcut...
.\venv\Scripts\python create_desktop_shortcut.py

echo.
echo =========================================================
echo  Build Successful!
echo  Executable Location: dist\DevPilot\DevPilot.exe
echo  Desktop Shortcut Created: "DevPilot AI Editor"
echo =========================================================
pause
