# Quick Test Guide - Routers Tab Auto-Refresh

## Prerequisites
1. Winyfi application running
2. UniFi API server running on `http://localhost:5001`
3. Database connected and healthy

## Test 1: Auto-Refresh Enabled by Default
**Expected**: Auto-refresh checkbox is checked when app starts

**Steps**:
1. Start Winyfi application
2. Navigate to "Routers" tab
3. Look at header section

**Verify**:
- ✅ "Auto-refresh" checkbox is checked
- ✅ "Last checked:" timestamp appears within 30 seconds
- ✅ Console shows: "✅ Routers auto-refresh enabled" (or similar)

---

## Test 2: Manual Refresh Button
**Expected**: Button refreshes routers immediately

**Steps**:
1. On Routers tab, click "🔄 Refresh" button
2. Observe button behavior

**Verify**:
- ✅ Button text changes to "⏳ Refreshing..."
- ✅ Button is disabled during refresh
- ✅ Routers list updates
- ✅ Timestamp shows "Last updated: HH:MM:SS (Manual refresh)"
- ✅ Button returns to "🔄 Refresh" and re-enables
- ✅ No UI glitch or freeze

---

## Test 3: Auto-Refresh Toggle Off
**Expected**: Auto-refresh stops when toggled off

**Steps**:
1. Uncheck the "Auto-refresh" checkbox
2. Wait 35+ seconds

**Verify**:
- ✅ Console shows: "⏸️ Routers auto-refresh paused"
- ✅ Timestamp does NOT update automatically
- ✅ Manual refresh button still works
- ✅ Routers still display correctly

---

## Test 4: Auto-Refresh Toggle On
**Expected**: Auto-refresh resumes when toggled back on

**Steps**:
1. Check the "Auto-refresh" checkbox (if unchecked)
2. Wait 35 seconds

**Verify**:
- ✅ Console shows: "✅ Routers auto-refresh enabled"
- ✅ Timestamp updates automatically
- ✅ No errors in console

---

## Test 5: New UniFi Device Discovery
**Expected**: New UniFi AP appears automatically

**Steps**:
1. Ensure auto-refresh is enabled
2. Add a new UniFi device to the mock data in `server/unifi_api.py`:
   ```python
   MOCK_APS.append({
       "mac_address": "aa:bb:cc:dd:ee:ff",
       "name": "Test AP",
       "ip_address": "192.168.1.200",
       "model": "U6-Lite",
       "xput_down": 50.0,
       "xput_up": 25.0
   })
   ```
3. Wait up to 30 seconds

**Verify**:
- ✅ New AP appears in routers tab automatically
- ✅ Timestamp shows "Last updated: HH:MM:SS (Found 1 new device(s))"
- ✅ No UI glitch
- ✅ Console shows: "🔄 Routers refreshed at HH:MM:SS - Found 1 new device(s)"

---

## Test 6: No Changes Detected
**Expected**: Timestamp updates but UI doesn't rebuild

**Steps**:
1. Ensure auto-refresh is enabled
2. Don't add any new routers
3. Wait for multiple refresh cycles (90+ seconds)

**Verify**:
- ✅ Timestamp shows "Last checked: HH:MM:SS" (not "updated")
- ✅ No UI rebuilding/flashing
- ✅ Routers remain stable
- ✅ No console errors

---

## Test 7: UniFi API Unavailable
**Expected**: Graceful handling of API errors

**Steps**:
1. Stop the UniFi API server (`Ctrl+C` in server terminal)
2. Wait for auto-refresh cycle (30 seconds)

**Verify**:
- ✅ No application crash
- ✅ Existing routers still visible
- ✅ Console shows error (once): "⚠️ Cannot connect to UniFi API server..."
- ✅ UI remains responsive

---

## Test 8: Prevent Overlapping Refreshes
**Expected**: Multiple refresh requests don't overlap

**Steps**:
1. Click "🔄 Refresh" button rapidly 5 times
2. Observe behavior

**Verify**:
- ✅ Only one refresh executes
- ✅ Button stays disabled until complete
- ✅ Console may show: "⏳ Refresh already in progress..."
- ✅ No UI corruption or errors

---

## Test 9: Filter Interaction
**Expected**: Auto-refresh works with type filters

**Steps**:
1. Enable auto-refresh
2. Set Type filter to "UniFi"
3. Wait 35 seconds
4. Change Type filter to "Non-UniFi"
5. Wait 35 seconds

**Verify**:
- ✅ Auto-refresh continues to work
- ✅ Timestamp updates appropriately
- ✅ Filtered routers display correctly
- ✅ No errors in console

---

## Test 10: Cleanup on Exit
**Expected**: Auto-refresh stops cleanly when app closes

**Steps**:
1. Ensure auto-refresh is enabled
2. Close the application (X button or File → Exit)
3. Click "Yes" on confirmation dialog

**Verify**:
- ✅ Application closes without errors
- ✅ No orphaned threads or processes
- ✅ Console shows clean shutdown

---

## Performance Tests

### Test 11: Long-Running Stability
**Expected**: Auto-refresh runs reliably for extended periods

**Steps**:
1. Start application with auto-refresh enabled
2. Leave running for 1+ hour
3. Periodically check timestamp updates

**Verify**:
- ✅ Timestamp continues updating every 30 seconds
- ✅ No memory leaks (use Task Manager)
- ✅ UI remains responsive
- ✅ No accumulated errors in console

---

### Test 12: UI Responsiveness During Refresh
**Expected**: UI never freezes during refresh

**Steps**:
1. Trigger manual refresh
2. Immediately interact with UI (click buttons, scroll, etc.)

**Verify**:
- ✅ UI responds immediately to interactions
- ✅ No "Not Responding" message
- ✅ Smooth scrolling and clicking

---

## Regression Tests

### Test 13: Manual Router Operations Still Work
**Expected**: Add/edit/delete routers work normally

**Steps**:
1. With auto-refresh enabled, perform:
   - Add a new router
   - Edit an existing router
   - Delete a router

**Verify**:
- ✅ All operations complete successfully
- ✅ Changes persist after auto-refresh
- ✅ No conflicts or errors

---

### Test 14: Other Tabs Not Affected
**Expected**: Dashboard and other tabs function normally

**Steps**:
1. With auto-refresh enabled on Routers tab
2. Switch to Dashboard tab
3. Switch to Bandwidth tab
4. Switch back to Routers tab

**Verify**:
- ✅ All tabs load correctly
- ✅ No errors when switching tabs
- ✅ Routers tab timestamp still updating
- ✅ No performance degradation

---

## Console Output Reference

### Expected Console Messages

**On Startup**:
```
(No message - auto-refresh starts silently)
```

**On Toggle ON**:
```
✅ Routers auto-refresh enabled
```

**On Toggle OFF**:
```
⏸️ Routers auto-refresh paused
```

**On Successful Refresh (changes detected)**:
```
🔄 Routers refreshed at 14:23:45 - Found 1 new device(s)
```

**On Check (no changes)**:
```
(No message - silent check)
```

**On Manual Refresh**:
```
🔄 Routers refreshed at 14:25:10 - Manual refresh
```

**On Error (UniFi API unavailable)**:
```
⚠️ Cannot connect to UniFi API server. Please check if server is running.
```

**On Overlapping Refresh Attempt**:
```
⏳ Refresh already in progress...
```

---

## Troubleshooting

### Issue: Auto-refresh not working
**Check**:
1. Is checkbox checked?
2. Is `self.app_running` True?
3. Any errors in console?
4. Is UniFi API server running?

### Issue: UI glitching during refresh
**Check**:
1. Is `needs_rebuild` logic working correctly?
2. Are multiple refreshes overlapping? (Check `is_refreshing_routers`)
3. Database connection healthy?

### Issue: Timestamp not updating
**Check**:
1. Console for errors
2. Is timer still running? (Check `self.routers_refresh_job`)
3. Is auto-refresh checkbox checked?

### Issue: New devices not appearing
**Check**:
1. Is UniFi API server returning new devices?
2. Are MAC addresses unique?
3. Is database accepting new routers?
4. Console for errors

---

## Success Criteria

All tests should pass with:
- ✅ No application crashes
- ✅ No UI glitches or freezing
- ✅ No console errors (except expected API unavailable messages)
- ✅ Smooth, responsive UI at all times
- ✅ Automatic discovery of new UniFi devices
- ✅ Proper cleanup on exit

If any test fails, check:
1. Error messages in console
2. Database connection
3. UniFi API server status
4. Code changes for typos or logic errors
