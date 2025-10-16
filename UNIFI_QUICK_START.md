# UniFi Integration - Quick Start Guide

## 🚀 Getting Started (3 Steps)

### Step 1: Start UniFi API Server
```powershell
# Terminal 1
python start_unifi_server.py
```

### Step 2: Start Main Dashboard
```powershell
# Terminal 2
python main.py
```

### Step 3: View UniFi Devices
1. Login as admin
2. Go to Dashboard/Routers tab
3. See UniFi devices displayed!

## 📱 What You'll See

```
╔═════════════════════════════════════════════════════════════════╗
║                        ADMIN DASHBOARD                          ║
╠═════════════════════════════════════════════════════════════════╣
║  📡 UniFi Access Points - Online                                ║
║  ┌────────────────────┐  ┌────────────────────┐               ║
║  │ Living Room AP     │  │ Bedroom AP         │               ║
║  │ ┌────────────┐     │  │ ┌────────────┐     │               ║
║  │ │ 📡 UniFi   │     │  │ │ 📡 UniFi   │     │               ║
║  │ └────────────┘     │  │ └────────────┘     │               ║
║  │ 192.168.1.2        │  │ 192.168.1.3        │               ║
║  │ 🟢 Online          │  │ 🟢 Online          │               ║
║  │ ⬇ 120.50 Mbps     │  │ ⬇ 80.10 Mbps       │               ║
║  │ ⬆ 30.20 Mbps      │  │ ⬆ 20.70 Mbps       │               ║
║  └────────────────────┘  └────────────────────┘               ║
║                                                                 ║
║  🟢 Regular Routers - Online                                    ║
║  ┌────────────────────┐  ┌────────────────────┐               ║
║  │ Router 1           │  │ Router 2           │               ║
║  │      ⛀             │  │      ⛀             │               ║
║  │ 192.168.1.1        │  │ 192.168.1.254      │               ║
║  │ 🟢 Online          │  │ 🟢 Online          │               ║
║  │ ⏱ 20 ms           │  │ ⏱ 15 ms           │               ║
║  │ ⬇ 95.50 Mbps      │  │ ⬇ 88.30 Mbps       │               ║
║  │ ⬆ 45.20 Mbps      │  │ ⬆ 52.10 Mbps       │               ║
║  └────────────────────┘  └────────────────────┘               ║
╚═════════════════════════════════════════════════════════════════╝
```

## 🎨 Visual Differences

### UniFi Devices
- **Card Color:** 🔵 Primary Blue
- **Badge:** 📡 UniFi
- **Icon:** 📡 (instead of ⛀)
- **Hover:** Changes to 🟢 Green
- **Bandwidth:** Real-time from API (no latency)

### Regular Routers
- **Card Color:** 🔵 Info Blue
- **Icon:** ⛀ Router emoji
- **Hover:** Changes to 🔵 Primary Blue
- **Bandwidth:** Includes latency (⏱ ms)

## 🔧 Features

### Automatic Sorting
- ✅ UniFi devices shown first
- ✅ Regular routers shown second
- ✅ Each group sorted by online/offline status

### Real-Time Data
- ✅ UniFi bandwidth updates from API
- ✅ No ping needed for UniFi devices
- ✅ Status indication (online/offline)

### Click Actions
- 🖱️ Left-click: View device details
- 🖱️ Right-click: Context menu (regular routers only)
- 🖱️ Hover: Card color change

## 📊 Mock Data Available

The test server includes:
- 2 UniFi Access Points
  - Living Room AP (UAP-AC-Pro)
  - Bedroom AP (UAP-AC-Lite)
- 2 Connected Clients
  - Laptop
  - Phone
- Total Bandwidth Stats
- Client Count

## ⚙️ Configuration

### Default URLs
```python
Main API:   http://localhost:5000  # Regular routers
UniFi API:  http://localhost:5001  # UniFi devices
```

### Custom URLs (Optional)
```python
# In login.py or dashboard initialization
api_base_url = "http://192.168.1.1:5000"
unifi_api_url = "http://192.168.1.1:5001"
```

## 🐛 Troubleshooting

### UniFi devices not showing?
1. Check UniFi server: `curl http://localhost:5001/api/unifi/devices`
2. Verify server is running in Terminal 1
3. Check for errors in console

### Bandwidth not updating?
- UniFi: Data comes from API (static per refresh)
- Regular: Uses ping-based monitoring

### Cards not rendering?
1. Refresh the routers tab
2. Check browser console for errors
3. Verify database connection

## 📚 Documentation

- `UNIFI_INTEGRATION_README.md` - Full technical documentation
- `test_unifi_integration.py` - Integration test script
- `start_unifi_server.py` - Server start script
- `server/unifi_api.py` - UniFi API implementation

## 🎯 Next Steps

After verifying the integration:
1. ✅ Add auto-refresh for UniFi data
2. ✅ Implement client viewer for UniFi devices
3. ✅ Add bandwidth graphs for UniFi APs
4. ✅ Connect to real UniFi controller

## 💡 Tips

- Keep both terminals running (API servers)
- Use test script to verify setup
- Check logs in `winyfi_error.log` for issues
- Toggle mock mode for testing vs production

---

**Ready to use!** 🎉 The UniFi integration is complete and tested.
