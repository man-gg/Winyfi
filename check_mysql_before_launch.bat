@echo off
REM Quick XAMPP MySQL Check
REM This script helps verify MySQL is running before launching Winyfi

echo ============================================================
echo   WINYFI - XAMPP MySQL Connection Check
echo ============================================================
echo.

REM Check if MySQL is running
echo Checking if MySQL is running...
netstat -an | findstr ":3306" >nul

if %errorlevel% equ 0 (
    echo [OK] MySQL is running on port 3306
    echo.
) else (
    echo [ERROR] MySQL is NOT running on port 3306
    echo.
    echo Please start MySQL:
    echo   1. Open XAMPP Control Panel
    echo   2. Click "Start" next to MySQL
    echo   3. Wait for it to show "Running"
    echo   4. Then run this script again
    echo.
    pause
    exit /b 1
)

REM Try to connect with mysql client (if available)
mysql -h localhost -u root -e "SELECT 1" >nul 2>&1

if %errorlevel% equ 0 (
    echo [OK] MySQL connection successful
    echo.
) else (
    echo [WARNING] Could not verify MySQL connection
    echo Possible issues:
    echo   - MySQL is not configured with root user
    echo   - MySQL root user has a password (edit db_config.json)
    echo.
)

REM Check database
mysql -h localhost -u root -e "USE winyfi; SELECT COUNT(*) as table_count FROM information_schema.tables WHERE table_schema='winyfi';" 2>nul

if %errorlevel% equ 0 (
    echo [OK] 'winyfi' database exists and is accessible
    echo.
) else (
    echo [ERROR] 'winyfi' database not found or not accessible
    echo.
    echo Setup instructions:
    echo   1. Open phpMyAdmin: http://localhost/phpmyadmin
    echo   2. Create a new database named 'winyfi'
    echo   3. Import winyfi.sql from the Winyfi installation folder
    echo.
    pause
    exit /b 1
)

echo ============================================================
echo   All checks passed! Ready to run Winyfi.
echo ============================================================
echo.
pause
