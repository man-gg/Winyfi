@echo off
REM WinyFi Dashboard Startup Script
REM Configure this script to point to your UniFi API server

echo ========================================
echo WinyFi Network Monitoring Dashboard
echo ========================================
echo.

REM Set the UniFi API URL (change this to your Machine A IP address)
REM For local: http://localhost:5001
REM For remote: http://<machine-a-ip>:5001
set WINYFI_UNIFI_API_URL=http://192.168.1.87:5001

echo UniFi API URL: %WINYFI_UNIFI_API_URL%
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Start the dashboard
echo Starting WinyFi Dashboard...
python main.py

pause
