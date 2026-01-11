# Service Manager Implementation Guide

## Overview
The Service Manager allows admins to control Flask API (app.py) and UniFi API (unifi_api.py) directly from the dashboard after logging in with admin credentials.

## What Was Implemented

### 1. **service_manager.py**
- Core service management class
- Start/stop Flask API and UniFi API as background processes
- Health checking for both services
- Auto-start configuration
- Persistent settings saved to service_config.json

### 2. **Dashboard Integration**
- Added "⚙️ Service Manager" button to Settings dropdown
- Modern UI with service status cards
- Real-time status indicators:
  - 🟢 Running / ⚫ Stopped / 🔴 Crashed
  - ✅ Healthy / ⚠️ Not Responding
- Toggle buttons to start/stop each service
- Auto-start checkboxes
- Auto-refresh every 5 seconds

### 3. **Health Endpoints**
- Flask API: http://localhost:5000/api/health ✅ (already existed)
- UniFi API: http://localhost:5001/api/health ✅ (newly added)

## How to Use

### For Admin Users:
1. **Login** with admin credentials
2. Click **⚙️ Settings** in the sidebar
3. Click **⚙️ Service Manager**
4. Toggle services:
   - Click **▶️ Start** to start a service
   - Click **⏹️ Stop** to stop a service
   - Check **🚀 Auto-start on login** to automatically start services when you login

### Service Cards Show:
- **Service Name**: Flask API or UniFi API
- **Script Path**: server/app.py or server/unifi_api.py
- **Port**: 5000 or 5001
- **Status**: Running, Stopped, or Crashed
- **Health**: Healthy, Not Responding, or N/A
- **Controls**: Start/Stop button and Auto-start checkbox

## Files Modified/Created

### New Files:
- `service_manager.py` - Service management logic
- `service_config.json` - Persistent service configuration

### Modified Files:
- `dashboard.py` - Added Service Manager button and window
- `server/unifi_api.py` - Added health check endpoint

## Configuration

### service_config.json
```json
{
  "flask_api": {
    "enabled": false,
    "auto_start": false
  },
  "unifi_api": {
    "enabled": false,
    "auto_start": false
  }
}
```

## Testing

To test the service manager:

1. **Start the dashboard**:
   ```bash
   python main.py
   ```

2. **Login as admin**

3. **Open Service Manager**:
   - Settings → Service Manager

4. **Test Flask API**:
   - Click "▶️ Start" on Flask API card
   - Wait for status to change to "🟢 Running"
   - Open browser: http://localhost:5000/api/health
   - Should see: {"status": "ok"}

5. **Test UniFi API**:
   - Click "▶️ Start" on UniFi API card
   - Wait for status to change to "🟢 Running"
   - Open browser: http://localhost:5001/api/health
   - Should see: {"status": "healthy", "service": "unifi_api"}

6. **Test Stop**:
   - Click "⏹️ Stop" on each service
   - Status should change to "⚫ Stopped"

7. **Test Auto-Start**:
   - Enable "🚀 Auto-start on login" for both services
   - Logout and login again
   - Services should start automatically

## Features

✅ **Admin-Only Access** - Service Manager only accessible after admin login
✅ **Real-Time Status** - Status updates every 5 seconds
✅ **Health Monitoring** - Checks if APIs are responding
✅ **Auto-Start** - Services can auto-start on admin login
✅ **Persistent Settings** - Configuration saved to JSON file
✅ **Visual Feedback** - Color-coded status indicators
✅ **Background Processes** - APIs run hidden (no console windows)
✅ **Graceful Shutdown** - Services stop cleanly

## Troubleshooting

### Service Won't Start
- Check if ports 5000/5001 are already in use
- Verify `server/app.py` and `server/unifi_api.py` exist
- Check for Python errors in the service logs

### Status Shows "Crashed"
- The service started but terminated unexpectedly
- Check for errors in the console output
- Try restarting the service

### Health Shows "Not Responding"
- Service is running but not responding to health checks
- Wait a few seconds for the service to fully initialize
- Check if the health endpoint is accessible

## Next Steps (Optional Enhancements)

1. **Service Logs Viewer** - View console output from services
2. **Port Configuration** - Allow changing default ports
3. **Windows Service** - Install as Windows service for system-wide availability
4. **Notification Integration** - Show notifications when services crash
5. **Performance Metrics** - Display CPU/memory usage per service
