import tkinter as tk
from tkinter import ttk, messagebox
import requests
import urllib3

# Disable SSL warnings (UniFi uses self-signed SSL by default)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

## UniFi Controller details
# Your UniFi controller configuration
CONTROLLER_URL = "http://127.0.0.1:8080"      # Your controller URL
USERNAME = "admin"                            # Your UniFi username
PASSWORD = "admin123"                         # Your UniFi password
SITE = "default"                            # Default site is usually 'default'
REFRESH_INTERVAL = 5000                     # Auto-refresh every 5000 ms (5 sec)

session = requests.Session()

# Flask API base URL (tests improved unifi_api.py)
FLASK_API_BASE = "http://127.0.0.1:5001/api/unifi"

def login_unifi():
    """Try login for UniFi v7+ (/api/auth/login), fallback to v6 (/api/login)."""
    login_payload = {"username": USERNAME, "password": PASSWORD}

    # Try UniFi v7+
    login_url_v7 = f"{CONTROLLER_URL}/api/auth/login"
    print(f"DEBUG: Trying login URL: {login_url_v7}")
    resp = session.post(login_url_v7, json=login_payload, verify=False)
    if resp.status_code == 200:
        return True, "v7+"

    # Try UniFi v6
    resp = session.post(f"{CONTROLLER_URL}/api/login", json=login_payload, verify=False)
    if resp.status_code == 200:
        return True, "v6"

    return False, resp.text

def fetch_devices():
    """Fetch UniFi devices (APs) directly from controller."""
    resp = session.get(f"{CONTROLLER_URL}/api/s/{SITE}/stat/device", verify=False)
    if resp.status_code == 200:
        try:
            return resp.json().get("data", [])
        except Exception:
            return []
    return []

def fetch_devices_via_flask():
    """Fetch devices via Flask API (improved unifi_api.py)."""
    try:
        resp = requests.get(f"{FLASK_API_BASE}/devices")
        if resp.status_code == 200:
            return resp.json() if isinstance(resp.json(), list) else []
        return []
    except Exception:
        return []

def fetch_clients():
    """Fetch connected clients directly from controller."""
    resp = session.get(f"{CONTROLLER_URL}/api/s/{SITE}/stat/sta", verify=False)
    if resp.status_code == 200:
        try:
            return resp.json().get("data", [])
        except Exception:
            return []
    return []

def fetch_clients_via_flask():
    """Fetch connected clients via Flask API (improved unifi_api.py)."""
    try:
        resp = requests.get(f"{FLASK_API_BASE}/clients")
        if resp.status_code == 200:
            data = resp.json()
            # Flask returns a list (not wrapped), pass-through
            return data if isinstance(data, list) else []
        return []
    except Exception:
        return []

def logout_unifi():
    """Logout cleanly."""
    session.get(f"{CONTROLLER_URL}/logout", verify=False)

# ------------------ GUI ------------------

class UniFiApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("UniFi Test App")
        self.geometry("900x550")

        # Buttons
        top_frame = ttk.Frame(self)
        top_frame.pack(fill="x", pady=5)

        self.refresh_btn = ttk.Button(top_frame, text="Manual Refresh", command=self.load_data)
        self.refresh_btn.pack(side="left", padx=5)

        self.status_label = ttk.Label(top_frame, text="Status: Not connected")
        self.status_label.pack(side="left", padx=10)

        # Data source toggle
        self.source_var = tk.StringVar(value="Flask API")
        self.source_combo = ttk.Combobox(top_frame, textvariable=self.source_var, state="readonly", values=["Flask API", "Controller"])
        self.source_combo.pack(side="right", padx=5)
        ttk.Label(top_frame, text="Data Source:").pack(side="right")

        # Notebook (tabs)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        # AP Tab
        self.ap_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.ap_frame, text="Access Points")

        self.ap_tree = ttk.Treeview(
            self.ap_frame,
            columns=("Model", "Name", "MAC", "IP", "Down", "Up"),
            show="headings"
        )
        for col in ("Model", "Name", "MAC", "IP", "Down", "Up"):
            self.ap_tree.heading(col, text=col)
            self.ap_tree.column(col, width=130)
        self.ap_tree.pack(fill="both", expand=True)

        # Clients Tab
        self.client_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.client_frame, text="Clients")

        self.client_tree = ttk.Treeview(
            self.client_frame,
            columns=("Host", "MAC", "IP", "AP", "RX_MB", "TX_MB"),
            show="headings"
        )
        for col in ("Host", "MAC", "IP", "AP", "RX_MB", "TX_MB"):
            self.client_tree.heading(col, text=col)
            self.client_tree.column(col, width=130)
        self.client_tree.pack(fill="both", expand=True)

        # API Test Tab
        self.api_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.api_frame, text="API Endpoints Test")

        self.api_test_btn = ttk.Button(self.api_frame, text="Test Endpoints", command=self.test_api_endpoints)
        self.api_test_btn.pack(pady=10)

        self.api_result = tk.Text(self.api_frame, height=20, width=100)
        self.api_result.pack(fill="both", expand=True)

        # Mock controls
        self.mock_frame = ttk.Frame(self.api_frame)
        self.mock_frame.pack(fill="x", pady=5)
        ttk.Label(self.mock_frame, text="Mock Mode:").pack(side="left")
        ttk.Button(self.mock_frame, text="Enable Mock (all)", command=lambda: self.set_mock(True)).pack(side="left", padx=5)
        ttk.Button(self.mock_frame, text="Disable Mock", command=lambda: self.set_mock(False)).pack(side="left", padx=5)

        # Auto-refresh loop
        self.after(2000, self.load_data)  # wait 2s then first load

    def load_data(self):
        # Clear tables
        for i in self.ap_tree.get_children():
            self.ap_tree.delete(i)
        for i in self.client_tree.get_children():
            self.client_tree.delete(i)

        source = self.source_var.get()
        version_info = "n/a"
        ok = False

        if source == "Controller":
            ok, version_info = login_unifi()
            if ok:
                aps = fetch_devices()
                clients = fetch_clients()
            else:
                aps, clients = [], []
            logout_unifi()
        else:  # Flask API
            # Use Flask endpoints directly
            try:
                aps = fetch_devices_via_flask()
                clients = fetch_clients_via_flask()
                ok = True
                version_info = "Flask"
            except Exception as e:
                aps, clients = [], []
                version_info = f"Flask error: {e}"

        # Populate tables
        for d in aps:
            self.ap_tree.insert("", "end", values=(
                d.get("model", "Unknown"),
                d.get("name", d.get("device_id", d.get("mac", "Unnamed"))),
                d.get("mac"),
                d.get("ip"),
                d.get("xput_down", d.get("speedtest-status", {}).get("xput_down", "N/A")),
                d.get("xput_up", d.get("speedtest-status", {}).get("xput_up", "N/A"))
            ))

        for c in clients:
            self.client_tree.insert("", "end", values=(
                c.get("hostname", c.get("name", "Unknown")),
                c.get("mac"),
                c.get("ip"),
                c.get("ap_mac"),
                round((c.get("rx_bytes", 0) or 0) / 1_000_000, 2),
                round((c.get("tx_bytes", 0) or 0) / 1_000_000, 2)
            ))

        status = "Connected" if ok else "Not connected"
        self.status_label.config(text=f"Status: {status} (Source: {source}, API {version_info})")

        # Schedule next refresh
        self.after(REFRESH_INTERVAL, self.load_data)

    def test_api_endpoints(self):
        """Test Flask API endpoints and show results."""
        self.api_result.delete("1.0", tk.END)

        def log_line(line: str):
            self.api_result.insert(tk.END, line + "\n")

        base_url = FLASK_API_BASE

        # Health: try root login endpoints (Flask stubs)
        try:
            resp = requests.post(base_url.replace("/api/unifi", "/api/auth/login"), json={"username": "x", "password": "y"})
            log_line(f"[Flask] /api/auth/login -> {resp.status_code}")
        except Exception as e:
            log_line(f"[Flask] /api/auth/login error: {e}")

        # Devices
        try:
            resp = requests.get(f"{base_url}/devices")
            log_line(f"/devices status: {resp.status_code}")
            devices = resp.json()
            log_line(f"/devices count: {len(devices) if isinstance(devices, list) else 'n/a'}")
        except Exception as e:
            log_line(f"Error testing /devices: {e}")
            devices = []

        # Clients
        try:
            resp = requests.get(f"{base_url}/clients")
            log_line(f"/clients status: {resp.status_code}")
            clients = resp.json()
            log_line(f"/clients count: {len(clients) if isinstance(clients, list) else 'n/a'}")
        except Exception as e:
            log_line(f"Error testing /clients: {e}")

        # Total bandwidth
        try:
            resp = requests.get(f"{base_url}/bandwidth/total")
            log_line(f"/bandwidth/total status: {resp.status_code}")
            log_line(f"/bandwidth/total response: {resp.json()}")
        except Exception as e:
            log_line(f"Error testing /bandwidth/total: {e}")

        # Client count
        try:
            resp = requests.get(f"{base_url}/clients/count")
            log_line(f"/clients/count status: {resp.status_code}")
            log_line(f"/clients/count response: {resp.json()}")
        except Exception as e:
            log_line(f"Error testing /clients/count: {e}")

        # Compatibility endpoints (should proxy controller)
        try:
            resp = requests.get(base_url.replace("/api/unifi", f"/api/s/{SITE}/stat/device"))
            log_line(f"/api/s/{SITE}/stat/device status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                log_line(f"compat devices count: {len(data)}")
        except Exception as e:
            log_line(f"Error compat /stat/device: {e}")

        try:
            resp = requests.get(base_url.replace("/api/unifi", f"/api/s/{SITE}/stat/sta"))
            log_line(f"/api/s/{SITE}/stat/sta status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                log_line(f"compat clients count: {len(data)}")
        except Exception as e:
            log_line(f"Error compat /stat/sta: {e}")

        # Ping first device (if any)
        try:
            if isinstance(devices, list) and devices:
                mac = devices[0].get("mac")
                if mac:
                    resp = requests.get(f"{base_url}/ping/{mac}")
                    log_line(f"/ping/{mac} status: {resp.status_code}")
                    log_line(f"/ping/{mac} response: {resp.json()}")
                else:
                    log_line("No MAC on first device to ping.")
            else:
                log_line("No devices available to ping.")
        except Exception as e:
            log_line(f"Error testing /ping/<mac>: {e}")

    def set_mock(self, enabled: bool):
        """Toggle mock on Flask API."""
        try:
            payload = {"routers": enabled, "clients": enabled, "bandwidth": enabled}
            resp = requests.post(FLASK_API_BASE + "/mock", json=payload)
            self.api_result.insert(tk.END, f"Set mock={enabled} -> {resp.status_code}, {resp.json()}\n")
        except Exception as e:
            self.api_result.insert(tk.END, f"Error toggling mock: {e}\n")

if __name__ == "__main__":
    app = UniFiApp()
    app.mainloop()
