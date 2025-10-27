# Loop Detection System Architecture

## System Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          NETWORK TRAFFIC                                │
│                    (Multiple Interfaces/Subnets)                        │
└────────────────────┬────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     PACKET CAPTURE LAYER                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │
│  │  Interface 1 │  │  Interface 2 │  │  Interface N │                 │
│  │   (eth0)     │  │   (eth1)     │  │   (wlan0)    │                 │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                 │
│         │                  │                  │                         │
│         └──────────────────┴──────────────────┘                         │
│                            │                                            │
│                  ┌─────────▼─────────┐                                  │
│                  │  Scapy Sniffer    │                                  │
│                  │  (Cross-platform) │                                  │
│                  └─────────┬─────────┘                                  │
└────────────────────────────┼──────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   INTELLIGENT SAMPLING LAYER                            │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Traffic Rate Detection:                                         │  │
│  │  • <100 pkt/s  → Analyze all packets (sample_rate=1)            │  │
│  │  • 100-500 pkt/s → Sample every 2nd packet                      │  │
│  │  • 500+ pkt/s → Sample every 5-10th packet                      │  │
│  │                                                                   │  │
│  │  Duplicate Detection:                                            │  │
│  │  • Hash-based deduplication                                      │  │
│  │  • Reduces redundant analysis by ~30%                            │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   PACKET CLASSIFICATION LAYER                           │
│                                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │    ARP      │  │    STP      │  │    LLDP     │  │     CDP     │  │
│  │  Broadcast  │  │   01:80:    │  │   01:80:    │  │   01:00:    │  │
│  │   Weight:   │  │  c2:00:00   │  │  c2:00:0e   │  │ 0c:cc:cc:cc │  │
│  │    2.5x     │  │  Weight:5x  │  │  Weight:4x  │  │  Weight:4x  │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │
│                                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │    DHCP     │  │    mDNS     │  │   NetBIOS   │  │ ICMP Redir  │  │
│  │  UDP 67/68  │  │  UDP 5353   │  │   UDP 137   │  │   Type 5    │  │
│  │  Weight:0.5x│  │  Weight:0.3x│  │  Weight:0.4x│  │  Weight:3x  │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   LOOP DETECTION ENGINE                                 │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │              MAC-CENTRIC TRACKING DATABASE                        │ │
│  │  ┌─────────────────────────────────────────────────────────────┐ │ │
│  │  │  MAC: aa:bb:cc:dd:ee:ff                                     │ │ │
│  │  │  ├─ packet_times: [t1, t2, t3, ..., tn]  (deque, max 1000) │ │ │
│  │  │  ├─ ip_changes: [(t1,ip1), (t2,ip2), ...] (deque, max 50)  │ │ │
│  │  │  ├─ subnets: {192.168.1.0/24, 10.0.0.0/24}                 │ │ │
│  │  │  ├─ first_seen: timestamp                                   │ │ │
│  │  │  └─ last_ip: 192.168.1.105                                  │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                  7-FACTOR SEVERITY ANALYSIS                       │ │
│  │                                                                   │ │
│  │  Factor 1: Packet Frequency    [0-10] × 1.5                     │ │
│  │    └─ packets_per_second / 10                                    │ │
│  │                                                                   │ │
│  │  Factor 2: Burst Detection     [0-10] × 2.0                     │ │
│  │    └─ Number of 20+ pkt/sec bursts                              │ │
│  │                                                                   │ │
│  │  Factor 3: Pattern Entropy     [0-10] × 1.2                     │ │
│  │    └─ Shannon entropy (low = repetitive = loop)                 │ │
│  │                                                                   │ │
│  │  Factor 4: Subnet Diversity    [0-10] × 1.8                     │ │
│  │    └─ Number of subnets × 3                                      │ │
│  │                                                                   │ │
│  │  Factor 5: Packet Type Weights [0-∞]  × 1.0                     │ │
│  │    └─ Weighted sum of all packet types                          │ │
│  │                                                                   │ │
│  │  Factor 6: IP Change Frequency [0-5]  × 0.5                     │ │
│  │    └─ Number of IP changes × 0.5                                 │ │
│  │                                                                   │ │
│  │  Factor 7: Time-based Analysis                                   │ │
│  │    └─ Implicit in burst detection                                │ │
│  │                                                                   │ │
│  │  ┌─────────────────────────────────────────────────────────────┐ │ │
│  │  │  TOTAL SEVERITY = Σ(Factor × Weight)                        │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   LEGITIMACY FILTER                                     │
│                                                                         │
│  ┌────────────────────┐        ┌────────────────────┐                  │
│  │  Auto Whitelist    │        │  Manual Whitelist  │                  │
│  │  ┌──────────────┐  │        │  ┌──────────────┐  │                  │
│  │  │ DHCP Servers │  │        │  │   Routers    │  │                  │
│  │  │ (>80% DHCP)  │  │        │  │   Known MAC  │  │                  │
│  │  └──────────────┘  │        │  └──────────────┘  │                  │
│  │  ┌──────────────┐  │        │  ┌──────────────┐  │                  │
│  │  │ mDNS Devices │  │        │  │ DHCP Servers │  │                  │
│  │  │ (<2 pkt/sec) │  │        │  │   Known MAC  │  │                  │
│  │  └──────────────┘  │        │  └──────────────┘  │                  │
│  └────────────────────┘        └────────────────────┘                  │
│           │                              │                              │
│           └──────────────┬───────────────┘                              │
│                          ▼                                              │
│              ┌────────────────────────┐                                 │
│              │  Legitimacy Checker    │                                 │
│              │  ├─ Check whitelist    │                                 │
│              │  ├─ Pattern analysis   │                                 │
│              │  └─ Behavior scoring   │                                 │
│              └────────────┬───────────┘                                 │
│                           │                                             │
│                ┌──────────┴──────────┐                                  │
│                ▼                     ▼                                  │
│         ┌────────────┐        ┌────────────┐                           │
│         │ Legitimate │        │ Suspicious │                           │
│         │  (Filter)  │        │  (Report)  │                           │
│         └────────────┘        └─────┬──────┘                           │
└───────────────────────────────────────┼──────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   DECISION & REPORTING LAYER                            │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Severity Thresholds:                                           │   │
│  │  ├─ 0-30:   Clean (No action)                                   │   │
│  │  ├─ 30-50:  Suspicious (Log)                                    │   │
│  │  ├─ 50-100: Warning (Alert)                                     │   │
│  │  └─ 100+:   Critical Loop (Immediate action)                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │
│  │   Database   │  │   Webhook    │  │    Email     │                 │
│  │   Storage    │  │    Alert     │  │    Alert     │                 │
│  └──────────────┘  └──────────────┘  └──────────────┘                 │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │
│  │   Logging    │  │    Report    │  │  Dashboard   │                 │
│  │   System     │  │  Generation  │  │  Integration │                 │
│  └──────────────┘  └──────────────┘  └──────────────┘                 │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Multi-Subnet Detection Flow

```
Network Topology:
┌──────────────────────────────────────────────────────────────────┐
│                        Router/Gateway                            │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐             │
│  │   eth0     │    │   eth1     │    │   wlan0    │             │
│  │ 192.168.   │    │  10.0.0.   │    │  172.16.   │             │
│  │   1.0/24   │    │   0.0/24   │    │   0.0/24   │             │
│  └─────┬──────┘    └─────┬──────┘    └─────┬──────┘             │
└────────┼─────────────────┼─────────────────┼──────────────────────┘
         │                 │                 │
         ▼                 ▼                 ▼
   ┌─────────┐       ┌─────────┐       ┌─────────┐
   │ Subnet 1│       │ Subnet 2│       │ Subnet 3│
   │ Devices │       │ Devices │       │ Devices │
   └─────────┘       └─────────┘       └─────────┘

Detection Process:
┌─────────────────────────────────────────────────────────────────┐
│ 1. Monitor all interfaces simultaneously (multi-threaded)       │
│    ├─ Thread 1: eth0  (192.168.1.0/24)                         │
│    ├─ Thread 2: eth1  (10.0.0.0/24)                            │
│    └─ Thread 3: wlan0 (172.16.0.0/24)                          │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Track packets per MAC across all subnets                    │
│    MAC aa:bb:cc:dd:ee:ff seen in:                              │
│    ├─ 192.168.1.105 (Subnet 1)                                 │
│    └─ 10.0.0.50     (Subnet 2)  ← SUSPICIOUS!                  │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Apply cross-subnet penalty                                  │
│    Base severity: 45                                            │
│    + Subnet penalty: 2 subnets × 3 = 6                         │
│    + Weighted by factor: 6 × 1.8 = 10.8                        │
│    Total: 45 + 10.8 = 55.8 ← ALERT!                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Packet Processing Pipeline

```
   Incoming Packet
         │
         ▼
   ┌──────────┐
   │ Sampling │  ← Dynamic rate based on traffic
   │  Filter  │
   └────┬─────┘
        │ (20-100% of packets)
        ▼
   ┌──────────┐
   │   Hash   │  ← Duplicate detection
   │  Check   │
   └────┬─────┘
        │ (Unique packets only)
        ▼
   ┌──────────┐
   │ Protocol │  ← Classify packet type
   │ Classify │     (ARP, STP, LLDP, etc.)
   └────┬─────┘
        │
        ▼
   ┌──────────┐
   │ Extract  │  ← Get MAC, IP, subnet
   │  Metadata│
   └────┬─────┘
        │
        ▼
   ┌──────────┐
   │  Update  │  ← Update tracking database
   │ Tracking │
   └────┬─────┘
        │
        ▼
   ┌──────────┐
   │Calculate │  ← 7-factor severity
   │ Severity │
   └────┬─────┘
        │
        ▼
   ┌──────────┐
   │  Check   │  ← Legitimacy filter
   │Whitelist │
   └────┬─────┘
        │
        ▼
   ┌──────────┐
   │ Report / │  ← Output results
   │  Alert   │
   └──────────┘
```

---

## Performance Optimization Flow

```
Low Traffic (<100 pkt/s)          High Traffic (>500 pkt/s)
        │                                   │
        ▼                                   ▼
┌───────────────┐                   ┌───────────────┐
│ Analyze ALL   │                   │ Sample 1/5-10 │
│   packets     │                   │    packets    │
│               │                   │               │
│ sample_rate=1 │                   │ sample_rate=5 │
└───────┬───────┘                   └───────┬───────┘
        │                                   │
        └──────────────┬────────────────────┘
                       │
                       ▼
               ┌───────────────┐
               │ Duplicate     │
               │ Detection     │
               │ (~30% savings)│
               └───────┬───────┘
                       │
                       ▼
               ┌───────────────┐
               │ Early Exit    │
               │ (if >1000 pkts│
               │   analyzed)   │
               └───────┬───────┘
                       │
                       ▼
               ┌───────────────┐
               │ Memory Mgmt   │
               │ (deque limits,│
               │  periodic GC) │
               └───────┬───────┘
                       │
                       ▼
                  Efficient
                  Detection
```

---

## Legitimacy Decision Tree

```
                    Packet from MAC
                         │
                         ▼
              ┌──────────────────────┐
              │ In manual whitelist? │
              └──────┬───────┬───────┘
                Yes  │       │  No
                     │       │
                     ▼       ▼
                 Legitimate  │
                             │
              ┌──────────────┴────────┐
              │ >80% DHCP traffic?    │
              │  + Count <100?        │
              └──────┬───────┬────────┘
                Yes  │       │  No
                     │       │
                     ▼       ▼
                 Legitimate  │
                             │
              ┌──────────────┴────────┐
              │ mDNS traffic present? │
              │  + Rate <2 pkt/sec?   │
              └──────┬───────┬────────┘
                Yes  │       │  No
                     │       │
                     ▼       ▼
                 Legitimate  │
                             │
              ┌──────────────┴────────┐
              │ Known router MAC?     │
              └──────┬───────┬────────┘
                Yes  │       │  No
                     │       │
                     ▼       ▼
                 Legitimate  Suspicious
                             │
                             ▼
                      Analyze with
                      full severity
```

---

## Data Structures

### MAC History Database

```python
mac_history = {
    "aa:bb:cc:dd:ee:ff": {
        "packet_times": deque([
            1698156000.123,  # Timestamp 1
            1698156000.156,  # Timestamp 2
            ...              # Up to 1000 timestamps
        ], maxlen=1000),
        
        "ip_changes": deque([
            (1698156000.123, "192.168.1.105"),
            (1698156123.456, "192.168.1.106"),
            ...  # Up to 50 IP changes
        ], maxlen=50),
        
        "subnets": {
            "192.168.1.0/24",
            "10.0.0.0/24"
        },
        
        "first_seen": 1698156000.123,
        "last_ip": "192.168.1.106"
    }
}
```

### Stats Output Structure

```python
stats = {
    "aa:bb:cc:dd:ee:ff": {
        "count": 150,
        "arp_count": 80,
        "dhcp_count": 5,
        "mdns_count": 10,
        "nbns_count": 2,
        "stp_count": 30,
        "lldp_count": 10,
        "cdp_count": 5,
        "icmp_redirect_count": 8,
        "other_count": 0,
        
        "ips": ["192.168.1.105", "10.0.0.50"],
        "subnets": ["192.168.1.0/24", "10.0.0.0/24"],
        "hosts": ["device1.local", "Unknown"],
        
        "fingerprints": {
            "Ether / ARP who has 192.168.1.1": 50,
            "Ether / IP / UDP 67 > 68": 5,
            ...
        },
        
        "severity": {
            "total": 125.5,
            "frequency": 8.2,
            "bursts": 6.5,
            "entropy": 3.1,
            "subnets": 6.0,
            "packet_types": 95.2,
            "ip_changes": 2.5
        },
        
        "is_legitimate": False,
        "legitimate_reason": None
    }
}
```

---

## Configuration Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│                       User Configuration                    │
│  loop_detection_config.py                                   │
│  ├─ DETECTION_MODE = "lightweight"/"advanced"/"auto"        │
│  ├─ CAPTURE_TIMEOUT = 5                                     │
│  ├─ SEVERITY_THRESHOLD = 50                                 │
│  ├─ ENABLE_SAMPLING = True                                  │
│  ├─ WHITELIST_ROUTERS = {...}                               │
│  └─ SAVE_TO_DATABASE = True                                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Configuration Presets                    │
│  ├─ development: Quick checks, debug logging                │
│  ├─ production_small: 50-200 devices                        │
│  ├─ production_large: 200+ devices, multi-interface         │
│  └─ troubleshooting: Detailed analysis, low threshold       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Default Parameters                       │
│  ├─ MIN_INTERVAL = 5                                        │
│  ├─ MAX_INTERVAL = 60                                       │
│  ├─ HIGH_BW_THRESHOLD = 20                                  │
│  └─ PACKET_WEIGHTS = {...}                                  │
└─────────────────────────────────────────────────────────────┘
```

---

**Note:** All diagrams are text-based for cross-platform compatibility. For graphical diagrams, consider using tools like draw.io, Lucidchart, or PlantUML with the textual descriptions provided above.
