@echo off
REM GST Scanner - System Test Runner
REM This script runs all system tests to verify setup

title GST Scanner - System Test

echo.
echo ================================================================================
echo                        GST SCANNER - SYSTEM TEST
echo ================================================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Run tests
python test_system.py

echo.
pause
