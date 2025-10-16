# UniFi Dashboard Integration

This document describes the UniFi API integration in the Winyfi Dashboard.

## Overview

The dashboard now supports displaying both **regular routers** and **UniFi Access Points** side-by-side, with distinct visual indicators and functionality.

## Features

### 1. **Separate Sections for UniFi and Regular Routers**
- 📡 **UniFi Access Points** section displays devices from the UniFi API
- 🟢 **Regular Routers** section displays routers from the database
- Can be sorted by online/offline status

### 2. **Visual Indicators**
- UniFi devices have a **primary blue card** color (instead of info)
- UniFi badge: **📡 UniFi** displayed on each UniFi device card
- Hover effects change to green for UniFi devices

### 3. **Real-Time Bandwidth**
- UniFi devices show bandwidth data from the UniFi API
- No need to ping UniFi devices - data comes directly from the controller
- Regular routers use traditional ping-based bandwidth monitoring

### 4. **Dual API Architecture**
- **Main API** (`http://localhost:5000`) - Regular router management
- **UniFi API** (`http://localhost:5001`) - UniFi device data

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Dashboard UI                            │
│  ┌──────────────────┐       ┌──────────────────┐           │
│  │  📡 UniFi APs    │       │  🟢 Regular      │           │
│  │                  │       │     Routers      │           │
│  │  - Living Room   │       │  - Router 1      │           │
│  │  - Bedroom AP    │       │  - Router 2      │           │
│  └──────────────────┘       └──────────────────┘           │
└─────────────────────────────────────────────────────────────┘
           │                              │
           ▼                              ▼
  ┌─────────────────┐          ┌─────────────────┐
  │  UniFi API      │          │  MySQL Database │
  │  (Port 5001)    │          │  + Router Utils │
  │                 │          │                 │
  │  Mock/Real      │          │  Regular Router │
  │  UniFi Data     │          │  Data           │
  └─────────────────┘          └─────────────────┘
```

## API Endpoints

### UniFi API Server (`http://localhost:5001`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/unifi/devices` | GET | List all UniFi APs with bandwidth |
| `/api/unifi/clients` | GET | List all connected clients |
| `/api/unifi/bandwidth/total` | GET | Get total bandwidth across APs |
| `/api/unifi/clients/count` | GET | Get total client count |
| `/api/unifi/mock` | POST | Toggle mock mode (for testing) |

### Device Data Structure

```python
{
    "model": "UAP-AC-Pro",
    "name": "Living Room AP",
    "mac": "AA:BB:CC:DD:EE:01",
    "ip": "192.168.1.2",
    "xput_down": 120.5,  # Download bandwidth in Mbps
    "xput_up": 30.2      # Upload bandwidth in Mbps
}
```

## Files Modified

### `dashboard.py`
- Added `requests` import for API calls
- Added `unifi_api_url` parameter to `Dashboard.__init__`
- Added `_fetch_unifi_devices()` method to fetch UniFi APs
- Modified `reload_routers()` to separate and display UniFi/regular routers
- Updated card rendering to show UniFi badges and different colors
- Added logic to display UniFi bandwidth from API (no ping needed)

### `router_utils.py`
- No changes needed (regular routers still use database)

### `server/unifi_api.py`
- Existing mock UniFi API server (already implemented)

## Usage

### 1. Start the UniFi API Server

```powershell
# In terminal 1
cd server
python unifi_api.py
```

Or use the convenience script:

```powershell
python start_unifi_server.py
```

### 2. Start the Main Dashboard

```powershell
# In terminal 2
python main.py
```

### 3. View in Dashboard

1. Login as admin
2. Navigate to the Routers/Dashboard tab
3. You'll see two sections:
   - **📡 UniFi Access Points - Online/Offline**
   - **🟢 Regular Routers - Online/Offline**

## Testing

### Run Integration Test

```powershell
python test_unifi_integration.py
```

This will:
1. Start the UniFi API server (if not running)
2. Test all endpoints
3. Display mock data
4. Provide next steps

### Manual Testing

1. **Check UniFi API:**
   ```powershell
   curl http://localhost:5001/api/unifi/devices
   ```

2. **Check bandwidth total:**
   ```powershell
   curl http://localhost:5001/api/unifi/bandwidth/total
   ```

## Mock Data

The UniFi API server comes with mock data for testing:

### Access Points
- **Living Room AP** (UAP-AC-Pro)
  - IP: 192.168.1.2
  - Download: 120.5 Mbps
  - Upload: 30.2 Mbps

- **Bedroom AP** (UAP-AC-Lite)
  - IP: 192.168.1.3
  - Download: 80.1 Mbps
  - Upload: 20.7 Mbps

### Clients
- **Laptop** (192.168.1.100)
- **Phone** (192.168.1.101)

## Configuration

### Environment Variables

```powershell
# Set custom UniFi API URL (optional)
$env:UNIFI_API = "http://192.168.1.1:5001"

# Set main API URL (optional)
$env:WINYFI_API = "http://localhost:5000"
```

### Mock Mode

Toggle mock mode for development/testing:

```python
import requests

# Enable mock mode
requests.post('http://localhost:5001/api/unifi/mock', json={
    'routers': True,
    'bandwidth': True,
    'clients': True
})

# Disable for real UniFi controller
requests.post('http://localhost:5001/api/unifi/mock', json={
    'routers': False,
    'bandwidth': False,
    'clients': False
})
```

## Connecting to Real UniFi Controller

To connect to a real UniFi controller, update `server/unifi_api.py`:

1. Set `MOCK_MODE` to `False` for production
2. Update `CONTROLLER_URL` to your UniFi controller IP
3. Update `USERNAME` and `PASSWORD` credentials
4. Update `SITE` if not using 'default'

```python
# In server/unifi_api.py
CONTROLLER_URL = "https://192.168.1.1:8443"  # Your UniFi controller
USERNAME = "admin"
PASSWORD = "your_password"
SITE = "default"
```

## Troubleshooting

### UniFi devices not showing up

1. **Check if UniFi API server is running:**
   ```powershell
   curl http://localhost:5001/api/unifi/devices
   ```

2. **Check server logs:**
   - Look for connection errors
   - Verify mock mode is enabled for testing

3. **Verify API URL in dashboard:**
   - Default is `http://localhost:5001`
   - Check `unifi_api_url` parameter

### Bandwidth not updating

- UniFi devices show static bandwidth from API
- Regular routers use ping-based monitoring
- Check if devices are online

### Cards not displaying correctly

1. Refresh the routers tab
2. Check for JavaScript/Python errors in console
3. Verify database connection for regular routers

## Future Enhancements

- [ ] Auto-refresh UniFi data every 5 seconds
- [ ] Client viewer popup for UniFi devices
- [ ] Historical bandwidth graphs for UniFi APs
- [ ] Alert notifications for UniFi device offline
- [ ] Integration with UniFi Network application API
- [ ] Support for multiple UniFi sites
- [ ] UniFi device settings/configuration panel

## Support

For issues or questions:
1. Check the logs in `winyfi_error.log`
2. Verify both API servers are running
3. Test endpoints individually using curl/requests
4. Check network connectivity to UniFi controller

## References

- [UniFi Controller API Documentation](https://ubntwiki.com/products/software/unifi-controller/api)
- [Original Integration Suggestions](UNIFI_DASHBOARD_INTEGRATION_SUGGESTIONS.md)
- [UniFi Test Client](unifi_test.py)
