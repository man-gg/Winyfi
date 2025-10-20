# Routers Tab Auto-Refresh - Implementation Summary

## Changes Made

### 1. Dashboard UI Updates (`dashboard.py` lines ~887-940)

#### Added to Router Header:
- **Auto-refresh toggle checkbox**: 
  - Variable: `self.routers_auto_refresh_var` (BooleanVar, default=True)
  - Widget: `self.routers_auto_refresh_check` (Checkbutton)
  - Command: `toggle_routers_auto_refresh()`
  - Style: "success-round-toggle"

- **Last update timestamp label**:
  - Widget: `self.routers_last_update_label`
  - Displays: "Last updated: HH:MM:SS (reason)" or "Last checked: HH:MM:SS"
  - Updates on every refresh or check

- **Manual refresh button**:
  - Widget: `self.refresh_routers_btn`
  - Text: "🔄 Refresh"
  - Command: `manual_refresh_routers()`
  - Bootstyle: "primary"
  - Disables during refresh to prevent spam

### 2. Initialization Variables (`dashboard.py` lines ~81-99)

Added to `Dashboard.__init__()`:
```python
# Routers tab auto-refresh settings
self.routers_refresh_job = None
self.routers_refresh_interval = 30000  # 30 seconds default
self.is_refreshing_routers = False  # Prevent overlapping refreshes
```

### 3. Auto-Refresh Methods (`dashboard.py` lines ~705-815)

#### New Methods Added:

1. **`toggle_routers_auto_refresh()`**
   - Toggles auto-refresh on/off based on checkbox state
   - Prints status to console

2. **`start_routers_auto_refresh()`**
   - Starts the auto-refresh timer
   - Cancels any existing job first
   - Schedules `_auto_refresh_routers()` after interval

3. **`stop_routers_auto_refresh()`**
   - Stops the auto-refresh timer
   - Cancels scheduled job

4. **`_auto_refresh_routers()`**
   - Main auto-refresh logic
   - Runs in background thread
   - Compares UniFi devices with DB routers
   - Detects new devices by comparing MAC addresses
   - Only triggers UI update if changes detected
   - Reschedules itself for next interval

5. **`_perform_routers_refresh(reason="")`**
   - Executes UI refresh on main thread
   - Calls `reload_routers(force_reload=False)`
   - Updates timestamp label with reason
   - Uses `is_refreshing_routers` flag to prevent overlaps

6. **`manual_refresh_routers()`**
   - Handles manual refresh button click
   - Disables button during refresh
   - Runs refresh in background thread
   - Re-enables button when complete

### 4. Startup Integration (`dashboard.py` lines ~117-135)

Added after UI build:
```python
# Start routers tab auto-refresh
self.start_routers_auto_refresh()
```

### 5. Cleanup on Exit (`dashboard.py` lines ~10900-10920)

Added to `on_close()`:
```python
try:
    self.stop_routers_auto_refresh()
except Exception:
    pass
```

## How It Works

### Auto-Refresh Flow

```
Timer (30s) → _auto_refresh_routers()
    ↓
Background Thread:
    1. Fetch UniFi devices via _fetch_unifi_devices()
    2. Get DB routers via get_routers()
    3. Compare MAC addresses (set operations)
    4. Calculate new_devices = unifi_macs - db_macs
    ↓
Changes detected? (new devices OR widget count mismatch)
    ↓ YES                           ↓ NO
UI Update                      Timestamp Update Only
    ↓                                ↓
_perform_routers_refresh()     "Last checked: HH:MM:SS"
    ↓
reload_routers()
    ↓
Smart UI rebuild (only if needed)
    ↓
"Last updated: HH:MM:SS (Found N new device(s))"
```

### Smart UI Rebuild Logic

The existing `reload_routers()` method already has intelligent rebuild logic:

```python
prev_ids = set(self.router_widgets.keys())
new_ids = set(r['id'] for r in all_devices if r.get('id'))
filtered_ids = set(r['id'] for r in (online + offline))

needs_rebuild = prev_ids != filtered_ids

if needs_rebuild:
    # Only rebuild UI if router IDs changed
    for w in self.scrollable_frame.winfo_children():
        w.destroy()
    self.router_widgets.clear()
```

This prevents unnecessary UI destruction and reconstruction.

## Anti-Glitch Features

### 1. Overlap Prevention
```python
if self.is_refreshing_routers:
    return  # Skip if already refreshing
```

### 2. Background Processing
```python
threading.Thread(target=background_check, daemon=True).start()
```
All expensive operations (API calls, DB queries) run in background threads.

### 3. Conditional UI Updates
```python
if new_devices or len(db_routers) != len(self.router_widgets):
    # Only update UI if changes detected
    self._perform_routers_refresh(...)
else:
    # Just update timestamp
    self.routers_last_update_label.config(text=f"Last checked: {timestamp}")
```

### 4. Smart Rebuild
Only rebuilds UI when router IDs change, not on every refresh.

### 5. Debounced Rendering
Card layout updates debounced by 300ms:
```python
sec._resize_job = sec.after(300, render_cards)
```

## Configuration

### Adjusting Refresh Interval

In `Dashboard.__init__()`, modify:
```python
self.routers_refresh_interval = 30000  # 30 seconds (milliseconds)
```

Examples:
- 15 seconds: `self.routers_refresh_interval = 15000`
- 60 seconds: `self.routers_refresh_interval = 60000`
- 2 minutes: `self.routers_refresh_interval = 120000`

## User Interface

### Header Layout (Left to Right)

```
[All Routers] [✓ Auto-refresh] [Last updated: HH:MM:SS (reason)] ... [🔄 Loop Test] [👥 See Network Clients] [🔄 Refresh] [➕ Add Router]
```

### Visual Feedback

1. **Auto-refresh enabled**: Checkbox checked, timer running
2. **Auto-refresh disabled**: Checkbox unchecked, timer stopped
3. **Refreshing**: Button shows "⏳ Refreshing...", disabled
4. **Normal**: Button shows "🔄 Refresh", enabled

### Console Messages

- `✅ Routers auto-refresh enabled` - When toggled on
- `⏸️ Routers auto-refresh paused` - When toggled off
- `🔄 Routers refreshed at HH:MM:SS - reason` - After successful refresh
- `⏳ Refresh already in progress...` - When manual refresh blocked
- `⚠️ Error in auto-refresh check: ...` - On background error

## Benefits

### For Users
✅ No manual refresh needed for new UniFi devices
✅ Toggle control for auto-refresh behavior
✅ Manual refresh button for immediate updates
✅ Visual feedback shows system status
✅ No UI glitches or freezing

### For Performance
✅ Background thread processing
✅ Smart UI rebuild (only when needed)
✅ Efficient set operations for comparison
✅ Overlap prevention
✅ Proper cleanup on exit

### For Maintenance
✅ Configurable refresh interval
✅ Console logging for debugging
✅ Error handling at all levels
✅ Clear code organization
✅ Comprehensive documentation

## Integration Points

### Works With:
- ✅ UniFi API error handling
- ✅ UniFi auto-discovery system
- ✅ Background status updater
- ✅ Bandwidth monitoring
- ✅ Router type filter (All/UniFi/Non-UniFi)
- ✅ Search/sort functionality

### Does Not Interfere With:
- ✅ Manual router add/edit/delete operations
- ✅ Router details popup
- ✅ Connected clients display
- ✅ Loop detection system
- ✅ Notification system

## Testing Scenarios

### Scenario 1: New UniFi AP Discovered
1. Start Winyfi with auto-refresh enabled
2. UniFi API adds new AP to mock data
3. Within 30 seconds: New AP appears in routers tab
4. Timestamp shows: "Last updated: HH:MM:SS (Found 1 new device(s))"
5. No UI glitch or freeze

### Scenario 2: Manual Refresh
1. Click "🔄 Refresh" button
2. Button changes to "⏳ Refreshing..." and disables
3. Refresh completes within 2 seconds
4. Button re-enables
5. Timestamp updates: "Last updated: HH:MM:SS (Manual refresh)"

### Scenario 3: Toggle Auto-Refresh
1. Uncheck "Auto-refresh" toggle
2. Console shows: "⏸️ Routers auto-refresh paused"
3. Timer stops, no more automatic checks
4. Re-check toggle
5. Console shows: "✅ Routers auto-refresh enabled"
6. Timer resumes

### Scenario 4: No Changes Detected
1. Auto-refresh runs every 30 seconds
2. No new devices found
3. Timestamp shows: "Last checked: HH:MM:SS"
4. UI not rebuilt, no glitch

### Scenario 5: UniFi API Unavailable
1. UniFi API server stopped
2. Auto-refresh runs
3. Error handled gracefully (logged once)
4. UI shows existing routers
5. No crash or freeze

## Files Modified

1. **dashboard.py**
   - Added UI elements (lines ~887-940)
   - Added initialization variables (lines ~81-99)
   - Added 6 new methods (lines ~705-815)
   - Updated startup (lines ~117-135)
   - Updated cleanup (lines ~10900-10920)

## Documentation Created

1. **ROUTERS_AUTO_REFRESH.md** - Comprehensive feature documentation
2. **ROUTERS_AUTO_REFRESH_SUMMARY.md** - This file, implementation summary

## Next Steps (Optional Enhancements)

1. **Settings UI**: Add refresh interval to settings page
2. **Statistics**: Track refresh performance and display to admin
3. **Notifications**: Show toast when new devices discovered
4. **Adaptive Interval**: Adjust interval based on activity
5. **Progressive Loading**: Load visible routers first

## Summary

The routers tab now features intelligent auto-refresh that:
- ✅ Automatically detects new UniFi APs every 30 seconds
- ✅ Updates UI smoothly without glitches
- ✅ Provides user control (toggle + manual button)
- ✅ Shows visual feedback (timestamp + status)
- ✅ Handles errors gracefully
- ✅ Integrates seamlessly with existing systems

Users can now leave the app running and new UniFi devices will appear automatically! 🎉
