# 🚀 Quick Integration Guide - Enhanced Bandwidth Tracking

## 📋 Checklist

- [ ] Run database migration
- [ ] Update UniFi API mock (already done)
- [ ] Replace function in dashboard.py
- [ ] Run tests
- [ ] Start application

---

## ⚡ 3-Minute Setup

### 1. Database Migration (30 seconds)
```powershell
# Windows PowerShell
Get-Content migrations\add_bandwidth_tracking.sql | mysql -u root -p winyfi
```

```bash
# Linux/Mac
mysql -u root -p winyfi < migrations/add_bandwidth_tracking.sql
```

### 2. Replace Function (1 minute)

**File:** `dashboard.py` (line ~593)

**Find this:**
```python
def _fetch_unifi_devices(self):
    """Fetch UniFi devices from the UniFi API server and save to database.
    Uses aggressive timeout and error handling to prevent app slowdown."""
```

**Replace with:** The entire function from `unifi_bandwidth_improved.py`

### 3. Test (30 seconds)
```powershell
python test_bandwidth_tracking.py
```

Expected: All tests pass ✅

### 4. Run Application (1 minute)
```powershell
python main.py
```

Look for enhanced logs:
```
[20:45:00] 📊 Living Room AP — RX +1.25 MB, TX +800.50 KB
```

---

## 🔍 Verification

### Check Database Schema
```sql
-- Verify new table exists
SHOW TABLES LIKE 'bandwidth_snapshots';

-- Verify new columns
DESCRIBE routers;
-- Should see: total_rx_bytes, total_tx_bytes, last_bandwidth_update

-- Check view
SELECT * FROM v_bandwidth_summary;
```

### Check Console Output
✅ Should see bandwidth delta logs  
✅ Should see human-readable format (KB/MB/GB)  
✅ Should see timestamps on each log  

### Check Database Data
```sql
-- After a few minutes of running:
SELECT COUNT(*) FROM bandwidth_snapshots;
-- Should have snapshots

SELECT name, total_rx_bytes, total_tx_bytes 
FROM routers 
WHERE brand = 'UniFi';
-- Should have non-zero values
```

---

## 📁 Files Reference

| File | Purpose | Required |
|------|---------|----------|
| `bandwidth_tracker.py` | Core tracking module | ✅ Yes |
| `unifi_bandwidth_improved.py` | Replacement function | ✅ Yes (copy to dashboard.py) |
| `migrations/add_bandwidth_tracking.sql` | Database schema | ✅ Yes (run once) |
| `test_bandwidth_tracking.py` | Test suite | ⭐ Recommended |
| `BANDWIDTH_TRACKING_README.md` | Full documentation | 📖 Reference |
| `BANDWIDTH_TRACKING_SUMMARY.md` | Implementation summary | 📖 Reference |

---

## 🎯 What Changes

### In dashboard.py
**Before:**
```python
insert_bandwidth_log(router_id, float(down or 0), float(up or 0), None)
```

**After:**
```python
# Compute delta
rx_diff, tx_diff, is_reset = tracker.compute_delta(router_id, rx_bytes, tx_bytes)

# Save snapshot
tracker.save_snapshot(router_id, rx_bytes, tx_bytes, rx_diff, tx_diff)

# Update totals
tracker.update_router_totals(router_id, rx_diff, tx_diff)

# Still log instantaneous throughput (backward compatible)
insert_bandwidth_log(router_id, float(down or 0), float(up or 0), None)
```

### In Database
**New table:** `bandwidth_snapshots`
```
+----------------+---------------------+
| Field          | Type                |
+----------------+---------------------+
| id             | int                 |
| router_id      | int                 |
| rx_bytes_total | bigint unsigned     |
| tx_bytes_total | bigint unsigned     |
| rx_bytes_diff  | bigint unsigned     |
| tx_bytes_diff  | bigint unsigned     |
| timestamp      | datetime            |
+----------------+---------------------+
```

**Updated table:** `routers`
```
Added columns:
- total_rx_bytes (bigint unsigned)
- total_tx_bytes (bigint unsigned)
- last_bandwidth_update (datetime)
```

---

## 🐛 Common Issues

### Issue: Migration fails
```
ERROR 1050: Table 'bandwidth_snapshots' already exists
```
**Fix:** Drop and recreate
```sql
DROP TABLE IF EXISTS bandwidth_snapshots;
-- Then run migration again
```

### Issue: No bandwidth logs showing
**Check:**
1. Is UniFi API running? `http://localhost:5001/api/unifi/devices`
2. Do devices have `rx_bytes` and `tx_bytes`?
3. Is `_bandwidth_tracker` initialized?

**Debug:**
```python
# Add to dashboard.py after line 593
print(f"DEBUG: Bandwidth tracker initialized: {hasattr(self, '_bandwidth_tracker')}")
```

### Issue: Negative values
**Shouldn't happen** - reboot detection prevents this.

If it does:
```sql
-- Check for negative deltas
SELECT * FROM bandwidth_snapshots 
WHERE rx_bytes_diff < 0 OR tx_bytes_diff < 0;
```

---

## 📊 Quick Queries

### View bandwidth by router
```sql
SELECT * FROM v_bandwidth_summary;
```

### Last 24 hours usage
```sql
SELECT 
    r.name,
    SUM(bs.rx_bytes_diff) / 1024 / 1024 as rx_mb,
    SUM(bs.tx_bytes_diff) / 1024 / 1024 as tx_mb
FROM bandwidth_snapshots bs
JOIN routers r ON r.id = bs.router_id
WHERE bs.timestamp >= NOW() - INTERVAL 24 HOUR
GROUP BY r.id;
```

### Top bandwidth consumers
```sql
SELECT 
    name,
    ROUND(total_rx_bytes / 1024 / 1024 / 1024, 2) as rx_gb,
    ROUND(total_tx_bytes / 1024 / 1024 / 1024, 2) as tx_gb
FROM routers
WHERE brand = 'UniFi'
ORDER BY (total_rx_bytes + total_tx_bytes) DESC
LIMIT 5;
```

---

## ✅ Success Indicators

After running for 5 minutes, you should see:

✅ **Console logs with deltas:**
```
[20:45:00] 📊 Living Room AP — RX +1.25 MB, TX +800.50 KB
[20:46:00] 📊 Living Room AP — RX +2.10 MB, TX +1.50 MB
```

✅ **Snapshots in database:**
```sql
mysql> SELECT COUNT(*) FROM bandwidth_snapshots;
+-----------+
| COUNT(*)  |
+-----------+
|        15 |  -- 5 min × 3 devices = 15 snapshots
+-----------+
```

✅ **Updated router totals:**
```sql
mysql> SELECT name, total_rx_bytes FROM routers WHERE brand='UniFi';
+----------------+----------------+
| name           | total_rx_bytes |
+----------------+----------------+
| Living Room AP |      125000000 |
| Bedroom AP     |       80000000 |
| Kitchen AP     |      210000000 |
+----------------+----------------+
```

---

## 🎉 You're Done!

Your bandwidth tracking system is now:
- ✅ Tracking cumulative bandwidth
- ✅ Computing deltas automatically
- ✅ Handling reboots gracefully
- ✅ Logging human-readable data
- ✅ Storing historical snapshots
- ✅ Ready for analytics

**Next:** Build custom reports and dashboards with your new bandwidth data!

---

## 📖 Need Help?

- Full docs: `BANDWIDTH_TRACKING_README.md`
- Implementation details: `BANDWIDTH_TRACKING_SUMMARY.md`
- Code reference: `bandwidth_tracker.py`
- Tests: `test_bandwidth_tracking.py`

**Questions?** Check the troubleshooting section in the README!
