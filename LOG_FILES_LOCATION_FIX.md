# LOG FILES LOCATION FIX - PyInstaller Dist Build

## Problem
Error logs (`winyfi_runtime_error.log`) and service logs (`app.log`, `app-error.log`, etc.) were not visible in the dist folder when running `winyfi.exe`.

## Root Cause
The ServiceManager was using `Path(__file__).parent` to determine the application directory. When running from a PyInstaller frozen executable:
- `__file__` points to the **temporary extraction folder** (e.g., `C:\Users\...\AppData\Local\Temp\_MEI123456\`)
- Log files were created in this temp folder, which is:
  - Not visible to users
  - Deleted when application closes
  - Different on each run

## Solution
Modified `service_manager.py` to detect PyInstaller frozen mode and use the correct directory:

```python
if getattr(sys, 'frozen', False):
    # Running in PyInstaller bundle - use executable's directory
    self.app_dir = Path(sys.executable).parent
else:
    # Running in normal Python - use script's directory
    self.app_dir = Path(__file__).parent
```

## Changes Made

### 1. Module-Level Log Initialization (Lines 20-26)
**Before:**
```python
# Create runtime error file logger
runtime_error_log = Path(__file__).parent / "winyfi_runtime_error.log"
runtime_error_handler = logging.FileHandler(runtime_error_log, mode='a', encoding='utf-8')
# ... handler setup
logger.addHandler(runtime_error_handler)
```

**After:**
```python
# Runtime error log will be created in ServiceManager.__init__()
runtime_error_log = None
runtime_error_handler = None
```

### 2. ServiceManager.__init__() - App Directory Detection (Lines 31-42)
**Before:**
```python
def __init__(self):
    self.app_dir = Path(__file__).parent
```

**After:**
```python
def __init__(self):
    # For PyInstaller: use executable directory, not __file__ location
    # In dev mode: use script directory
    # In dist mode: use directory where winyfi.exe lives
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundle - use executable's directory
        self.app_dir = Path(sys.executable).parent
    else:
        # Running in normal Python - use script's directory
        self.app_dir = Path(__file__).parent
```

### 3. Runtime Error Log Creation (Lines 95-103)
**Added to ServiceManager.__init__() after logs_dir creation:**
```python
# Create runtime error log in logs directory (accessible in dist builds)
global runtime_error_log, runtime_error_handler
runtime_error_log = self.logs_dir / "winyfi_runtime_error.log"
if runtime_error_handler is None:
    runtime_error_handler = logging.FileHandler(runtime_error_log, mode='a', encoding='utf-8')
    runtime_error_handler.setLevel(logging.ERROR)
    runtime_error_formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s')
    runtime_error_handler.setFormatter(runtime_error_formatter)
    logger.addHandler(runtime_error_handler)
    logger.info(f"[SUCCESS] Runtime error logging enabled: {runtime_error_log}")
```

## Expected Behavior After Fix

### Development Mode (python main.py)
```
c:\Users\Consigna\Desktop\Winyfi\Winyfi\
├── main.py
├── service_manager.py
├── logs/
│   ├── winyfi_runtime_error.log  ← Runtime errors
│   ├── app.log                   ← Flask stdout
│   ├── app-error.log             ← Flask stderr
│   ├── unifi-api.log             ← UniFi stdout
│   └── unifi-api-error.log       ← UniFi stderr
```

### Dist Build (dist\winyfi.exe)
```
c:\Users\Consigna\Desktop\Winyfi\Winyfi\dist\
├── winyfi.exe
├── logs/
│   ├── winyfi_runtime_error.log  ← Runtime errors (NOW VISIBLE!)
│   ├── app.log                   ← Flask stdout
│   ├── app-error.log             ← Flask stderr
│   ├── unifi-api.log             ← UniFi stdout
│   └── unifi-api-error.log       ← UniFi stderr
```

## Verification Test

Run this after rebuild:

```powershell
# Start winyfi.exe
.\dist\winyfi.exe

# In another terminal, check logs directory
ls .\dist\logs\

# Should see:
# winyfi_runtime_error.log  <- Error log now visible!
# app.log (if Flask started)
# app-error.log (if Flask started)
```

## Additional Benefits

1. **Config files now loaded correctly**: `service_config.json` and `server_config.json` are now found in the executable's directory, not temp folder

2. **Scripts auto-detected correctly**: `run_app.py` and `run_unifi_api.py` are now found relative to executable

3. **Portable installation**: Can copy entire dist\ folder to another location and logs will still be created in the correct place

## Technical Details

### sys.frozen Attribute
PyInstaller sets `sys.frozen = True` when running from a frozen executable. This is the standard way to detect bundled Python applications.

### sys.executable Behavior
- **Dev mode**: Points to Python interpreter (e.g., `C:\Python313\python.exe`)
- **Dist mode**: Points to frozen executable (e.g., `C:\...\dist\winyfi.exe`)

Using `Path(sys.executable).parent` gives us:
- **Dev mode**: Python installation directory → fallback to `__file__` is correct
- **Dist mode**: Directory containing winyfi.exe → exactly what we need!

## Files Modified

- [service_manager.py](c:\Users\Consigna\Desktop\Winyfi\Winyfi\service_manager.py)
  - Lines 20-26: Module-level log initialization
  - Lines 31-42: App directory detection with PyInstaller support
  - Lines 95-103: Runtime error log creation

## Status

✅ Code changes complete
⏳ Dist rebuild required
⏳ Verification testing pending

## Next Steps

1. Complete dist rebuild
2. Run winyfi.exe
3. Start Flask services
4. Verify `dist\logs\winyfi_runtime_error.log` exists and is writable
5. Test error capture by triggering a service failure

---
**Date**: 2026-01-17  
**Issue**: Log files not visible in dist build  
**Status**: FIXED - awaiting rebuild verification
