# 🚀 WinyFi UniFi Remote Setup - Quick Reference

## 📋 Summary

Connect WinyFi Admin Dashboard (Machine B) to UniFi Controller (Machine A) over the network.

## ⚙️ Configuration Files

| File | Purpose |
|------|---------|
| `.env` | Main configuration (copy from `.env.example`) |
| `UNIFI_API_SETUP.md` | Detailed setup guide |
| `test_unifi_connection.py` | Test script before starting server |
| `start_unifi_api.bat` | Easy startup script |

## 🔧 Quick Setup

### Machine A (Controller + API Server)

```powershell
# 1. Set environment variables
$env:UNIFI_URL = "https://192.168.1.100:8443"
$env:UNIFI_USER = "admin"
$env:UNIFI_PASS = "your_password"
$env:UNIFI_VERIFY = "false"

# 2. Test connection (optional but recommended)
python test_unifi_connection.py

# 3. Start API server
cd server
python unifi_api.py
```

### Machine B (WinyFi Dashboard)

```powershell
# 1. Point to Machine A
$env:WINYFI_UNIFI_API_URL = "http://192.168.1.100:5001"

# 2. Start dashboard
python main.py
```

## 🎯 Key Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `UNIFI_URL` | `https://127.0.0.1:8443` | UniFi Controller URL |
| `UNIFI_USER` | `admin` | Controller username |
| `UNIFI_PASS` | `admin123` | Controller password |
| `UNIFI_VERIFY` | `false` | SSL verification (false = allow self-signed) |
| `WINYFI_UNIFI_API_URL` | `http://localhost:5001` | API server URL (for dashboard) |

## 🧪 Testing

```powershell
# Test UniFi Controller connection
python test_unifi_connection.py

# Test API endpoints
curl http://localhost:5001/api/unifi/test
curl http://localhost:5001/api/unifi/status
curl http://localhost:5001/api/unifi/devices
```

## ❌ Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| SSL Certificate Error | Set `UNIFI_VERIFY=false` |
| Connection Refused | Check firewall, verify controller is running |
| 502 Bad Gateway | Check UniFi Controller is online and credentials are correct |
| Dashboard shows no data | Verify `WINYFI_UNIFI_API_URL` points to correct IP |
| Timeout | Increase `HTTP_TIMEOUT=30` or check network latency |

## 🔥 Firewall Rules

### Windows (Machine A)
```powershell
New-NetFirewallRule -DisplayName "WinyFi UniFi API" -Direction Inbound -LocalPort 5001 -Protocol TCP -Action Allow
```

### Linux (Machine A)
```bash
sudo ufw allow 5001/tcp
```

## 📡 API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/api/unifi/test` | Test connection |
| `/api/unifi/status` | Controller status |
| `/api/unifi/devices` | List devices |
| `/api/unifi/clients` | List clients |
| `/api/unifi/bandwidth/total` | Total bandwidth |

## 🔐 Security Tips

1. **Use API Keys in Production:**
   ```powershell
   $env:ALLOW_NO_AUTH = "false"
   $env:API_KEYS = "your-secret-key"
   ```

2. **Restrict by IP:**
   - Use firewall rules
   - Configure reverse proxy with IP whitelist

3. **Use HTTPS for API Server:**
   - Deploy behind nginx/Apache with SSL

## 📞 Need Help?

1. Check logs where `unifi_api.py` is running
2. Run `test_unifi_connection.py` to diagnose issues
3. Verify environment variables are set correctly
4. Check network connectivity: `ping <controller-ip>`
5. See `UNIFI_API_SETUP.md` for detailed troubleshooting

---

**Made with ❤️ for WinyFi Network Monitoring**
