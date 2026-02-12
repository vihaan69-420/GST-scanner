@echo off
REM Simple batch file to watch invoice processing logs

echo.
echo ========================================
echo    GST Scanner - Live Log Monitor
echo ========================================
echo.
echo Monitoring: C:\Users\clawd bot\Documents\GST-scanner\logs\gst_scanner.log
echo Dashboard: http://localhost:8080/dashboard
echo.
echo Press Ctrl+C to stop
echo ----------------------------------------
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Content 'C:\Users\clawd bot\Documents\GST-scanner\logs\gst_scanner.log' -Wait -Tail 20 | ForEach-Object { if ($_ -match '\[ERROR\]') { Write-Host $_ -ForegroundColor Red } elseif ($_ -match '\[WARNING\]') { Write-Host $_ -ForegroundColor Yellow } elseif ($_ -match 'Started processing') { Write-Host $_ -ForegroundColor Cyan } elseif ($_ -match 'complete') { Write-Host $_ -ForegroundColor Green } else { Write-Host $_ } }"
