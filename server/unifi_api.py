"""
Flask API for UniFi integration

Adds real UniFi Controller integration while keeping mock mode as a fallback.

Key endpoints (unchanged for consumers):
- GET  /api/unifi/devices                -> List APs with simplified fields
- GET  /api/unifi/clients                -> List client stations
- GET  /api/unifi/bandwidth/total        -> Aggregate down/up throughput
- GET  /api/unifi/clients/count          -> Count of active clients
- GET  /api/unifi/devices/<mac>/clients  -> Clients connected to specific AP
- GET  /api/unifi/ping/<mac>             -> Ping AP by MAC (real latency if possible)

Compatibility endpoints (raw UniFi-like):
- GET  /api/s/<site>/stat/device
- GET  /api/s/<site>/stat/sta

Configuration:
- CONTROLLER_URL: default http://127.0.0.1:8080
- USERNAME:        default admin
- PASSWORD:        default admin 123
- SITE:            default default

Environment variables can override these: UNIFI_URL, UNIFI_USER, UNIFI_PASS, UNIFI_SITE.
"""

from flask import Flask, jsonify, request, g
import random
import time
import platform
import subprocess
import os
from typing import Any, Dict, List, Optional, Tuple
import re
import hmac
from functools import wraps

import requests
from requests.adapters import HTTPAdapter
try:
    # urllib3 location differs across versions; this import covers common cases
    from urllib3.util.retry import Retry  # type: ignore
except Exception:  # pragma: no cover
    Retry = None  # Fallback to no retries if urllib3 Retry unavailable

app = Flask(__name__)

# --- Controller configuration (overridable via env) ---
# Your UniFi controller runs on HTTP port 8080
CONTROLLER_URL = os.getenv("UNIFI_URL", "http://127.0.0.1:8080").rstrip("/")
USERNAME = os.getenv("UNIFI_USER", "admin")
PASSWORD = os.getenv("UNIFI_PASS", "admin123")
SITE = os.getenv("UNIFI_SITE", "default")
REFRESH_INTERVAL = 5000  # Auto-refresh every 5000 ms (5 sec)

# --- Security & behavior configuration ---
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
# In dev we allow skipping auth for convenience; in prod default is strict
ALLOW_NO_AUTH = os.getenv("ALLOW_NO_AUTH", "true" if FLASK_DEBUG else "false").lower() == "true"

# API Keys (comma separated). If empty and ALLOW_NO_AUTH is False, all requests will be rejected.
API_KEYS = {k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()}
ADMIN_API_KEYS = {k.strip() for k in os.getenv("ADMIN_API_KEYS", "").split(",") if k.strip()}

# Limit which sites are accessible via /api/s/<site>/...
ALLOWED_SITES = {s.strip() for s in os.getenv("ALLOWED_SITES", SITE).split(",") if s.strip()}

# Mock controls
ENABLE_MOCK = os.getenv("ENABLE_MOCK", "true" if FLASK_DEBUG else "false").lower() == "true"

# CORS and headers
ALLOWED_ORIGINS = {o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()}
ENABLE_HSTS = os.getenv("ENABLE_HSTS", "false").lower() == "true"

# Simple in-memory rate-limiter storage { key: [timestamps] }
_RATE_STORE: Dict[str, List[float]] = {}

# Debug logging
print(f"[UniFi API] Starting with config:")
print(f"  Controller URL: {CONTROLLER_URL}")
print(f"  Site: {SITE}")
print(f"  Debug: {FLASK_DEBUG}")
print(f"  Auth: {'disabled' if ALLOW_NO_AUTH else 'required'} | API keys loaded: {len(API_KEYS)} | Admin keys: {len(ADMIN_API_KEYS)}")
print(f"  Allowed sites: {sorted(ALLOWED_SITES)}")
print(f"  Mock enabled: {ENABLE_MOCK}")


# --- Real UniFi session helper ---
class UniFiSession:
    """Manages login, cookies, and CSRF headers for UniFi Network Application.

    Supports both newer /api/auth/login and legacy /api/login flows.
    """

    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.s = requests.Session()
        # Disable redirects on login calls to better detect auth issues
        self.s.max_redirects = 3
        # TLS verification: only relevant on HTTPS. Default to verify True on HTTPS.
        # Allow override UNIFI_VERIFY=true/false or UNIFI_CA_BUNDLE=/path/to/ca.pem
        if self.base_url.startswith("https://"):
            ca_bundle = os.getenv("UNIFI_CA_BUNDLE")
            if ca_bundle and os.path.exists(ca_bundle):
                self.verify = ca_bundle
            else:
                self.verify = os.getenv("UNIFI_VERIFY", "true").lower() == "true"
        else:
            self.verify = False  # verify parameter ignored for http
        # Install simple retry strategy for transient errors if available
        if Retry is not None:
            retries = Retry(
                total=int(os.getenv("HTTP_RETRY_TOTAL", "2")),
                backoff_factor=float(os.getenv("HTTP_RETRY_BACKOFF", "0.3")),
                status_forcelist=(500, 502, 503, 504),
                allowed_methods=frozenset(["GET", "POST"])  # type: ignore[arg-type]
            )
            adapter = HTTPAdapter(max_retries=retries)
            self.s.mount("http://", adapter)
            self.s.mount("https://", adapter)
        self._csrf_header = None  # type: Optional[str]

    def _set_csrf_from_response(self, resp: requests.Response):
        # UniFi sets a cookie named csrf_token; echo as X-CSRF-Token header on subsequent calls
        csrf_token = resp.cookies.get("csrf_token")
        if csrf_token:
            self._csrf_header = csrf_token

    def _auth_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._csrf_header:
            headers["X-CSRF-Token"] = self._csrf_header
        return headers

    def login(self) -> None:
        """Attempt login using new then legacy endpoints."""
        payload = {"username": self.username, "password": self.password}
        last_error = None
        
        # Try new auth
        try:
            url = f"{self.base_url}/api/auth/login"
            print(f"[UniFi] Attempting login to {url}")
            resp = self.s.post(url, json=payload, headers={"Content-Type": "application/json"}, allow_redirects=False, verify=self.verify, timeout=10)
            print(f"[UniFi] New auth response: {resp.status_code}")
            if resp.status_code in (200, 204):
                self._set_csrf_from_response(resp)
                print("[UniFi] Login successful (new auth)")
                return
        except Exception as e:
            last_error = str(e)
            print(f"[UniFi] New auth failed: {e}")

        # Fallback to legacy auth
        try:
            url = f"{self.base_url}/api/login"
            print(f"[UniFi] Trying legacy login to {url}")
            resp = self.s.post(url, json=payload, headers={"Content-Type": "application/json"}, allow_redirects=False, verify=self.verify, timeout=10)
            print(f"[UniFi] Legacy auth response: {resp.status_code}")
            if resp.status_code not in (200, 204):
                raise RuntimeError(f"UniFi login failed: {resp.status_code} {resp.text}")
            self._set_csrf_from_response(resp)
            print("[UniFi] Login successful (legacy auth)")
        except Exception as e:
            print(f"[UniFi] Legacy auth failed: {e}")
            raise RuntimeError(f"UniFi login failed. Last error: {e}. Controller URL: {self.base_url}")

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {})
        merged_headers = {**self._auth_headers(), **headers}
        # Default timeout to avoid hanging workers
        kwargs.setdefault("timeout", float(os.getenv("HTTP_TIMEOUT", "8")))
        resp = self.s.request(method, url, headers=merged_headers, verify=self.verify, **kwargs)
        # If unauthorized, try a re-login once
        if resp.status_code in (401, 403):
            self.login()
            resp = self.s.request(method, url, headers=self._auth_headers(), verify=self.verify, **kwargs)
        return resp

    def get_devices(self, site: str) -> List[Dict[str, Any]]:
        resp = self._request("GET", f"/api/s/{site}/stat/device")
        resp.raise_for_status()
        data = resp.json().get("data", [])
        return data

    def get_clients(self, site: str) -> List[Dict[str, Any]]:
        resp = self._request("GET", f"/api/s/{site}/stat/sta")
        resp.raise_for_status()
        data = resp.json().get("data", [])
        return data


# Create a lazy session (login on first use)
_unifi_session: Optional[UniFiSession] = None

def get_session() -> UniFiSession:
    global _unifi_session
    if _unifi_session is None:
        _unifi_session = UniFiSession(CONTROLLER_URL, USERNAME, PASSWORD)
        _unifi_session.login()
    return _unifi_session


# --- Helpers: Auth, Rate limiting, Validation, Headers ---

def _constant_time_in(member: str, choices: set) -> bool:
    for c in choices:
        if hmac.compare_digest(member, c):
            return True
    return False


def require_api_key(admin: bool = False):
    """Decorator enforcing API key auth. Allows bypass when ALLOW_NO_AUTH is True."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if ALLOW_NO_AUTH:
                return f(*args, **kwargs)
            key = request.headers.get("X-API-Key") or request.args.get("api_key")
            if not key:
                return jsonify({"error": "unauthorized"}), 401
            if admin:
                if ADMIN_API_KEYS and _constant_time_in(key, ADMIN_API_KEYS):
                    return f(*args, **kwargs)
                return jsonify({"error": "forbidden"}), 403
            if API_KEYS and _constant_time_in(key, API_KEYS):
                return f(*args, **kwargs)
            return jsonify({"error": "unauthorized"}), 401
        return wrapper
    return decorator


def rate_limit(limit: int, window_seconds: int = 60):
    """Very small in-memory fixed-window rate limiter per IP+endpoint."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            now = time.time()
            ip = request.headers.get("X-Forwarded-For", request.remote_addr or "?").split(",")[0].strip()
            key = f"{ip}:{request.path}:{window_seconds}"
            bucket = _RATE_STORE.get(key, [])
            # prune
            threshold = now - window_seconds
            bucket = [t for t in bucket if t > threshold]
            if len(bucket) >= limit:
                return jsonify({"error": "rate_limit_exceeded"}), 429
            bucket.append(now)
            _RATE_STORE[key] = bucket
            return f(*args, **kwargs)
        return wrapper
    return decorator


MAC_REGEX = re.compile(r"^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$")


def validate_site(site: str) -> Optional[Tuple[Dict[str, str], int]]:
    if site not in ALLOWED_SITES:
        return {"error": "forbidden_site"}, 403
    return None


@app.after_request
def add_security_headers(resp):
    # Security headers suitable for an API
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    # Very strict CSP for APIs
    resp.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'")
    if ENABLE_HSTS and request.scheme == "https":
        resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    # CORS allowlist (simple)
    origin = request.headers.get("Origin")
    if ALLOWED_ORIGINS and origin in ALLOWED_ORIGINS:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Key"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp

# --- Mock Data ---
MOCK_MODE = {
    'routers': False,   # When True, serve APs from MOCK_APS
    'bandwidth': False, # When True, compute bandwidth from MOCK_APS
    'clients': False    # When True, serve clients from MOCK_CLIENTS
}

MOCK_APS = [
    {
        "model": "UAP-AC-Pro",
        "name": "Living Room AP",
        "mac": "AA:BB:CC:DD:EE:01",
        "ip": "192.168.1.22",
        "xput_down": 120.5,
        "xput_up": 30.2,
        "rx_bytes": 5000000000,  # 5 GB cumulative RX
        "tx_bytes": 2000000000,  # 2 GB cumulative TX
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
        "rx_bytes": 3000000000,  # 3 GB cumulative RX
        "tx_bytes": 1000000000,  # 1 GB cumulative TX
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
        "rx_bytes": 8000000000,  # 8 GB cumulative RX
        "tx_bytes": 3500000000,  # 3.5 GB cumulative TX
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
@require_api_key()
def compat_auth_login_root():
    # Compatibility endpoint preserved but protected by API key
    return jsonify({'result': 'success', 'version': 'compat'}), 200

@app.route('/api/login', methods=['POST'])
@require_api_key()
def compat_login_root():
    return jsonify({'result': 'success', 'version': 'compat'}), 200


# --- Compatibility endpoints for UniFi test client ---
@app.route('/api/s/<site>/stat/device')
@require_api_key()
def compat_stat_device(site):
    forbidden = validate_site(site)
    if forbidden:
        return jsonify(forbidden[0]), forbidden[1]
    if MOCK_MODE['routers']:
        return jsonify({'data': MOCK_APS})
    try:
        devices = get_session().get_devices(site)
        return jsonify({'data': devices})
    except Exception as e:
        return jsonify({'data': [], 'error': 'upstream_error'}), 502

@app.route('/api/s/<site>/stat/sta')
@require_api_key()
def compat_stat_sta(site):
    forbidden = validate_site(site)
    if forbidden:
        return jsonify(forbidden[0]), forbidden[1]
    if MOCK_MODE['clients']:
        return jsonify({'data': MOCK_CLIENTS})
    try:
        clients = get_session().get_clients(site)
        return jsonify({'data': clients})
    except Exception as e:
        return jsonify({'data': [], 'error': 'upstream_error'}), 502


# --- Additional endpoints for dashboard integration ---
@app.route('/api/unifi/devices')
@require_api_key()
def api_devices():
    if MOCK_MODE['routers']:
        return jsonify(MOCK_APS)
    try:
        raw = get_session().get_devices(SITE)
        # Debug: print first device to see available fields
        if raw and len(raw) > 0:
            print(f"[UniFi API] Sample device keys: {list(raw[0].keys())}")
        
        # Map to simplified structure similar to mocks
        mapped = []
        for d in raw:
            # Try multiple field locations for bandwidth/throughput
            # Real-time throughput (current speed)
            xput_down = None
            xput_up = None
            
            # Check speedtest-status (scheduled speedtests)
            if d.get('speedtest-status'):
                xput_down = d['speedtest-status'].get('xput_down')
                xput_up = d['speedtest-status'].get('xput_up')
            
            # Check uplink stats (actual current usage)
            if d.get('uplink'):
                xput_down = xput_down or d['uplink'].get('rx_rate')
                xput_up = xput_up or d['uplink'].get('tx_rate')
            
            # Check stat aggregates
            stat = d.get('stat', {})
            
            # Normalize throughput units to Mbps and ensure numeric defaults
            def _to_mbps(val: Any) -> float:
                try:
                    v = float(val)
                except Exception:
                    return 0.0
                # Heuristics: if value is huge it's likely bps; medium -> Kbps; else already Mbps
                if v > 1_000_000:
                    return v / 1_000_000.0
                if v > 1_000:
                    return v / 1_000.0
                return v

            down_mbps = _to_mbps(xput_down) if xput_down is not None else 0.0
            up_mbps = _to_mbps(xput_up) if xput_up is not None else 0.0
            
            mapped.append({
                'model': d.get('model'),
                'name': d.get('name') or d.get('hostname') or d.get('device_id') or d.get('mac'),
                'mac': d.get('mac'),
                'ip': d.get('ip'),
                'xput_down': down_mbps,
                'xput_up': up_mbps,
                'rx_bytes': d.get('rx_bytes') or stat.get('rx_bytes') or 0,
                'tx_bytes': d.get('tx_bytes') or stat.get('tx_bytes') or 0,
                'state': d.get('state'),
                'connected': True if d.get('state') == 1 else False,
            })
        return jsonify(mapped)
    except Exception as e:
        print(f"[UniFi API] /api/unifi/devices error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'upstream_error'}), 502

@app.route('/api/unifi/clients')
@require_api_key()
def api_clients():
    if MOCK_MODE['clients']:
        return jsonify(MOCK_CLIENTS)
    try:
        raw_clients = get_session().get_clients(SITE)
        if raw_clients and len(raw_clients) > 0:
            print(f"[UniFi API] Found {len(raw_clients)} clients")
            print(f"[UniFi API] Sample client keys: {list(raw_clients[0].keys())}")
        else:
            print("[UniFi API] No clients found")

        def map_client(c: Dict[str, Any]) -> Dict[str, Any]:
            """Map UniFi raw client to simplified structure expected by dashboard."""
            hostname = (
                c.get('hostname')
                or c.get('name')
                or c.get('device_name')
                or c.get('oui')
                or c.get('mac')
            )
            ip = c.get('ip') or c.get('ip_address') or c.get('ipaddr')
            ap_mac = c.get('ap_mac') or c.get('apMac') or c.get('bssid')
            # Prefer 'signal' if present, else 'rssi'
            signal = c.get('signal')
            if signal is None:
                signal = c.get('rssi')
            # rx/tx rate may be in bps; preserve value and let UI scale as it already does
            rx_rate = c.get('rx_rate') or c.get('rx_rate_kbps')
            if rx_rate is not None and 'rx_rate_kbps' in c:
                try:
                    rx_rate = float(c.get('rx_rate_kbps')) * 1000.0
                except Exception:
                    pass
            tx_rate = c.get('tx_rate') or c.get('tx_rate_kbps')
            if tx_rate is not None and 'tx_rate_kbps' in c:
                try:
                    tx_rate = float(c.get('tx_rate_kbps')) * 1000.0
                except Exception:
                    pass

            return {
                'hostname': hostname or 'Unknown',
                'mac': c.get('mac'),
                'ip': ip,
                'ap_mac': ap_mac,
                'rx_bytes': c.get('rx_bytes'),
                'tx_bytes': c.get('tx_bytes'),
                'rx_rate': rx_rate,
                'tx_rate': tx_rate,
                'signal': signal,
                'channel': c.get('channel') or c.get('radio'),
                'uptime': c.get('uptime')
            }

        clients = [map_client(c) for c in raw_clients]
        return jsonify(clients)
    except Exception as e:
        print(f"[UniFi API] /api/unifi/clients error: {e}")
        return jsonify({'error': 'upstream_error'}), 502

@app.route('/api/unifi/mock', methods=['POST'])
@require_api_key(admin=True)
def api_mock_toggle():
    if not ENABLE_MOCK:
        return jsonify({'error': 'mock_disabled'}), 403
    data = request.get_json(force=True) or {}
    # Strict boolean enforcement
    for key in ['routers', 'bandwidth', 'clients']:
        if key in data:
            val = data[key]
            if isinstance(val, bool):
                MOCK_MODE[key] = val
            elif isinstance(val, (int, float)):
                MOCK_MODE[key] = bool(val)
            elif isinstance(val, str):
                MOCK_MODE[key] = val.strip().lower() in ("1", "true", "yes", "on")
            else:
                return jsonify({'error': f'invalid_type_for_{key}'}), 400
    return jsonify({'mock': MOCK_MODE})

@app.route('/api/unifi/bandwidth/total')
@require_api_key()
def api_bandwidth_total():
    if MOCK_MODE['bandwidth']:
        total_down = sum(ap.get('xput_down') or 0 for ap in MOCK_APS)
        total_up = sum(ap.get('xput_up') or 0 for ap in MOCK_APS)
        return jsonify({'total_down': total_down, 'total_up': total_up})
    try:
        devices = get_session().get_devices(SITE)
        total_down = 0.0
        total_up = 0.0
        for d in devices:
            st = d.get('speedtest-status') or {}
            total_down += float(st.get('xput_down') or 0)
            total_up += float(st.get('xput_up') or 0)
        return jsonify({'total_down': total_down, 'total_up': total_up})
    except Exception as e:
        return jsonify({'total_down': 0, 'total_up': 0, 'error': 'upstream_error'}), 502

@app.route('/api/unifi/clients/count')
@require_api_key()
def api_clients_count():
    if MOCK_MODE['clients']:
        return jsonify({'count': len(MOCK_CLIENTS)})
    try:
        clients = get_session().get_clients(SITE)
        return jsonify({'count': len(clients)})
    except Exception as e:
        return jsonify({'count': 0, 'error': 'upstream_error'}), 502

@app.route('/api/unifi/devices/<mac>/clients')
@require_api_key()
def api_device_clients(mac):
    """Get all clients connected to a specific AP by MAC address"""
    if not MAC_REGEX.match(mac):
        return jsonify({'error': 'invalid_mac'}), 400
    if MOCK_MODE['clients']:
        device_clients = [c for c in MOCK_CLIENTS if c.get('ap_mac', '').upper() == mac.upper()]
        return jsonify(device_clients)
    try:
        raw_clients = get_session().get_clients(SITE)
        # Filter by AP MAC using common fields
        filtered = []
        for c in raw_clients:
            ap_mac = (c.get('ap_mac') or c.get('apMac') or c.get('bssid') or '').upper()
            if ap_mac == mac.upper():
                filtered.append(c)

        # Map to simplified structure
        def map_client(c: Dict[str, Any]) -> Dict[str, Any]:
            hostname = (
                c.get('hostname')
                or c.get('name')
                or c.get('device_name')
                or c.get('oui')
                or c.get('mac')
            )
            ip = c.get('ip') or c.get('ip_address') or c.get('ipaddr')
            ap_mac_val = c.get('ap_mac') or c.get('apMac') or c.get('bssid')
            signal = c.get('signal') if c.get('signal') is not None else c.get('rssi')
            rx_rate = c.get('rx_rate') or c.get('rx_rate_kbps')
            if rx_rate is not None and 'rx_rate_kbps' in c:
                try:
                    rx_rate = float(c.get('rx_rate_kbps')) * 1000.0
                except Exception:
                    pass
            tx_rate = c.get('tx_rate') or c.get('tx_rate_kbps')
            if tx_rate is not None and 'tx_rate_kbps' in c:
                try:
                    tx_rate = float(c.get('tx_rate_kbps')) * 1000.0
                except Exception:
                    pass
            return {
                'hostname': hostname or 'Unknown',
                'mac': c.get('mac'),
                'ip': ip,
                'ap_mac': ap_mac_val,
                'rx_bytes': c.get('rx_bytes'),
                'tx_bytes': c.get('tx_bytes'),
                'rx_rate': rx_rate,
                'tx_rate': tx_rate,
                'signal': signal,
                'channel': c.get('channel') or c.get('radio'),
                'uptime': c.get('uptime')
            }

        device_clients = [map_client(c) for c in filtered]
        return jsonify(device_clients)
    except Exception as e:
        return jsonify({'error': 'upstream_error'}), 502


# --- NEW: Simulated Ping Endpoint ---
@app.route('/api/unifi/ping/<mac>')
@require_api_key()
@rate_limit(limit=int(os.getenv('PING_RATE_LIMIT', '20')), window_seconds=int(os.getenv('PING_RATE_WINDOW', '60')))
def api_ping_device(mac):
    if not MAC_REGEX.match(mac):
        return jsonify({'error': 'invalid_mac'}), 400
    # Try real devices first
    ip = None
    try:
        devices = get_session().get_devices(SITE)
        ap = next((d for d in devices if (d.get('mac') or '').upper() == mac.upper()), None)
        if ap:
            ip = ap.get('ip')
            state = ap.get('state')
    except Exception:
        ap = None
        state = None

    # Fallback to mock list for metadata if needed
    if ip is None:
        ap = next((a for a in MOCK_APS if a['mac'].upper() == mac.upper()), None)
        if ap:
            ip = ap.get('ip')
            state = ap.get('state')
    if not ip:
        return jsonify({'error': 'Device not found or IP unavailable'}), 404

    is_online, latency = ping_with_latency(ip)
    payload = {
        'mac': mac.upper(),
        'ip': ip,
        'connected': is_online if is_online is not None else (state == 1),
        'latency_ms': latency,
        'timestamp': int(time.time())
    }
    return jsonify(payload)


# --- OPTIONAL: real ping helper (for future real devices) ---
def ping_with_latency(ip: str) -> Tuple[Optional[bool], Optional[float]]:
    """Ping a host once and return (is_online, latency_ms).

    Returns (None, None) if parsing fails.
    """
    try:
        is_windows = platform.system().lower().startswith('win')
        count_flag = '-n' if is_windows else '-c'
        # Timeout flags: Windows -w in ms, Linux/mac -W seconds
        if is_windows:
            cmd = ['ping', count_flag, '1', '-w', '2000', ip]
        else:
            cmd = ['ping', count_flag, '1', '-W', '2', ip]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, universal_newlines=True)
        # Parse latency
        latency = None
        for line in out.splitlines():
            line = line.strip()
            if is_windows and 'time=' in line.lower():
                # Example: Reply from 192.168.1.1: bytes=32 time=3ms TTL=64
                try:
                    part = [p for p in line.split() if 'time=' in p.lower()][0]
                    val = part.split('=')[1]
                    val = val.replace('ms', '').replace('MS', '')
                    latency = float(val)
                    break
                except Exception:
                    continue
            elif not is_windows and 'time=' in line:
                # Example: time=3.12 ms
                try:
                    after = line.split('time=')[1]
                    val = after.split()[0]
                    latency = float(val)
                    break
                except Exception:
                    continue
        return True, latency
    except subprocess.CalledProcessError as e:
        # Ping failed; try to parse latency anyway
        try:
            out = e.output.decode() if isinstance(e.output, bytes) else e.output
            if out:
                # Try parse like above
                is_windows = platform.system().lower().startswith('win')
                latency = None
                for line in out.splitlines():
                    line = line.strip()
                    if is_windows and 'time=' in line.lower():
                        part = [p for p in line.split() if 'time=' in p.lower()][0]
                        val = part.split('=')[1]
                        val = val.replace('ms', '').replace('MS', '')
                        latency = float(val)
                        break
                    elif not is_windows and 'time=' in line:
                        after = line.split('time=')[1]
                        val = after.split()[0]
                        latency = float(val)
                        break
                return False, latency
        except Exception:
            pass
        return False, None
    except Exception:
        return None, None


if __name__ == '__main__':
    # Never enable debug=True by default
    app.run(port=5001, debug=FLASK_DEBUG)
