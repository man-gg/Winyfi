# 🔄 Advanced Loop Detection Test Simulator

## Overview

The Enhanced Loop Simulator is a comprehensive testing tool designed to validate the multi-interface loop detection system. It can simulate **12 different types of network loops and storms** that test all aspects of the detection engine.

## Features

### 🎯 12 Loop Types Supported

1. **Clean Network** - Normal baseline traffic
2. **Suspicious Activity** - Elevated but not critical
3. **Broadcast Storm** - Massive broadcast flooding
4. **ARP Storm** - Excessive ARP requests
5. **Spanning Tree Loop** - BPDU storm simulation
6. **Multicast Storm** - Excessive multicast traffic
7. **MAC Flapping** - Same MAC on multiple interfaces
8. **Cross-Subnet Loop** - Traffic between subnets
9. **Duplicate Packets** - Repeated identical packets
10. **Burst Loop** - Intermittent high-traffic bursts
11. **Low Entropy** - Repetitive patterns
12. **Multi-Protocol Storm** - Mixed protocol traffic

### ⚡ Advanced Capabilities

- **Auto-interface detection** - Finds best network interface
- **Real-time monitoring** - Shows detection results live
- **Comparison mode** - Test multiple scenarios side-by-side
- **Custom configuration** - Define your own test parameters
- **Sequential testing** - Run all scenarios automatically
- **Expected outcome display** - Shows what should be detected

## Installation

### Prerequisites

```bash
# Ensure you have required packages
pip install scapy psutil

# Or install from requirements.txt
pip install -r requirements.txt
```

### Permissions

**Windows (PowerShell as Administrator):**
```powershell
# Right-click PowerShell → Run as Administrator
cd "C:\Users\63967\Desktop\network monitoring"
python simulate_loop.py
```

**Linux:**
```bash
sudo python3 simulate_loop.py
```

## Usage

### Quick Start

1. **Start the simulator:**
   ```powershell
   python simulate_loop.py
   ```

2. **Select network interface** (auto-detected or manual selection)

3. **Choose a scenario** from the menu

4. **Monitor results** in real-time

### Menu Options

```
🎯 Available Test Scenarios:

📊 BASIC SCENARIOS:
  1. CLEAN              - Clean network simulation
  2. SUSPICIOUS         - Suspicious activity simulation

🔥 ADVANCED LOOP TYPES:
  3. BROADCAST_STORM    - Broadcast Storm simulation
  4. ARP_STORM          - ARP Storm simulation
  5. SPANNING_TREE_LOOP - Spanning Tree Loop simulation
  6. MULTICAST_STORM    - Multicast Storm simulation
  7. MAC_FLAPPING       - MAC Flapping simulation
  8. CROSS_SUBNET_LOOP  - Cross-Subnet Loop simulation
  9. DUPLICATE_PACKETS  - Duplicate Packets simulation
 10. BURST_LOOP         - Burst Loop simulation
 11. ENTROPY_TEST       - Low Entropy simulation
 12. MULTI_PROTOCOL_STORM - Multi-Protocol Storm simulation

⚙️  SPECIAL OPTIONS:
 13. CUSTOM             - Manual configuration
 14. CONTINUOUS         - Run all scenarios sequentially
 15. COMPARISON         - Compare multiple loop types
  0. EXIT               - Quit simulator
```

## Testing Strategies

### 1. Basic Validation

Test that detection works at all:

```
Recommended sequence:
1. Run "Clean" (should show: Network Clean)
2. Run "Suspicious" (should show: Suspicious Activity)
3. Run "Broadcast Storm" (should show: Loop Detected)
```

### 2. Comprehensive Testing

Test all detection features:

```
Run scenarios: 3-12
Duration: ~25 minutes
Purpose: Validate all loop types are detected correctly
```

### 3. Comparison Testing

Compare specific loop types:

```
Select option 15 (Comparison)
Choose scenarios: 3,4,6 (Broadcast, ARP, Multicast)
Purpose: Compare detection accuracy across similar loop types
```

### 4. Custom Testing

Test specific parameters:

```
Select option 13 (Custom)
Set: Packets/sec, Duration, Packet Type
Purpose: Fine-tune detection thresholds
```

## Loop Type Details

### Broadcast Storm
```python
Packets/sec: 80
Duration: 15 seconds
Packet Type: Broadcast (dst=ff:ff:ff:ff:ff:ff)
Detection Features Tested:
  ✓ Broadcast packet count
  ✓ High packet rate
  ✓ Severity scoring
Expected Result: Loop Detected (severity > 80)
```

### ARP Storm
```python
Packets/sec: 60
Duration: 15 seconds
Packet Type: ARP requests
Detection Features Tested:
  ✓ ARP packet count
  ✓ Protocol-specific detection
  ✓ ARP request/reply analysis
Expected Result: Loop Detected (severity > 70)
```

### Cross-Subnet Loop
```python
Packets/sec: 50
Duration: 20 seconds
Packet Type: Mixed subnet traffic
Subnets: 192.168.1.x, 192.168.2.x, 10.0.0.x, 172.16.0.x
Detection Features Tested:
  ✓ Cross-subnet tracking
  ✓ Subnet diversity
  ✓ IP range analysis
Expected Result: Loop Detected (cross-subnet flag)
```

### MAC Flapping
```python
Packets/sec: 40
Duration: 15 seconds
Pattern: Same MAC, different IPs
Detection Features Tested:
  ✓ MAC tracking
  ✓ IP-MAC correlation
  ✓ Port flapping indicators
Expected Result: Suspicious/Loop Detected
```

### Burst Loop
```python
Pattern: 3 seconds burst (100 pps) + 3 seconds quiet
Duration: 20 seconds
Detection Features Tested:
  ✓ Burst detection
  ✓ Temporal pattern analysis
  ✓ Intermittent activity tracking
Expected Result: Suspicious/Loop Detected
```

### Duplicate Packets
```python
Packets/sec: 45
Duration: 15 seconds
Pattern: Same packets repeated in groups
Detection Features Tested:
  ✓ Packet fingerprinting
  ✓ Duplicate detection
  ✓ Signature analysis
Expected Result: Loop Detected
```

### Low Entropy
```python
Packets/sec: 35
Duration: 15 seconds
Pattern: Repetitive payloads with low variability
Detection Features Tested:
  ✓ Entropy analysis
  ✓ Pattern recognition
  ✓ Payload diversity
Expected Result: Suspicious/Loop Detected
```

### Multi-Protocol Storm
```python
Packets/sec: 65
Duration: 18 seconds
Protocols: ARP, ICMP, Broadcast, Multicast, TCP SYN
Detection Features Tested:
  ✓ Multi-protocol tracking
  ✓ Protocol diversity
  ✓ Mixed traffic analysis
Expected Result: Loop Detected
```

## Output Examples

### Clean Network
```
✅ Simulating CLEAN NETWORK...
   Sent 20 packets

🔍 Starting enhanced loop detection checker...
✅ Network clean. Severity: 5.00
   Total packets: 2
```

### Loop Detected
```
🌊 Simulating BROADCAST STORM...
   Sent 1200 broadcast packets

⚠️ LOOP DETECTED! Severity: 95.30, Offenders: 1
   Total packets: 1203, Offenders: ['00:11:22:33:44:55']

📊 EXPECTED DETECTION OUTCOME:
   Expected Status: 🔴 Loop Detected
   Description: Broadcast storm detected
```

### Suspicious Activity
```
⚠️ Simulating MILD SUSPICIOUS ACTIVITY...
   Sent 150 packets

🔍 Suspicious activity detected. Severity: 55.20
   Total packets: 152
```

## Integration with Dashboard

### Run Simultaneously

1. **Start Dashboard** (Terminal 1):
   ```powershell
   python main.py
   ```

2. **Enable Loop Detection** in dashboard

3. **Run Simulator** (Terminal 2):
   ```powershell
   python simulate_loop.py
   ```

4. **Watch Both**:
   - Simulator: Shows packet generation
   - Dashboard: Shows real-time detection

### Expected Behavior

When running both:
- Simulator generates loop traffic
- Dashboard detects and logs it
- Notifications appear in dashboard
- Database records are created
- Statistics are updated

## Troubleshooting

### Issue: "No interfaces found"
```
Solution:
1. Check network connections: ipconfig /all
2. Ensure at least one interface is connected
3. Try running as Administrator
```

### Issue: "Permission denied"
```
Solution:
Run as Administrator (Windows) or with sudo (Linux)
```

### Issue: No packets detected
```
Possible causes:
1. Wrong interface selected
2. Firewall blocking Scapy
3. Detection not running in dashboard

Solutions:
- Select correct interface manually
- Disable firewall temporarily
- Verify dashboard loop detection is enabled
```

### Issue: Detection not working
```
Check:
1. Dashboard loop detection is running
2. Correct interface selected in both
3. Detection interval settings (default 3-5 min)

Force detection:
- Use manual scan in dashboard
- Run "Broadcast Storm" scenario (high severity)
```

## Performance Notes

### Resource Usage
- **CPU**: Low to moderate (10-30% during simulation)
- **Memory**: ~50-100 MB
- **Network**: Generates specified packets per second
- **Duration**: Each scenario: 10-20 seconds

### Recommended Hardware
- **CPU**: Any modern processor
- **RAM**: 2 GB minimum
- **Network**: Active network interface
- **OS**: Windows 10/11, Linux, macOS

## Best Practices

### 1. Start Simple
```
Run order:
1. Clean → Verify baseline
2. Suspicious → Test moderate detection
3. Broadcast Storm → Confirm loop detection works
```

### 2. Document Results
```
For each scenario, note:
- Detection status (Clean/Suspicious/Loop)
- Severity score
- Number of offenders
- Time to detection
```

### 3. Test Regularly
```
- After code changes
- Before deployment
- When adding new features
- During troubleshooting
```

### 4. Use Comparison Mode
```
Compare similar scenarios:
- Broadcast vs Multicast storms
- ARP vs ICMP floods
- Different packet rates
```

## Advanced Usage

### Custom Packet Rates

Edit `TEST_SCENARIOS` in code:
```python
"custom_storm": {
    "packets_per_sec": 120,  # Adjust rate
    "duration": 30,          # Adjust duration
    "description": "Custom test",
    "loop_type": "broadcast"
}
```

### Add New Loop Types

1. Create packet generator:
```python
def create_my_packet():
    return Ether(dst="...") / IP(...) / ...
```

2. Create simulator:
```python
def simulate_my_loop(duration, packets_per_sec):
    # Implementation
```

3. Add to scenarios:
```python
"my_loop": {
    "packets_per_sec": 50,
    "duration": 15,
    "description": "My custom loop",
    "loop_type": "custom"
}
```

### Modify Detection Thresholds

In `detect_loops_lightweight()`:
```python
threshold=30,  # Adjust this value
```

Lower = more sensitive (detect smaller loops)
Higher = less sensitive (only detect major loops)

## API Reference

### Main Functions

```python
simulate_scenario(scenario: str)
# Simulate a specific loop type
# Parameters:
#   scenario: One of TEST_SCENARIOS keys
# Returns: None

detect_loops_lightweight(timeout, threshold, iface)
# Run loop detection
# Parameters:
#   timeout: Capture duration (seconds)
#   threshold: Minimum packets to flag
#   iface: Network interface name
# Returns: (total_packets, offenders, stats, status, severity)

create_*_packet()
# Generate specific packet types
# Returns: Scapy packet object
```

## Testing Checklist

Before deploying to production:

- [ ] Clean network shows "Clean"
- [ ] Suspicious activity shows "Suspicious"
- [ ] Broadcast storm shows "Loop Detected"
- [ ] ARP storm shows "Loop Detected"
- [ ] Cross-subnet detection works
- [ ] MAC flapping is detected
- [ ] Burst patterns are detected
- [ ] Multi-protocol storms are detected
- [ ] Dashboard notifications work
- [ ] Database records are created
- [ ] Multi-interface detection works
- [ ] All scenarios complete without errors

## FAQ

**Q: How long should I run each scenario?**
A: Default durations (10-20s) are sufficient. Longer tests don't improve detection.

**Q: Can I run multiple scenarios at once?**
A: Use "Continuous" mode (option 14) to run all sequentially.

**Q: Why aren't loops detected?**
A: Ensure dashboard loop detection is running and check detection interval (default 3-5 min).

**Q: Can I use this on production networks?**
A: **NO!** This generates heavy traffic that can disrupt production. Test on isolated networks only.

**Q: What's the difference between Suspicious and Loop Detected?**
A: Suspicious = elevated activity (40-80 severity). Loop = confirmed loop (80+ severity).

**Q: How do I verify detection accuracy?**
A: Compare simulator output with dashboard detection results. Both should show similar status.

## Support

For issues or questions:
1. Check console output for detailed errors
2. Review documentation files
3. Verify prerequisites are met
4. Test with basic scenarios first

## Version History

- **v2.0** - Multi-interface support, 12 loop types, comparison mode
- **v1.0** - Basic broadcast storm simulation

## License

Part of the Network Monitoring Dashboard project.

---

**Last Updated**: October 24, 2025  
**Author**: Network Monitoring Team  
**Status**: Production Ready
