# WinyFi UniFi API Setup Guide

## Architecture Overview

```
Machine A (Controller + API Server)
├── UniFi Controller (https://localhost:8443)
└── unifi_api.py (Flask API on port 5001)

Machine B (Admin Dashboard)
└── dashboard.py (WinyFi Admin App)
    └── Connects to Machine A:5001
```

## Quick Setup

### Machine A (UniFi Controller + API Server)

1. **Configure UniFi Controller Connection**
   ```bash
   # Edit .env file or set environment variables
   set UNIFI_URL=https://127.0.0.1:8443
   set UNIFI_USER=admin
   set UNIFI_PASS=your_password
   set UNIFI_VERIFY=false
   ```

2. **Start the UniFi API Server**
   ```bash
   cd server
   python unifi_api.py
   ```
   
   The API will listen on `0.0.0.0:5001` (accessible from other machines)

### Machine B (WinyFi Admin Dashboard)

1. **Configure API Connection**
   ```bash
   # Point to Machine A's IP address
   set WINYFI_UNIFI_API_URL=http://192.168.1.100:5001
   ```

2. **Start the Dashboard**
   ```bash
   python main.py
   ```

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `UNIFI_URL` | `https://127.0.0.1:8443` | UniFi Controller URL |
| `UNIFI_USER` | `admin` | Controller username |
| `UNIFI_PASS` | `admin123` | Controller password |
| `UNIFI_SITE` | `default` | Site ID |
| `UNIFI_VERIFY` | `false` | SSL verification (false for self-signed) |
| `WINYFI_UNIFI_API_URL` | `http://localhost:5001` | API server URL (for dashboard) |

### Remote Setup Example

**Machine A (192.168.1.100):**
```bash
set UNIFI_URL=https://192.168.1.100:8443
set UNIFI_USER=admin
set UNIFI_PASS=MySecurePass123
cd server
python unifi_api.py
```

**Machine B (any IP):**
```bash
set WINYFI_UNIFI_API_URL=http://192.168.1.100:5001
python main.py
```

## Testing Connection

### Test UniFi Controller Connection
```bash
curl http://localhost:5001/api/unifi/test
```

Expected response:
```json
{
  "status": "success",
  "message": "Connected to UniFi Controller",
  "url": "https://192.168.1.100:8443"
}
```

### Test Device Retrieval
```bash
curl http://localhost:5001/api/unifi/devices
```

## Troubleshooting

### SSL Certificate Errors
**Error:** `SSLError: certificate verify failed`

**Solution:** Set `UNIFI_VERIFY=false` to disable SSL verification for self-signed certificates.

### Connection Refused
**Error:** `Connection Error: Cannot connect to controller`

**Solutions:**
1. Verify UniFi Controller is running
2. Check firewall rules (ports 8443, 5001)
3. Verify IP address and port in `UNIFI_URL`
4. Test connectivity: `ping <controller-ip>`

### Timeout Errors
**Error:** `Connection timeout`

**Solutions:**
1. Increase timeout: `set HTTP_TIMEOUT=30`
2. Check network latency
3. Verify controller isn't overloaded

### 502 Bad Gateway
**Error:** `upstream_error`

**Solutions:**
1. Check UniFi Controller status
2. Verify credentials are correct
3. Check controller logs
4. Test login manually at `https://<controller-ip>:8443`

### Dashboard Can't Connect to API
**Error:** Dashboard shows offline or no data

**Solutions:**
1. Verify API server is running on Machine A
2. Check `WINYFI_UNIFI_API_URL` points to correct IP
3. Test from Machine B: `curl http://<machine-a-ip>:5001/api/unifi/test`
4. Check firewall allows port 5001

## Firewall Configuration

### Windows Firewall (Machine A)
```powershell
# Allow UniFi API on port 5001
New-NetFirewallRule -DisplayName "WinyFi UniFi API" -Direction Inbound -LocalPort 5001 -Protocol TCP -Action Allow
```

### Linux Firewall (Machine A)
```bash
# UFW
sudo ufw allow 5001/tcp

# iptables
sudo iptables -A INPUT -p tcp --dport 5001 -j ACCEPT
```

## Security Considerations

1. **Use API Keys in Production**
   ```bash
   set ALLOW_NO_AUTH=false
   set API_KEYS=your-secret-key-1,your-secret-key-2
   ```

2. **Enable HTTPS for API Server**
   - Use reverse proxy (nginx/Apache) with SSL
   - Or use Flask-SSLify for HTTPS

3. **Restrict Access by IP**
   - Configure `ALLOWED_ORIGINS` for CORS
   - Use firewall rules to limit access

## API Endpoints

- `GET /api/unifi/status` - Controller status
- `GET /api/unifi/test` - Connection test
- `GET /api/unifi/devices` - List all devices
- `GET /api/unifi/clients` - List all clients
- `GET /api/unifi/bandwidth/total` - Total bandwidth
- `GET /api/unifi/clients/count` - Client count
- `GET /api/unifi/devices/<mac>/clients` - Clients per device
- `GET /api/unifi/ping/<mac>` - Ping device

## Support

For issues:
1. Check logs in terminal where `unifi_api.py` is running
2. Test connection endpoints first
3. Verify environment variables are set correctly
4. Check network connectivity between machines
