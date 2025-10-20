# Routers Tab Auto-Refresh Implementation

## Overview
The routers tab now features intelligent auto-refresh that automatically detects new UniFi Access Points discovered by the UniFi API without causing UI glitches or performance degradation.

## Features

### 1. Smart Auto-Refresh
- **Interval**: 30 seconds (configurable via `routers_refresh_interval`)
- **Background Check**: Runs device discovery in a background thread
- **Conditional Updates**: Only updates UI when changes are detected
- **Non-Blocking**: Never freezes the UI during checks

### 2. Manual Refresh Button
- **Location**: Top-right of routers tab header
- **Functionality**: Immediate refresh on demand
- **Spam Protection**: Button disabled during refresh to prevent multiple simultaneous refreshes
- **Visual Feedback**: Button text changes to "⏳ Refreshing..." during operation

### 3. Auto-Refresh Toggle
- **Location**: Top-left of routers tab header, next to "All Routers" title
- **State Persistence**: Enabled by default
- **Real-Time Control**: Can be toggled on/off without restarting the app
- **Visual Indicator**: Shows current auto-refresh state

### 4. Last Update Timestamp
- **Location**: Next to auto-refresh toggle
- **Format**: "Last updated: HH:MM:SS" or "Last checked: HH:MM:SS"
- **Reasons**: Shows why refresh occurred (e.g., "Found 2 new device(s)", "Manual refresh")
- **Updates**: Automatically updates on each refresh

## Technical Implementation

### Architecture

```
User Action/Timer
    ↓
toggle_routers_auto_refresh() / _auto_refresh_routers()
    ↓
Background Thread: Check for changes
    ↓
Compare DB routers vs UniFi devices
    ↓
New devices detected?
    ↓ Yes                    ↓ No
_perform_routers_refresh()   Update timestamp only
    ↓
reload_routers()
    ↓
Smart UI Update (only rebuild if needed)
```

### Key Methods

#### `start_routers_auto_refresh()`
Starts the auto-refresh timer using `root.after()`.

```python
def start_routers_auto_refresh(self):
    if not self.app_running:
        return
    if self.routers_refresh_job:
        self.root.after_cancel(self.routers_refresh_job)
    self.routers_refresh_job = self.root.after(self.routers_refresh_interval, self._auto_refresh_routers)
```

#### `_auto_refresh_routers()`
Background check for changes without blocking UI.

```python
def _auto_refresh_routers(self):
    # Prevent overlapping refreshes
    if self.is_refreshing_routers:
        return
    
    # Background thread checks for new devices
    def background_check():
        unifi_devices = self._fetch_unifi_devices()
        db_routers = get_routers()
        
        # Compare MAC addresses to detect new devices
        db_macs = {r.get('mac_address') for r in db_routers}
        unifi_macs = {d.get('mac_address') for d in unifi_devices}
        new_devices = unifi_macs - db_macs
        
        # Only update UI if changes detected
        if new_devices or len(db_routers) != len(self.router_widgets):
            self.root.after(0, lambda: self._perform_routers_refresh(f"Found {len(new_devices)} new device(s)"))
```

#### `_perform_routers_refresh(reason="")`
Performs actual UI refresh on main thread.

```python
def _perform_routers_refresh(self, reason=""):
    self.is_refreshing_routers = True
    try:
        self.reload_routers(force_reload=False)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.routers_last_update_label.config(text=f"Last updated: {timestamp} ({reason})")
    finally:
        self.is_refreshing_routers = False
```

#### `manual_refresh_routers()`
Manual refresh triggered by button click.

```python
def manual_refresh_routers(self):
    if self.is_refreshing_routers:
        return
    
    self.refresh_routers_btn.config(state="disabled", text="⏳ Refreshing...")
    
    def do_refresh():
        try:
            self._perform_routers_refresh("Manual refresh")
        finally:
            self.root.after(0, lambda: self.refresh_routers_btn.config(state="normal", text="🔄 Refresh"))
    
    threading.Thread(target=do_refresh, daemon=True).start()
```

### Anti-Glitch Mechanisms

#### 1. Overlap Prevention
```python
self.is_refreshing_routers = False  # Flag to prevent overlapping refreshes

if self.is_refreshing_routers:
    return  # Skip refresh if already in progress
```

#### 2. Smart UI Rebuild
The `reload_routers()` method only rebuilds UI when necessary:

```python
prev_ids = set(self.router_widgets.keys())
new_ids = set(r['id'] for r in all_devices if r.get('id'))
filtered_ids = set(r['id'] for r in (online + offline))

needs_rebuild = prev_ids != filtered_ids

if needs_rebuild:
    # Clear and rebuild UI
else:
    # Keep existing UI, just update data
```

#### 3. Background Processing
All expensive operations (API calls, database queries) run in background threads:

```python
threading.Thread(target=background_check, daemon=True).start()
```

#### 4. Debounced Card Rendering
Card layout updates are debounced by 300ms to prevent rapid re-renders:

```python
def on_resize(event):
    if sec._resize_job:
        sec.after_cancel(sec._resize_job)
    sec._resize_job = sec.after(300, render_cards)
```

## Configuration

### Adjustable Settings

Located in `Dashboard.__init__()`:

```python
# Routers tab auto-refresh settings
self.routers_refresh_job = None
self.routers_refresh_interval = 30000  # 30 seconds (in milliseconds)
self.is_refreshing_routers = False
```

### Changing Refresh Interval

To change the refresh interval, modify the `routers_refresh_interval` value:

```python
self.routers_refresh_interval = 60000  # 60 seconds
self.routers_refresh_interval = 15000  # 15 seconds
```

## User Experience

### Normal Operation
1. User opens the app → Auto-refresh starts automatically
2. Every 30 seconds → Background check for new UniFi devices
3. No changes detected → Timestamp updates: "Last checked: HH:MM:SS"
4. New device found → UI refreshes smoothly, timestamp shows: "Last updated: HH:MM:SS (Found 1 new device(s))"

### Manual Refresh
1. User clicks "🔄 Refresh" button
2. Button disables and shows "⏳ Refreshing..."
3. Refresh completes → Button re-enables
4. Timestamp updates: "Last updated: HH:MM:SS (Manual refresh)"

### Toggle Auto-Refresh
1. User unchecks "Auto-refresh" toggle
2. Auto-refresh timer stops
3. Console shows: "⏸️ Routers auto-refresh paused"
4. User re-checks toggle → Auto-refresh resumes
5. Console shows: "✅ Routers auto-refresh enabled"

## Benefits

### 1. No UI Glitches
- Smart rebuild logic prevents unnecessary UI destruction
- Overlapping refresh prevention
- Debounced resize handling

### 2. Performance
- Background thread processing
- Conditional UI updates (only when needed)
- Efficient MAC address comparison using sets

### 3. User Control
- Toggle auto-refresh on/off
- Manual refresh button
- Visual feedback at all times

### 4. Automatic Discovery
- New UniFi APs automatically detected
- No manual refresh required
- Database automatically updated via `upsert_unifi_router()`

## Integration with Existing Systems

### UniFi Auto-Discovery
Works seamlessly with the existing UniFi auto-discovery system:
- `_fetch_unifi_devices()` fetches devices from UniFi API
- `upsert_unifi_router()` adds/updates devices in database
- `reload_routers()` displays devices in UI

### Background Status Updater
Runs independently of the status monitoring thread:
- `_background_status_updater()` monitors router status
- `start_routers_auto_refresh()` checks for new devices
- Both update `self.status_history` and `self.router_widgets`

### Bandwidth Tab
Auto-refresh also benefits the bandwidth tab:
- New routers appear in bandwidth monitoring
- Background bandwidth updater automatically picks up new devices
- Charts update to include new devices

## Cleanup on Exit

Auto-refresh is properly stopped when the app closes:

```python
def on_close(self):
    self.app_running = False
    try:
        self.stop_routers_auto_refresh()
    except Exception:
        pass
```

## Troubleshooting

### Issue: UI still glitches during refresh
**Solution**: Check `needs_rebuild` logic in `reload_routers()`. Ensure only necessary rebuilds occur.

### Issue: Auto-refresh not working
**Solution**: 
1. Check that `self.routers_auto_refresh_var.get()` returns `True`
2. Verify `self.app_running` is `True`
3. Check console for error messages

### Issue: Overlapping refreshes
**Solution**: The `is_refreshing_routers` flag should prevent this. If it occurs:
1. Check that flag is properly set/unset in try-finally blocks
2. Verify background threads are daemon threads

### Issue: Performance degradation
**Solution**:
1. Increase `routers_refresh_interval` to reduce frequency
2. Check UniFi API response times
3. Verify database connection is healthy

## Future Enhancements

Potential improvements for consideration:

1. **Adaptive Refresh Interval**: Automatically adjust interval based on activity
2. **Progressive Loading**: Load visible routers first, then off-screen ones
3. **Differential Updates**: Only update changed router cards, not entire sections
4. **Refresh Statistics**: Track refresh performance and display to admin
5. **Notification on Discovery**: Show toast notification when new devices found

## Summary

The routers tab auto-refresh system provides:
✅ Automatic detection of new UniFi devices
✅ Smooth, glitch-free UI updates
✅ User-controlled refresh behavior
✅ Performance-optimized background processing
✅ Visual feedback and transparency
✅ Proper cleanup on exit

Users can now leave the app running and new UniFi APs will be automatically discovered and displayed without any manual intervention or UI disruptions.
