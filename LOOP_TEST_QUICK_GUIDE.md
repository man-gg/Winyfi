# Loop Detection Quick Reference Card

## 🎯 Quick Test Commands

### 1. Check if Your Network is Normal (SAFE)
```powershell
python test_real_loop.py --baseline
```
**Expected:** Severity 10-50, Status "clean"

---

### 2. Test Real Loop Detection (⚠️ DISRUPTIVE)
```powershell
# Step 1: Start monitoring
python test_real_loop.py --monitor --duration 60

# Step 2: Create physical loop (plug cable into same switch)
# Step 3: Watch for detection (should happen in 5-10 seconds)
# Step 4: REMOVE LOOP IMMEDIATELY
```
**Expected WITH loop:** Severity 250+, Status "loop_detected"

---

### 3. Safe Simulation Test (SAFE)
```powershell
python test_real_loop.py --simulate
```
**Expected:** Should detect simulated traffic as loop

---

## 📊 What the Numbers Mean

| Severity Score | Status | Meaning |
|----------------|--------|---------|
| **0-50** | ✅ Clean | Normal network - no loop |
| **50-100** | ⚠️ Suspicious | High traffic - investigate |
| **100-250** | 🔶 High Alert | Very high traffic - possible loop |
| **250+** | 🚨 Loop Detected | **CONFIRMED LOOP - REMOVE NOW!** |

---

## 🔍 How to Read Test Results

### ✅ Normal Network (NO LOOP)
```
Status: CLEAN
Severity: 23.4
Packets: 67
ARP: 18, Broadcast: 12, STP: 0
Offenders: 0
```
👉 **This is good!** Loop detection working, network healthy.

---

### 🚨 Network with Loop
```
Status: LOOP DETECTED!
Severity: 487.3
Packets: 2,341
ARP: 876, Broadcast: 923, STP: 234
Offenders: 3
```
👉 **ACTION REQUIRED:** Remove physical loop NOW!

---

## 🔧 Quick Troubleshooting

### Problem: "Permission denied"
**Fix:** Run as Administrator
```powershell
# Right-click PowerShell → "Run as Administrator"
```

### Problem: No loop detected despite physical loop
**Possible causes:**
1. Switch has STP enabled (preventing loop - this is good!)
2. Running on wrong network interface
3. Need to disable STP on test switch ports

### Problem: False positives (detects loop when none exists)
**This was the original bug - should be FIXED now!**
If still happening:
1. Run baseline test 3 times
2. If consistently showing severity >100, there might be a real network issue
3. Check for broadcast storms or malfunctioning devices

---

## ⚡ Physical Loop Test - Step by Step

```
1. Get Ethernet cable
   
2. Plug BOTH ENDS into SAME switch
   ┌─────────┐
   │ SWITCH  │
   ├─[Port1]─┤
   │    │    │  
   │    └────┼─── Cable
   │         │
   ├─[Port2]─┤  ← Plug other end here
   └─────────┘
   
3. Watch terminal - should detect loop in 5-10 seconds
   
4. UNPLUG CABLE immediately after detection
```

⚠️ **WARNING:** This WILL disrupt your network!
- Only test on isolated network
- Have physical access to remove cable quickly
- Inform users before testing

---

## 📱 Using Dashboard Instead

1. Open dashboard: `python main.py`
2. Go to **Routers** tab
3. Click **"🔄 Loop Test"** button
4. Create physical loop (if testing with real loop)
5. View results in modal window

---

## 🎓 What Each Metric Means

**Severity Score:**
- Weighted sum of suspicious network activity
- Higher = more suspicious
- 250+ = confirmed loop

**Packets:**
- Total packets captured during scan
- Normal: 50-200
- Loop: 500-5000+

**ARP Count:**
- Address Resolution Protocol packets
- Normal: 10-30
- Loop: 100-1000+

**Broadcast Count:**
- Packets sent to all devices
- Normal: 5-20
- Loop: 50-500+

**STP Count:**
- Spanning Tree Protocol packets
- Normal: 0-5
- Loop: 20-200+ (major red flag!)

**Offenders:**
- MAC addresses exceeding threshold
- Normal: 0
- Loop: 1-5+

---

## 🎯 Success Criteria

Loop detection is working if:

✅ **Without loop:** 
- Severity < 50
- Status = "clean"
- 0 offenders

✅ **With real loop:**
- Severity > 250
- Status = "loop_detected"
- Detection within 10 seconds
- Specific MAC addresses identified

---

## 📋 Testing Checklist

- [ ] Run baseline test first
- [ ] Record normal severity score: _______
- [ ] Start monitoring script
- [ ] Create physical loop (two ports, one cable)
- [ ] Verify detection (should be < 10 seconds)
- [ ] Remove loop immediately
- [ ] Verify network returns to normal
- [ ] Document results

---

## 🚀 Advanced Options

```powershell
# Longer monitoring (2 minutes)
python test_real_loop.py --monitor --duration 120

# Faster checks (every 3 seconds)
python test_real_loop.py --monitor --interval 3

# Get help
python test_real_loop.py --help
```

---

## 💡 Pro Tips

1. **Test on unmanaged switch** - Managed switches may block loops with STP
2. **Use short test duration first** - Start with 30 seconds
3. **Test during low-traffic times** - Easier to see results
4. **Have someone help** - One monitors, one creates/removes loop
5. **Watch switch LEDs** - Rapid blinking = loop activity

---

## 📞 Need Help?

See detailed guides:
- `TESTING_LOOP_DETECTION.md` - Full testing guide
- `LOOP_DETECTION_FIX.md` - Technical details
- `test_real_loop.py --help` - Command line options

---

## ⚠️ Final Safety Note

**NEVER:**
- Test loops on production network during business hours
- Leave loop in place > 30 seconds
- Test without physical access to remove loop
- Test without informing network users

**ALWAYS:**
- Test on isolated network when possible
- Have removal plan ready
- Monitor impact carefully
- Document everything
