# Loop Detection Quick Start Guide

## Installation

### Prerequisites
```bash
# Install required packages
pip install scapy psutil requests

# Windows: Install Npcap
# Download from: https://npcap.com/

# Linux: Install libpcap
sudo apt-get install libpcap-dev

# macOS: Already included
```

### Verify Installation
```python
from network_utils import get_default_iface
print(f"Default interface: {get_default_iface()}")
```

---

## Quick Examples

### 1. Simple Loop Check (10 seconds)

```python
from network_utils import detect_loops

total, offenders, stats, metrics = detect_loops(
    timeout=10,
    threshold=100,
    enable_advanced=True
)

if offenders:
    print(f"⚠️ Loop detected! Offenders: {offenders}")
else:
    print("✓ Network is clean")
```

### 2. Background Monitoring

```python
from network_utils import auto_loop_detection
import time

while True:
    result = auto_loop_detection(save_to_db=False)
    
    if result["success"]:
        print(f"Status: {result['status']} | Severity: {result['severity_score']:.2f}")
    
    time.sleep(300)  # Every 5 minutes
```

### 3. Lightweight Check (3 seconds)

```python
from network_utils import detect_loops_lightweight

total, offenders, stats, status, severity, metrics = detect_loops_lightweight(
    timeout=3,
    threshold=30,
    use_sampling=True
)

print(f"Status: {status} | Efficiency: {metrics['efficiency_ratio']*100:.1f}%")
```

---

## Common Use Cases

### Use Case 1: One-Time Manual Check

**When:** Troubleshooting suspected loop issue  
**Method:** `detect_loops()` with advanced features  
**Duration:** 10-15 seconds for thorough analysis

```python
from network_utils import detect_loops

total, offenders, stats, metrics = detect_loops(
    timeout=15,
    threshold=80,
    enable_advanced=True
)

# Detailed analysis
for mac in offenders:
    info = stats[mac]
    severity = info['severity']
    
    print(f"\nOffender: {mac}")
    print(f"  Severity: {severity['total']:.2f}")
    print(f"  Subnets: {info['subnets']}")
    print(f"  Packet breakdown:")
    print(f"    ARP: {info['arp_count']}")
    print(f"    STP: {info['stp_count']}")
    print(f"    LLDP: {info['lldp_count']}")
```

### Use Case 2: Continuous Background Monitoring

**When:** Production network monitoring  
**Method:** `auto_loop_detection()` lightweight  
**Frequency:** Every 5-10 minutes

```python
from network_utils import auto_loop_detection
import time
import logging

logging.basicConfig(level=logging.INFO)

while True:
    result = auto_loop_detection(
        save_to_db=True,
        api_base_url="http://localhost:5000",
        use_advanced=False  # Lightweight for efficiency
    )
    
    if result["success"] and result["status"] != "clean":
        logging.warning(f"Loop detected: {result['offenders']}")
    
    time.sleep(600)  # 10 minutes
```

### Use Case 3: Multi-Interface Monitoring

**When:** Router or multi-NIC server  
**Method:** Multiple threads, one per interface

```python
import threading
from network_utils import auto_loop_detection

def monitor(iface):
    while True:
        result = auto_loop_detection(iface=iface, use_advanced=False)
        if result["success"] and result["status"] != "clean":
            print(f"[{iface}] ⚠️ {result['status']}")
        time.sleep(300)

interfaces = ["Wi-Fi", "Ethernet"]
for iface in interfaces:
    threading.Thread(target=monitor, args=(iface,), daemon=True).start()

# Keep alive
while True:
    time.sleep(60)
```

### Use Case 4: Integration with Existing Dashboard

**When:** Adding loop detection to existing monitoring system

```python
from flask import Flask, jsonify
from network_utils import auto_loop_detection

app = Flask(__name__)

@app.route('/api/check-loops')
def check_loops():
    result = auto_loop_detection(save_to_db=False, use_advanced=True)
    return jsonify(result)

if __name__ == '__main__':
    app.run(port=5001)
```

---

## Parameter Tuning Guide

### Timeout Selection

| Network Size | Recommended Timeout | Use Case |
|--------------|---------------------|----------|
| Small (< 50 devices) | 3-5 seconds | Quick checks |
| Medium (50-200 devices) | 5-10 seconds | Standard monitoring |
| Large (200+ devices) | 10-15 seconds | Thorough analysis |
| Multi-subnet | 15-20 seconds | Cross-subnet detection |

### Threshold Selection

| Sensitivity | Threshold | When to Use |
|-------------|-----------|-------------|
| Very High | 20-30 | Testing/development |
| High | 30-50 | Sensitive production |
| Medium | 50-100 | Standard production |
| Low | 100-150 | Noisy networks |

### Advanced vs. Lightweight

| Feature | Advanced | Lightweight |
|---------|----------|-------------|
| CPU Usage | 15-25% | 5-10% |
| Memory | 150-200 MB | 50-80 MB |
| Detection Time | 10-15s | 3-5s |
| Accuracy | Very High | High |
| False Positives | Very Low | Low |
| Use Case | Manual checks | Background monitoring |

---

## Interpreting Results

### Severity Scores

```
0-30:   Clean - Normal operation
30-50:  Suspicious - Monitor closely
50-100: Warning - Investigate soon
100+:   Critical - Immediate action required
```

### Status Codes

- **clean**: No loops detected
- **suspicious**: Unusual activity, but not confirmed loop
- **loop_detected**: High confidence loop detection
- **error**: Detection failed

### Common Offender Patterns

#### Pattern 1: ARP Storm
```
arp_count: 500+
stp_count: 0
severity: 150+
→ Likely: Broadcast loop
```

#### Pattern 2: STP Loop
```
stp_count: 200+
arp_count: Low
severity: 200+
→ Likely: Spanning tree misconfiguration
```

#### Pattern 3: Routing Loop
```
icmp_redirect_count: 100+
subnets: Multiple
severity: 120+
→ Likely: Routing loop
```

#### Pattern 4: False Positive (DHCP Server)
```
dhcp_count: 80%+ of total
is_legitimate: True
→ Normal DHCP server operation
```

---

## Troubleshooting

### Problem: No packets captured

**Symptoms:**
```
total_packets: 0
offenders: []
```

**Solutions:**
1. Run as administrator/root
2. Check interface: `get_default_iface()`
3. Verify Npcap/libpcap installed
4. Specify interface manually: `detect_loops(iface="Ethernet")`

### Problem: High false positives

**Symptoms:**
```
Many offenders with low severity scores
is_legitimate: False for known good devices
```

**Solutions:**
1. Increase threshold: `threshold=150`
2. Enable advanced detection: `enable_advanced=True`
3. Add to whitelist:
   ```python
   engine = LoopDetectionEngine()
   engine.legitimate_patterns["routers"].add("MAC_ADDRESS")
   ```

### Problem: Missing loops in multi-subnet environment

**Symptoms:**
```
cross_subnet_activity: False
No offenders detected but network is slow
```

**Solutions:**
1. Monitor all interfaces
2. Lower threshold: `threshold=30`
3. Increase timeout: `timeout=20`
4. Check ICMP redirect counts manually

### Problem: High CPU usage

**Symptoms:**
```
CPU: 50%+
System lag during detection
```

**Solutions:**
1. Use lightweight: `detect_loops_lightweight()`
2. Enable sampling: `use_sampling=True`
3. Reduce frequency: Check every 10 minutes instead of every minute
4. Reduce timeout: `timeout=3`

---

## Best Practices

### 1. Baseline Your Network

Run detection during normal hours to establish baseline:

```python
from network_utils import detect_loops

# Run several times during normal operation
baselines = []
for i in range(5):
    total, _, stats, _ = detect_loops(timeout=10, threshold=1000)  # High threshold to capture all
    baselines.append(stats)
    time.sleep(300)

# Analyze baseline to set appropriate threshold
# Average severity across all MACs should be your threshold baseline
```

### 2. Use Appropriate Method for Context

- **Manual troubleshooting:** `detect_loops()` with `enable_advanced=True`
- **Background monitoring:** `auto_loop_detection()` with `use_advanced=False`
- **Resource-constrained:** `detect_loops_lightweight()` with `use_sampling=True`

### 3. Whitelist Management

Maintain whitelist of known-good devices:

```python
# In your initialization code
engine = LoopDetectionEngine()

# Add known infrastructure
engine.legitimate_patterns["routers"].add("aa:bb:cc:dd:ee:11")
engine.legitimate_patterns["dhcp_servers"].add("aa:bb:cc:dd:ee:22")

# Save for reuse
import json
whitelist = {
    "routers": list(engine.legitimate_patterns["routers"]),
    "dhcp_servers": list(engine.legitimate_patterns["dhcp_servers"])
}
with open("whitelist.json", "w") as f:
    json.dump(whitelist, f)
```

### 4. Multi-Subnet Monitoring

For networks with multiple subnets:

```python
# Monitor all router interfaces
interfaces = ["eth0", "eth1", "wlan0"]

import threading

results = {}

def monitor_interface(iface):
    results[iface] = auto_loop_detection(iface=iface, use_advanced=True)

threads = []
for iface in interfaces:
    t = threading.Thread(target=monitor_interface, args=(iface,))
    t.start()
    threads.append(t)

for t in threads:
    t.join()

# Check for cross-subnet issues
all_subnets = set()
for iface, result in results.items():
    if result["success"] and result["cross_subnet_detected"]:
        print(f"⚠️ Cross-subnet activity on {iface}")
```

### 5. Alert Integration

Integrate with alerting system:

```python
import smtplib
from email.mime.text import MIMEText

def send_alert(subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = 'network@company.com'
    msg['To'] = 'admin@company.com'
    
    s = smtplib.SMTP('localhost')
    s.send_message(msg)
    s.quit()

# In monitoring loop
result = auto_loop_detection()
if result["success"] and result["severity_score"] > 100:
    send_alert(
        "CRITICAL: Network Loop Detected",
        f"Severity: {result['severity_score']}\nOffenders: {result['offenders']}"
    )
```

---

## Performance Tips

### 1. Optimize for Your Environment

**High-traffic network (1000+ pkt/sec):**
```python
detect_loops_lightweight(timeout=3, use_sampling=True)  # Sample every 5-10 packets
```

**Low-traffic network (<100 pkt/sec):**
```python
detect_loops(timeout=15, enable_advanced=True)  # Full analysis
```

### 2. Adjust Capture Duration

Don't over-capture:
- 3-5 seconds sufficient for most loop detection
- 10+ seconds only for thorough analysis or slow networks

### 3. Use Caching

Cache results to avoid redundant checks:

```python
import time

last_check = 0
cached_result = None

def get_loop_status():
    global last_check, cached_result
    
    now = time.time()
    if now - last_check < 60:  # Cache for 60 seconds
        return cached_result
    
    cached_result = auto_loop_detection()
    last_check = now
    return cached_result
```

---

## Testing

Run the comprehensive test suite:

```bash
# All tests
python test_advanced_loop_detection.py

# Specific test
python test_advanced_loop_detection.py 1  # Test 1: Basic detection
python test_advanced_loop_detection.py 2  # Test 2: Lightweight
python test_advanced_loop_detection.py 6  # Test 6: Performance
```

---

## Support & Resources

- **Full Documentation:** See `ADVANCED_LOOP_DETECTION_README.md`
- **Source Code:** `network_utils.py` (lines 445-700)
- **Test Suite:** `test_advanced_loop_detection.py`

---

## Quick Checklist

Before deploying to production:

- [ ] Tested on your specific network
- [ ] Established baseline severity scores
- [ ] Created whitelist of legitimate devices
- [ ] Set appropriate threshold for your environment
- [ ] Configured alerting/logging
- [ ] Tested on all monitored interfaces
- [ ] Verified cross-platform compatibility
- [ ] Set up appropriate monitoring frequency
- [ ] Documented your configuration

---

**Last Updated:** October 24, 2025
