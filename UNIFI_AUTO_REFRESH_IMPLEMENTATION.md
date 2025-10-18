# UniFi Auto-Refresh Implementation with Ping

This document describes the auto-refresh functionality added for UniFi API integration in the dashboard, including ping-based status monitoring.

## Overview

The dashboard now automatically refreshes UniFi device data from the UniFi API server, pings each device to verify connectivity, and displays UniFi Access Points alongside regular routers with real-time updates.

## Features Implemented

### 1. **Auto-Refresh in `reload_routers`**
- UniFi devices are fetched from the API every 10 seconds
- **Each device is pinged to verify online status**
- Devices are merged with regular routers in the router list
- UniFi devices show distinct visual styling (primary blue cards)
- UniFi devices display live bandwidth data from API + latency from ping
- Auto-refresh starts automatically when viewing the routers page
- Online/Offline status based on ping response

### 2. **Auto-Refresh in `open_router_details`**
- Router details window refreshes every 3 seconds
- For UniFi devices: fetches fresh data from API + pings device
- For regular routers: uses existing status history and bandwidth data
- Displays real-time latency from ping
- Shows appropriate information based on device type

### 3. **Ping-Based Status Monitoring**
- **Every UniFi device is pinged** when fetched from API
- Ping latency is measured and displayed
- Online/Offline status determined by ping response
- Status history is updated with ping results
- Latency stored in bandwidth data for display

### 4. **Visual Indicators**
- **UniFi devices**: Blue primary-style cards with 📡 icon
- **UniFi badge**: Shows "UniFi Device" label
- **Status indicator**: 🟢 Online or 🔴 Offline based on ping
- **Latency display**: Shows ping latency in milliseconds
- **Hover effect**: Changes to green for UniFi devices
- **Details window**: Shows "UniFi Access Point" subtitle
- **No edit/delete buttons**: UniFi devices are managed by the controller

### 4. **Resource Management**
- Auto-refresh stops when user logs out
- Background thread cleanup on application exit
- Graceful handling when UniFi API is unavailable
- Ping operations use dynamic interval management
- No network congestion from excessive pings

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    Dashboard UI                                   │
│  ┌──────────────────────┐       ┌──────────────────────┐        │
│  │  📡 UniFi APs        │       │  🟢 Regular Routers   │        │
│  │  (Auto-refresh 10s)  │       │                       │        │
│  │  + Ping every fetch  │       │  Ping-based status   │        │
│  │  🟢/🔴 Status        │       │  🟢/🔴 Status        │        │
│  │  ⚡ Latency shown    │       │  ⚡ Latency shown    │        │
│  └──────────────────────┘       └──────────────────────┘        │
└──────────────────────────────────────────────────────────────────┘
           │                              │
           ▼                              ▼
  ┌─────────────────┐          ┌─────────────────────────┐
  │  UniFi API      │          │  MySQL Database         │
  │  localhost:5001 │          │  + Router Utils         │
  │                 │          │                         │
  │  Fetch device   │          │  Regular Router Data    │
  │  info + Ping    │          │  + Ping monitoring      │
  │  IP addresses   │          │                         │
  └─────────────────┘          └─────────────────────────┘
```

## Technical Details

### New Methods Added

#### `_fetch_unifi_devices()`
```python
def _fetch_unifi_devices(self):
    """Fetch UniFi devices from the UniFi API server and ping them."""
```
- Connects to `http://localhost:5001/api/unifi/devices`
- Transforms UniFi device data to match router structure
- **Pings each device to verify online status**
- **Measures latency for online devices**
- Stores ping results in `status_history`
- Stores latency in `bandwidth_data`
- Returns empty list if API is unavailable
- Adds `is_unifi: True` flag to identify UniFi devices

#### `_start_unifi_auto_refresh()`
```python
def _start_unifi_auto_refresh(self):
    """Start auto-refresh for UniFi devices."""
```
- Fetches UniFi devices
- Schedules next refresh after 10 seconds
- Uses `root.after()` for non-blocking updates

#### `_stop_unifi_auto_refresh()`
```python
def _stop_unifi_auto_refresh(self):
    """Stop auto-refresh for UniFi devices."""
```
- Cancels scheduled refresh jobs
- Called on logout

### Modified Methods

#### `__init__()`
- Added `self.unifi_api_url = "http://localhost:5001"`
- Added `self.unifi_devices = []`
- Added `self.unifi_refresh_job = None`

#### `reload_routers()`
- Fetches UniFi devices on each reload (with ping)
- Starts auto-refresh if not running
- Merges UniFi devices with regular routers
- **Sorts devices by online/offline status (based on ping)**
- Displays UniFi devices with distinct styling
- Shows live bandwidth from API + latency from ping
- Offline UniFi devices show "N/A (Offline)" for bandwidth

#### `open_router_details()`
- Detects if device is UniFi
- For UniFi: **fetches fresh data from API + pings device every 3 seconds**
- For regular routers: uses existing logic
- **Shows real-time ping latency for UniFi devices**
- Shows appropriate UI elements based on device type
- Hides edit/delete buttons for UniFi devices
- Displays online/offline status based on ping response

#### `logout()`
- Calls `_stop_unifi_auto_refresh()` to cleanup

## Configuration

### UniFi API Server
- **URL**: `http://localhost:5001`
- **Endpoint**: `/api/unifi/devices`
- **Refresh Interval**: 10 seconds (routers page)
- **Details Refresh**: 3 seconds (details window)

### Device Data Structure

UniFi devices are transformed to:
```python
{
    'id': 'unifi_{mac_address}',
    'name': 'Device Name',
    'ip_address': '192.168.1.x',
    'mac_address': 'AA:BB:CC:DD:EE:FF',
    'brand': 'UniFi',
    'location': 'Model Name',
    'is_unifi': True,
    'is_online': True/False,        # Based on ping response
    'latency': 45.2,                # Ping latency in ms (or None if offline)
    'download_speed': 120.5,        # Mbps from API
    'upload_speed': 30.2,           # Mbps from API
    'last_seen': '2025-10-16 12:00:00',
    'image_path': None
}
```

### Ping Behavior

- **Frequency**: Pings occur during each UniFi device fetch (every 10 seconds)
- **Timeout**: 1000ms (1 second) per ping
- **Dynamic Interval**: Uses the same `DynamicPingManager` as regular routers
- **Latency Storage**: Stored in `self.bandwidth_data[device_id]['latency']`
- **Status Storage**: Stored in `self.status_history[device_id]['current']`
- **Online Detection**: Device is online if ping returns latency value
- **Offline Detection**: Device is offline if ping returns None

## Usage

### Starting the UniFi API Server

1. Open a terminal in the project directory
2. Run: `python start_unifi_server.py`
3. The server will start on `http://localhost:5001`

### Viewing UniFi Devices

1. Log into the dashboard
2. Navigate to the Routers page
3. UniFi devices will appear with blue cards and 📡 icons
4. They auto-refresh every 10 seconds
5. **Online/Offline status shows based on ping response**
6. **Latency is displayed alongside bandwidth (e.g., "⚡45ms")**

### Viewing UniFi Device Details

1. Click on any UniFi device card
2. Details window shows live data
3. Auto-refreshes every 3 seconds
4. **Pings device to check status**
5. **Shows real-time latency**
6. No edit/delete buttons (managed by controller)

## Testing

### Test UniFi Integration
```bash
python test_unifi_integration.py
```

### Manual Testing Checklist

- [ ] UniFi API server is running
- [ ] UniFi devices appear in routers list
- [ ] UniFi devices have blue primary-style cards
- [ ] **UniFi devices show online/offline status based on ping**
- [ ] **Latency is displayed for online UniFi devices**
- [ ] **Offline UniFi devices show "Offline" status**
- [ ] Bandwidth data updates automatically
- [ ] Details window shows correct UniFi data
- [ ] **Details window shows real-time ping latency**
- [ ] Auto-refresh works without blocking UI
- [ ] No errors when UniFi API is offline
- [ ] Refresh stops on logout
- [ ] Regular routers still work normally
- [ ] **Ping doesn't cause network congestion**

## Troubleshooting

### UniFi Devices Not Showing

**Problem**: No UniFi devices appear in the routers list

**Solutions**:
1. Check if UniFi API server is running on port 5001
2. Verify network connectivity to localhost:5001
3. Check browser console/terminal for errors
4. Ensure mock mode is enabled in the API server

### Slow Performance

**Problem**: Dashboard is slow or unresponsive

**Solutions**:
1. Reduce refresh interval (increase timeout in `_start_unifi_auto_refresh`)
2. Check network latency to UniFi API
3. Verify API server is responding quickly

### Auto-Refresh Not Working

**Problem**: Data doesn't update automatically

**Solutions**:
1. Check if `self.unifi_refresh_job` is set
2. Verify `self.app_running` is True
3. Check for errors in the console
4. Restart the dashboard

## Future Enhancements

- [ ] Configurable refresh intervals via settings
- [ ] Pause/resume auto-refresh button
- [ ] Connection status indicator for UniFi API
- [ ] Historical bandwidth graphs for UniFi devices
- [ ] Client count and client list from UniFi
- [ ] UniFi controller health monitoring
- [ ] Multi-site support for UniFi
- [ ] Real-time alerts for UniFi devices

## Dependencies

- `requests` library for HTTP calls
- UniFi API server running on localhost:5001
- ttkbootstrap for UI components

## Notes

- UniFi devices are read-only in the dashboard
- They cannot be edited or deleted (managed by controller)
- Auto-refresh is non-blocking and doesn't freeze UI
- Gracefully handles API unavailability
- Compatible with existing router functionality
- No database changes required
