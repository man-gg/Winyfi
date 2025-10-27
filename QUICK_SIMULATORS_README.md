# 🚀 Quick Loop Simulators - One-Click Testing

## Overview

Three simple simulators to test your loop detection system with minimal effort. Perfect for quick validation and demonstrations.

## Available Simulators

### 1. 🎯 Auto Loop Simulator (Recommended)
**File**: `auto_loop_simulator.py`

**Features**:
- ✅ Runs automatically, no user interaction needed
- ✅ 60-second test duration
- ✅ 50 packets/second (guaranteed detection)
- ✅ Progress updates every 5 seconds
- ✅ Auto-detects network interface

**Usage**:
```powershell
# Windows (as Administrator)
python auto_loop_simulator.py

# Linux
sudo python3 auto_loop_simulator.py
```

**Expected Output**:
```
============================================================
🔄 BACKGROUND LOOP SIMULATOR - Auto Mode
============================================================
📡 Interface: Wi-Fi
⏱️  Duration: 60 seconds
📊 Rate: ~50 pps
🚀 Starting: 18:18:41

Generating traffic... (Ctrl+C to stop)
============================================================

  ⏱️  5s | 250 packets | 50.0 pps
  ⏱️  10s | 500 packets | 50.0 pps
  ...
  ⏱️  60s | 3000 packets | 50.0 pps

============================================================
✅ COMPLETED
============================================================
Sent: 3000 packets in 60.0s (50.0 pps)

💡 Check dashboard Loop Detection Monitor for results!
============================================================
```

---

### 2. 💬 Quick Loop Simulator (Interactive)
**File**: `quick_loop_simulator.py`

**Features**:
- ✅ User-friendly with prompts
- ✅ Detailed instructions and tips
- ✅ Safety confirmation before running
- ✅ Comprehensive results summary
- ✅ Troubleshooting guidance

**Usage**:
```powershell
python quick_loop_simulator.py
```

**What It Shows**:
- Configuration details
- Expected dashboard behavior
- Real-time progress
- Completion statistics
- Verification checklist
- Troubleshooting tips

---

### 3. 🖱️ One-Click Test (Windows)
**File**: `test_loop_detection.bat`

**Features**:
- ✅ Double-click to run
- ✅ No command line needed
- ✅ Simple instructions
- ✅ Auto-cleanup

**Usage**:
```
1. Double-click test_loop_detection.bat
2. Press any key to start
3. Wait 60 seconds
4. Check dashboard for results
```

---

## Quick Start Guide

### Step 1: Start Your Dashboard
```powershell
# Terminal 1 (as Administrator)
python main.py
```

### Step 2: Enable Loop Detection
In dashboard:
1. Click "Loop Detection" button
2. Click "▶ Start Auto" button
3. Leave dashboard running

### Step 3: Run Simulator
```powershell
# Terminal 2 (as Administrator)
python auto_loop_simulator.py
```

### Step 4: Verify Detection
In dashboard (wait 3-5 minutes for automatic detection):
- Loop Detection Monitor shows "Loop Detected"
- Notification badge appears
- Severity score is 80-100
- Database has new records

**OR** run manual scan immediately:
- Open Loop Detection Monitor
- Go to "Manual Scan" tab
- Click "▶ Run Manual Scan"

---

## Expected Results

### Dashboard Indicators

**Loop Detection Monitor:**
```
Status: ⚠️ Loop Detected!
Severity Score: 95.30
Total Packets: 3000
Offenders: 1
```

**Notification:**
```
🔴 Loop Detected
Network loop detected on Wi-Fi
Severity: High (95.30)
Click to view details
```

**Database Record:**
```sql
SELECT * FROM loop_detections ORDER BY detection_time DESC LIMIT 1;

-- Should show:
-- status: 'loop_detected'
-- severity_score: 80-100
-- total_packets: 2500-3500
-- offenders_count: 1
```

---

## Timing and Detection

### Automatic Detection
- **Simulator Duration**: 60 seconds
- **Detection Interval**: 3-5 minutes (default)
- **When Detection Occurs**: During or shortly after simulation
- **Total Wait Time**: Up to 5 minutes after starting simulator

### Manual Detection (Immediate)
- **Method**: Use "Run Manual Scan" in dashboard
- **Wait Time**: 3-5 seconds
- **Benefit**: Instant verification without waiting

---

## Troubleshooting

### Issue: No Detection After 5 Minutes

**Check:**
1. Dashboard loop detection is enabled
   - Look for "⏹ Stop Auto" button (means it's running)
   
2. Detection interval setting
   - Default is 5 minutes
   - May need to wait full interval

3. Network interface
   - Simulator uses same interface as dashboard
   - Check console output for interface name

**Solutions:**
```powershell
# Force immediate detection
1. Open Loop Detection Monitor in dashboard
2. Click "Run Manual Scan"
3. Should detect within 5 seconds
```

---

### Issue: "Permission Denied" Error

**Problem**: Packet capture requires elevated privileges

**Solution:**
```powershell
# Windows
Right-click PowerShell → Run as Administrator
python auto_loop_simulator.py

# Linux
sudo python3 auto_loop_simulator.py
```

---

### Issue: "No Interface Found"

**Problem**: No active network connection

**Solution:**
1. Check network connection: `ipconfig /all`
2. Connect to WiFi or plug in Ethernet
3. Verify interface is UP and has IP address

---

### Issue: Simulator Runs But No Packets Sent

**Check:**
- Firewall blocking Scapy
- Anti-virus blocking packet generation
- VPN interfering with network interface

**Solution:**
1. Temporarily disable firewall
2. Add Python to anti-virus exceptions
3. Disconnect VPN during test

---

### Issue: Low Severity Score (<80)

**Problem**: Not enough packets detected

**Possible Causes:**
- Simulator stopped early
- Network interface dropped packets
- Detection threshold too high

**Solution:**
```powershell
# Run simulator for longer duration
# Edit auto_loop_simulator.py:
DURATION = 120  # Change from 60 to 120 seconds
PACKETS_PER_SECOND = 80  # Increase from 50 to 80
```

---

## Configuration

### Adjust Test Duration

**File**: `auto_loop_simulator.py`
```python
DURATION = 60  # Change to 30, 90, 120, etc.
```

### Adjust Packet Rate

**File**: `auto_loop_simulator.py`
```python
PACKETS_PER_SECOND = 50  # Increase for stronger signal
# Recommended: 50-100 pps
```

### Change Loop Type

**File**: `auto_loop_simulator.py`
```python
# Current: Broadcast storm
pkt = Ether(dst="ff:ff:ff:ff:ff:ff") / IP(...)

# Alternative: ARP storm
from scapy.all import ARP
pkt = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(...)
```

---

## Performance Notes

### Resource Usage
- **CPU**: Low-moderate (10-20%)
- **Memory**: ~50 MB
- **Network**: 50 packets/second (~40 KB/s)
- **Duration**: 60 seconds default

### Scalability
| Packet Rate | Detection Confidence | Resource Usage |
|-------------|---------------------|----------------|
| 30 pps | Low (may not trigger) | Light |
| 50 pps | High (recommended) | Moderate |
| 80 pps | Very High | Moderate |
| 100+ pps | Maximum | Higher |

---

## Advanced Usage

### Run Multiple Tests
```powershell
# Test 1: Normal rate
python auto_loop_simulator.py

# Wait 5 minutes for detection

# Test 2: High rate
# Edit PACKETS_PER_SECOND = 100
python auto_loop_simulator.py
```

### Continuous Testing
```powershell
# Run simulator in loop
while ($true) {
    python auto_loop_simulator.py
    Start-Sleep -Seconds 300  # Wait 5 minutes
}
```

### Background Testing (Windows)
```powershell
# Run in background
Start-Process powershell -ArgumentList "-Command python auto_loop_simulator.py" -WindowStyle Hidden
```

---

## Comparison with Full Simulator

### Auto Simulator (This)
✅ One command to run  
✅ Automatic configuration  
✅ 60-second test  
✅ Single loop type (broadcast)  
✅ Perfect for quick testing  

### Full Simulator (`simulate_loop.py`)
✅ 12 different loop types  
✅ Custom configuration  
✅ Comparison mode  
✅ Detailed analysis  
✅ Perfect for comprehensive testing  

**Use This When:**
- Quick validation needed
- Testing basic functionality
- Demonstrating to others
- Continuous integration testing

**Use Full Simulator When:**
- Testing specific loop types
- Comprehensive validation
- Comparing scenarios
- Development and debugging

---

## Integration Testing

### Test Workflow
```
1. Start dashboard → python main.py
2. Enable loop detection
3. Run simulator → python auto_loop_simulator.py
4. Wait for detection (3-5 min) OR run manual scan
5. Verify results in dashboard
6. Check database records
7. Review notifications
```

### Automated Testing
```python
# test_integration.py
import subprocess
import time

# Start simulator
proc = subprocess.Popen(['python', 'auto_loop_simulator.py'])

# Wait for completion
proc.wait()

# Verify detection (pseudo-code)
# - Check database for new records
# - Verify severity score > 80
# - Confirm notification sent
```

---

## FAQ

**Q: How long should I run the simulator?**  
A: Default 60 seconds is sufficient. Detection typically occurs within 5-10 seconds of packet capture.

**Q: Can I run this on production networks?**  
A: **NO!** This generates network traffic that could be disruptive. Use only on test/isolated networks.

**Q: Why isn't it detecting?**  
A: Most common: Loop detection not enabled in dashboard. Check that "Stop Auto" button is visible.

**Q: Can I run multiple simulators at once?**  
A: Yes, but not recommended. Results may be confusing and resource usage will increase.

**Q: How do I know it's working?**  
A: You should see "packets sent" incrementing in terminal. If nothing happens, check permissions.

**Q: What if I want to test different loop types?**  
A: Use the full simulator: `python simulate_loop.py`

---

## Best Practices

### 1. Always Test on Isolated Networks
❌ Don't run on production networks  
✅ Use test/development networks only

### 2. Enable Dashboard First
```
Start dashboard → Enable detection → Run simulator
```

### 3. Wait for Full Detection Cycle
```
Simulator: 60 seconds
Detection: Up to 5 minutes
Total: Up to 6 minutes for automatic detection
```

### 4. Use Manual Scan for Immediate Results
```
Run simulator → Open dashboard → Manual Scan → Instant results
```

### 5. Document Results
```
Note: Severity score, packet count, detection time
Compare: Different runs to verify consistency
```

---

## Support

### Getting Help
1. Check console output for errors
2. Verify running as Administrator
3. Confirm network connection active
4. Review dashboard console logs
5. Check database records manually

### Common Success Indicators
✅ Terminal shows packets being sent  
✅ Dashboard shows loop detection notification  
✅ Severity score is 80+  
✅ Database has new loop_detections records  
✅ Notification badge appears  

### Known Limitations
- Requires Administrator/root privileges
- Must have active network interface
- Detection may take up to 5 minutes (automatic mode)
- Some anti-virus software may block Scapy

---

## Quick Reference

### Commands
```powershell
# Start dashboard
python main.py

# Run automatic simulator
python auto_loop_simulator.py

# Run interactive simulator
python quick_loop_simulator.py

# Windows one-click
test_loop_detection.bat

# Check database
mysql -u root -p network_monitor
SELECT * FROM loop_detections ORDER BY detection_time DESC LIMIT 5;
```

### Expected Timeline
```
00:00 - Start simulator
00:60 - Simulator completes
00:60-05:00 - Wait for automatic detection
05:00 - Detection triggers
05:01 - Notification appears
```

### Quick Verification
```
1. Check dashboard: Loop Detection Monitor
2. Check database: SELECT COUNT(*) FROM loop_detections WHERE status='loop_detected'
3. Check notifications: Click notification badge
```

---

**Created**: October 24, 2025  
**Version**: 1.0  
**Status**: ✅ Production Ready  
**Purpose**: Quick loop detection testing
