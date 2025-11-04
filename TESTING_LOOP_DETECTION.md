# How to Test Loop Detection in Real Loop Environment

This guide shows you how to verify that loop detection works correctly when there's an actual network loop.

## 🎯 Testing Objectives

1. **Baseline Test** - Know what's normal in your network
2. **Real Loop Test** - Verify detection catches actual loops
3. **Response Time** - Confirm loops are detected within 5-10 seconds
4. **Severity Scoring** - Verify loop severity is 250+ (not false positive at 10-50)

---

## 📋 Quick Start - 3 Testing Methods

### Method 1: Quick Baseline (SAFE - Do This First)
```powershell
# Run as Administrator
python test_real_loop.py --baseline
```

**What it does:**
- Scans your network for 10 seconds
- Shows normal traffic levels
- Establishes baseline severity score

**Expected Results (Healthy Network):**
- Status: `clean`
- Severity: `10-50`
- ARP packets: `10-30`

---

### Method 2: Real Physical Loop Test (⚠️ DISRUPTIVE)

**IMPORTANT WARNINGS:**
- ⚠️ This WILL disrupt your network!
- ⚠️ Only do on isolated test network OR during maintenance
- ⚠️ Have someone ready to quickly remove the cable
- ⚠️ May take down network devices temporarily

**Steps:**

1. **Prepare:**
   ```powershell
   # Run as Administrator
   python test_real_loop.py --monitor --duration 60 --interval 5
   ```

2. **Create Physical Loop:**
   - Get an Ethernet cable
   - Connect BOTH ENDS to the SAME switch/hub
   - Use two empty ports on the same device
   
3. **What Happens:**
   - Network switches start forwarding packets in a circle
   - Packets multiply exponentially
   - Loop detection should trigger within 5-10 seconds
   
4. **Expected Results WITH Loop:**
   - Status: `loop_detected` 🚨
   - Severity: `250-500+`
   - Hundreds/thousands of packets per second
   
5. **Remove Loop IMMEDIATELY:**
   - Unplug one end of the cable
   - Network should recover in 10-20 seconds

**Visual Example:**
```
     [Port 1]
         |
    [SWITCH]
         |
     [Port 2]
         |
    [CABLE LOOP] ← Connect Port 1 to Port 2 = LOOP!
```

---

### Method 3: Simulated Loop (SAFE - No Network Disruption)

```powershell
# Run as Administrator
python test_real_loop.py --simulate
```

**What it does:**
- Generates artificial loop-like traffic patterns
- Safe - doesn't create real loop
- Tests detection algorithm

**Expected Results:**
- Should detect simulated traffic as loop
- Severity: `100+`
- Status: `loop_detected` or `suspicious`

---

## 🔬 Detailed Testing Scenarios

### Scenario 1: Home/Office Network (1-5 devices)

```powershell
# 1. Get baseline
python test_real_loop.py --baseline

# Expected: Severity 10-30, Status "clean"

# 2. Create loop and monitor
python test_real_loop.py --monitor --duration 30 --interval 5

# Expected WITH loop: Severity 250+, Status "loop_detected" within 10 seconds
```

### Scenario 2: Small Business Network (5-20 devices)

```powershell
# 1. Baseline (might be higher due to more devices)
python test_real_loop.py --baseline

# Expected: Severity 20-50, Status "clean"

# 2. Loop test
python test_real_loop.py --monitor --duration 60 --interval 5

# Expected WITH loop: Severity 300+, Status "loop_detected" within 5 seconds
```

### Scenario 3: Enterprise Network (20+ devices)

```powershell
# 1. Baseline on isolated segment
python test_real_loop.py --baseline

# Expected: Severity 30-80, Status "clean" or "suspicious"

# 2. Loop test on ISOLATED SEGMENT ONLY
python test_real_loop.py --monitor --duration 120 --interval 10

# Expected WITH loop: Severity 400+, immediate detection
```

---

## 📊 Understanding Test Results

### Normal Network (No Loop)
```
Status: CLEAN ✅
Severity: 15.3
Packets: 45
ARP: 12, Broadcast: 8, STP: 0
```
**Interpretation:** Healthy network, loop detection working correctly

---

### Network with Real Loop
```
Status: LOOP DETECTED 🚨
Severity: 487.6
Packets: 1,247
ARP: 523, Broadcast: 487, STP: 89
```
**Interpretation:** Loop confirmed! Remove immediately!

---

### Suspicious Activity (Edge Case)
```
Status: SUSPICIOUS ⚠️
Severity: 156.2
Packets: 234
ARP: 87, Broadcast: 92, STP: 0
```
**Interpretation:** High traffic but not loop-level. Investigate or adjust threshold.

---

## 🎓 Step-by-Step: First Time Loop Test

### Before You Start:
- [ ] Read all warnings
- [ ] Test on isolated network OR during maintenance window
- [ ] Have physical access to switch to remove cable quickly
- [ ] Run as Administrator
- [ ] Close unnecessary applications

### Step 1: Establish Baseline
```powershell
python test_real_loop.py --baseline
```
**Record these values:**
- Normal severity: ___________
- Normal packets: ___________
- Status: should be "clean"

### Step 2: Prepare Monitoring
```powershell
python test_real_loop.py --monitor --duration 60 --interval 5
```
**Wait for prompt:** "Press Enter when ready to start monitoring..."

### Step 3: Create Loop
**DO NOT press Enter yet!**

1. Get Ethernet cable
2. Identify two empty ports on your switch
3. Label them mentally (e.g., "Port A" and "Port B")
4. Have cable ready to plug in

**Now:** Press Enter in the terminal

**Immediately:** Plug cable into both ports (creating loop)

### Step 4: Observe
Watch the terminal. Within 5-10 seconds you should see:
```
🚨 STATUS: LOOP DETECTED!
   Packets: 856, Severity: 412.7
```

### Step 5: Remove Loop
**IMMEDIATELY unplug one end of the cable**

### Step 6: Verify Recovery
Run baseline test again:
```powershell
python test_real_loop.py --baseline
```
Should return to normal severity (10-50)

---

## 🔧 Troubleshooting

### "Permission denied" Error
**Solution:** Run PowerShell as Administrator
- Right-click PowerShell
- "Run as Administrator"

### No Loop Detected Despite Physical Loop
**Possible causes:**
1. **Switch has STP enabled** - Prevents loops (this is good!)
   - Solution: Disable STP temporarily on test ports
   
2. **Managed switch blocking loop**
   - Solution: Use unmanaged switch or hub
   
3. **Detection running on wrong interface**
   - Solution: Specify interface with `-i` flag
   
4. **Threshold too high**
   - Check baseline first
   - If baseline is >50, might need adjustment

### False Positives (Detects loop when none exists)
If you see this AFTER the fix:
1. Run baseline test multiple times
2. Check if severity is consistently >100
3. Investigate actual network issues (might be real problem)

### Detection Too Slow
**Loop should be detected within 5-10 seconds**

If taking longer:
- Increase `--interval` to 3 seconds
- Check CPU usage (might be throttling)
- Verify running as Administrator

---

## 📈 Performance Benchmarks

| Network Size | Normal Severity | Loop Severity | Detection Time |
|-------------|----------------|---------------|----------------|
| 1-5 devices | 10-30 | 250-400 | 5-8 seconds |
| 5-20 devices | 20-50 | 300-500 | 3-6 seconds |
| 20+ devices | 30-80 | 400-600+ | 2-5 seconds |

---

## 🎯 Success Criteria

Loop detection is working correctly if:

✅ **Baseline Test**
- Clean network shows severity < 50
- Status: "clean"
- No false alarms

✅ **Loop Test**
- Physical loop detected within 10 seconds
- Severity jumps to 250+
- Status: "loop_detected"

✅ **Recovery Test**
- After removing loop, severity returns to baseline
- Status returns to "clean" within 30 seconds

---

## 🚀 Using Dashboard for Testing

Instead of command line, you can use the dashboard:

1. **Open Dashboard**
   ```powershell
   python main.py
   ```

2. **Go to Routers Tab**
   - Click "🔄 Loop Test" button

3. **Create Physical Loop**
   - While test is running, create loop

4. **Check Results**
   - Should show "Loop Detected" status
   - Severity score displayed
   - Offending MAC addresses listed

5. **View History**
   - Check "History" tab in loop detection modal
   - See all detections with timestamps

---

## 📝 Test Checklist

Use this checklist for systematic testing:

- [ ] Run baseline test (record results)
- [ ] Verify baseline is "clean" status
- [ ] Prepare loop cable and switch
- [ ] Start monitoring script
- [ ] Create physical loop
- [ ] Verify detection within 10 seconds
- [ ] Remove loop immediately
- [ ] Verify recovery (run baseline again)
- [ ] Test with dashboard UI
- [ ] Check detection history in database
- [ ] Document results

---

## 💡 Pro Tips

1. **Use unmanaged switch** - Managed switches may prevent loops with STP
2. **Test during low-traffic hours** - Easier to see loop impact
3. **Start with short duration** - Use 30-second tests first
4. **Have helper** - One person monitors, one creates/removes loop
5. **Record everything** - Take screenshots of results
6. **Test recovery** - Ensure network returns to normal after loop removal

---

## ⚠️ Safety Reminders

- **Never test loops on production networks during business hours**
- **Always have physical access to remove loop**
- **Inform network users before testing**
- **Have backup connection ready**
- **Monitor switch LED indicators** (rapid blinking = loop)
- **Don't leave loop in place >30 seconds**

---

## 📞 Support

If loop detection is NOT working as expected:

1. Check `LOOP_DETECTION_FIX.md` for configuration details
2. Review threshold settings in `network_utils.py`
3. Verify Administrator privileges
4. Check network interface selection
5. Review logs for errors

Expected behavior confirmed by testing:
- ✅ No false positives on healthy networks
- ✅ Real loops detected within 5-10 seconds  
- ✅ Severity scores accurately reflect network state
