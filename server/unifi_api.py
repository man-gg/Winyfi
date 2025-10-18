# Flask API for UniFi integration (mockable for home development)
# Extended with:
# - /api/unifi/ping/<mac>: Simulated ping + online/offline status
# - Added `state` and `connected` fields in mock devices

from flask import Flask, jsonify, request
import random
import time
import platform
import subprocess

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
        "ip": "192.168.1.22",
        "xput_down": 120.5,
        "xput_up": 30.2,
        "state": 1,          # 1 = online, 0 = offline
        "connected": True
    },
    {
        "model": "UAP-AC-Lite",
        "name": "Bedroom AP",
        "mac": "AA:BB:CC:DD:EE:02",
        "ip": "192.168.1.23",
        "xput_down": 80.1,
        "xput_up": 20.7,
        "state": 0,
        "connected": False
    },
    {
        "model": "UAP-AC-Lite",
        "name": "Kitchen AP",
        "mac": "AA:BB:CC:DD:EE:12",
        "ip": "192.168.1.24",
        "xput_down": 80.1,
        "xput_up": 20.7,
        "state": 1,
        "connected": False
    }
]

MOCK_CLIENTS = [
    {
        "hostname": "Laptop",
        "mac": "11:22:33:44:55:66",
        "ip": "192.168.1.100",
        "ap_mac": "AA:BB:CC:DD:EE:01",
        "rx_bytes": 500000000,
        "tx_bytes": 200000000,
        "rx_rate": 866000,  # in bps (866 Mbps)
        "tx_rate": 650000,  # in bps (650 Mbps)
        "signal": -45,  # dBm
        "channel": 36,
        "uptime": 7200  # 2 hours in seconds
    },
    {
        "hostname": "Phone",
        "mac": "22:33:44:55:66:77",
        "ip": "192.168.1.101",
        "ap_mac": "AA:BB:CC:DD:EE:01",
        "rx_bytes": 300000000,
        "tx_bytes": 100000000,
        "rx_rate": 433000,  # in bps (433 Mbps)
        "tx_rate": 390000,  # in bps (390 Mbps)
        "signal": -52,  # dBm
        "channel": 36,
        "uptime": 3600  # 1 hour in seconds
    },
    {
        "hostname": "iPad",
        "mac": "33:44:55:66:77:88",
        "ip": "192.168.1.102",
        "ap_mac": "AA:BB:CC:DD:EE:02",
        "rx_bytes": 200000000,
        "tx_bytes": 80000000,
        "rx_rate": 300000,  # in bps (300 Mbps)
        "tx_rate": 270000,  # in bps (270 Mbps)
        "signal": -60,  # dBm
        "channel": 48,
        "uptime": 1800  # 30 minutes in seconds
    },
    {
        "hostname": "Smart TV",
        "mac": "44:55:66:77:88:99",
        "ip": "192.168.1.103",
        "ap_mac": "AA:BB:CC:DD:EE:12",
        "rx_bytes": 1500000000,
        "tx_bytes": 50000000,
        "rx_rate": 866000,  # in bps (866 Mbps)
        "tx_rate": 433000,  # in bps (433 Mbps)
        "signal": -38,  # dBm
        "channel": 108,
        "uptime": 86400  # 24 hours in seconds
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

@app.route('/api/unifi/devices/<mac>/clients')
def api_device_clients(mac):
    """Get all clients connected to a specific AP by MAC address"""
    if MOCK_MODE['clients']:
        # Filter clients by AP MAC address
        device_clients = [c for c in MOCK_CLIENTS if c.get('ap_mac', '').upper() == mac.upper()]
        return jsonify(device_clients)
    return jsonify([])


# --- NEW: Simulated Ping Endpoint ---
@app.route('/api/unifi/ping/<mac>')
def api_ping_device(mac):
    ap = next((a for a in MOCK_APS if a['mac'].upper() == mac.upper()), None)
    if not ap:
        return jsonify({'error': 'Device not found'}), 404

    if MOCK_MODE['routers']:
        # Simulate ping: 75% online, 25% offline
        latency = round(random.uniform(1, 100), 2)
        is_online = random.choice([True, True, True, False])

        ap['connected'] = is_online
        ap['state'] = 1 if is_online else 0

        return jsonify({
            'mac': ap['mac'],
            'ip': ap['ip'],
            'connected': is_online,
            'latency_ms': latency if is_online else None,
            'timestamp': int(time.time())
        })

    return jsonify({'connected': False, 'latency_ms': None})


# --- OPTIONAL: real ping helper (for future real devices) ---
def ping_host(ip):
    count_flag = '-n' if platform.system().lower() == 'windows' else '-c'
    try:
        subprocess.check_output(['ping', count_flag, '1', ip],
                                stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False


if __name__ == '__main__':
    app.run(port=5001, debug=True)
