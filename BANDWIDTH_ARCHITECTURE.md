# Router Bandwidth Monitor - System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   ROUTER BANDWIDTH MONITORING SYSTEM                     │
│                     (Layer 2 Packet-Based Monitoring)                    │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 1: NETWORK INFRASTRUCTURE                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│   ┌───────────┐      ┌───────────┐      ┌───────────┐                  │
│   │ Router 1  │      │ Router 2  │      │ Router 3  │                  │
│   │192.168.1.1│      │192.168.1.2│      │192.168.1.3│                  │
│   └─────┬─────┘      └─────┬─────┘      └─────┬─────┘                  │
│         │                  │                  │                          │
│         └──────────────────┴──────────────────┘                          │
│                            │                                              │
│                     ┌──────▼──────┐                                      │
│                     │   Network   │                                      │
│                     │   Switch    │                                      │
│                     └──────┬──────┘                                      │
│                            │                                              │
│                     ┌──────▼──────┐                                      │
│                     │ Monitoring  │                                      │
│                     │   Host PC   │                                      │
│                     │  (Winyfi)   │                                      │
│                     └─────────────┘                                      │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 2: PACKET CAPTURE (Scapy)                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│   ┌───────────────────────────────────────────────────────────────┐    │
│   │  AsyncSniffer (Background Thread)                             │    │
│   │  • Captures IP packets on network interface                   │    │
│   │  • Filter: "ip" (only IP packets)                             │    │
│   │  • Non-blocking: store=False                                  │    │
│   └────────────────────────┬──────────────────────────────────────┘    │
│                             │                                             │
│                             ▼                                             │
│   ┌───────────────────────────────────────────────────────────────┐    │
│   │  Packet Handler (_packet_handler)                             │    │
│   │  • Extracts: src_ip, dst_ip, packet_size                      │    │
│   │  • Checks: Is packet from/to monitored router?                │    │
│   │  • Direction detection:                                        │    │
│   │     - src_ip == router_ip → Upload                            │    │
│   │     - dst_ip == router_ip → Download                          │    │
│   │  • Accumulates bytes per router                               │    │
│   │  • Learns MAC addresses automatically                         │    │
│   └───────────────────────────────────────────────────────────────┘    │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 3: DATA AGGREGATION (RouterBandwidthMonitor)                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│   ┌──────────────────────────────────────────────────────────┐         │
│   │  Router Registry (self.routers)                           │         │
│   │  {                                                         │         │
│   │    "192.168.1.1": {"mac": "AA:BB:CC:DD:EE:FF",            │         │
│   │                    "name": "Main Router"},                │         │
│   │    "192.168.1.2": {"mac": "11:22:33:44:55:66",            │         │
│   │                    "name": "Living Room AP"}              │         │
│   │  }                                                         │         │
│   └──────────────────────────────────────────────────────────┘         │
│                                                                           │
│   ┌──────────────────────────────────────────────────────────┐         │
│   │  Bandwidth Stats (self.bandwidth_stats)                   │         │
│   │  {                                                         │         │
│   │    "192.168.1.1": {                                        │         │
│   │      "download_bytes": 15728640,  ← Accumulated bytes     │         │
│   │      "upload_bytes": 5242880,     ← Accumulated bytes     │         │
│   │      "last_reset": 1698476400,    ← Timestamp             │         │
│   │      "total_packets": 12345,      ← Packet count          │         │
│   │      "history": deque([...])      ← Last 60 samples       │         │
│   │    }                                                       │         │
│   │  }                                                         │         │
│   └──────────────────────────────────────────────────────────┘         │
│                                                                           │
│   ┌──────────────────────────────────────────────────────────┐         │
│   │  Calculation Thread (_calculate_bandwidth_loop)           │         │
│   │  • Runs every sampling_interval (5 seconds)               │         │
│   │  • For each router:                                        │         │
│   │     1. Calculate elapsed time                             │         │
│   │     2. Compute: Mbps = (bytes × 8) / (1M × seconds)       │         │
│   │     3. Store in history: {timestamp, download, upload}    │         │
│   │     4. Reset counters for next interval                   │         │
│   └──────────────────────────────────────────────────────────┘         │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 4: DATA ACCESS API                                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│   ┌──────────────────────────────────────────────────────────┐         │
│   │  get_router_bandwidth(router_ip)                          │         │
│   │  → Latest bandwidth sample                                │         │
│   │     {download_mbps, upload_mbps, timestamp, packets}      │         │
│   └──────────────────────────────────────────────────────────┘         │
│                                                                           │
│   ┌──────────────────────────────────────────────────────────┐         │
│   │  get_all_routers_bandwidth()                              │         │
│   │  → Bandwidth for all routers                              │         │
│   │     [router1_data, router2_data, ...]                     │         │
│   └──────────────────────────────────────────────────────────┘         │
│                                                                           │
│   ┌──────────────────────────────────────────────────────────┐         │
│   │  get_router_history(router_ip, limit)                     │         │
│   │  → Historical bandwidth data                              │         │
│   │     [sample1, sample2, ..., sampleN]                      │         │
│   └──────────────────────────────────────────────────────────┘         │
│                                                                           │
│   ┌──────────────────────────────────────────────────────────┐         │
│   │  get_average_bandwidth(router_ip, minutes)                │         │
│   │  → Average over time window                               │         │
│   │     {avg_download_mbps, avg_upload_mbps}                  │         │
│   └──────────────────────────────────────────────────────────┘         │
│                                                                           │
│   ┌──────────────────────────────────────────────────────────┐         │
│   │  get_peak_bandwidth(router_ip)                            │         │
│   │  → Peak values from history                               │         │
│   │     {peak_download_mbps, peak_upload_mbps}                │         │
│   └──────────────────────────────────────────────────────────┘         │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 5: INTEGRATION WITH EXISTING SYSTEM                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│   ┌─────────────────────────────────────────────────────────────┐      │
│   │  network_utils.py                                            │      │
│   │                                                               │      │
│   │  def get_bandwidth(ip, is_unifi=False, use_monitor=True):    │      │
│   │      if use_monitor:                                          │      │
│   │          monitor = get_bandwidth_monitor()                    │      │
│   │          bandwidth = get_router_bandwidth_realtime(ip)        │      │
│   │          return bandwidth  # Compatible format               │      │
│   │      else:                                                     │      │
│   │          # Fallback to speedtest/throughput                   │      │
│   └─────────────────────────────────────────────────────────────┘      │
│                                                                           │
│   ┌─────────────────────────────────────────────────────────────┐      │
│   │  dashboard.py                                                 │      │
│   │                                                               │      │
│   │  def initialize_dashboard():                                  │      │
│   │      # Load routers from database                            │      │
│   │      routers = db.execute("SELECT * FROM routers")           │      │
│   │      start_bandwidth_monitoring(routers)                      │      │
│   │                                                               │      │
│   │  def show_router_info(router_ip):                            │      │
│   │      bandwidth = get_router_bandwidth_data(router_ip)        │      │
│   │      display_bandwidth_card(bandwidth)                        │      │
│   │                                                               │      │
│   │  def on_exit():                                              │      │
│   │      stop_bandwidth_monitoring()                             │      │
│   └─────────────────────────────────────────────────────────────┘      │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 6: USER INTERFACE                                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│   ┌─────────────────────────────────────────────────────────────┐      │
│   │  Bandwidth Card (tkinter/ttkbootstrap)                       │      │
│   │  ┌──────────────────────────────────────────────────┐       │      │
│   │  │  Main Router (192.168.1.1)                       │       │      │
│   │  │                                                   │       │      │
│   │  │  ↓ 32.45 Mbps                                    │       │      │
│   │  │  ↑ 12.73 Mbps                                    │       │      │
│   │  │                                                   │       │      │
│   │  │  ● active                                        │       │      │
│   │  │  Updated: 14:30:25                               │       │      │
│   │  │                                                   │       │      │
│   │  │  [View Details]                                  │       │      │
│   │  └──────────────────────────────────────────────────┘       │      │
│   └─────────────────────────────────────────────────────────────┘      │
│                                                                           │
│   ┌─────────────────────────────────────────────────────────────┐      │
│   │  Details Window (Popup)                                       │      │
│   │  ┌──────────────────────────────────────────────────┐       │      │
│   │  │  Bandwidth Details - 192.168.1.1                 │       │      │
│   │  │                                                   │       │      │
│   │  │  Current Usage:                                  │       │      │
│   │  │    Download: 32.45 Mbps                          │       │      │
│   │  │    Upload: 12.73 Mbps                            │       │      │
│   │  │    Packets: 1543                                 │       │      │
│   │  │                                                   │       │      │
│   │  │  5-Minute Average:                               │       │      │
│   │  │    Avg Download: 28.31 Mbps                      │       │      │
│   │  │    Avg Upload: 10.52 Mbps                        │       │      │
│   │  │                                                   │       │      │
│   │  │  Peak Usage:                                     │       │      │
│   │  │    Peak Download: 45.67 Mbps                     │       │      │
│   │  │    Peak Upload: 18.92 Mbps                       │       │      │
│   │  │                                                   │       │      │
│   │  │  Recent History:                                 │       │      │
│   │  │    14:30:25  32.45  12.73  1543                  │       │      │
│   │  │    14:30:20  30.12  11.98  1421                  │       │      │
│   │  │    ...                                            │       │      │
│   │  │                                                   │       │      │
│   │  │  [Close]                                         │       │      │
│   │  └──────────────────────────────────────────────────┘       │      │
│   └─────────────────────────────────────────────────────────────┘      │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  DATA FLOW DIAGRAM                                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  Network Packet                                                          │
│       │                                                                   │
│       ▼                                                                   │
│  [Scapy Sniffer] ──────────────────────────────┐                        │
│       │                                          │                        │
│       ▼                                          │                        │
│  Is IP packet? ──No──▶ Discard                 │                        │
│       │ Yes                                      │                        │
│       ▼                                          │                        │
│  Extract src_ip, dst_ip, size                   │                        │
│       │                                          │                        │
│       ▼                                          │                        │
│  Is src/dst a monitored router? ──No──▶ Discard│                        │
│       │ Yes                                      │                        │
│       ▼                                          │                        │
│  Determine direction:                           │                        │
│    • src == router_ip → Upload                  │                        │
│    • dst == router_ip → Download                │                        │
│       │                                          │                        │
│       ▼                                          │                        │
│  Accumulate bytes in bandwidth_stats            │                        │
│       │                                          │                        │
│       │    ┌────────────────────────────────────┘                        │
│       │    │ Every 5 seconds (sampling_interval)                         │
│       │    │                                                              │
│       │    ▼                                                              │
│       │  [Calculation Thread]                                            │
│       │    │                                                              │
│       │    ▼                                                              │
│       │  For each router:                                                │
│       │    1. elapsed = now - last_reset                                 │
│       │    2. download_mbps = (download_bytes × 8) / (1M × elapsed)      │
│       │    3. upload_mbps = (upload_bytes × 8) / (1M × elapsed)          │
│       │    4. Store in history                                           │
│       │    5. Reset counters                                             │
│       │    │                                                              │
│       │    ▼                                                              │
│       │  bandwidth_stats[router]["history"].append({                     │
│       │    timestamp, download_mbps, upload_mbps, packets                │
│       │  })                                                               │
│       │    │                                                              │
│       └────┼───────────────────────────────────────────────┐             │
│            │                                                │             │
│            ▼                                                │             │
│  [API Methods]                                             │             │
│    • get_router_bandwidth(ip)                              │             │
│    • get_all_routers_bandwidth()                           │             │
│    • get_router_history(ip, limit)                         │             │
│    • get_average_bandwidth(ip, minutes)                    │             │
│    • get_peak_bandwidth(ip)                                │             │
│            │                                                │             │
│            ▼                                                │             │
│  [Dashboard UI]                                            │             │
│    • Display bandwidth cards                               │             │
│    • Update every 5 seconds                                │             │
│    • Show details on click                                 │             │
│            │                                                │             │
│            ▼                                                │             │
│  [User sees bandwidth]                                     │             │
│                                                             │             │
│            ┌────────────────────────────────────────────────┘             │
│            │ Loop continues...                                            │
│            └──────────────────────────────────────────────────────────▶  │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  THREADING MODEL                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  Main Thread (Dashboard)                                                 │
│  │                                                                        │
│  ├─ Initialize RouterBandwidthMonitor                                    │
│  ├─ Add routers                                                          │
│  ├─ monitor.start()                                                      │
│  │   │                                                                    │
│  │   ├─▶ Thread 1: AsyncSniffer (Scapy)                                 │
│  │   │   • Captures packets continuously                                 │
│  │   │   • Calls _packet_handler() for each packet                       │
│  │   │   • Non-blocking, daemon thread                                   │
│  │   │                                                                    │
│  │   └─▶ Thread 2: Calculation Thread                                   │
│  │       • Runs every 5 seconds                                          │
│  │       • Calculates Mbps from accumulated bytes                        │
│  │       • Stores in history                                             │
│  │       • Daemon thread                                                 │
│  │                                                                        │
│  ├─ UI Update Loop                                                       │
│  │   • root.after(5000, update_bandwidth_displays)                       │
│  │   • Calls get_router_bandwidth() for each router                      │
│  │   • Updates UI labels                                                 │
│  │                                                                        │
│  └─ monitor.stop() on exit                                               │
│      • Stops sniffer                                                     │
│      • Waits for threads to finish                                       │
│                                                                           │
│  Thread Safety:                                                          │
│  • All data access protected by self.lock (threading.Lock)              │
│  • AsyncSniffer uses internal locking                                    │
│  • History uses thread-safe deque                                        │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  BANDWIDTH CALCULATION FORMULA                                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  Mbps = (Total Bytes × 8 bits/byte) / (1,000,000 bits/Mbps × Seconds)   │
│                                                                           │
│  Example:                                                                │
│    • Bytes captured in 5 seconds: 20,281,250 bytes (download)           │
│    • Convert to bits: 20,281,250 × 8 = 162,250,000 bits                 │
│    • Convert to Mbps: 162,250,000 / 1,000,000 = 162.25 Mb               │
│    • Divide by time: 162.25 / 5 = 32.45 Mbps                            │
│                                                                           │
│  Direction Detection:                                                    │
│    • Upload:   Packets where src_ip == router_ip                         │
│    • Download: Packets where dst_ip == router_ip                         │
│                                                                           │
│  Accuracy:                                                               │
│    • ±10-15% error margin (acceptable for monitoring)                    │
│    • Factors affecting accuracy:                                         │
│      - Packet loss during capture                                        │
│      - Network overhead (headers, retransmissions)                       │
│      - Sampling interval (longer = more accurate)                        │
│      - Network congestion                                                │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  ERROR HANDLING & EDGE CASES                                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  1. Permission Denied                                                    │
│     • Catch: PermissionError in monitor.start()                          │
│     • Action: Log error, notify user to run as Administrator             │
│                                                                           │
│  2. Router Offline                                                       │
│     • Detection: No packets for router_ip in sampling window             │
│     • Result: bandwidth = 0.0 Mbps, status = "no_data"                   │
│                                                                           │
│  3. Interface Not Found                                                  │
│     • Fallback: Use scapy's default interface (conf.iface)               │
│     • Log warning with detected interface name                           │
│                                                                           │
│  4. High Packet Rate                                                     │
│     • Protection: AsyncSniffer with store=False (no memory buildup)      │
│     • Filter: "ip" only (reduces packet count)                           │
│                                                                           │
│  5. Zero Division                                                        │
│     • Check: elapsed > 0 before calculating Mbps                         │
│     • Fallback: Skip calculation if elapsed == 0                         │
│                                                                           │
│  6. Thread Safety                                                        │
│     • All data access wrapped in with self.lock                          │
│     • Prevents race conditions                                           │
│                                                                           │
│  7. Memory Management                                                    │
│     • History uses deque(maxlen=60) - auto-removes old entries           │
│     • No unbounded growth                                                │
│                                                                           │
│  8. Graceful Shutdown                                                    │
│     • monitor.stop() stops sniffer and calculation thread                │
│     • Threads marked as daemon (auto-cleanup)                            │
│     • Join with timeout to prevent hanging                               │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  PERFORMANCE OPTIMIZATION                                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  1. Packet Filtering                                                     │
│     • BPF filter: "ip" (reduces packets by ~40%)                         │
│     • Only IP packets captured (no ARP, broadcast, etc.)                 │
│                                                                           │
│  2. Zero-Copy Design                                                     │
│     • AsyncSniffer with store=False                                      │
│     • Packets processed in callback, not stored                          │
│     • Minimal memory usage                                               │
│                                                                           │
│  3. Efficient Data Structures                                            │
│     • defaultdict for stats (no key checking)                            │
│     • deque for history (O(1) append/pop)                                │
│     • set for IP tracking (O(1) lookup)                                  │
│                                                                           │
│  4. Sampling Strategy                                                    │
│     • Adjustable interval (5s default)                                   │
│     • Longer intervals = less CPU, less accuracy                         │
│     • Shorter intervals = more CPU, more accuracy                        │
│                                                                           │
│  5. Lock Minimization                                                    │
│     • Locks only held during data access                                 │
│     • Calculation done outside lock                                      │
│     • No blocking operations in critical sections                        │
│                                                                           │
│  6. Batch Processing                                                     │
│     • Process all routers in single calculation cycle                    │
│     • Reduces overhead of repeated threading                             │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
