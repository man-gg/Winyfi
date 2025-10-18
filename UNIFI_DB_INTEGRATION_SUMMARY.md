# UniFi Database Integration - Summary

## What Changed?

UniFi devices are now **automatically saved to the database** instead of only existing in memory. They are stored in the same `routers` table as regular routers.

## Key Changes

### 1. **router_utils.py** - New Function
```python
upsert_unifi_router(name, ip, mac, brand, location, image_path=None)
```
- Inserts new UniFi devices or updates existing ones (based on MAC address)
- Returns the database-assigned router ID
- Updates `last_seen` timestamp on each save

### 2. **dashboard.py** - Modified `_fetch_unifi_devices()`
- Now calls `upsert_unifi_router()` for each device
- Saves all UniFi devices to database during fetch
- Uses real database ID instead of temporary "unifi_xxx" ID

### 3. **dashboard.py** - Modified `reload_routers()`
- Fetches UniFi devices (saves to DB)
- Reloads complete router list from database (includes UniFi devices)
- Marks UniFi devices with `is_unifi=True` flag
- Adds live bandwidth data from API
- No more duplicate lists

## Database Schema

UniFi devices in `routers` table:

| Column       | Example Value                      |
|--------------|------------------------------------|
| id           | 15 (auto-increment)                |
| name         | "Office AP"                        |
| ip_address   | "192.168.1.105"                    |
| mac_address  | "00:11:22:33:44:55"                |
| brand        | "UniFi"                            |
| location     | "UAP-AC-PRO"                       |
| last_seen    | "2025-10-16 14:30:25"              |
| image_path   | NULL                               |

## Benefits

✅ **Persistent** - Devices survive app restarts  
✅ **Unified** - All devices in one table  
✅ **History** - Status logs work for UniFi devices  
✅ **Reports** - Included in exports and reports  
✅ **No Duplicates** - MAC address prevents duplicates  
✅ **Auto-Update** - `last_seen` updated every 10 seconds  

## How It Works

1. **Every 10 seconds**: Dashboard fetches UniFi devices from API
2. **For each device**: `upsert_unifi_router()` saves/updates in database
3. **Reload UI**: Fetches all routers from database (includes UniFi)
4. **Identify UniFi**: Checks `brand='UniFi'` to mark as UniFi device
5. **Add bandwidth**: Attaches live bandwidth data from API

## Visual Identification

UniFi devices still have:
- 📡 Icon (instead of 🌐)
- Blue card styling (instead of red)
- "UniFi" brand label
- Bandwidth displayed from API

## Testing

### Quick Test:
```powershell
# Start UniFi API server
python start_unifi_server.py

# Run test script
python test_unifi_database.py

# Start dashboard
python main.py
```

### Verify in Database:
```sql
SELECT * FROM routers WHERE brand = 'UniFi';
```

### Expected Results:
- UniFi devices appear in database immediately
- `last_seen` updates every 10 seconds
- No duplicates created on refresh
- Devices persist after dashboard restart

## Notes

- **Unique Key**: MAC address prevents duplicate entries
- **Auto-Sync**: Devices auto-update from API every 10 seconds
- **Manual Control**: Can edit/delete UniFi devices like regular routers
- **Status Logs**: UniFi device status changes logged to `router_status_log`
- **Reports**: UniFi devices included in uptime and bandwidth reports

## Rollback (if needed)

To revert to memory-only UniFi devices:

1. Restore old `_fetch_unifi_devices()` without `upsert_unifi_router()` call
2. Restore old `reload_routers()` with `all_devices = self.router_list + self.unifi_devices`
3. Delete UniFi devices from database: `DELETE FROM routers WHERE brand = 'UniFi'`
