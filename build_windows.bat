@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo Python launcher ^(py^) was not found. Install Python 3.10+ first.
    exit /b 1
)

py -m pip install --upgrade pip
if errorlevel 1 exit /b 1
py -m pip install -r requirements.txt TgCrypto
if errorlevel 1 exit /b 1

py -m PyInstaller --clean --noconfirm --onefile --noconsole ^
  --name powerpro_uploader_service ^
  --hidden-import pywin32timezone ^
  --hidden-import win32timezone ^
  --hidden-import win32service ^
  --hidden-import win32serviceutil ^
  --hidden-import servicemanager ^
  --hidden-import win32event ^
  --collect-all pyrogram ^
  service_runner.py
if errorlevel 1 exit /b 1

echo.
echo Build complete: %CD%\dist\powerpro_uploader_service.exe
echo Install and start it from an Administrator Command Prompt using the README instructions.
endlocal
