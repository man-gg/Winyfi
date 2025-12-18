@echo off
echo ========================================
echo    Winyfi Database Check
echo ========================================
echo.

REM Check if XAMPP is installed
if exist "C:\xampp\mysql\bin\mysql.exe" (
    echo [OK] XAMPP is installed
) else (
    echo [ERROR] XAMPP not found!
    echo Please install XAMPP from: https://www.apachefriends.org/
    pause
    exit /b 1
)

echo.
echo Checking MySQL service...
echo.

REM Try to connect to MySQL
"C:\xampp\mysql\bin\mysql.exe" -u root -h localhost -e "SELECT 1;" 2>nul

if %ERRORLEVEL% EQU 0 (
    echo [OK] MySQL is running
    
    REM Check if winyfi database exists
    "C:\xampp\mysql\bin\mysql.exe" -u root -h localhost -e "USE winyfi; SELECT 'Database exists' as status;" 2>nul
    
    if %ERRORLEVEL% EQU 0 (
        echo [OK] Winyfi database exists
        echo.
        echo ========================================
        echo    All checks passed! 
        echo    You can now run Winyfi.exe
        echo ========================================
    ) else (
        echo [WARNING] Winyfi database not found
        echo.
        echo Please create the database:
        echo 1. Open http://localhost/phpmyadmin
        echo 2. Create database named: winyfi
        echo 3. Import winyfi.sql
    )
) else (
    echo [ERROR] MySQL is not running!
    echo.
    echo Please start MySQL:
    echo 1. Open XAMPP Control Panel
    echo 2. Click "Start" next to MySQL
    echo 3. Wait for status to show "Running"
)

echo.
pause
