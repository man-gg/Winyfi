import tkinter as tk
from tkinter import ttk, messagebox
import requests
import urllib3

# Disable SSL warnings (UniFi uses self-signed SSL by default)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# UniFi Controller details
CONTROLLER_URL = "https://127.0.0.1:8443/"   # Change if remote
USERNAME = "admin"                          # Replace with your UniFi username
PASSWORD = "admin123"                       # Replace with your UniFi password
SITE = "default"                            # Default site is usually 'default'
REFRESH_INTERVAL = 5000                     # Auto-refresh every 5000 ms (5 sec)

session = requests.Session()

def login_unifi():
    """Try login for UniFi v7+ (/api/auth/login), fallback to v6 (/api/login)."""
    login_payload = {"username": USERNAME, "password": PASSWORD}

    # Try UniFi v7+
    resp = session.post(f"{CONTROLLER_URL}/api/auth/login", json=login_payload, verify=False)
    if resp.status_code == 200:
        return True, "v7+"

    # Try UniFi v6
    resp = session.post(f"{CONTROLLER_URL}/api/login", json=login_payload, verify=False)
    if resp.status_code == 200:
        return True, "v6"

    return False, resp.text

def fetch_devices():
    """Fetch UniFi devices (APs)."""
    resp = session.get(f"{CONTROLLER_URL}/api/s/{SITE}/stat/device", verify=False)
    if resp.status_code == 200:
        return resp.json().get("data", [])
    return []

def fetch_clients():
    """Fetch connected clients."""
    resp = session.get(f"{CONTROLLER_URL}/api/s/{SITE}/stat/sta", verify=False)
    if resp.status_code == 200:
        return resp.json().get("data", [])
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

        # Auto-refresh loop
        self.after(2000, self.load_data)  # wait 2s then first load

    def load_data(self):
        ok, version = login_unifi()
        if not ok:
            self.status_label.config(text=f"Status: Login failed ({version})")
            return

        # Clear tables
        for i in self.ap_tree.get_children():
            self.ap_tree.delete(i)
        for i in self.client_tree.get_children():
            self.client_tree.delete(i)

        # Load APs
        aps = fetch_devices()
        for d in aps:
            self.ap_tree.insert("", "end", values=(
                d.get("model", "Unknown"),
                d.get("name", "Unnamed"),
                d.get("mac"),
                d.get("ip"),
                d.get("xput_down", "N/A"),
                d.get("xput_up", "N/A")
            ))

        # Load Clients
        clients = fetch_clients()
        for c in clients:
            self.client_tree.insert("", "end", values=(
                c.get("hostname", "Unknown"),
                c.get("mac"),
                c.get("ip"),
                c.get("ap_mac"),
                round(c.get("rx_bytes", 0) / 1_000_000, 2),
                round(c.get("tx_bytes", 0) / 1_000_000, 2)
            ))

        self.status_label.config(text=f"Status: Connected (API {version})")

        logout_unifi()

        # Schedule next refresh
        self.after(REFRESH_INTERVAL, self.load_data)

if __name__ == "__main__":
    app = UniFiApp()
    app.mainloop()
