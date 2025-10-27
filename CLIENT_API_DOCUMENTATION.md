# Client Discovery API Endpoints

## Overview
API endpoints for network-wide client discovery integrated with the Flask backend (`server/app.py`). These endpoints enable the dashboard to scan, retrieve, and track network clients across all AP subnets.

---

## Endpoints

### 1. Scan Network Clients
**POST** `/api/clients/scan`

Triggers a full network scan across all AP subnets in the database.

#### Request Body (Optional)
```json
{
  "timeout": 2,
  "use_db_routers": true
}
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `timeout` | int | 2 | ARP scan timeout per subnet (seconds) |
| `use_db_routers` | bool | true | Only scan AP subnets from database |

#### Response
```json
{
  "success": true,
  "total_discovered": 15,
  "saved_to_db": 15,
  "clients": [
    {
      "mac_address": "00:11:22:33:44:55",
      "ip_address": "192.168.1.100",
      "hostname": "DESKTOP-ABC123",
      "vendor": "Intel",
      "subnet": "192.168.1.0/24",
      "interface": "Ethernet",
      "router_id": 1,
      "router_name": "Main AP",
      "last_seen": "2025-10-25T14:30:00"
    }
  ]
}
```

#### Status Codes
- `200 OK`: Scan completed successfully
- `500 Internal Server Error`: Scan failed (check error message)

#### Error Response
```json
{
  "error": "No AP subnets found - falling back to all subnets scan"
}
```

---

### 2. Get All Clients
**GET** `/api/clients`

Retrieve all network clients from the database.

#### Query Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `online_only` | bool | false | Filter for only online clients |
| `limit` | int | 1000 | Maximum number of clients to return |

#### Examples
```bash
# Get all clients
GET /api/clients

# Get only online clients
GET /api/clients?online_only=true

# Get last 50 clients
GET /api/clients?limit=50
```

#### Response
```json
{
  "success": true,
  "total": 15,
  "clients": [
    {
      "id": 1,
      "mac_address": "00:11:22:33:44:55",
      "ip_address": "192.168.1.100",
      "hostname": "DESKTOP-ABC123",
      "vendor": "Intel",
      "is_online": true,
      "ping_latency_ms": 12.5,
      "first_seen": "2025-10-20T10:00:00",
      "last_seen": "2025-10-25T14:30:00",
      "created_at": "2025-10-20T10:00:00",
      "updated_at": "2025-10-25T14:30:00"
    }
  ]
}
```

---

### 3. Get Router Clients
**GET** `/api/routers/<router_id>/clients`

Get all clients associated with a specific router/AP.

#### Path Parameters
| Parameter | Type | Description |
|-----------|------|-------------|
| `router_id` | int | Database ID of the router |

#### Example
```bash
GET /api/routers/1/clients
```

#### Response (Non-UniFi)
```json
{
  "success": true,
  "router_id": 1,
  "router_name": "Main AP",
  "total_clients": 8,
  "clients": [
    {
      "mac_address": "00:11:22:33:44:55",
      "ip_address": "192.168.1.100",
      "hostname": "DESKTOP-ABC123",
      "vendor": "Intel",
      "subnet": "192.168.1.0/24",
      "interface": "Ethernet",
      "last_seen": "2025-10-25T14:30:00"
    }
  ]
}
```

#### Response (UniFi Device)
```json
{
  "success": false,
  "message": "UniFi devices should use UniFi API endpoint",
  "is_unifi": true
}
```

#### Status Codes
- `200 OK`: Success
- `404 Not Found`: Router not found
- `500 Internal Server Error`: Scan failed

---

### 4. Get Client Connection History
**GET** `/api/clients/<mac_address>/history`

Get connection event history for a specific client.

#### Path Parameters
| Parameter | Type | Description |
|-----------|------|-------------|
| `mac_address` | string | Client MAC address (e.g., "00:11:22:33:44:55") |

#### Query Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 50 | Maximum number of events to return |

#### Example
```bash
GET /api/clients/00:11:22:33:44:55/history?limit=20
```

#### Response
```json
{
  "success": true,
  "mac_address": "00:11:22:33:44:55",
  "total_events": 5,
  "history": [
    {
      "id": 1,
      "event_type": "CONNECT",
      "event_time": "2025-10-25T14:30:00",
      "ip_address": "192.168.1.100",
      "previous_ip": null,
      "ping_latency": 12.5,
      "hostname": "DESKTOP-ABC123",
      "vendor": "Intel",
      "session_duration": null
    },
    {
      "id": 2,
      "event_type": "IP_CHANGE",
      "event_time": "2025-10-25T15:00:00",
      "ip_address": "192.168.1.105",
      "previous_ip": "192.168.1.100",
      "ping_latency": 13.2,
      "hostname": "DESKTOP-ABC123",
      "vendor": "Intel",
      "session_duration": null
    },
    {
      "id": 3,
      "event_type": "DISCONNECT",
      "event_time": "2025-10-25T17:00:00",
      "ip_address": "192.168.1.105",
      "previous_ip": null,
      "ping_latency": null,
      "hostname": "DESKTOP-ABC123",
      "vendor": "Intel",
      "session_duration": 7200
    }
  ]
}
```

#### Event Types
- `CONNECT`: Device connected to network
- `DISCONNECT`: Device disconnected from network
- `IP_CHANGE`: Device IP address changed
- `RECONNECT`: Device reconnected after disconnect

---

## Integration Examples

### Dashboard Integration

#### 1. Show Network Clients (Routers Tab)
```python
import requests

# Scan and retrieve all clients
response = requests.post('http://localhost:5000/api/clients/scan')
if response.status_code == 200:
    data = response.json()
    print(f"Found {data['total_discovered']} clients")
    for client in data['clients']:
        print(f"{client['hostname']} - {client['ip_address']}")
```

#### 2. Router Details Modal - Show Connected Clients
```python
import requests

# Get clients for specific router
router_id = 1
response = requests.get(f'http://localhost:5000/api/routers/{router_id}/clients')
if response.status_code == 200:
    data = response.json()
    if data['success']:
        print(f"Router: {data['router_name']}")
        print(f"Connected clients: {data['total_clients']}")
        for client in data['clients']:
            print(f"  - {client['hostname']} ({client['ip_address']})")
```

#### 3. Client Connection History
```python
import requests

# Get connection history for a client
mac = "00:11:22:33:44:55"
response = requests.get(f'http://localhost:5000/api/clients/{mac}/history?limit=10')
if response.status_code == 200:
    data = response.json()
    print(f"Connection history for {mac}:")
    for event in data['history']:
        print(f"  {event['event_time']}: {event['event_type']}")
```

---

## Error Handling

### Common Errors

#### No Routers in Database
```json
{
  "error": "No AP subnets found - falling back to all subnets scan"
}
```
**Solution**: Add routers to the database first.

#### Permission Denied
```json
{
  "error": "Permission denied: ARP scanning requires administrator privileges"
}
```
**Solution**: Run the Flask app with administrator privileges.

#### Npcap Not Installed
```json
{
  "error": "Npcap is not installed or not accessible"
}
```
**Solution**: Install Npcap from https://npcap.com/

#### Database Connection Error
```json
{
  "error": "Database connection failed: Access denied for user"
}
```
**Solution**: Check database credentials in `db.py`.

---

## Data Models

### Client Object
```python
{
  "id": int,                    # Database ID
  "mac_address": str,           # MAC address (unique)
  "ip_address": str,            # Current IP address
  "hostname": str,              # Resolved hostname
  "vendor": str,                # Device vendor (from OUI)
  "is_online": bool,            # Current online status
  "ping_latency_ms": float,     # Ping latency in milliseconds
  "first_seen": datetime,       # First detection time
  "last_seen": datetime,        # Last seen time
  "created_at": datetime,       # Record creation time
  "updated_at": datetime        # Record update time
}
```

### Enhanced Client Object (from discovery)
```python
{
  "mac_address": str,
  "ip_address": str,
  "hostname": str,
  "vendor": str,
  "subnet": str,                # e.g., "192.168.1.0/24"
  "interface": str,             # e.g., "Ethernet"
  "router_id": int,             # Associated router ID
  "router_name": str,           # Associated router name
  "last_seen": datetime
}
```

### Connection Event Object
```python
{
  "id": int,
  "mac_address": str,
  "event_type": str,            # CONNECT, DISCONNECT, IP_CHANGE, RECONNECT
  "event_time": datetime,
  "ip_address": str,
  "previous_ip": str,           # For IP_CHANGE events
  "ping_latency": float,
  "hostname": str,
  "vendor": str,
  "session_duration": int       # For DISCONNECT events (seconds)
}
```

---

## Performance Considerations

### Scanning
- **Chunked ARP**: Scans in chunks of 50 hosts for efficiency
- **Parallel Subnets**: Multiple subnets scanned concurrently
- **Timeout**: Default 2 seconds per subnet (configurable)
- **Network Load**: ~0.5-2 seconds per /24 subnet

### Database
- **Batch Inserts**: Clients saved in batch operations
- **Indexing**: MAC address indexed for fast lookups
- **History Pruning**: Limit history queries to prevent large results

### Recommendations
- **Auto-refresh**: 30-60 second intervals for client list
- **Manual Scan**: Use button-triggered scans for immediate updates
- **Pagination**: Implement for networks with 500+ clients
- **Caching**: Cache results for 10-30 seconds to reduce repeated scans

---

## Security Considerations

### 1. Authentication
All endpoints should be protected with authentication middleware:
```python
from functools import wraps

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token or not validate_token(token):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.post("/api/clients/scan")
@require_auth
def scan_network_clients():
    # ... endpoint code
```

### 2. Rate Limiting
Prevent abuse of scan endpoints:
```python
from flask_limiter import Limiter

limiter = Limiter(app, key_func=lambda: request.remote_addr)

@app.post("/api/clients/scan")
@limiter.limit("5 per minute")
def scan_network_clients():
    # ... endpoint code
```

### 3. Admin-Only Endpoints
Restrict scanning to admin users:
```python
def require_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_role = get_user_role_from_token()
        if user_role != 'admin':
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated_function
```

---

## Testing

### Manual Testing with cURL

#### Scan Network
```bash
curl -X POST http://localhost:5000/api/clients/scan \
  -H "Content-Type: application/json" \
  -d '{"timeout": 2, "use_db_routers": true}'
```

#### Get All Clients
```bash
curl http://localhost:5000/api/clients?online_only=true
```

#### Get Router Clients
```bash
curl http://localhost:5000/api/routers/1/clients
```

#### Get Client History
```bash
curl http://localhost:5000/api/clients/00:11:22:33:44:55/history?limit=10
```

### Python Testing
```python
import requests
import json

BASE_URL = "http://localhost:5000"

# Test scan
response = requests.post(f"{BASE_URL}/api/clients/scan", 
                        json={"timeout": 2})
print(json.dumps(response.json(), indent=2))

# Test get clients
response = requests.get(f"{BASE_URL}/api/clients?online_only=true")
print(json.dumps(response.json(), indent=2))

# Test router clients
response = requests.get(f"{BASE_URL}/api/routers/1/clients")
print(json.dumps(response.json(), indent=2))
```

---

## Deployment

### Production Considerations

1. **Environment Variables**
   ```bash
   export FLASK_ENV=production
   export FLASK_DEBUG=0
   export DATABASE_HOST=your-db-host
   export DATABASE_USER=your-db-user
   export DATABASE_PASSWORD=your-db-password
   ```

2. **WSGI Server** (Use Gunicorn instead of Flask dev server)
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:5000 server.app:app
   ```

3. **Reverse Proxy** (Nginx)
   ```nginx
   location /api/ {
       proxy_pass http://127.0.0.1:5000/api/;
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
   }
   ```

4. **Monitoring**
   - Log all scan requests
   - Track API response times
   - Monitor database query performance
   - Alert on repeated scan failures

---

## Related Files

- `server/app.py`: API endpoint implementations
- `network_utils.py`: Core client discovery logic
- `db.py`: Database operations (save_network_client, get_network_clients, etc.)
- `dashboard.py`: Frontend UI integration
- `ENHANCED_CLIENT_DISCOVERY.md`: Backend discovery documentation
- `NETWORK_CLIENTS_ENHANCED.md`: Dashboard UI documentation

---

## Future Enhancements

- [ ] WebSocket support for real-time client updates
- [ ] Bulk export endpoints (CSV, JSON, Excel)
- [ ] Client grouping by subnet/router
- [ ] Advanced filtering (by vendor, hostname pattern, date range)
- [ ] Client alerting (new device detected, device offline)
- [ ] Network topology visualization endpoint
- [ ] Historical analytics (peak times, usage patterns)
- [ ] MAC address vendor database integration
- [ ] Client tagging and categorization
- [ ] DHCP lease information integration
