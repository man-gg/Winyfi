@echo off
REM Quick Loop Detection Test
REM Run this to test loop detection in your dashboard

echo ================================================================
echo    LOOP DETECTION TEST - Quick Start
echo ================================================================
echo.
echo This will:
echo   1. Generate network loop traffic for 60 seconds
echo   2. Your dashboard should detect it automatically
echo   3. Check Loop Detection Monitor for results
echo.
echo IMPORTANT: Keep your dashboard running in another window!
echo.
pause

echo.
echo Starting loop simulator...
echo.

python auto_loop_simulator.py

echo.
echo ================================================================
echo Test completed!
echo.
echo Check your dashboard:
echo   - Loop Detection Monitor should show detection
echo   - Notification badge should appear
echo   - Database should have new records
echo ================================================================
echo.
pause
