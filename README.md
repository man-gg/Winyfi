# WINYFI Network Monitoring

A desktop-first network monitoring and management system built with Python. It provides a modern Tk/ttkbootstrap dashboard for admins and clients, a lightweight Flask API, real-time router status tracking, loop detection, bandwidth logging, reporting (CSV/PDF), and push-style notifications.

## What’s inside

- Desktop GUI (Tkinter + ttkbootstrap) — `main.py`, `dashboard.py`
- REST API server (Flask) — `server/app.py`
- MySQL for operational data — routers, status logs, bandwidth logs, users, sessions
- SQLite for notifications — `network_monitoring.db`
- Packet sniffing and loop detection — Scapy-based utilities in `network_utils.py`
- Reporting and exports — charts (matplotlib) and PDFs (ReportLab)

## Features

- Router inventory, online/offline status, last seen, image per router
- Auto-refreshing, card-based dashboard with charts (router status, bandwidth, health)
- Background loop detection (lightweight) with history and severity scoring
- Bandwidth logging per router (periodic, configurable) and CSV export
- Notification system with toast popups, panel, and settings (SQLite-backed)
- User login (admin/client), login session logging, user management UI
- Reports API + downloadable PDFs with charts; CSV export from the app

## Requirements

- Python 3.10+ (3.13 supported)
- MySQL or MariaDB (for operational data)
- Npcap/WinPcap (packet capture on Windows for Scapy sniffing)
- Windows: run the app as Administrator for packet capture features

Python packages (installed via requirements files):
- Root app: `flask`, `mysql-connector-python`, `requests`, `ttkbootstrap`, `matplotlib`, `reportlab`
- Server: `flask`, `flask-cors`, `mysql-connector-python`, `werkzeug`, `ttkbootstrap`, `Pillow`
- Additionally used in code: `speedtest-cli`, `scapy`, `psutil`, `Pillow`
   - Note: bandwidth tests are disabled by default via `DISABLE_BANDWIDTH = True` in `network_utils.py`, but the module `speedtest` is still imported. Install `speedtest-cli` if you enable bandwidth tests.

## Setup (Windows PowerShell)

1) Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2) Install dependencies (desktop app + API server)

```powershell
pip install -r requirements.txt
pip install -r server/requirements.txt
# Optional but recommended for all features:
pip install speedtest-cli scapy psutil
```

3) Database configuration

- Create a MySQL database (default expected name in code: `winyfi`).
- Update credentials in `db.py` if needed:
   - host, user, password, database

Minimal tables expected by the app (simplified schema):

```sql
CREATE TABLE IF NOT EXISTS users (
   id INT AUTO_INCREMENT PRIMARY KEY,
   first_name VARCHAR(100),
   last_name VARCHAR(100),
   username VARCHAR(100) UNIQUE NOT NULL,
   password_hash VARCHAR(255) NOT NULL,
   role ENUM('admin','user') NOT NULL DEFAULT 'user'
);

CREATE TABLE IF NOT EXISTS routers (
   id INT AUTO_INCREMENT PRIMARY KEY,
   name VARCHAR(255),
   ip_address VARCHAR(100),
   mac_address VARCHAR(100),
   brand VARCHAR(100),
   location VARCHAR(255),
   image_path VARCHAR(255),
   last_seen DATETIME NULL
);

CREATE TABLE IF NOT EXISTS router_status_log (
   id INT AUTO_INCREMENT PRIMARY KEY,
   router_id INT NOT NULL,
   status ENUM('online','offline') NOT NULL,
   timestamp DATETIME NOT NULL,
   INDEX (router_id, timestamp)
);

CREATE TABLE IF NOT EXISTS bandwidth_logs (
   id INT AUTO_INCREMENT PRIMARY KEY,
   router_id INT NOT NULL,
   download_mbps DOUBLE,
   upload_mbps DOUBLE,
   latency_ms DOUBLE,
   timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
   INDEX (router_id, timestamp)
);

-- Session logging used by login.py and server/app.py
CREATE TABLE IF NOT EXISTS login_sessions (
   id INT AUTO_INCREMENT PRIMARY KEY,
   user_id INT NOT NULL,
   username VARCHAR(100) NOT NULL,
   device_ip VARCHAR(45),
   device_mac VARCHAR(17),
   device_hostname VARCHAR(255),
   device_platform VARCHAR(100),
   user_agent TEXT,
   login_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
   logout_timestamp TIMESTAMP NULL,
   session_duration_seconds INT NULL,
   is_active BOOLEAN DEFAULT TRUE,
   login_type ENUM('admin','client') NOT NULL,
   INDEX (user_id), INDEX (username), INDEX (device_mac), INDEX (login_timestamp), INDEX (is_active)
);
```

Loop detection and network clients tables are auto-created by the app via `db.py` helpers when features are used:
- `create_loop_detections_table()` → `loop_detections`
- `create_network_clients_table()` and `create_connection_history_table()`

4) Seed an admin user (quick way)

```powershell
python -c "from user_utils import insert_user; insert_user('admin','admin123','Admin','User','admin')"
```

5) Npcap/WinPcap (for loop detection)
- Install Npcap from https://nmap.org/npcap/
- Run the desktop app as Administrator when using loop detection or client discovery

## Running

Start the API server (port 5000 by default):

```powershell
python .\server\app.py
```

Start the desktop app. Optionally point it to a remote API with `WINYFI_API` env var (defaults to http://localhost:5000):

```powershell
$env:WINYFI_API = "http://localhost:5000"; python .\main.py
```

Login with the seeded admin or an existing user. Admins see the full dashboard; non-admins get the client portal.

## Configuration tips

- `db.py`: MySQL connection settings
- `network_utils.py`: set `DISABLE_BANDWIDTH = False` to enable speed tests. Requires `speedtest-cli` and Internet access. Heavy tests run with cooldowns.
- `bandwidth_logger.py`: `LOG_INTERVAL` (default 300s)
- `server/app.py`: Flask app; exposes report, bandwidth, router status, and loop detection endpoints
- `WINYFI_API`: environment variable to override API URL used by the desktop app

## Notable endpoints (server)

- GET `/api/health`
- POST `/api/login`
- GET `/api/routers`, `/api/routers/<id>/status`
- GET `/api/dashboard/stats`
- GET `/api/reports/uptime`
- GET `/api/reports/pdf`, `/api/reports/pdf-with-charts`
- GET `/api/bandwidth/logs`, `/api/bandwidth/stats`
- GET `/api/loop-detection` (history + stats)

## File guide

- `main.py` — Desktop app entry; themed root window → login → dashboard/client
- `login.py` — Login UI, rate limiting, session logging, device info
- `dashboard.py` — Modern dashboard UI, routers management, reports, bandwidth, notifications, exports
- `router_utils.py` — CRUD + status logging and online checks via `router_status_log`
- `network_utils.py` — Ping, bandwidth hybrid logic, loop detection (Scapy), client discovery, subnet scan
- `bandwidth_logger.py` — Periodic bandwidth logging worker
- `report_utils.py` — Uptime %, status logs, bandwidth usage aggregation
- `notification_utils.py` / `notification_ui.py` — SQLite-backed notifications + UI (toast + panel)
- `server/app.py` — Flask API server used by the desktop app and clients

## Troubleshooting

- MySQL connection errors: verify `db.py` credentials and that the `winyfi` DB exists
- Packet capture fails or detects zero traffic: install Npcap and run as Administrator; choose the right interface in code if needed
- Bandwidth tests failing: install `speedtest-cli`; Internet connectivity is required; keep `DISABLE_BANDWIDTH` true in constrained environments
- Missing images: ensure files in `assets/images/` exist (`Banner.png`, `logo1.png`)
- PDFs require `reportlab`; charts require `matplotlib` — both are included in requirements

## Contributing

1. Create a feature branch from `main`
2. Keep changes focused; include minimal docs/tests when public behavior changes
3. Open a PR explaining the change and how to verify

## License

[Add your license here]

## Support

Open an issue or reach out to the maintainer with environment details (Windows version, Python version, MySQL version, error logs).
