@echo off
REM Get test summary after uploading invoices

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0test_summary.ps1"
pause
