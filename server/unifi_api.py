
# Flask API for UniFi integration (mockable for home development)
# Endpoints:
# - /api/auth/login: Mock login (UniFi v7+)
# - /api/login: Mock login (UniFi v6)
# - /api/s/<site>/stat/device: Mock APs
# - /api/s/<site>/stat/sta: Mock clients
# - /api/unifi/devices: Get APs and bandwidth stats
# - /api/unifi/clients: Get connected clients and stats
# - /api/unifi/mock: Toggle mock mode (for home dev)
# - /api/unifi/bandwidth/total: Get total bandwidth
# - /api/unifi/clients/count: Get client count

from flask import Flask, jsonify, request

app = Flask(__name__)

# --- Mock credentials for reference ---
USERNAME = "admin"  # Replace with your UniFi username
PASSWORD = "admin123"  # Replace with your UniFi password
SITE = "default"  # Default site is usually 'default'
REFRESH_INTERVAL = 5000  # Auto-refresh every 5000 ms (5 sec)

# --- Mock Data ---
MOCK_MODE = {
    'routers': True,
    'bandwidth': True,
    'clients': True
}
MOCK_APS = [
    {
        "model": "UAP-AC-Pro",
        "name": "Living Room AP",
        "mac": "AA:BB:CC:DD:EE:01",
        "ip": "192.168.1.2",
        "xput_down": 120.5,
        "xput_up": 30.2
    },
    {
        "model": "UAP-AC-Lite",
        "name": "Bedroom AP",
        "mac": "AA:BB:CC:DD:EE:02",
        "ip": "192.168.1.3",
        "xput_down": 80.1,
        "xput_up": 20.7
    }
]
MOCK_CLIENTS = [
    {
        "hostname": "Laptop",
        "mac": "11:22:33:44:55:66",
        "ip": "192.168.1.100",
        "ap_mac": "AA:BB:CC:DD:EE:01",
        "rx_bytes": 500000000,
        "tx_bytes": 200000000
    },
    {
        "hostname": "Phone",
        "mac": "22:33:44:55:66:77",
        "ip": "192.168.1.101",
        "ap_mac": "AA:BB:CC:DD:EE:02",
        "rx_bytes": 300000000,
        "tx_bytes": 100000000
    }
]

# --- Root login endpoints for compatibility with test client ---
@app.route('/api/auth/login', methods=['POST'])
def compat_auth_login_root():
    return jsonify({'result': 'success', 'version': 'mock'}), 200

@app.route('/api/login', methods=['POST'])
def compat_login_root():
    return jsonify({'result': 'success', 'version': 'mock'}), 200

# --- Compatibility endpoints for UniFi test client ---
@app.route('/api/s/<site>/stat/device')
def compat_stat_device(site):
    if MOCK_MODE['routers']:
        return jsonify({'data': MOCK_APS})
    return jsonify({'data': []})

@app.route('/api/s/<site>/stat/sta')
def compat_stat_sta(site):
    if MOCK_MODE['clients']:
        return jsonify({'data': MOCK_CLIENTS})
    return jsonify({'data': []})

# --- Additional endpoints for dashboard integration ---
@app.route('/api/unifi/devices')
def api_devices():
    if MOCK_MODE['routers']:
        return jsonify(MOCK_APS)
    return jsonify([])

@app.route('/api/unifi/clients')
def api_clients():
    if MOCK_MODE['clients']:
        return jsonify(MOCK_CLIENTS)
    return jsonify([])

@app.route('/api/unifi/mock', methods=['POST'])
def api_mock_toggle():
    data = request.get_json(force=True)
    for key in ['routers', 'bandwidth', 'clients']:
        if key in data:
            MOCK_MODE[key] = bool(data[key])
    return jsonify({'mock': MOCK_MODE})

@app.route('/api/unifi/bandwidth/total')
def api_bandwidth_total():
    if MOCK_MODE['bandwidth']:
        total_down = sum(ap['xput_down'] for ap in MOCK_APS)
        total_up = sum(ap['xput_up'] for ap in MOCK_APS)
        return jsonify({'total_down': total_down, 'total_up': total_up})
    return jsonify({'total_down': 0, 'total_up': 0})

@app.route('/api/unifi/clients/count')
def api_clients_count():
    if MOCK_MODE['clients']:
        return jsonify({'count': len(MOCK_CLIENTS)})
    return jsonify({'count': 0})

if __name__ == '__main__':
    app.run(port=5001, debug=True)
