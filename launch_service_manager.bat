@echo off
REM Launch WinyFi in Service Manager Only mode
REM This starts the application with the --service-manager-only flag

cd /d "%~dp0"

REM For development/testing:
if exist "main.py" (
    python main.py --service-manager-only
    exit /b
)

REM For packaged executable:
if exist "dist\Winyfi.exe" (
    "dist\Winyfi.exe" --service-manager-only
    exit /b
)

REM For installed version:
"Winyfi.exe" --service-manager-only
