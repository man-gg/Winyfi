# UniFi Auto-Discovery Update

## Overview
Updated `reload_routers()` method to automatically discover and add new UniFi Access Points to the routers tab.

## Changes Made

### 1. Modified `reload_routers()` Method
**File:** `dashboard.py`

**Key Changes:**
- **Fetch Order Changed**: Now fetches UniFi devices FIRST, then DB routers
  - This ensures new devices are added to the database before the UI is built
  - Previous order: DB routers → UniFi devices
  - New order: UniFi devices → DB routers

- **Comment Updated**: Clarified that `_fetch_unifi_devices()` adds new devices via `upsert_unifi_router()`

### 2. Enhanced `_fetch_unifi_devices()` Method
**File:** `dashboard.py`

**New Features:**
- **Pre-fetch Existing MACs**: Queries database for existing UniFi device MAC addresses before processing
- **New Device Detection**: Compares API devices against existing MACs to detect new additions
- **Enhanced Logging**: 
  - Shows total devices found from API
  - Alerts when new devices are discovered with details (name, MAC, IP)
  - Confirms how many new devices were added
  - Shows error messages if UniFi API is unavailable

**Example Console Output:**
```
📡 Found 3 UniFi device(s) from API
✨ New UniFi device discovered: Kitchen AP (MAC: AA:BB:CC:DD:EE:12, IP: 192.168.1.24)
🎉 Added 1 new UniFi device(s) to the database and routers tab
```

### 3. Data Flow

```
1. User opens Routers tab or refreshes
   ↓
2. reload_routers() is called
   ↓
3. _fetch_unifi_devices() queries UniFi API
   ↓
4. For each device from API:
   - Check if MAC exists in database
   - If NEW: Mark as new device
   - Call upsert_unifi_router() to add/update in DB
   - Log bandwidth data
   ↓
5. Fetch all routers from database (includes new UniFi devices)
   ↓
6. Merge UniFi API data with DB data
   ↓
7. Display all devices in UI with proper status/badges
```

## How It Works

### New Device Detection
1. Before processing UniFi devices, query all existing UniFi MAC addresses from DB
2. For each device from API, check if MAC is in the existing set
3. If not found → mark as new device
4. `upsert_unifi_router()` adds it to the database
5. Console logs the discovery with device details

### Automatic Integration
- New devices automatically appear in the routers tab
- UniFi badge (📡) is shown on device cards
- Device status is checked and displayed
- Bandwidth data is logged automatically
- All standard router features work immediately

## Benefits

✅ **Automatic Discovery**: No manual intervention needed to add new UniFi APs
✅ **Real-time Updates**: New devices appear on next tab refresh
✅ **Status Tracking**: New devices immediately start status monitoring
✅ **Bandwidth Logging**: Throughput data collected from the first detection
✅ **User Visibility**: Console logs provide clear feedback on discovery events
✅ **Database Integration**: All devices properly stored with MAC-based deduplication
✅ **Seamless UX**: New devices look and behave like existing routers

## Testing

### To Test New Device Discovery:
1. Start the UniFi API server with mock data
2. Open the dashboard and navigate to Routers tab
3. Edit `server/unifi_api.py` to add a new device to `MOCK_APS`
4. Refresh the Routers tab
5. Check console for discovery messages
6. Verify new device appears in the routers tab with UniFi badge

### Example Test:
```python
# Add to MOCK_APS in server/unifi_api.py
{
    "model": "UAP-AC-HD",
    "name": "Garage AP",
    "mac": "AA:BB:CC:DD:EE:99",
    "ip": "192.168.1.50",
    "xput_down": 150.0,
    "xput_up": 50.0,
    "state": 1,
    "connected": True
}
```

Expected console output:
```
📡 Found 4 UniFi device(s) from API
✨ New UniFi device discovered: Garage AP (MAC: AA:BB:CC:DD:EE:99, IP: 192.168.1.50)
🎉 Added 1 new UniFi device(s) to the database and routers tab
```

## Technical Notes

- Uses `upsert_unifi_router()` which handles insert/update logic based on MAC address
- MAC address is the unique identifier for UniFi devices
- Controller-managed fields (IP, brand) are updated on each refresh
- User-editable fields (name, location, image) are preserved in DB
- No duplicate devices can be created (MAC-based deduplication)
- Error handling ensures app continues if UniFi API is unavailable

## Files Modified
- `dashboard.py` - `reload_routers()` method
- `dashboard.py` - `_fetch_unifi_devices()` method

## Dependencies
- `router_utils.upsert_unifi_router()` - Handles database insert/update
- `db.get_connection()` - Database connection for MAC lookup
- UniFi API server running on configured URL (default: http://localhost:5001)
