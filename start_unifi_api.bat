@echo off
REM WinyFi UniFi API Server Startup Script
REM This script starts the UniFi API server with proper configuration

echo ========================================
echo WinyFi UniFi API Server
echo ========================================
echo.

REM Check if .env file exists, if not copy from example
if not exist ".env" (
    if exist ".env.example" (
        echo Creating .env file from .env.example...
        copy .env.example .env
        echo.
        echo IMPORTANT: Please edit .env file with your UniFi Controller settings!
        echo Press any key to open .env file for editing...
        pause >nul
        notepad .env
    )
)

REM Load environment variables from .env file (simple parser)
if exist ".env" (
    echo Loading configuration from .env file...
    for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
        set "line=%%a"
        REM Skip comments and empty lines
        if not "!line:~0,1!"=="#" if not "%%a"=="" (
            set "%%a=%%b"
        )
    )
)

REM Set defaults if not configured
if not defined UNIFI_URL set UNIFI_URL=https://127.0.0.1:8443
if not defined UNIFI_USER set UNIFI_USER=admin
if not defined UNIFI_PASS set UNIFI_PASS=admin123
if not defined UNIFI_VERIFY set UNIFI_VERIFY=false

echo.
echo Current Configuration:
echo ----------------------
echo UniFi Controller: %UNIFI_URL%
echo Username: %UNIFI_USER%
echo SSL Verify: %UNIFI_VERIFY%
echo.
echo The API will listen on 0.0.0.0:5001 (accessible from network)
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7+ and try again
    pause
    exit /b 1
)

REM Check if in server directory
if not exist "unifi_api.py" (
    if exist "server\unifi_api.py" (
        echo Changing to server directory...
        cd server
    ) else (
        echo ERROR: Cannot find unifi_api.py
        echo Please run this script from the project root directory
        pause
        exit /b 1
    )
)

REM Install requirements if needed
if exist "requirements.txt" (
    echo Checking dependencies...
    python -c "import flask, requests" >nul 2>&1
    if errorlevel 1 (
        echo Installing required packages...
        pip install -r requirements.txt
    )
)

echo.
echo Starting UniFi API Server...
echo Press Ctrl+C to stop
echo.

REM Start the server
python unifi_api.py

pause
