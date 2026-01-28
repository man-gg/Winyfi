# Service Manager Only Mode

## Problem Fixed

When starting Flask API services from the Service Manager, the login window would pop up, causing confusion:
- **If login successful**: Dashboard would appear (creating "2 dashboards" effect)
- **If login failed**: Flask startup would appear to fail

## Solution

WinyFi now supports a **Service Manager Only Mode** that allows users to start and manage services without logging into the dashboard.

## Usage

### Option 1: Using the Batch Launcher (Windows)
```batch
launch_service_manager.bat
```

### Option 2: Using Python Launcher
```bash
python launch_service_manager.py
```

### Option 3: Direct Command Line
```bash
# From source
python main.py --service-manager-only

# From packaged executable
Winyfi.exe --service-manager-only
```

## What's Different

### Normal Mode (Default)
```
Start WinyFi → Login Window → Dashboard → Click "⚙️ Service Manager" → Service Manager Toplevel Window
```

### Service Manager Only Mode (New)
```
Start with --service-manager-only → Service Manager Window Directly (No Login!)
```

## Features in Service Manager Only Mode

- ✅ Start/Stop Flask API service
- ✅ Start/Stop UniFi API service  
- ✅ View real-time service logs
- ✅ Monitor service health
- ✅ **No login required**
- ✅ **No dashboard functionality**
- ✅ **Clean, focused UI**

## Installation Notes

### For End Users (Installed Version)
Create a desktop shortcut with:
```
Target: C:\Program Files\Winyfi\Winyfi.exe --service-manager-only
Start in: C:\Program Files\Winyfi
```

### For Developers  
```bash
# Test the mode from source
python main.py --service-manager-only

# Or use the launcher script
python launch_service_manager.py
```

## Technical Details

- When `--service-manager-only` is detected in `sys.argv`, main.py skips the login flow
- Instead, it directly instantiates the Dashboard class and calls `show_service_manager()`
- The service manager window is created as the root window (not a Toplevel)
- All service management functionality is identical to the dashboard version
- Health checks still run to ensure database connectivity

## Files Modified

1. **main.py**
   - Added `SERVICE_MANAGER_ONLY` flag detection
   - Added conditional logic to skip login and show service manager directly

2. **Created Files**
   - `launch_service_manager.bat` - Windows batch launcher
   - `launch_service_manager.py` - Python launcher
   - `SERVICE_MANAGER_README.md` - This file

## Testing

To verify the fix works:

```bash
# Test normal mode (should show login)
python main.py

# Test service manager mode (should NOT show login)
python main.py --service-manager-only
```

Both modes should work without errors, with database health checks completing successfully.
