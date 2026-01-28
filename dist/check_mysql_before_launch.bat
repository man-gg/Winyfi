@echo off
setlocal enabledelayedexpansion

REM Quick XAMPP MySQL Check
REM Verifies MySQL is running and reachable with winyfi user

set MYSQL_BIN=C:\xampp\mysql\bin\mysql.exe
set HOST=127.0.0.1
set PORT=3306
set DBUSER=winyfi
set DBPASS=winyfi123
set DBNAME=winyfi
REM Use APPDATA folder which is always writable
if not exist "%APPDATA%\Winyfi" mkdir "%APPDATA%\Winyfi"
set LOG_FILE=%APPDATA%\Winyfi\mysql_check_error.log

echo ============================================================
echo   WINYFI - XAMPP MySQL Connection Check
echo ============================================================
echo.
echo [LOG] Writing detailed diagnostics to: %LOG_FILE%
echo.

REM Initialize log file
(
echo [%date% %time%] MySQL Check Started
echo Configuration:
echo   MYSQL_BIN=%MYSQL_BIN%
echo   HOST=%HOST%
echo   PORT=%PORT%
echo   DBUSER=%DBUSER%
echo   DBNAME=%DBNAME%
echo.
) > "%LOG_FILE%"

REM Check if MySQL client exists
if not exist "%MYSQL_BIN%" (
    echo [ERROR] MySQL client not found at %MYSQL_BIN%
    echo [%date% %time%] ERROR: MySQL client not found at %MYSQL_BIN% >> "%LOG_FILE%"
    echo Install/verify XAMPP MySQL and update MYSQL_BIN if needed.
    echo Check %LOG_FILE% for details.
    pause
    exit /b 1
)

REM Check if MySQL is running
echo Checking if MySQL is running on port %PORT%...
echo [%date% %time%] Checking if MySQL is listening on port %PORT%... >> "%LOG_FILE%"
netstat -an | findstr ":%PORT%" >nul

if %errorlevel% equ 0 (
    echo [OK] MySQL is running on port %PORT%
    echo [%date% %time%] SUCCESS: MySQL is listening on port %PORT% >> "%LOG_FILE%"
    echo [%date% %time%] Port check: PASSED >> "%LOG_FILE%"
    echo. >> "%LOG_FILE%"
) else (
    echo [ERROR] MySQL is NOT running on port %PORT%
    echo [%date% %time%] ERROR: MySQL is NOT listening on port %PORT% >> "%LOG_FILE%"
    echo.
    echo Please start MySQL:
    echo   1. Open XAMPP Control Panel
    echo   2. Click "Start" next to MySQL
    echo   3. Wait for it to show "Running"
    echo   4. Then run this script again
    echo.
    echo Check %LOG_FILE% for details.
    pause
    exit /b 1
)

REM Try to connect with mysql client using app credentials
echo.
echo Attempting to connect with winyfi user...
echo [%date% %time%] Attempting connection with user %DBUSER%... >> "%LOG_FILE%"

"%MYSQL_BIN%" -h %HOST% -P %PORT% -u %DBUSER% -p%DBPASS% -e "SELECT 1" > nul 2> nul
set CONN_RESULT=!errorlevel!

if !CONN_RESULT! equ 0 (
    echo [OK] MySQL connection with winyfi user succeeded
    echo [%date% %time%] SUCCESS: Connection established with user %DBUSER% >> "%LOG_FILE%"
    echo.
) else (
    echo [ERROR] Could not verify MySQL connection with winyfi user
    echo [%date% %time%] ERROR: Connection failed with user %DBUSER% (Exit code: !CONN_RESULT!) >> "%LOG_FILE%"
    echo Check credentials in db_config.json and ensure user exists.
    echo See %LOG_FILE% for detailed error information.
    echo.
    pause
    exit /b 1
)

REM Check database
echo Checking database '%DBNAME%'...
echo [%date% %time%] Checking database '%DBNAME%'... >> "%LOG_FILE%"

"%MYSQL_BIN%" -h %HOST% -P %PORT% -u %DBUSER% -p%DBPASS% -e "USE %DBNAME%;" > nul 2> nul
set DB_RESULT=!errorlevel!

if !DB_RESULT! equ 0 (
    echo [OK] '%DBNAME%' database exists and is accessible
    echo [%date% %time%] SUCCESS: Database '%DBNAME%' is accessible >> "%LOG_FILE%"
    echo.
) else (
    echo [ERROR] '%DBNAME%' database not found or not accessible with winyfi user
    echo [%date% %time%] ERROR: Database '%DBNAME%' check failed (Exit code: !DB_RESULT!) >> "%LOG_FILE%"
    echo.
    echo Setup instructions:
    echo   1. Open phpMyAdmin: http://localhost/phpmyadmin
    echo   2. Ensure database '%DBNAME%' exists
    echo   3. Ensure winyfi user has privileges
    echo   4. Import winyfi.sql from the Winyfi installation folder if needed
    echo.
    echo See %LOG_FILE% for detailed diagnostics.
    pause
    exit /b 1
)

del "%TEMP%\mysql_db_error.tmp" 2>nul

echo ============================================================
echo   All checks passed! Ready to run Winyfi.
echo ============================================================
echo [%date% %time%] All MySQL checks passed successfully >> "%LOG_FILE%"
echo.
echo Full diagnostic log saved to: %LOG_FILE%
echo.
pause

