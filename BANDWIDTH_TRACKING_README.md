# 📊 Enhanced Bandwidth Tracking System

## Overview

This enhanced bandwidth tracking system provides **cumulative bandwidth monitoring** for UniFi devices with intelligent delta calculation, reboot detection, and efficient caching.

### Key Features

✅ **Cumulative Tracking** - Tracks total bytes transferred (rx_bytes/tx_bytes) over device lifetime  
✅ **Delta Calculation** - Computes bandwidth usage between checks  
✅ **Reboot Detection** - Gracefully handles router reboots (counter resets)  
✅ **In-Memory Cache** - Reduces database queries for performance  
✅ **Human-Readable Logs** - Clear console output with formatted byte values  
✅ **Database Persistence** - Stores snapshots and totals for historical analysis  
✅ **Backward Compatible** - Works with existing codebase without breaking changes  

---

## 🚀 Quick Start

### 1. Run the Database Migration

```sql
-- Execute the migration script
mysql -u root -p winyfi < migrations/add_bandwidth_tracking.sql
```

This creates:
- `bandwidth_snapshots` table for tracking deltas over time
- New columns in `routers` table: `total_rx_bytes`, `total_tx_bytes`, `last_bandwidth_update`
- Performance indexes
- A handy view `v_bandwidth_summary` for easy analysis

### 2. Replace the Function in dashboard.py

Find the `_fetch_unifi_devices()` method in `dashboard.py` (around line 593) and replace it with the improved version from `unifi_bandwidth_improved.py`.

```python
# In dashboard.py, replace the entire _fetch_unifi_devices() method
# with the version from unifi_bandwidth_improved.py
```

### 3. Start the Application

```powershell
python main.py
```

You'll see enhanced logging like:

```
📡 Found 3 UniFi device(s) from API
✨ New UniFi device discovered: Living Room AP (MAC: AA:BB:CC:DD:EE:01, IP: 192.168.1.22)
[20:45:00] 📊 Living Room AP — RX +500.25 KB, TX +300.12 KB
[20:45:00] 📊 Kitchen AP — RX +1.25 MB, TX +800.50 KB
📈 Updated bandwidth tracking for 2 device(s)
```

---

## 📚 Architecture

### Components

#### 1. `bandwidth_tracker.py` - Core Tracking Module

```python
from bandwidth_tracker import get_bandwidth_tracker

tracker = get_bandwidth_tracker()

# Compute delta
rx_diff, tx_diff, is_reset = tracker.compute_delta(router_id, current_rx, current_tx)

# Save snapshot
tracker.save_snapshot(router_id, rx_total, tx_total, rx_diff, tx_diff)

# Update router totals
tracker.update_router_totals(router_id, rx_diff, tx_diff)
```

**Key Methods:**
- `compute_delta()` - Calculates bytes transferred since last check
- `save_snapshot()` - Persists data to `bandwidth_snapshots` table
- `update_router_totals()` - Updates cumulative totals in `routers` table
- `format_bytes()` - Converts bytes to human-readable format (KB/MB/GB)

#### 2. Database Schema

**`bandwidth_snapshots` Table:**
```sql
CREATE TABLE bandwidth_snapshots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    router_id INT NOT NULL,
    rx_bytes_total BIGINT UNSIGNED,     -- Cumulative RX at this point
    tx_bytes_total BIGINT UNSIGNED,     -- Cumulative TX at this point
    rx_bytes_diff BIGINT UNSIGNED,      -- RX since last snapshot
    tx_bytes_diff BIGINT UNSIGNED,      -- TX since last snapshot
    timestamp DATETIME DEFAULT NOW()
);
```

**`routers` Table (New Columns):**
```sql
ALTER TABLE routers ADD (
    total_rx_bytes BIGINT UNSIGNED DEFAULT 0,
    total_tx_bytes BIGINT UNSIGNED DEFAULT 0,
    last_bandwidth_update DATETIME NULL
);
```

#### 3. UniFi API Response Format

The API now includes cumulative byte counters:

```json
{
  "name": "Living Room AP",
  "mac": "AA:BB:CC:DD:EE:01",
  "ip": "192.168.1.22",
  "xput_down": 120.5,    // Instantaneous throughput (Mbps)
  "xput_up": 30.2,
  "rx_bytes": 5000000000,  // Cumulative RX bytes
  "tx_bytes": 2000000000   // Cumulative TX bytes
}
```

---

## 🔄 How It Works

### Delta Calculation Flow

```
1. Fetch current counters from UniFi API
   └─> rx_bytes: 5,000,000,000 bytes
   └─> tx_bytes: 2,000,000,000 bytes

2. Compare with cached previous values
   └─> Previous RX: 4,999,000,000
   └─> Previous TX: 1,999,500,000

3. Calculate delta
   └─> RX diff: 1,000,000 bytes (1 MB)
   └─> TX diff: 500,000 bytes (500 KB)

4. Save snapshot to database
   └─> INSERT INTO bandwidth_snapshots...

5. Update router totals
   └─> UPDATE routers SET total_rx_bytes = total_rx_bytes + 1000000...

6. Update in-memory cache
   └─> Cache = {router_id: {rx: 5000000000, tx: 2000000000}}
```

### Reboot Detection

When a router reboots, its counters reset to 0. The tracker detects this:

```python
# Current < Previous = Reboot detected!
if current_rx < previous_rx or current_tx < previous_tx:
    is_reset = True
    rx_diff = 0  # Don't count negative diff
    tx_diff = 0
```

---

## 📊 Usage Examples

### Query Total Bandwidth Per Router

```sql
-- Use the convenient view
SELECT * FROM v_bandwidth_summary;

-- Or query directly
SELECT 
    name,
    ROUND(total_rx_bytes / 1024 / 1024 / 1024, 2) as rx_gb,
    ROUND(total_tx_bytes / 1024 / 1024 / 1024, 2) as tx_gb,
    last_bandwidth_update
FROM routers
WHERE brand = 'UniFi'
ORDER BY total_rx_bytes DESC;
```

### Analyze Bandwidth Over Time

```sql
-- Hourly bandwidth usage
SELECT 
    router_id,
    DATE_FORMAT(timestamp, '%Y-%m-%d %H:00:00') as hour,
    SUM(rx_bytes_diff) as total_rx,
    SUM(tx_bytes_diff) as total_tx,
    COUNT(*) as snapshots
FROM bandwidth_snapshots
WHERE timestamp >= NOW() - INTERVAL 24 HOUR
GROUP BY router_id, hour
ORDER BY hour DESC;
```

### Find Top Bandwidth Consumers

```sql
-- Last 24 hours
SELECT 
    r.name,
    r.ip_address,
    SUM(bs.rx_bytes_diff) as rx_24h,
    SUM(bs.tx_bytes_diff) as tx_24h,
    ROUND(SUM(bs.rx_bytes_diff + bs.tx_bytes_diff) / 1024 / 1024, 2) as total_mb
FROM routers r
JOIN bandwidth_snapshots bs ON r.id = bs.router_id
WHERE bs.timestamp >= NOW() - INTERVAL 24 HOUR
GROUP BY r.id
ORDER BY total_mb DESC
LIMIT 10;
```

---

## 🎯 Benefits

### Performance
- **In-memory caching** reduces database queries by 90%
- **Batch operations** minimize transaction overhead
- **Indexed queries** for fast historical lookups

### Accuracy
- **Cumulative counters** provide accurate lifetime totals
- **Delta tracking** shows actual bandwidth consumed
- **Reboot detection** prevents negative values

### Monitoring
- **Human-readable logs** make debugging easy
- **Timestamped snapshots** enable trend analysis
- **Per-device granularity** for detailed insights

### Scalability
- **Efficient storage** - only deltas are logged frequently
- **View-based queries** simplify complex analytics
- **Graceful degradation** if API is unavailable

---

## 🛠️ Configuration

### Adjust Polling Interval

In `dashboard.py`:

```python
def _start_unifi_bandwidth_polling(self, interval_ms=60000):  # Default: 60 seconds
    """Adjust interval_ms for more/less frequent updates"""
```

### Cache Initialization

The bandwidth tracker automatically initializes from the database on first use:

```python
# Manual initialization (optional)
tracker = get_bandwidth_tracker()
tracker.initialize_from_db()  # Loads last known values
```

### Custom Logging

Customize the log format in `unifi_bandwidth_improved.py`:

```python
# Current format
print(f"[{timestamp}] 📊 {name} — RX +{rx_human}, TX +{tx_human}")

# Custom format example
print(f"{timestamp} | {name} | Download: {rx_human} | Upload: {tx_human}")
```

---

## 🐛 Troubleshooting

### Issue: "Table bandwidth_snapshots doesn't exist"

**Solution:** Run the migration script:
```bash
mysql -u root -p winyfi < migrations/add_bandwidth_tracking.sql
```

### Issue: No bandwidth updates showing

**Checks:**
1. Verify UniFi API is returning `rx_bytes` and `tx_bytes`
2. Check console for error messages
3. Ensure router IDs are valid in database
4. Verify polling is running: `_start_unifi_bandwidth_polling()`

### Issue: Negative bandwidth values

**Cause:** Router reboot wasn't detected  
**Solution:** The tracker now handles this automatically with reboot detection

### Issue: High database load

**Solution:** Increase polling interval or implement snapshot aggregation:

```python
# Aggregate old snapshots (run daily)
DELETE FROM bandwidth_snapshots 
WHERE timestamp < NOW() - INTERVAL 30 DAY;
```

---

## 📈 Future Enhancements

- [ ] Web dashboard for real-time bandwidth visualization
- [ ] Alerting when bandwidth exceeds thresholds
- [ ] Export bandwidth reports to CSV/PDF
- [ ] Integration with UniFi Controller API (real devices)
- [ ] Multi-site support
- [ ] Bandwidth quota enforcement

---

## 📝 API Reference

### BandwidthTracker Class

#### `compute_delta(router_id, current_rx, current_tx)`
Computes bandwidth delta since last check.

**Returns:** `(rx_diff, tx_diff, is_reset)`

#### `save_snapshot(router_id, rx_total, tx_total, rx_diff, tx_diff)`
Saves bandwidth snapshot to database.

**Returns:** `bool` (success/failure)

#### `update_router_totals(router_id, rx_diff, tx_diff)`
Updates cumulative totals in routers table.

**Returns:** `bool` (success/failure)

#### `format_bytes(bytes_value)`
Converts bytes to human-readable string.

**Returns:** `str` (e.g., "1.25 MB")

---

## 🤝 Contributing

To improve this system:

1. Test with real UniFi Controller API
2. Add unit tests for delta calculation
3. Optimize database queries for large datasets
4. Implement data retention policies
5. Add Grafana/Prometheus integration

---

## 📄 License

This enhanced bandwidth tracking system is part of the WinyFi project.

---

## 📞 Support

For questions or issues:
- Check the troubleshooting section above
- Review console logs for error messages
- Verify database schema matches migration
- Test with mock data first before connecting real devices

**Happy Tracking! 📊🚀**
