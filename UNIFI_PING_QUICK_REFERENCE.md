# UniFi Ping Feature - Quick Reference

## What Was Added
✅ Ping functionality for UniFi devices (same as regular routers)
✅ Online/offline status based on ping response
✅ Real-time latency measurement and display
✅ Auto-refresh with ping every 10 seconds

## How It Works

### Router List View
```
Every 10 seconds:
1. Fetch UniFi devices from API
2. Ping each device IP
3. Measure latency
4. Update status (online/offline)
5. Display: "📶 ↓120.5 Mbps ↑30.2 Mbps | ⚡45ms"
```

### Details Window
```
Every 3 seconds:
1. Fetch device data from API
2. Ping the device
3. Update status and latency
4. Show in "⚡ Latency" field
```

## Visual Changes

### Online Device
- Status: 🟢 Online
- Bandwidth: `📶 ↓120.5 Mbps ↑30.2 Mbps | ⚡45ms`
- Card: Blue primary style

### Offline Device
- Status: 🔴 Offline
- Bandwidth: `⏳ Bandwidth: N/A (Offline)`
- Card: Blue primary style (moves to offline section)

## Code Locations

### Main Ping Logic
**File**: `dashboard.py` → `_fetch_unifi_devices()`
```python
# Ping the device to check status
latency = ping_latency(ip, timeout=1000)
is_online = latency is not None
```

### Status Display
**File**: `dashboard.py` → `reload_routers()`
```python
# Status based on ping for both UniFi and regular routers
cur = self.status_history.get(router['id'], {}).get('current')
status_text = "🟢 Online" if cur is True else "🔴 Offline"
```

### Details Refresh
**File**: `dashboard.py` → `open_router_details()` → `refresh_details()`
```python
# Ping UniFi device every 3 seconds
latency = ping_latency(ip, timeout=1000)
is_device_online = latency is not None
```

## Testing

### Quick Test
```bash
# Start UniFi server
python start_unifi_server.py

# Run test
python test_unifi_auto_refresh.py

# Start dashboard
python main.py
```

### Verify
- [ ] UniFi devices show in router list
- [ ] Status shows 🟢 or 🔴 based on ping
- [ ] Latency displayed (e.g., ⚡45ms)
- [ ] Updates every 10 seconds
- [ ] Details window shows latency
- [ ] Offline devices show "N/A (Offline)"

## Troubleshooting

**UniFi devices always offline?**
- Check if device IPs are reachable
- Verify firewall allows ping
- Check UniFi API server is running

**No latency shown?**
- Ping may be blocked by network
- Device may be offline
- Check network_utils.py for ping_latency function

**Slow performance?**
- Normal - pings add ~1 second per device
- Uses dynamic interval to prevent congestion
- Runs in background, doesn't block UI

## Summary
UniFi devices now use **the same ping method as regular routers**, providing consistent status monitoring and latency measurements across all devices! 🎯
