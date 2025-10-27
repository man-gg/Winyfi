@echo off
echo ================================================================
echo LOOP DETECTION SYSTEM - Enhanced Sensitivity
echo ================================================================
echo.
echo This script will test the enhanced loop detection system.
echo.
echo IMPORTANT: You must run this as Administrator!
echo.
echo If you see "0 packets captured":
echo   1. Close this window
echo   2. Right-click PowerShell
echo   3. Select "Run as Administrator"
echo   4. Navigate to this folder
echo   5. Run: python test_loop_detection_enhanced.py
echo.
echo ================================================================
pause
echo.
echo Running enhanced loop detection test...
echo.
python test_loop_detection_enhanced.py
echo.
echo ================================================================
echo Test complete!
echo.
echo Next steps:
echo   • If tests passed: Start dashboard and enable loop detection
echo   • If no packets: Run PowerShell as Administrator
echo   • To test with loop: python auto_loop_simulator.py
echo   • For diagnosis: python diagnose_loop_detection.py
echo.
pause
