# UniFi Database Integration

## Overview
UniFi devices are now automatically saved to the database `routers` table, making them persistent and treating them like regular routers.

## Changes Made

### 1. New Function in `router_utils.py`
Added `upsert_unifi_router()` function that:
- Checks if a UniFi device already exists in the database (by MAC address)
- Updates existing devices or inserts new ones
- Updates the `last_seen` timestamp on each fetch
- Returns the router ID from the database

### 2. Modified `_fetch_unifi_devices()` in `dashboard.py`
Now saves UniFi devices to database:
- Fetches devices from UniFi API
- Calls `upsert_unifi_router()` for each device
- Uses the database-assigned router ID instead of temporary ID
- Devices are saved with:
  - `name`: Device name from UniFi
  - `ip_address`: IP address
  - `mac_address`: MAC address (unique identifier)
  - `brand`: 'UniFi'
  - `location`: Device model (e.g., "UAP-AC-PRO")
  - `last_seen`: Current timestamp
  - `image_path`: NULL

### 3. Modified `reload_routers()` in `dashboard.py`
Changed to avoid duplicates:
- Fetches UniFi devices (which updates database)
- Reloads router list from database (now includes UniFi devices)
- Marks UniFi devices by checking `brand='UniFi'`
- Adds bandwidth data from API to UniFi devices
- No longer combines two separate lists

## Database Structure

UniFi devices are stored in the `routers` table with these columns:

| Column       | Value for UniFi Devices           |
|--------------|-----------------------------------|
| id           | Auto-incrementing database ID     |
| name         | Device name (e.g., "Office AP")   |
| ip_address   | IP address from UniFi API         |
| mac_address  | MAC address (unique identifier)   |
| brand        | 'UniFi'                           |
| location     | Device model (e.g., "UAP-AC-PRO") |
| last_seen    | Updated every 10 seconds          |
| image_path   | NULL (no images for UniFi)        |

## Benefits

1. **Persistence**: UniFi devices survive application restarts
2. **History**: Status logs and history work for UniFi devices
3. **Unified Management**: UniFi devices appear alongside regular routers
4. **Export Support**: UniFi devices included in CSV exports
5. **Reports**: UniFi devices included in uptime reports
6. **Duplicate Prevention**: MAC address ensures no duplicates

## Behavior

- **Auto-Update**: Every 10 seconds, UniFi devices are fetched and updated in database
- **Identification**: UniFi devices marked by `brand='UniFi'` or `is_unifi=True` flag
- **Visual Distinction**: Still shown with blue cards and 📡 icon in UI
- **Bandwidth**: Live bandwidth data from UniFi API added to database records
- **Status**: UniFi devices show as online when present in API response

## Testing

To verify UniFi devices are in database:

1. Start UniFi API server:
   ```powershell
   python start_unifi_server.py
   ```

2. Start dashboard:
   ```powershell
   python main.py
   ```

3. Check database:
   ```sql
   SELECT id, name, ip_address, mac_address, brand, location, last_seen 
   FROM routers 
   WHERE brand = 'UniFi';
   ```

4. Verify:
   - UniFi devices appear in routers list
   - `last_seen` updates every 10 seconds
   - Devices persist after restarting dashboard
   - No duplicate entries (MAC address is unique)

## Notes

- MAC address is used as the unique identifier for UniFi devices
- If a UniFi device's name or IP changes, it will be updated in the database
- Removing a device from UniFi controller won't automatically delete it from database
- Manual deletion is possible through the UI (Edit/Delete buttons)
- UniFi devices can be exported to CSV like regular routers
