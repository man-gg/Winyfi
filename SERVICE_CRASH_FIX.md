# Service Manager Crash Fix - Summary

## Problem
Flask API and UniFi API services were crashing immediately after being started by the Service Manager.

## Root Causes Identified

### 1. **Flask Debug Mode with Reloader**
- `app.run(debug=True)` enables Flask's auto-reloader
- The reloader spawns a second process which conflicts with subprocess management
- When run as a background service, this causes immediate crashes

### 2. **No Error Logging**
- Services were started with `stdout=PIPE` and `stderr=PIPE`
- Errors were not captured or logged anywhere
- Made debugging impossible

### 3. **No Port Checking**
- Services would try to start even if port was already in use
- Led to multiple failed start attempts

## Fixes Implemented

### 1. **Disabled Flask Debug Mode for Services** ✅
```python
# In server/app.py
debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
app.run(host="0.0.0.0", port=5000, debug=debug_mode, use_reloader=False)
```

### 2. **Added Comprehensive Error Logging** ✅
```python
# In service_manager.py
- Created logs/ directory
- Each service now logs to:
  - flask-api.log (stdout)
  - flask-api-error.log (stderr)
  - unifi-api.log (stdout)
  - unifi-api-error.log (stderr)
```

### 3. **Added Port Availability Checking** ✅
```python
def _is_port_in_use(self, port):
    """Check if a port is already in use"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            result = s.connect_ex(('localhost', port))
            return result == 0
    except Exception:
        return False
```

### 4. **Set Flask Environment Variables** ✅
```python
env = os.environ.copy()
env['FLASK_DEBUG'] = 'false'
env['WERKZEUG_RUN_MAIN'] = 'true'  # Prevent Flask reloader
```

### 5. **Added "View Logs" Button** ✅
- New button in Service Manager window
- Opens logs/ directory in Windows Explorer
- Allows quick access to error logs for debugging

## Testing Results

✅ **Flask API** - Imports and responds correctly
```
✓ Health endpoint: 200
✓ Response: {'status': 'ok', 'service': 'network-monitoring-api'}
```

✅ **UniFi API** - Imports and responds correctly
```
✓ Health endpoint: 200
✓ Response: {'status': 'healthy', 'service': 'unifi_api'}
```

## Files Modified

1. **server/app.py**
   - Disabled debug mode by default
   - Added environment variable check
   - Disabled Flask reloader

2. **service_manager.py**
   - Added socket import for port checking
   - Added logs directory creation
   - Implemented port-in-use checking
   - Added comprehensive error logging to files
   - Set Flask environment variables
   - Close log files on service stop

3. **dashboard.py**
   - Added "View Logs" button to Service Manager window
   - Opens logs directory in file explorer

4. **test_services.py** (new)
   - Quick test script to verify services work
   - Tests health endpoints
   - Catches and displays errors

## How to Use

### Start Services
1. Open WinyFi and login as admin
2. Go to Settings → Service Manager
3. Click "▶️ Start" on Flask API
4. Click "▶️ Start" on UniFi API
5. Services should show "🟢 Running" and "✅ Healthy"

### View Logs
1. In Service Manager window
2. Click "📋 View Logs" button
3. Windows Explorer opens with log files:
   - `flask-api.log` - Flask API output
   - `flask-api-error.log` - Flask API errors
   - `unifi-api.log` - UniFi API output
   - `unifi-api-error.log` - UniFi API errors

### Troubleshooting
If services still crash:
1. Click "📋 View Logs"
2. Open the `-error.log` file for the crashed service
3. Look for Python tracebacks or error messages
4. Common issues:
   - Missing Python packages → Install from requirements.txt
   - Database connection errors → Check MySQL is running
   - Port already in use → Stop conflicting service

## Expected Behavior Now

1. **First Start**: Services start successfully in 1-2 seconds
2. **Status**: Shows "🟢 Running" and "✅ Healthy"
3. **Crash Detection**: If crash occurs, status shows "🔴 Crashed"
4. **Error Visibility**: All errors logged to files in logs/ directory
5. **No Multiple Starts**: Port checking prevents duplicate starts

## Notes

- UniFi API will show connection warnings if no UniFi controller is running at 127.0.0.1:8443
- This is expected and the API will still work in mock mode
- To connect to a real UniFi controller, set environment variable:
  ```
  UNIFI_URL=https://your-controller-ip:8443
  ```

## Next Steps (Optional)

If you still experience issues:
1. Check log files for specific errors
2. Verify MySQL database is accessible
3. Ensure all dependencies are installed: `pip install -r requirements.txt`
4. Test services manually: `python test_services.py`
