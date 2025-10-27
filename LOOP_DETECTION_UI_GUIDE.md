# 🎯 Loop Detection UI - What to Expect

## Where to See Loop Detection Status

### 1. **Main Dashboard Status Indicator** (NEW!)

**Location**: Top of dashboard, left side next to "Auto-refresh"

**What You'll See**:

```
Idle (Nothing detected):
⚪ Loop Detection: Idle

Scanning (During detection):
🔄 Loop Detection: Scanning...

Clean Network:
✅ Network Clean (Severity: 3.2)

Suspicious Activity:
🟡 Suspicious Activity (Severity: 12.4)

Loop Detected:
🔴 Loop Detected! Severity: 95.3
```

**Updates**: Real-time, every 5 minutes (detection interval)

---

### 2. **Popup Alert** (NEW!)

**When**: Loop is detected (severity > 22.5)

**What You'll See**:
```
⚠️ Network Loop Detected!

A network loop has been detected!

Severity Score: 95.3
Offending Devices: 1
Interface: Wi-Fi

Click 'Loop Test' button to view details.
```

**Action**: Click "OK" to dismiss, then click "🔄 Loop Test" button for details

---

### 3. **Loop Test Modal**

**How to Open**: Click "🔄 Loop Test" button (top right of dashboard)

**What You'll See**:

#### Status Tab:
- Real-time detection status
- Severity score
- Offenders count
- Interface information

#### Manual Scan Tab:
- Run immediate scan
- View detailed results
- Export data

#### Statistics & History Tab:
- Total detections: 5
- Loops detected: 2
- Suspicious: 1
- Clean: 2

#### History Table:
| Time | Status | Packets | Offenders | Severity |
|------|--------|---------|-----------|----------|
| 18:25:30 | ⚠️ Loop Detected | 3245 | 1 | 125.4 |
| 18:20:15 | ✅ Clean | 234 | 0 | 3.2 |

---

### 4. **Console Output**

**Location**: PowerShell terminal where you ran `python main.py`

**What You'll See**:
```
🔍 Starting multi-interface loop detection on 1 interface(s)...
  📡 Scanning interface: Wi-Fi

📊 Detection: packets=3245, offenders=1, severity=125.4, status=loop_detected
   Offending MACs: aa:bb:cc:dd:ee:ff
⚠️ LOOP DETECTED! Severity: 125.40, Offenders: 1
```

---

### 5. **Notification Badge**

**Location**: Bell icon (if you have notifications enabled)

**What You'll See**: Red badge with number of unread notifications

**Click**: Opens notification panel showing loop detection alerts

---

## Testing Loop Detection Visibility

### Quick Test:

```powershell
# Terminal 1 - Start Dashboard
python main.py
# Enable loop detection (Start Auto button in Loop Test modal)

# Terminal 2 - Run Simulator
python auto_loop_simulator.py
```

### What Should Happen (in order):

1. **Status indicator changes**:
   - ⚪ Idle → 🔄 Scanning... → 🔴 Loop Detected!

2. **Popup appears** (after ~30 seconds):
   - Alert window pops up
   - Shows severity score and details
   - You must click OK to dismiss

3. **Console shows detection**:
   - "⚠️ LOOP DETECTED!" message
   - Severity and offender details

4. **Notification badge** (if enabled):
   - Red badge appears on bell icon
   - Shows number of alerts

5. **Modal updates** (if open):
   - History table shows new detection
   - Statistics counters increment
   - Status changes to "Loop Detected"

---

## Troubleshooting UI Issues

### Issue: Status Indicator Not Updating

**Symptoms**: Shows "⚪ Idle" even after detection

**Cause**: Loop detection not enabled

**Solution**:
1. Click "🔄 Loop Test" button
2. Click "▶ Start Auto" button
3. Wait for status to change to "🔄 Scanning..."

---

### Issue: No Popup Alert

**Symptoms**: Detection happening but no alert window

**Possible Causes**:
1. Severity below threshold (need >22.5 for "loop_detected")
2. Status is "suspicious" not "loop_detected" (no popup for suspicious)
3. Already dismissed the popup

**Check**:
- Look at status indicator (shows severity score)
- Check console output for severity value
- If severity < 22.5, it's suspicious (no popup), not loop

---

### Issue: Modal Shows Old Data

**Symptoms**: Loop Test modal doesn't show latest detection

**Solution**:
1. Close the modal
2. Re-open with "🔄 Loop Test" button
3. OR click "🔄 Refresh" in the History tab

---

### Issue: Nothing Visible at All

**Symptoms**: No status changes, no detections

**Causes**:
1. Loop detection not started
2. No loops on network
3. Simulator not running

**Solutions**:
1. Enable auto-detection: Loop Test → Start Auto
2. Run simulator: `python auto_loop_simulator.py`
3. Wait 5 minutes for detection cycle
4. OR use Manual Scan for immediate results

---

## What "Suspicious" Means vs "Loop Detected"

### Suspicious (🟡):
- Severity: 7.5 - 22.5
- Light unusual traffic
- Could be normal network activity
- **No popup alert** (less intrusive)
- Console shows "🟡 SUSPICIOUS ACTIVITY"

### Loop Detected (🔴):
- Severity: > 22.5
- Clear loop indication
- **Popup alert appears**
- Console shows "⚠️ LOOP DETECTED!"
- Requires investigation

---

## Expected Behavior with Simulator

When you run `python auto_loop_simulator.py`:

**Timeline**:
- 0:00 - Simulator starts
- 0:60 - Simulator completes (sent ~2500 packets)
- 0:60-5:00 - Wait for detection cycle
- ~5:00 - Detection occurs
- ~5:01 - **Status indicator updates to 🔴**
- ~5:02 - **Popup alert appears**
- ~5:03 - **Console shows detection**
- ~5:04 - **Notification badge appears**

**OR for immediate detection**:
1. Run simulator
2. Open Loop Test modal
3. Go to Manual Scan tab
4. Click "▶ Run Manual Scan"
5. Results in 5 seconds!

---

## Summary Checklist

When loop is detected, you should see:

- [x] Status indicator changes to 🔴
- [x] Shows severity score in status
- [x] Popup alert appears (must click OK)
- [x] Console shows "⚠️ LOOP DETECTED!"
- [x] Notification badge increments
- [x] History table updates (if modal open)
- [x] Statistics increment (if modal open)

If you don't see ALL of these, refer to troubleshooting section above.

---

## Quick Commands

```powershell
# Test detection visibility
python test_loop_detection_enhanced.py

# Generate loop traffic
python auto_loop_simulator.py

# Diagnose issues
python diagnose_loop_detection.py --timeout 15
```

---

**Created**: October 24, 2025  
**Status**: ✅ Enhanced UI with real-time visibility  
**Next**: Test with simulator to verify all indicators work
