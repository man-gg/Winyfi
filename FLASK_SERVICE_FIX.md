# Flask API Service Manager Fix - Quick Guide

## The Problem You Described

When you run `python server/app.py` directly in terminal → **Works fine** ✅
When you start it via Service Manager → **Crashes** ❌ and shows "Not Responding"

## Root Cause

The issue is how Flask apps behave when run as Windows subprocesses:

1. **Working Directory**: When `app.py` runs directly, it knows its location
2. **Import Paths**: The app adds parent directory to `sys.path` using `__file__`
3. **Subprocess Issues**: When run via `subprocess.Popen`, `__file__` and working directory can be incorrect

## The Fix

I created **wrapper scripts** that ensure correct startup:

### New Files Created:
- `server/run_app.py` - Wrapper for Flask API
- `server/run_unifi_api.py` - Wrapper for UniFi API

These wrappers:
1. ✅ Set correct working directory
2. ✅ Add parent directory to `sys.path` for imports
3. ✅ Disable Flask debug mode and reloader
4. ✅ Catch and log startup errors

### Service Manager Improvements:
1. ✅ Waits up to 15 seconds for Flask to be ready
2. ✅ Checks process is still alive during startup
3. ✅ Tests health endpoint before declaring success
4. ✅ Logs detailed error messages if crash occurs
5. ✅ Shows actual exit code when process crashes

## How to Test

### Method 1: Test wrapper directly
```powershell
# Activate venv
.venv\Scripts\Activate.ps1

# Test Flask API wrapper
python server\run_app.py
```

Expected output:
```
============================================================
Starting Flask API Server
============================================================
 * Running on http://127.0.0.1:5000
 * Running on http://192.168.1.15:5000
```

Press Ctrl+C to stop.

### Method 2: Use Service Manager

1. Open WinyFi and login as admin
2. Go to Settings → ⚙️ Service Manager
3. Click **▶️ Start** on Flask API
4. Watch the status:
   - Should show "⏳ Starting..."
   - Then "🟢 Running" + "✅ Healthy"

If it shows "🔴 Crashed":
1. Click **📋 View Logs**
2. Open `flask-api-error.log`
3. Check for Python errors

## Common Issues & Solutions

### Issue: "Port 5000 already in use"
**Solution**: Another Flask instance is running
```powershell
# Kill all Python processes
taskkill /F /IM python.exe

# Then try starting again
```

### Issue: "Module not found" errors
**Solution**: Missing dependencies
```powershell
# Activate venv first
.venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt
```

### Issue: Database connection errors
**Solution**: MySQL not running
```powershell
# Check MySQL status
net start | findstr MySQL

# Start MySQL if not running
net start MySQL80
```

## What Changed in the Code

### Before (Crashing):
```python
# service_manager.py used direct script
'script': 'server/app.py'

# app.py expected to be run from its directory
# Crashed when run as subprocess from wrong directory
```

### After (Working):
```python
# service_manager.py uses wrapper
'script': 'server/run_app.py'

# run_app.py ensures correct environment
os.chdir(script_dir)  # Go to server/ directory
sys.path.insert(0, parent_dir)  # Add parent for imports
from app import create_app  # Import works correctly
```

## Testing Checklist

- [ ] Flask API starts from Service Manager
- [ ] Shows "🟢 Running" status  
- [ ] Shows "✅ Healthy" health check
- [ ] UniFi API starts from Service Manager
- [ ] Both services accessible via health endpoints
- [ ] Services survive restart
- [ ] Logs are written to logs/ directory
- [ ] "View Logs" button opens logs folder

## Next Steps

If you still have issues:

1. **Check the logs**:
   - Service Manager → 📋 View Logs
   - Look at `flask-api-error.log`

2. **Test wrapper manually**:
   ```powershell
   .venv\Scripts\Activate.ps1
   python server\run_app.py
   ```

3. **Verify Python path**:
   ```powershell
   # Should use venv Python
   .venv\Scripts\python.exe --version
   ```

4. **Check requirements**:
   ```powershell
   pip list | findstr -i "flask mysql"
   ```

## Summary

The wrapper scripts (`run_app.py` and `run_unifi_api.py`) solve the subprocess startup issues by:
- Setting correct working directory
- Fixing import paths
- Ensuring Flask runs without reloader
- Catching and logging all errors

The Service Manager now properly waits for Flask to be ready before declaring success.
