@echo off
REM GST Scanner Bot - Windows Launcher
REM This script starts the GST Scanner Telegram Bot

title GST Scanner Bot

echo.
echo ================================================================================
echo                           GST SCANNER BOT LAUNCHER
echo ================================================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://www.python.org/
    pause
    exit /b 1
)

echo [OK] Python is installed
echo.

REM Check if virtual environment exists
if exist "..\venv\" (
    echo [INFO] Found virtual environment, activating...
    call ..\venv\Scripts\activate.bat
    echo [OK] Virtual environment activated
    echo.
)

REM Check if dependencies are installed
echo [INFO] Checking dependencies...
python -c "import telegram" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Dependencies not installed
    echo [INFO] Installing dependencies from requirements.txt...
    cd ..
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies
        pause
        exit /b 1
    )
    cd scripts
    echo [OK] Dependencies installed
)

echo [OK] Dependencies are installed
echo.

REM Check if .env file exists
if not exist "..\..env" (
    echo [ERROR] Configuration file .env not found
    echo.
    echo Please copy config\.env.example to .env and fill in your credentials:
    echo   1. Telegram Bot Token
    echo   2. Google Gemini API Key
    echo   3. Google Sheet ID
    echo.
    echo See docs\guides\SETUP_GUIDE.md for detailed instructions
    pause
    exit /b 1
)

echo [OK] Configuration file found
echo.

REM Check if credentials.json exists
if not exist "..\config\credentials.json" (
    echo [ERROR] Google Sheets credentials file not found
    echo.
    echo Please download credentials.json from Google Cloud Console
    echo and place it in the config\ folder.
    echo.
    echo See docs\guides\SETUP_GUIDE.md for detailed instructions
    pause
    exit /b 1
)

echo [OK] Credentials file found
echo.

echo ================================================================================
echo                            STARTING BOT...
echo ================================================================================
echo.
echo Press Ctrl+C to stop the bot
echo.

REM Start the bot
cd ..
python start_bot.py

REM If bot exits, show message
echo.
echo ================================================================================
echo                            BOT STOPPED
echo ================================================================================
echo.
pause
