import os
import shutil
import time
import threading
import concurrent.futures
import csv
import requests
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import messagebox, Toplevel, Menu, filedialog, ttk, simpledialog, Text
import time as _perf_time  # for loader timing (perf counter)
import tkinter as tk
from ttkbootstrap.dialogs import DatePickerDialog
from PIL import Image, ImageTk
from collections import defaultdict
from tkinter import Toplevel, messagebox
import ttkbootstrap as tb
import tkinter.ttk as ttk 
import tkinter as tk
from datetime import datetime, time
import time
from tkinter.ttk import Notebook
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

# Suppress matplotlib warnings
import logging
matplotlib_logger = logging.getLogger('matplotlib')
matplotlib_logger.setLevel(logging.ERROR)

import tkinter as tk
from datetime import datetime, date, timedelta
# tkcalendar Calendar not needed; using ttkbootstrap DateEntry
from datetime import datetime, timedelta  # ensure timedelta is imported
from ttkbootstrap.widgets import DateEntry
from report_utils import get_uptime_percentage, get_status_logs, get_bandwidth_usage
from router_utils import get_routers
from user_utils import insert_user, get_all_users, delete_user, update_user, get_user_last_login
from network_utils import ping_latency,get_bandwidth, detect_loops, discover_clients, get_default_iface,scan_subnet, get_default_iface
from bandwidth_logger import start_bandwidth_logging
from db import get_connection 
from db import database_health_check, get_database_info, DatabaseConnectionError
from db import create_activity_logs_table, log_activity, get_activity_logs, log_user_logout
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import ticket_utils
from ticket_utils import fetch_srfs, create_srf
import itertools
from print_utils import print_srf_form
import numpy as np

# Safe print function that handles Unicode encoding errors on Windows
def safe_print(message):
    """Print with fallback for Unicode encoding errors on Windows console."""
    try:
        print(message)
    except UnicodeEncodeError:
        # Fall back to ASCII-safe version (remove emojis and special chars)
        import re
        ascii_message = re.sub(r'[^\x00-\x7F]+', '?', str(message))
        print(ascii_message)
from matplotlib.ticker import MaxNLocator
import mplcursors

from router_utils import (
    insert_router,
    get_routers,
    is_online,
    update_router,
    delete_router,
    update_router_status_in_db
)

# Import notification system
from notification_utils import (
    notification_manager,
    notify_loop_detected,
    notify_router_status_change,
    notify_bandwidth_high,
    notify_system_alert,
    NotificationPriority
)
from notification_ui import NotificationSystem
from resource_utils import get_resource_path, ensure_directory, resource_exists
from service_manager import get_service_manager
import logging
logger = logging.getLogger(__name__)

# Safe emoji printing for Windows console compatibility
def safe_emoji_print(text):
    """Print text with emoji, safely handling Unicode encoding errors."""
    try:
        print(text)
    except UnicodeEncodeError:
        # Fallback: remove emoji and print plain text
        import re
        # Remove emoji characters
        plain_text = re.sub(r'[\U0001F300-\U0001F9FF]', '', text)
        try:
            print(plain_text)
        except:
            # Last resort: just print without any special chars
            pass


# Directory for router images
IMAGE_FOLDER = ensure_directory("routerLocImg")

router_widgets = {}
class Dashboard:
    def ping_all_online_aps_once(self):
        """Immediately ping all online APs in parallel and update their cards."""
        import concurrent.futures
        import threading
        online_rids = [rid for rid, w in self.router_widgets.items()
                       if self.status_history.get(rid, {}).get('current') is True]
        if not online_rids:
            return
        def do_ping():
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(online_rids)) as pool:
                futures = [
                    pool.submit(self.fetch_and_update_bandwidth, rid, self.router_widgets[rid]['data']['ip_address'])
                    for rid in online_rids
                ]
                concurrent.futures.wait(futures, timeout=10)
        threading.Thread(target=do_ping, daemon=True).start()
    def __init__(self, root, current_user, api_base_url="http://localhost:5000"):
        self.app_running = True
        # UniFi API URL - configurable via environment or use localhost default
        # For remote setup: set WINYFI_UNIFI_API_URL=http://<machine-a-ip>:5001
        self.unifi_api_url = os.getenv("WINYFI_UNIFI_API_URL", "http://192.168.1.27:5001")
        print(f"[Dashboard] UniFi API URL: {self.unifi_api_url}")
        self.unifi_devices = []  # Store UniFi devices
        self.unifi_refresh_job = None  # Auto-refresh job for UniFi data
        self.root = root
        self.current_user = current_user
        self.api_base_url = api_base_url
        self.router_list = []
        self.status_history = defaultdict(lambda: {"failures": 0, "current": None})
        self.router_widgets = {}
        self.bandwidth_data = {}
        self.update_task = None  # Store .after() task ID
        self.db_health_status = {"status": "unknown", "message": "Not checked"}
        
        # Inline loader state defaults (defensive init)
        self._bandwidth_loading = False
        self._reports_loading = False
        self._bandwidth_loading_started = None
        self._reports_loading_started = None
        self._loader_min_ms = 350
        self._bandwidth_hide_after_job = None
        self._reports_hide_after_job = None
        
        # Routers view caching (avoid glitchy redraws)
        self._routers_snapshot_hash = None
        
        # Routers tab auto-refresh settings
        self.routers_refresh_job = None
        self.routers_refresh_interval = 30000  # 30 seconds default
        self.is_refreshing_routers = False  # Prevent overlapping refreshes
        
        # Perform database health check before proceeding
        self._check_database_health()
        
        # Loop detection settings
        self.loop_detection_running = False
        self.loop_detection_interval = 300  # 5 minutes default
        self.loop_detection_enabled = True
        self.loop_detection_thread = None
        self.loop_detection_history = []
        
        # Client modal tracking
        self.client_modal = None
        self.client_modal_is_open = False
        
        # Initialize database and load stats (with error handling)
        self._initialize_database()
        
        # Initialize notification system
        self.notification_system = NotificationSystem(self.root)
        self.notification_count = 0
        
        # Initialize performance optimization for notifications
        from notification_performance import initialize_cached_count, get_throttler
        self._notification_throttler = get_throttler()
        self._cached_notification_count = initialize_cached_count(
            lambda: self.notification_system.get_notification_count(),
            cache_duration=2.0  # Cache for 2 seconds
        )
        
        self._build_ui()
        self.reload_routers(force_reload=True)
        # Refresh dashboard stats now that routers list has been populated
        try:
            if hasattr(self, 'update_statistics'):
                self.update_statistics()
        except Exception:
            pass

        # 🟩 Place this BEFORE any looping tasks like background threads or after()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)


        self.schedule_update()  # For auto-refresh
        threading.Thread(target=self._background_status_updater, daemon=True).start()

        # Start periodic UniFi bandwidth polling
        self._unifi_bandwidth_job = None
        self._start_unifi_bandwidth_polling()
        
        # Start routers tab auto-refresh
        self.start_routers_auto_refresh()

        # Start automatic loop detection (only if database is healthy)
        if self.loop_detection_enabled and self.db_health_status["status"] == "healthy":
            self.start_loop_detection()

        start_bandwidth_logging(self._fetch_router_list)
            
    def _start_unifi_bandwidth_polling(self, interval_ms=60000):
        """Periodically fetch UniFi device bandwidth and log to DB."""
        def poll():
            # Check if app is running and window still exists
            if not self.app_running:
                return
            
            try:
                if not self.root.winfo_exists():
                    return
            except Exception:
                return
            
            try:
                devices = self._fetch_unifi_devices()
                # Already logs to DB in _fetch_unifi_devices
                # Live-update router cards if the Routers tab is rendered
                try:
                    # Build mac->(down,up) map from API payload
                    mac_to_speeds = {}
                    for d in devices or []:
                        mac = d.get('mac_address') or d.get('mac')
                        if mac:
                            mac_to_speeds[mac] = (
                                float(d.get('download_speed') or 0.0),
                                float(d.get('upload_speed') or 0.0)
                            )
                    # Update existing cards without full reload
                    if hasattr(self, 'router_widgets') and self.router_widgets:
                        for rid, widgets in list(self.router_widgets.items()):
                            try:
                                router = widgets.get('data') or {}
                                if not router.get('is_unifi'):
                                    continue
                                mac = router.get('mac_address')
                                if not mac or mac not in mac_to_speeds:
                                    continue
                                down, up = mac_to_speeds[mac]
                                # Persist into stored data for future refreshes
                                router['download_speed'] = down
                                router['upload_speed'] = up
                                lbl = widgets.get('bandwidth_label')
                                latency = router.get('latency')
                                # Compose display string (show speeds even if latency unknown)
                                speed_text = (
                                    f"📶 ↓{down:.1f} Mbps ↑{up:.1f} Mbps" if (down > 0 or up > 0)
                                    else "📶 Bandwidth: --"
                                )
                                latency_text = f"   ⚡ {latency:.1f} ms" if isinstance(latency, (int, float)) else "   ⚡ --"
                                if lbl and hasattr(lbl, 'winfo_exists') and lbl.winfo_exists():
                                    lbl.config(text=speed_text + latency_text, bootstyle=("info" if (down > 0 or up > 0) else "secondary"))
                            except Exception:
                                continue
                except Exception:
                    pass
            except Exception:
                pass
            # Schedule next poll
            self._unifi_bandwidth_job = self.root.after(interval_ms, poll)
        poll()

    def stop_unifi_bandwidth_polling(self):
        if self._unifi_bandwidth_job:
            self.root.after_cancel(self._unifi_bandwidth_job)
            self._unifi_bandwidth_job = None

        # State flags for inline loaders
        self._bandwidth_loading = False
        self._reports_loading = False
        self._bandwidth_loading_started = None
        self._reports_loading_started = None
        self._loader_min_ms = 350  # minimum visible time for spinners
        self._bandwidth_hide_after_job = None

    # Defensive: ensure _bandwidth_hide_after_job always exists
    @property
    def _bandwidth_hide_after_job(self):
        return getattr(self, "__bandwidth_hide_after_job", None)
    @_bandwidth_hide_after_job.setter
    def _bandwidth_hide_after_job(self, value):
        self.__bandwidth_hide_after_job = value
        self._reports_hide_after_job = None

    # Defensive: ensure _loader_min_ms always exists
    @property
    def _loader_min_ms(self):
        return getattr(self, "__loader_min_ms", 350)
    @_loader_min_ms.setter
    def _loader_min_ms(self, value):
        self.__loader_min_ms = value

    def _check_database_health(self):
        """Check database health and display warnings if needed"""
        try:
            self.db_health_status = database_health_check()
            
            if self.db_health_status["status"] == "error":
                self._show_database_error_dialog()
            elif self.db_health_status["status"] == "warning":
                self._show_database_warning_dialog()
                
        except Exception as e:
            self.db_health_status = {
                "status": "error",
                "message": f"Failed to check database health: {str(e)}"
            }
            self._show_database_error_dialog()
    
    def _show_database_error_dialog(self):
        """Show database error dialog with detailed information and options"""
        from tkinter import messagebox
    
    def _show_database_warning_dialog(self):
        """Show database warning dialog"""
        from tkinter import messagebox
        
        warning_msg = (
            "⚠️ Database Connection Warning\n\n"
            f"{self.db_health_status['message']}\n\n"
            "Some features may not work properly."
        )
        
        messagebox.showwarning("Database Warning", warning_msg)
    
    def _initialize_database(self):
        """Initialize database tables and load initial data with error handling"""
        try:
            # Only proceed if database is accessible
            if self.db_health_status["status"] in ["healthy", "warning"]:
                from db import (
                    create_loop_detections_table,
                    get_loop_detection_stats,
                    get_loop_detections_history,
                    create_bandwidth_logs_table,
                )
                
                # Create tables
                create_loop_detections_table()
                create_bandwidth_logs_table()
                
                # Load statistics
                self.loop_detection_stats = get_loop_detection_stats()
                self.loop_detection_history = get_loop_detections_history(100)
            else:
                # Set safe defaults when database is unavailable
                self.loop_detection_stats = {
                    "total_detections": 0,
                    "loops_detected": 0,
                    "suspicious_activity": 0,
                    "clean_detections": 0
                }
                self.loop_detection_history = []
                
        except Exception as e:
            # Set safe defaults on any error
            self.loop_detection_stats = {
                "total_detections": 0,
                "loops_detected": 0,
                "suspicious_activity": 0,
                "clean_detections": 0
            }
            self.loop_detection_history = []
            print(f"Warning: Could not initialize database: {e}")

    def _check_database_health(self):
        """Check database health and display warnings if needed"""
        try:
            self.db_health_status = database_health_check()
            
            if self.db_health_status["status"] == "error":
                self._show_database_error_dialog()
            elif self.db_health_status["status"] == "warning":
                self._show_database_warning_dialog()
                
        except Exception as e:
            self.db_health_status = {
                "status": "error",
                "message": f"Failed to check database health: {str(e)}"
            }
            self._show_database_error_dialog()
    
    def _show_database_error_dialog(self):
        """Show database error dialog with simplified message"""
        from tkinter import messagebox
        
        error_msg = (
            "Unable to connect to the database.\n\n"
            "Please start MySQL (XAMPP/WAMP) and try again.\n\n"
            "The application will continue with limited functionality."
        )
        
        messagebox.showerror("Database Connection Error", error_msg)
    
    def _show_database_warning_dialog(self):
        """Show database warning dialog"""
        from tkinter import messagebox
        
        warning_msg = (
            "Database connection is unstable.\n\n"
            "Some features may not work properly."
        )
        
        messagebox.showwarning("Database Warning", warning_msg)
    
    def _initialize_database(self):
        """Initialize database with error handling"""
        try:
            if self.db_health_status["status"] in ["healthy", "warning"]:
                from db import create_loop_detections_table, get_loop_detection_stats, get_loop_detections_history
                
                # Try to create tables
                create_result = create_loop_detections_table()
                if create_result:
                    self.loop_detection_stats = get_loop_detection_stats()
                    self.loop_detection_history = get_loop_detections_history(100)
                else:
                    # Use default values if table creation failed
                    self.loop_detection_stats = {
                        "total_detections": 0,
                        "loops_detected": 0,
                        "suspicious_activity": 0,
                        "clean_detections": 0
                    }
                    self.loop_detection_history = []
            else:
                # Database is not accessible, use default values
                self.loop_detection_stats = {
                    "total_detections": 0,
                    "loops_detected": 0,
                    "suspicious_activity": 0,
                    "clean_detections": 0
                }
                self.loop_detection_history = []
                
        except Exception as e:
            print(f"Error initializing database: {e}")
            # Use default values
            self.loop_detection_stats = {
                "total_detections": 0,
                "loops_detected": 0,
                "suspicious_activity": 0,
                "clean_detections": 0
            }
            self.loop_detection_history = []
    
    def get_database_status(self):
        """Get current database status for display in UI"""
        return self.db_health_status
    
    def refresh_database_health(self):
        """Refresh database health check"""
        self._check_database_health()
        return self.db_health_status
    
    # =============================
    # Inline Loading Animation Helpers
    # =============================
    def _show_bandwidth_loading(self):
        if getattr(self, '_bandwidth_loading', False):
            return
        if hasattr(self, 'bandwidth_loading_spinner'):
            try:
                self._bandwidth_loading_started = _perf_time.perf_counter()
                # Disable action buttons in bandwidth button frame while loading
                try:
                    if not hasattr(self, '_bandwidth_disabled_widgets'):
                        self._bandwidth_disabled_widgets = []
                    # Find parent frame of spinner (button_frame was used when created)
                    btn_parent = self.bandwidth_loading_spinner.master
                    for child in btn_parent.winfo_children():
                        # Don't disable the spinner itself
                        if child is self.bandwidth_loading_spinner:
                            continue
                        # Disable only buttons
                        if child.winfo_class() in ("TButton", "Button") and child['state'] != 'disabled':
                            self._bandwidth_disabled_widgets.append(child)
                            child.config(state='disabled')
                except Exception:
                    pass

                # Add / reuse a small label
                if not hasattr(self, 'bandwidth_loading_label'):
                    try:
                        self.bandwidth_loading_label = tb.Label(
                            self.bandwidth_loading_spinner.master,
                            text="Loading...",
                            font=("Segoe UI", 9, "italic"),
                            bootstyle="secondary"
                        )
                        self.bandwidth_loading_label.pack(side="left", padx=(8,0))
                    except Exception:
                        pass
                else:
                    if not self.bandwidth_loading_label.winfo_ismapped():
                        self.bandwidth_loading_label.pack(side="left", padx=(8,0))

                self.bandwidth_loading_spinner.pack(side="left", padx=(15,0))
                self.bandwidth_loading_spinner.start(12)
                self._bandwidth_loading = True
            except Exception:
                pass

    def _hide_bandwidth_loading(self):
        if not getattr(self, '_bandwidth_loading', False):
            return
        # Enforce minimum display duration
        elapsed_ms = 0
        if self._bandwidth_loading_started is not None:
            elapsed_ms = ( _perf_time.perf_counter() - self._bandwidth_loading_started ) * 1000
        remaining = self._loader_min_ms - elapsed_ms
        if remaining > 0:
            # schedule hide later if too soon
            if self._bandwidth_hide_after_job:
                try: self.root.after_cancel(self._bandwidth_hide_after_job)
                except Exception: pass
            self._bandwidth_hide_after_job = self.root.after(int(remaining), self._hide_bandwidth_loading)
            return
        if hasattr(self, 'bandwidth_loading_spinner'):
            try:
                self.bandwidth_loading_spinner.stop()
                self.bandwidth_loading_spinner.pack_forget()
                if hasattr(self, 'bandwidth_loading_label') and self.bandwidth_loading_label.winfo_exists():
                    self.bandwidth_loading_label.pack_forget()
            except Exception:
                pass
        if hasattr(self, '_bandwidth_disabled_widgets'):
            for w in self._bandwidth_disabled_widgets:
                try: w.config(state='normal')
                except Exception: pass
            self._bandwidth_disabled_widgets.clear()
        self._bandwidth_loading = False

    def _show_reports_loading(self):
        if getattr(self, '_reports_loading', False):
            return
        if hasattr(self, 'reports_loading_spinner'):
            try:
                self._reports_loading_started = _perf_time.perf_counter()
                # Reset cancellation flag
                self._report_cancel_requested = False
                # If a previous thread is still alive, don't start another (user must cancel first)
                if getattr(self, '_report_generation_thread', None) and self._report_generation_thread.is_alive():
                    return
                # Create a small container right after the Generate Report button (only once)
                if hasattr(self, 'generate_report_btn') and not hasattr(self, 'reports_spinner_container'):
                    parent = self.generate_report_btn.master
                    self.reports_spinner_container = tb.Frame(parent)
                    # Insert before the next sibling (open tickets) if it exists
                    try:
                        if hasattr(self, 'open_tickets_btn'):
                            self.reports_spinner_container.pack(side="left", padx=(6,4), before=self.open_tickets_btn)
                        else:
                            self.reports_spinner_container.pack(side="left", padx=(6,4))
                    except Exception:
                        self.reports_spinner_container.pack(side="left", padx=(6,4))

                # Disable report action buttons except Open Tickets and spinner container
                try:
                    if not hasattr(self, '_reports_disabled_widgets'):
                        self._reports_disabled_widgets = []
                    btn_parent = self.reports_loading_spinner.master
                    for child in btn_parent.winfo_children():
                        # Skip container, spinner, label, and open tickets button
                        if child in (
                            getattr(self, 'reports_spinner_container', None),
                            self.reports_loading_spinner,
                            getattr(self, 'reports_loading_label', None),
                            getattr(self, 'open_tickets_btn', None)
                        ):
                            continue
                        if child.winfo_class() in ("TButton", "Button") and child['state'] != 'disabled':
                            self._reports_disabled_widgets.append(child)
                            child.config(state='disabled')
                except Exception:
                    pass

                # Re-parent spinner & label into container if we have it
                container = getattr(self, 'reports_spinner_container', None)
                target_parent = container if container else self.reports_loading_spinner.master

                # Loading label
                if not hasattr(self, 'reports_loading_label'):
                    try:
                        self.reports_loading_label = tb.Label(
                            target_parent,
                            text="Preparing...",
                            font=("Segoe UI", 9, "italic"),
                            bootstyle="secondary"
                        )
                        # Pack order: spinner then label for compact look
                    except Exception:
                        pass

                # Ensure spinner is packed
                try:
                    self.reports_loading_spinner.pack_forget()
                except Exception:
                    pass
                try:
                    self.reports_loading_spinner.configure(length=110)
                except Exception:
                    pass
                try:
                    self.reports_loading_spinner.pack(in_=target_parent, side="left")
                except Exception:
                    pass

                # Pack label (after spinner) if not visible
                if hasattr(self, 'reports_loading_label'):
                    if not self.reports_loading_label.winfo_ismapped():
                        try:
                            self.reports_loading_label.pack(in_=target_parent, side="left", padx=(6,4))
                        except Exception:
                            pass

                # Cancel button (show only during generation)
                if not hasattr(self, 'cancel_report_btn'):
                    try:
                        self.cancel_report_btn = tb.Button(target_parent, text="Cancel", bootstyle="danger-outline", command=self._cancel_report_generation)
                    except Exception:
                        self.cancel_report_btn = None
                if self.cancel_report_btn and not self.cancel_report_btn.winfo_ismapped():
                    try:
                        self.cancel_report_btn.pack(in_=target_parent, side="left", padx=(6,0))
                    except Exception:
                        pass

                self.reports_loading_spinner.start(12)
                self._reports_loading = True
            except Exception:
                pass

    def _hide_reports_loading(self):
        if not getattr(self, '_reports_loading', False):
            return
        elapsed_ms = 0
        if self._reports_loading_started is not None:
            elapsed_ms = ( _perf_time.perf_counter() - self._reports_loading_started ) * 1000
        remaining = self._loader_min_ms - elapsed_ms
        if remaining > 0:
            if getattr(self, '_reports_hide_after_job', None):
                try: self.root.after_cancel(self._reports_hide_after_job)
                except Exception: pass
            self._reports_hide_after_job = self.root.after(int(remaining), self._hide_reports_loading)
            return
        if hasattr(self, 'reports_loading_spinner'):
            try:
                self.reports_loading_spinner.stop()
                self.reports_loading_spinner.pack_forget()
                if hasattr(self, 'reports_loading_label') and self.reports_loading_label.winfo_exists():
                    self.reports_loading_label.pack_forget()
            except Exception:
                pass
        if hasattr(self, '_reports_disabled_widgets'):
            for w in self._reports_disabled_widgets:
                try: w.config(state='normal')
                except Exception: pass
            self._reports_disabled_widgets.clear()
        # Hide cancel button
        if hasattr(self, 'cancel_report_btn') and self.cancel_report_btn:
            try: self.cancel_report_btn.pack_forget()
            except Exception: pass
        # Reset label if exists
        if hasattr(self, 'reports_loading_label') and self.reports_loading_label and self.reports_loading_label.winfo_exists():
            try: self.reports_loading_label.config(text="")
            except Exception: pass
        self._reports_loading = False
        self._report_generation_thread = None
        self._report_cancel_requested = False

    def _update_reports_phase(self, text):
        """Update the phase/status text for report generation safely from any thread."""
        try:
            if hasattr(self, 'reports_loading_label') and self.reports_loading_label.winfo_exists():
                self.reports_loading_label.config(text=text)
                self.reports_loading_label.update_idletasks()
        except Exception:
            pass

    def _cancel_report_generation(self):
        if getattr(self, '_reports_loading', False):
            self._report_cancel_requested = True
            self._update_reports_phase("Cancelling...")

    def _fetch_router_list(self):
        """Return router list from DB."""
        return get_routers()
    
    def _fetch_unifi_devices(self):
        """Fetch UniFi devices from the UniFi API server and save to database.
        Uses aggressive timeout and error handling to prevent app slowdown."""
        try:
            import requests
            from requests.exceptions import ConnectionError, Timeout, RequestException
            from router_utils import upsert_unifi_router
            from db import insert_bandwidth_log, get_connection
            
            # Use short timeout to prevent app slowdown (1 second connection, 2 second read)
            response = requests.get(
                f"{self.unifi_api_url}/api/unifi/devices", 
                timeout=(1, 2)  # (connect timeout, read timeout)
            )
            
            if response.status_code == 200:
                devices = response.json()
                safe_print(f"📡 Found {len(devices)} UniFi device(s) from API")
                
                # Get existing MAC addresses from database to detect new devices
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT mac_address FROM routers WHERE brand = 'UniFi'")
                    existing_macs = set(row[0] for row in cursor.fetchall())
                    cursor.close()
                    conn.close()
                except Exception as db_error:
                    safe_print(f"⚠️ Database error while checking existing UniFi devices: {str(db_error)}")
                    existing_macs = set()
                
                # Transform UniFi devices to match router structure
                transformed = []
                new_devices_count = 0
                
                for device in devices:
                    try:
                        name = device.get('name', 'Unknown AP')
                        ip = device.get('ip', 'N/A')
                        mac = device.get('mac', 'N/A')
                        brand = 'UniFi'
                        location = device.get('model', 'Access Point')
                        
                        # Check if this is a new device
                        is_new_device = mac not in existing_macs
                        
                        # Save/update UniFi device in database
                        # This will add new devices or update existing ones
                        router_id = upsert_unifi_router(name, ip, mac, brand, location, image_path=None)
                        
                        if is_new_device and router_id:
                            new_devices_count += 1
                            safe_print(f"✨ New UniFi device discovered: {name} (MAC: {mac}, IP: {ip})")
                        
                        # Persist current throughput snapshot to bandwidth_logs
                        # UniFi API throughput units may vary (bps, Kbps, or Mbps). Normalize to Mbps.
                        try:
                            def _to_mbps(val):
                                try:
                                    v = float(val or 0)
                                except Exception:
                                    return 0.0
                                # Heuristics:
                                # - If value > 1,000,000 it's likely in bps -> convert to Mbps
                                # - If 1,000 < value <= 1,000,000 it's likely in Kbps -> convert to Mbps
                                # - Else assume already in Mbps
                                if v > 1_000_000:
                                    return v / 1_000_000.0
                                if v > 1_000:
                                    return v / 1_000.0
                                return v

                            raw_down = device.get('xput_down')
                            raw_up = device.get('xput_up')
                            down_mbps = _to_mbps(raw_down)
                            up_mbps = _to_mbps(raw_up)

                            if router_id and (raw_down is not None or raw_up is not None):
                                # latency is not provided by this endpoint; leave NULL
                                insert_bandwidth_log(router_id, down_mbps, up_mbps, None)
                        except Exception:
                            pass
                        
                        transformed.append({
                            'id': router_id if router_id else f"unifi_{mac}",
                            'name': name,
                            'ip_address': ip,
                            'mac_address': mac,
                            'brand': brand,
                            'location': location,
                            'is_unifi': True,
                            # Expose normalized Mbps in UI payload for consistency
                            'download_speed': down_mbps if 'down_mbps' in locals() else device.get('xput_down', 0),
                            'upload_speed': up_mbps if 'up_mbps' in locals() else device.get('xput_up', 0),
                            'last_seen': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'image_path': None
                        })
                    except Exception as device_error:
                        safe_print(f"⚠️ Error processing UniFi device {device.get('name', 'Unknown')}: {str(device_error)}")
                        continue
                
                if new_devices_count > 0:
                    safe_print(f"🎉 Added {new_devices_count} new UniFi device(s) to the database and routers tab")
                
                return transformed
            else:
                # API returned non-200 status
                if not hasattr(self, '_unifi_api_error_logged'):
                    safe_print(f"⚠️ UniFi API returned status code: {response.status_code}")
                    self._unifi_api_error_logged = True
                return []
                
        except ConnectionError:
            # Connection refused or network unreachable - log once to avoid spam
            if not hasattr(self, '_unifi_connection_error_logged'):
                safe_print("⚠️ UniFi API server is not reachable (connection refused)")
                self._unifi_connection_error_logged = True
            return []
            
        except Timeout:
            # Request timed out - log once to avoid spam
            if not hasattr(self, '_unifi_timeout_logged'):
                safe_print("⚠️ UniFi API request timed out (server may be slow or down)")
                self._unifi_timeout_logged = True
            return []
            
        except RequestException as e:
            # Other requests-related errors
            if not hasattr(self, '_unifi_request_error_logged'):
                safe_print(f"⚠️ UniFi API request error: {str(e)}")
                self._unifi_request_error_logged = True
            return []
            
        except Exception as e:
            # Catch-all for any other unexpected errors
            if not hasattr(self, '_unifi_general_error_logged'):
                safe_print(f"⚠️ Unexpected error fetching UniFi devices: {str(e)}")
                self._unifi_general_error_logged = True
            return []
    
    def _start_unifi_auto_refresh(self):
        """Start auto-refresh for UniFi devices."""
        if not self.app_running:
            return
        
        # Fetch UniFi devices
        self.unifi_devices = self._fetch_unifi_devices()
        
        # Schedule next refresh (every 10 seconds)
        self.unifi_refresh_job = self.root.after(10000, self._start_unifi_auto_refresh)
    
    def _stop_unifi_auto_refresh(self):
        """Stop auto-refresh for UniFi devices."""
        if hasattr(self, 'unifi_refresh_job') and self.unifi_refresh_job:
            self.root.after_cancel(self.unifi_refresh_job)
            self.unifi_refresh_job = None
    
    def toggle_routers_auto_refresh(self):
        """Toggle auto-refresh for routers tab"""
        if self.routers_auto_refresh_var.get():
            self.start_routers_auto_refresh()
            safe_print("[SUCCESS] Routers auto-refresh enabled")
        else:
            self.stop_routers_auto_refresh()
            safe_print("[INFO] Routers auto-refresh paused")
    
    def start_routers_auto_refresh(self):
        """Start auto-refresh for routers tab with smart updates"""
        if not self.app_running:
            return
        
        # Cancel any existing refresh job
        if self.routers_refresh_job:
            self.root.after_cancel(self.routers_refresh_job)
        
        # Schedule the refresh
        self.routers_refresh_job = self.root.after(self.routers_refresh_interval, self._auto_refresh_routers)
    
    def stop_routers_auto_refresh(self):
        """Stop auto-refresh for routers tab"""
        if self.routers_refresh_job:
            self.root.after_cancel(self.routers_refresh_job)
            self.routers_refresh_job = None
    
    def _auto_refresh_routers(self):
        """Auto-refresh routers tab - called by timer"""
        # Check if app is running and window still exists
        if not self.app_running or not self.routers_auto_refresh_var.get():
            return
        
        try:
            if not self.root.winfo_exists():
                return
        except Exception:
            return
        
        # Prevent overlapping refreshes
        if self.is_refreshing_routers:
            # Reschedule for later
            self.routers_refresh_job = self.root.after(self.routers_refresh_interval, self._auto_refresh_routers)
            return
        
        # Perform smart refresh in background
        def background_check():
            try:
                # Fetch UniFi devices to check for new APs
                unifi_devices = self._fetch_unifi_devices()
                
                # Get current router list from DB
                db_routers = get_routers()
                
                # Build a lightweight snapshot hash of routers and UniFi presence
                def compute_snapshot(routers, devices):
                    try:
                        import hashlib
                        # Core router identity + placement fields only
                        r_tuples = [(
                            r.get('id'),
                            r.get('name'),
                            r.get('ip_address'),
                            r.get('brand'),
                            r.get('mac_address'),
                            r.get('location'),
                        ) for r in routers or []]
                        r_tuples.sort(key=lambda t: t[0])
                        # UniFi device MAC set captures add/remove without including transient speeds
                        u_macs = sorted([d.get('mac_address') for d in (devices or []) if d.get('mac_address')])
                        payload = repr((r_tuples, u_macs)).encode('utf-8')
                        return hashlib.md5(payload).hexdigest()
                    except Exception:
                        # Fallback: length-based signature
                        return f"len:{len(routers or [])}|u:{len(devices or [])}"

                new_hash = compute_snapshot(db_routers, unifi_devices)

                def only_update_timestamp():
                    from datetime import datetime
                    ts = datetime.now().strftime("%H:%M:%S")
                    self.routers_last_update_label.config(text=f"Last checked: {ts}")

                # Schedule UI update on main thread if changes detected
                if self._routers_snapshot_hash != new_hash or len(db_routers) != len(self.router_widgets):
                    def do_refresh():
                        self._routers_snapshot_hash = new_hash
                        self._perform_routers_refresh("")
                    self.root.after(0, do_refresh)
                else:
                    self.root.after(0, only_update_timestamp)
                
            except Exception as e:
                print(f"⚠️ Error in auto-refresh check: {str(e)}")
            finally:
                # Schedule next refresh
                if self.app_running and self.routers_auto_refresh_var.get():
                    self.routers_refresh_job = self.root.after(self.routers_refresh_interval, self._auto_refresh_routers)
        
        # Run check in background thread
        threading.Thread(target=background_check, daemon=True).start()
    
    def _perform_routers_refresh(self, reason=""):
        """Perform actual UI refresh on main thread"""
        if self.is_refreshing_routers:
            return
        
        self.is_refreshing_routers = True
        try:
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            # Update UI
            self.reload_routers(force_reload=False)
            
            # Update last update label
            update_text = f"Last updated: {timestamp}"
            if reason:
                update_text += f" ({reason})"
            self.routers_last_update_label.config(text=update_text)
            
            safe_emoji_print(f"[REFRESH] Routers refreshed at {timestamp}" + (f" - {reason}" if reason else ""))
        except Exception as e:
            safe_emoji_print(f"[WARNING] Error refreshing routers UI: {str(e)}")
        finally:
            self.is_refreshing_routers = False
    
    def manual_refresh_routers(self):
        """Manual refresh triggered by button click"""
        if self.is_refreshing_routers:
            safe_emoji_print("[INFO] Refresh already in progress...")
            return
        
        # Temporarily disable button to prevent spam
        self.refresh_routers_btn.config(state="disabled", text="[REFRESHING]")
        
        def do_refresh():
            try:
                self._perform_routers_refresh("Manual refresh")
            finally:
                # Re-enable button after refresh
                self.root.after(0, lambda: self.refresh_routers_btn.config(state="normal", text="🔄 Refresh"))
        
        # Run in background thread
        threading.Thread(target=do_refresh, daemon=True).start()
        


    def _center_window(self, win, w, h):
        """Center `win` (a Toplevel) to be size w×h over self.root."""
        self.root.update_idletasks()
        rx, ry = self.root.winfo_x(), self.root.winfo_y()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        x = rx + (rw - w) // 2
        y = ry + (rh - h) // 2
        win.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        # —— THEME STYLES ——————————————————————————————
        style = self.root.style
        style.colors.set('primary', '#d32f2f')
        style.colors.set('danger', '#b71c1c')

        # Sidebar frame style
        style.configure('Sidebar.TFrame', background='white', borderwidth=0)

        # Sidebar buttons
        style.configure('Sidebar.TButton',
                        background='white',
                        foreground='black',
                        font=('Segoe UI', 11, 'bold'),
                        relief='flat',
                        focusthickness=0)
        style.map('Sidebar.TButton', background=[('active', '#f8f9fa')])

        # Active sidebar button
        style.configure('ActiveSidebar.TButton',
                        background='#d32f2f',
                        foreground='white',
                        font=('Segoe UI', 11, 'bold'),
                        relief='flat')
        style.map('ActiveSidebar.TButton', background=[('active', '#b71c1c')])

        # Dashboard frame style
        style.configure('Dashboard.TFrame', background='white')
        
        # Section header label style
        style.configure('SectionHeader.TLabel',
                        background="#830000",
                        foreground='white',
                        font=('Segoe UI', 9, 'bold'),
                        padding=(10, 5))

        # —— WINDOW SETUP ——————————————————————————————
        r = self.root
        r.title("WINYFI Monitoring Dashboard")
        W, H = 1000, 600
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        x, y = (sw - W) // 2, 50
        r.geometry(f"{W}x{H}+{x}+{y}")

        # === Sidebar and content layout ===
        # Create sidebar
        self.sidebar = tb.Frame(r, style='Sidebar.TFrame', width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        
        # Add black border line on the right side of sidebar only
        sidebar_border = tk.Frame(r, width=1, bg='#000000', bd=0, highlightthickness=3)
        sidebar_border.pack(side="left", fill="y")

        self.content_frame = tb.Frame(r)  # replaces Notebook
        self.content_frame.pack(side="left", fill="both", expand=True)

        # === Frames (pages) ===
        self.dashboard_frame = tb.Frame(self.content_frame)
        self.routers_frame = tb.Frame(self.content_frame)
        self.reports_frame = tb.Frame(self.content_frame)
        self.settings_frame = tb.Frame(self.content_frame)
        self.bandwidth_frame = tb.Frame(self.content_frame)

        # Store them for page switching
        self.pages = {
            "Dashboard": self.dashboard_frame,
            "Routers": self.routers_frame,
            "Reports": self.reports_frame,
            "Bandwidth": self.bandwidth_frame,
            "Settings": self.settings_frame,
        }

        # Function to show a page
        def show_page(name):
            # Hide all frames
            for f in self.pages.values():
                f.pack_forget()
            # Show selected frame
            self.pages[name].pack(fill="both", expand=True)
            # Update sidebar button styles
            for tname, btn in self.sidebar_buttons.items():
                btn_style = 'ActiveSidebar.TButton' if tname == name else 'Sidebar.TButton'
                btn.config(style=btn_style)

        # === Sidebar Buttons ===
        self.sidebar_buttons = {}

        def add_section_header(text):
            """Add a red section header"""
            header = tb.Label(self.sidebar, 
                            text=text.upper(),
                            style='SectionHeader.TLabel')
            header.pack(fill='x', pady=(10, 0))

        def add_sidebar_button(text, icon):
            btn = tb.Button(self.sidebar,
                            text=f"{icon} {text}",
                            style='Sidebar.TButton',
                            width=22,
                            command=lambda: show_page(text))
            btn.pack(pady=5)
            self.sidebar_buttons[text] = btn

        # Logo
        logo_path = get_resource_path(os.path.join("assets", "images", "logo1.png"))
        if os.path.exists(logo_path):
            img = Image.open(logo_path)
            img = img.resize((85, 50), Image.Resampling.LANCZOS)
            self.sidebar_logo = ImageTk.PhotoImage(img)
            tb.Label(self.sidebar, image=self.sidebar_logo,
                    background='white', borderwidth=0).pack(pady=(15, 10))
        else:
            tb.Label(self.sidebar, text="WINYFI",
                    font=("Segoe UI", 16, "bold"),
                    foreground='#d32f2f',
                    background='white').pack(pady=15)

        # Overview section
        add_section_header("Overview")
        add_sidebar_button("Dashboard", "🏠")
        add_sidebar_button("Routers", "�")
        add_sidebar_button("Bandwidth", "📶")
        
        # Reports & Analysis section
        add_section_header("Reports & Analysis")
        add_sidebar_button("Reports", "📄")
        
        # Export button
        self.export_btn = tb.Button(
            self.sidebar,
            text="📁 Export To Csv",
            style='Sidebar.TButton',
            width=22,
            command=self.open_export_menu
        )
        self.export_btn.pack(pady=5)
        
        # Notifications section
        add_section_header("Notifications")

        # Notification bell button
        self.notification_btn = tb.Button(
            self.sidebar,
            text="🔔 Notifications",
            style='Sidebar.TButton',
            width=22,
            command=self.show_notifications_panel
        )
        self.notification_btn.pack(pady=5)
        
        # Notification count badge
        self.notification_badge = tb.Label(
            self.sidebar,
            text="0",
            font=("Segoe UI", 8, "bold"),
            foreground="white",
            background="#dc3545",
            width=2
        )
        self.notification_badge.place(in_=self.notification_btn, x=180, y=5)

        # Default tab
        show_page("Dashboard")

        self.build_bandwidth_tab()
        self.build_reports_tab()

        # Account & Settings section
        add_section_header("Account & Settings")

        # Settings dropdown
        settings_btn = tb.Button(self.sidebar,
                                text="⚙️ Settings ▼",
                                style='Sidebar.TButton',
                                width=22,
                                command=self.toggle_settings_dropdown)
        settings_btn.pack(pady=5)
        self.sidebar_buttons["Settings"] = settings_btn

        self.settings_dropdown = tb.Frame(self.sidebar, style='Sidebar.TFrame')
        self.dropdown_target_height = 260  # Increased height (+10px) for Service Manager button
        
        # Dropdown buttons with proper alignment and styling
        profile_btn = tb.Button(self.settings_dropdown, 
                        text="  👤 User Profile",
                        style='Sidebar.TButton',
                        width=22,
                        command=self.show_user_profile)
        um_btn = tb.Button(self.settings_dropdown, 
                        text="  👥 User Management",
                        style='Sidebar.TButton',
                        width=22,
                        command=self.open_user_mgmt)
        service_mgr_btn = tb.Button(self.settings_dropdown, 
                        text="  ⚙️ Service Manager",
                        style='Sidebar.TButton',
                        width=22,
                        command=self.show_service_manager)
        notif_btn = tb.Button(self.settings_dropdown, 
                        text="  🔔 Notification Settings",
                        style='Sidebar.TButton',
                        width=22,
                        command=self.show_notification_settings)
        activity_log_btn = tb.Button(self.settings_dropdown, 
                        text="  📋 Activity Log",
                        style='Sidebar.TButton',
                        width=22,
                        command=self.show_activity_log)
        sep = ttk.Separator(self.settings_dropdown, orient='horizontal')
        lo_btn = tb.Button(self.settings_dropdown, 
                        text="  ⏏️ Log Out",
                        style='Sidebar.TButton',
                        width=22,
                        command=self.logout)
        
        profile_btn.pack(fill='x', pady=2, padx=0)
        um_btn.pack(fill='x', pady=2, padx=0)
        service_mgr_btn.pack(fill='x', pady=2, padx=0)
        notif_btn.pack(fill='x', pady=2, padx=0)
        activity_log_btn.pack(fill='x', pady=2, padx=0)
        sep.pack(fill='x', pady=2)
        lo_btn.pack(fill='x', pady=2, padx=0)
        
        self.settings_dropdown.pack_propagate(False)
        self.settings_dropdown.config(height=0)

        # === Routers Page Content ===
        # Add horizontal separator line at the top
        router_top_separator = tk.Frame(self.routers_frame, height=1, bg='#000000')
        router_top_separator.pack(fill="x", pady=0)
        
        router_header_frame = tb.Frame(self.routers_frame)
        router_header_frame.pack(fill="x", padx=10, pady=(10, 0))

        # Left side - Title and auto-refresh toggle
        left_header = tb.Frame(router_header_frame)
        left_header.pack(side="left", fill="x", expand=True)
        
        tb.Label(left_header, text="All Routers",
                font=("Segoe UI", 14, "bold")).pack(side="left")
        
        # Auto-refresh toggle for routers tab
        self.routers_auto_refresh_var = tb.BooleanVar(value=True)
        self.routers_auto_refresh_check = tb.Checkbutton(
            left_header,
            text="Auto-refresh",
            variable=self.routers_auto_refresh_var,
            bootstyle="success-round-toggle",
            command=self.toggle_routers_auto_refresh
        )
        self.routers_auto_refresh_check.pack(side="left", padx=(15, 0))
        
        # Last update label
        self.routers_last_update_label = tb.Label(
            left_header,
            text="",
            font=("Segoe UI", 9, "italic"),
            bootstyle="secondary"
        )
        self.routers_last_update_label.pack(side="left", padx=(10, 0))

        # Right side - Action buttons
        tb.Button(router_header_frame, text="➕ Add Router",
                bootstyle="success", command=self.open_router_popup).pack(side="right")

        tb.Button(
            router_header_frame,
            text="👥 See Network Clients",
            bootstyle="info",
            command=self.show_clients
        ).pack(side="right", padx=5)

        tb.Button(
            router_header_frame,
            text="🔄 Loop Test",
            bootstyle="warning",
            command=self.open_loop_test_modal
        ).pack(side="right", padx=5)
        tb.Button(
            router_header_frame,
            text="🗺️ Topology",
            bootstyle="secondary",
            command=self.open_topology_window
        ).pack(side="right", padx=5)
        
        # Manual refresh button
        self.refresh_routers_btn = tb.Button(
            router_header_frame,
            text="🔄 Refresh",
            bootstyle="primary",
            command=self.manual_refresh_routers
        )
        self.refresh_routers_btn.pack(side="right", padx=5)

        filter_frame = tb.Frame(self.routers_frame)
        filter_frame.pack(pady=5, padx=10, fill="x")

        # Use a unique var name for the Routers tab to avoid collisions with
        # other pages (Clients, Reports) that also define search_var.
        self.routers_search_var = tb.StringVar()
        self.routers_search_var.trace_add("write", lambda *_: self.apply_filter())
        self.sort_var = tb.StringVar(value="default")
        self.router_type_filter = tb.StringVar(value="All")  # All, UniFi, Non-UniFi

        tb.Label(filter_frame, text="Filter:", bootstyle="info").pack(side="left", padx=(0, 5))
        tb.Entry(filter_frame, textvariable=self.routers_search_var, width=30).pack(side="left")
        
        tb.Label(filter_frame, text="Type:", bootstyle="info").pack(side="left", padx=(20, 5))
        type_combo = tb.Combobox(filter_frame, textvariable=self.router_type_filter, 
                                 values=["All", "UniFi", "Non-UniFi"], state="readonly", width=12)
        type_combo.pack(side="left")
        type_combo.bind("<<ComboboxSelected>>", lambda e: self.reload_routers())
        
        tb.Label(filter_frame, text="Sort by:", bootstyle="info").pack(side="left", padx=(20, 5))
        tb.Radiobutton(filter_frame, text="Default", variable=self.sort_var, value="default",
                    command=self.reload_routers).pack(side="left")
        tb.Radiobutton(filter_frame, text="Online First", variable=self.sort_var, value="online",
                    command=self.reload_routers).pack(side="left", padx=(5, 0))

        canvas_frame = tb.Frame(self.routers_frame)
        canvas_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Loading indicator for routers
        self.routers_loading_frame = tb.Frame(canvas_frame)
        self.routers_loading_label = tb.Label(
            self.routers_loading_frame, 
            text="⏳ Loading routers...", 
            font=("Segoe UI", 14, "bold"),
            bootstyle="info"
        )
        self.routers_loading_label.pack(pady=50)
        
        self.canvas = tb.Canvas(canvas_frame)
        scrollbar = tb.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)

        self.scrollable_frame = tb.Frame(self.canvas)
        self._canvas_window_id = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        def _sync_inner_width(event):
            self.canvas.itemconfig(self._canvas_window_id, width=event.width)
        self.canvas.bind("<Configure>", _sync_inner_width)

        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Bind mouse wheel scrolling to canvas
        def on_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            return "break"
        
        self.canvas.bind("<MouseWheel>", on_mousewheel)
        self.scrollable_frame.bind("<MouseWheel>", on_mousewheel)

        # === Modern Dashboard Page Content ===
        self._build_modern_dashboard()

    def _build_modern_dashboard(self):
        """Build a modern dashboard with enhanced charts and metrics"""
        # Configure modern styling
        self._configure_dashboard_styles()
        
        # Main container with padding
        main_container = tb.Frame(self.dashboard_frame)
        main_container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header section
        header_frame = tb.Frame(main_container)
        header_frame.pack(fill="x", pady=(0, 20))
        
        # Title and refresh controls
        title_frame = tb.Frame(header_frame)
        title_frame.pack(side="left")
        
        tb.Label(title_frame, text="📊 Network Dashboard", 
                font=("Segoe UI", 16)).pack(side="left")

        # Auto-refresh controls
        refresh_frame = tb.Frame(header_frame)
        refresh_frame.pack(side="right")
        
        self.auto_refresh_var = tb.BooleanVar(value=True)
        auto_refresh_check = tb.Checkbutton(refresh_frame, text="Auto Refresh", 
                                          variable=self.auto_refresh_var,
                                          command=self.toggle_dashboard_auto_refresh,
                                          bootstyle="success")
        auto_refresh_check.pack(side="right", padx=(0, 10))
        
        refresh_btn = tb.Button(refresh_frame, text="🔄 Refresh Now",
                              bootstyle="info", command=self.update_statistics)
        refresh_btn.pack(side="right")
        
        # Top metrics cards row
        metrics_frame = tb.Frame(main_container)
        metrics_frame.pack(fill="x", pady=(0, 20))
        
        # Configure grid weights for equal spacing between cards
        for i in range(4):
            metrics_frame.grid_columnconfigure(i, weight=1, uniform="cards")  # Equal column sizing
        metrics_frame.grid_rowconfigure(0, weight=0)  # Fixed height row
        
        # Router Status Card
        self.router_card = self._create_metric_card(
            metrics_frame, "🌐 Router Status", "primary", 0, 0
        )
        card_content = tb.Frame(self.router_card)
        card_content.pack(expand=True, fill="both")
        self.total_routers_label = tb.Label(card_content, text="0", 
                                          font=("Segoe UI", 28, "bold"),
                                          bootstyle="primary")
        self.total_routers_label.pack(pady=(10, 5))
        tb.Label(card_content, text="Total Routers", 
                font=("Segoe UI", 10), bootstyle="secondary").pack()
        
        # Online Routers Card
        self.online_card = self._create_metric_card(
            metrics_frame, "🟢 Online", "success", 0, 1
        )
        card_content = tb.Frame(self.online_card)
        card_content.pack(expand=True, fill="both")
        self.online_routers_label = tb.Label(card_content, text="0", 
                                           font=("Segoe UI", 28, "bold"),
                                           bootstyle="success")
        self.online_routers_label.pack(pady=(10, 5))
        tb.Label(card_content, text="Online Routers", 
                font=("Segoe UI", 10), bootstyle="secondary").pack()
        
        # Offline Routers Card
        self.offline_card = self._create_metric_card(
            metrics_frame, "🔴 Offline", "danger", 0, 2
        )
        card_content = tb.Frame(self.offline_card)
        card_content.pack(expand=True, fill="both")
        self.offline_routers_label = tb.Label(card_content, text="0", 
                                            font=("Segoe UI", 28, "bold"),
                                            bootstyle="danger")
        self.offline_routers_label.pack(pady=(10, 5))
        tb.Label(card_content, text="Offline Routers", 
                font=("Segoe UI", 10), bootstyle="secondary").pack()
        
        # Uptime Card
        self.uptime_card = self._create_metric_card(
            metrics_frame, "⏱️ Avg Uptime", "info", 0, 3
        )
        card_content = tb.Frame(self.uptime_card)
        card_content.pack(expand=True, fill="both")
        self.uptime_label = tb.Label(card_content, text="0%", 
                                   font=("Segoe UI", 28, "bold"),
                                   bootstyle="info")
        self.uptime_label.pack(pady=(10, 5))
        tb.Label(card_content, text="Average Uptime", 
                font=("Segoe UI", 10), bootstyle="secondary").pack()
        
        # Add status indicator
        status_frame = tb.Frame(main_container)
        status_frame.pack(fill="x", pady=(0, 20))
        
        # Network Status Indicator
        self.status_indicator = tb.LabelFrame(status_frame, text="🌐 Network Status", 
                                            bootstyle="success", padding=15)
        self.status_indicator.pack(side="left", padx=(0, 10))
        
        self.status_label = tb.Label(self.status_indicator, text="🟢 All Systems Operational", 
                                   font=("Segoe UI", 12, "bold"), bootstyle="success")
        self.status_label.pack()
        
        # Last Update Time
        self.last_update_frame = tb.LabelFrame(status_frame, text="🕐 Last Update", 
                                             bootstyle="secondary", padding=15)
        self.last_update_frame.pack(side="right", padx=(10, 0))
        
        self.last_update_label = tb.Label(self.last_update_frame, text="Never", 
                                        font=("Segoe UI", 12), bootstyle="secondary")
        self.last_update_label.pack()
        
        # Charts section
        charts_frame = tb.Frame(main_container)
        charts_frame.pack(fill="both", expand=True)
        
        # Left charts column
        left_charts = tb.Frame(charts_frame)
        left_charts.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        # Right charts column
        right_charts = tb.Frame(charts_frame)
        right_charts.pack(side="right", fill="both", expand=True, padx=(10, 0))
        
        # Router Status Pie Chart
        self._create_pie_chart(left_charts, "Router Status Distribution", 0)
        
        # Network Health Chart
        self._create_network_health_chart(left_charts, 1)
        
        # Bandwidth Usage Chart
        self._create_bandwidth_chart(right_charts, 0)
        
        # Initialize stable data storage
        self.bandwidth_data = {}
        self.health_data = {}
        
        # Initialize dashboard data
        self.update_statistics()
        
        # Start auto-refresh if enabled
        if self.auto_refresh_var.get():
            self.start_dashboard_auto_refresh()

    def _configure_dashboard_styles(self):
        """Configure modern dashboard styles - optimized for performance"""
        # Configure matplotlib style for modern look and performance
        plt.style.use('default')  # Use default style for better performance
        
        # Set optimized global font settings
        plt.rcParams.update({
            'font.size': 9,
            'font.family': 'sans-serif',
            'axes.titlesize': 11,
            'axes.labelsize': 9,
            'xtick.labelsize': 8,
            'ytick.labelsize': 8,
            'legend.fontsize': 8,
            'figure.titlesize': 12,
            'figure.dpi': 100,  # Optimize DPI for performance
            'savefig.dpi': 100,
            'axes.linewidth': 0.8,
            'grid.linewidth': 0.5,
            'lines.linewidth': 1.5
        })

    def _create_metric_card(self, parent, title, style, row, col):
        """Create a modern metric card with uniform sizing"""
        card = tb.LabelFrame(parent, text=title, bootstyle=style, padding=15)
        card.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
        
        # Configure uniform sizing - prevent content from affecting card size
        card.grid_propagate(False)  # Prevent card from resizing based on content
        card.pack_propagate(False)  # Prevent pack from resizing the card
        
        # Set fixed dimensions for uniform appearance
        card.config(width=250, height=140)  # Fixed width and height for uniformity
        
        return card
    
    def _enforce_card_sizes(self):
        """Re-enforce fixed sizes on metric cards after content updates"""
        cards = [
            ('router_card', 250, 140),
            ('online_card', 250, 140),
            ('offline_card', 250, 140),
            ('uptime_card', 250, 140)
        ]
        
        for card_name, width, height in cards:
            if hasattr(self, card_name):
                card = getattr(self, card_name)
                if card.winfo_exists():
                    card.config(width=width, height=height)
                    card.grid_propagate(False)
                    card.pack_propagate(False)

    def _create_pie_chart(self, parent, title, row):
        """Create a modern pie chart for router status"""
        chart_frame = tb.LabelFrame(parent, text=title, bootstyle="info", padding=15)
        chart_frame.grid(row=row, column=0, padx=5, pady=5, sticky="nsew")
        
        # Create pie chart with optimized size and settings
        self.pie_fig, self.pie_ax = plt.subplots(figsize=(4.5, 3.5), dpi=100)
        self.pie_fig.patch.set_facecolor('#ffffff')
        self.pie_ax.set_facecolor('#ffffff')
        
        # Optimize figure settings
        self.pie_fig.tight_layout(pad=1.0)
        
        # Remove spines for cleaner look
        self.pie_ax.spines['top'].set_visible(False)
        self.pie_ax.spines['right'].set_visible(False)
        self.pie_ax.spines['bottom'].set_visible(False)
        self.pie_ax.spines['left'].set_visible(False)
        
        self.pie_canvas = FigureCanvasTkAgg(self.pie_fig, master=chart_frame)
        self.pie_canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # Configure grid
        parent.grid_rowconfigure(row, weight=1)
        parent.grid_columnconfigure(0, weight=1)

    def _create_network_health_chart(self, parent, row):
        """Create a network health trend chart"""
        chart_frame = tb.LabelFrame(parent, text="Network Health Trend", bootstyle="success", padding=15)
        chart_frame.grid(row=row, column=0, padx=5, pady=5, sticky="nsew")
        
        # Create line chart with optimized size and settings
        self.health_fig, self.health_ax = plt.subplots(figsize=(4.5, 3.5), dpi=100)
        self.health_fig.patch.set_facecolor('#ffffff')
        self.health_ax.set_facecolor('#ffffff')
        
        # Optimize figure settings
        self.health_fig.tight_layout(pad=1.0)
        
        # Style the chart
        self.health_ax.spines['top'].set_visible(False)
        self.health_ax.spines['right'].set_visible(False)
        self.health_ax.spines['left'].set_color('#dee2e6')
        self.health_ax.spines['bottom'].set_color('#dee2e6')
        
        self.health_canvas = FigureCanvasTkAgg(self.health_fig, master=chart_frame)
        self.health_canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # Configure grid
        parent.grid_rowconfigure(row, weight=1)

    def _create_bandwidth_chart(self, parent, row):
        """Create a bandwidth usage chart"""
        chart_frame = tb.LabelFrame(parent, text="Bandwidth Usage", bootstyle="warning", padding=15)
        chart_frame.grid(row=row, column=0, padx=5, pady=5, sticky="nsew")
        
        # Create bar chart with optimized size and settings
        self.bandwidth_fig, self.bandwidth_ax = plt.subplots(figsize=(4.5, 3.5), dpi=100)
        self.bandwidth_fig.patch.set_facecolor('#ffffff')
        self.bandwidth_ax.set_facecolor('#ffffff')
        
        # Initialize with proper axes limits to prevent 0.0-1.0 default display
        self.bandwidth_ax.set_ylim(0, 100)
        self.bandwidth_ax.set_xlim(-0.5, 2.5)  # For up to 3 routers
        
        # Set initial labels and title
        self.bandwidth_ax.set_xlabel('Routers', fontsize=10)
        self.bandwidth_ax.set_ylabel('Bandwidth Usage (Mbps)', fontsize=10)
        self.bandwidth_ax.set_title('Top 3 Routers by Bandwidth', fontsize=12, fontweight='bold', pad=10)
        self.bandwidth_ax.grid(True, alpha=0.15, axis='y')
        
        # Optimize figure settings
        self.bandwidth_fig.tight_layout(pad=1.0)
        
        # Style the chart
        self.bandwidth_ax.spines['top'].set_visible(False)
        self.bandwidth_ax.spines['right'].set_visible(False)
        self.bandwidth_ax.spines['left'].set_color('#dee2e6')
        self.bandwidth_ax.spines['bottom'].set_color('#dee2e6')
        
        # Show placeholder message initially
        self.bandwidth_ax.text(0.5, 0.5, 'Loading...', ha='center', va='center', 
                             transform=self.bandwidth_ax.transAxes, fontsize=12, color='#6c757d')
        
        self.bandwidth_canvas = FigureCanvasTkAgg(self.bandwidth_fig, master=chart_frame)
        self.bandwidth_canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # Configure grid
        parent.grid_rowconfigure(row, weight=1)
        parent.grid_columnconfigure(0, weight=1)


    def toggle_dashboard_auto_refresh(self):
        """Toggle dashboard auto-refresh"""
        if self.auto_refresh_var.get():
            self.start_dashboard_auto_refresh()
        else:
            self.stop_dashboard_auto_refresh()

    def start_dashboard_auto_refresh(self):
        """Start auto-refresh for dashboard"""
        if hasattr(self, 'dashboard_refresh_job'):
            self.root.after_cancel(self.dashboard_refresh_job)
        self.dashboard_refresh_job = self.root.after(30000, self._auto_refresh_dashboard)

    def stop_dashboard_auto_refresh(self):
        """Stop auto-refresh for dashboard"""
        if hasattr(self, 'dashboard_refresh_job'):
            self.root.after_cancel(self.dashboard_refresh_job)

    def _auto_refresh_dashboard(self):
        """Auto-refresh dashboard data"""
        # Check if app is running and window still exists
        if not self.app_running:
            return
        
        try:
            if not self.root.winfo_exists():
                return
        except Exception:
            return
        
        if self.auto_refresh_var.get():
            self.update_statistics()
            self.start_dashboard_auto_refresh()

    def _on_tab_change(self, event):
        tab = event.widget.tab(event.widget.select(), "text")
        if tab == "Bandwidth":
            # Refresh the bandwidth chart when tab becomes visible
            if hasattr(self, 'bandwidth_frame') and hasattr(self, 'refresh_total_bandwidth_chart'):
                # Small delay to ensure tab is fully visible before refreshing
                self.root.after(100, self.refresh_total_bandwidth_chart)

    def refresh_report_tables(self):
        # parse dates from the Entry widgets
        try:
            start = datetime.strptime(self.report_start_date.entry.get(), "%m/%d/%Y")
            end   = datetime.strptime(self.report_end_date.entry.get(), "%m/%d/%Y")
        except Exception:
            messagebox.showerror("Date Error", "Please use MM/DD/YYYY format.")
            return

        # clear all tables
        for tree in (self.uptime_tree, self.log_tree, self.off_tree):
            for iid in tree.get_children():
                tree.delete(iid)

        routers = get_routers()

        # Uptime %
        for r in routers:
            pct = get_uptime_percentage(r['id'], start, end)
            self.uptime_tree.insert('', 'end', values=(r['name'], f"{pct:.1f}%"))

        # Status logs
        for r in routers:
            for ts, status in get_status_logs(r['id'], start, end):
                self.log_tree.insert('', 'end', values=(
                    r['name'],
                    ts.strftime("%Y-%m-%d %H:%M:%S"),
                    status
                ))

        # Top offenders
        window_secs = (end - start).total_seconds()
        offenders = []
        for r in routers:
            pct = get_uptime_percentage(r['id'], start, end)
            downtime_min = round((window_secs * (100 - pct) / 100) / 60, 2)
            offenders.append((r['name'], downtime_min))
        for name, mins in sorted(offenders, key=lambda x: x[1], reverse=True):
            self.off_tree.insert('', 'end', values=(name, f"{mins:.2f}"))

    def toggle_settings_dropdown(self):
        steps, delay = 5, 20
        opening = not getattr(self, 'dropdown_open', False)

        # if opening, pack it directly after the Settings button
        if opening:
            self.settings_dropdown.pack(fill='x', pady=0)

        def animate(step):
            frac = step / steps
            h = int(self.dropdown_target_height * (frac if opening else (1 - frac)))
            self.settings_dropdown.config(height=h)
            if step < steps:
                self.settings_dropdown.after(delay, lambda: animate(step+1))
            else:
                # flip the flag
                self.dropdown_open = opening

                # update the Settings button
                btn = self.sidebar_buttons["Settings"]
                btn.config(
                    style='Sidebar.TButton' if opening else 'Sidebar.TButton',
                    text=f"⚙️ Settings {'▲' if opening else '▼'}"
                )

                # if we just closed, remove it from layout
                if not opening:
                    self.settings_dropdown.pack_forget()

        animate(0)


    def animate_dropdown(self, closing=False):
        if closing:
            self.dropdown_current_height = max(0, self.dropdown_current_height - self.dropdown_animation_speed)
        else:
            self.dropdown_current_height = min(self.dropdown_target_height, self.dropdown_current_height + self.dropdown_animation_speed)

        self.settings_dropdown.config(height=self.dropdown_current_height)

        # Simulate fade by changing background brightness
        fade_ratio = self.dropdown_current_height / self.dropdown_target_height if self.dropdown_target_height else 0
        brightness = int(240 - (40 * (1 - fade_ratio)))  # 200 to 240 range
        fade_color = f"#{brightness:02x}{brightness:02x}{brightness:02x}"
        self.settings_dropdown.configure(style='Sidebar.TFrame')  # Must have dynamic style set
        self.style.configure("Sidebar.TFrame", background=fade_color)

        if (not closing and self.dropdown_current_height < self.dropdown_target_height) or \
        (closing and self.dropdown_current_height > 0):
            self.after(10, lambda: self.animate_dropdown(closing))



    # New method in Dashboard class:
    def generate_report(self):
        # Build full datetime range for SQL
        # Read from DateEntry entry string to avoid API differences across versions
        start_date = datetime.combine(datetime.strptime(self.report_start_date.entry.get(), "%m/%d/%Y").date(), datetime.min.time())
        end_date = datetime.combine(datetime.strptime(self.report_end_date.entry.get(), "%m/%d/%Y").date(), datetime.max.time())

        # Clear previous contents
        for w in self.report_canvas.winfo_children():
            w.destroy()

        # Fetch routers and compute uptimes
        routers = get_routers()
        names, uptimes = [], []
        for r in routers:
            pct = get_uptime_percentage(r['id'], start_date, end_date)
            names.append(r['name'])
            uptimes.append(pct)

        # Create bar chart
        fig, ax = plt.subplots(figsize=(6, 4), dpi=100)
        ax.bar(names, uptimes)
        ax.set_ylabel('Uptime (%)')
        ax.set_title(f"Uptime from {start_date.date()} to {end_date.date()}")
        ax.set_xticklabels(names, rotation=45, ha='right')
        ax.set_ylim(0, 100)

        # Embed the chart in Tkinter canvas
        canvas = FigureCanvasTkAgg(fig, master=self.report_canvas)
        canvas.get_tk_widget().pack(fill='both', expand=True)
        canvas.draw()


    def update_statistics(self):
        if not self.app_running:
            return

        # Check if modern dashboard widgets exist
        if not hasattr(self, 'total_routers_label') or not self.total_routers_label.winfo_exists():
            return

        # Fetch routers and calculate online/offline counts
        routers = self.router_list or get_routers()
        total = len(routers)
        # Prefer computed display status (from routers tab) and fall back to status_history
        online = sum(
            1
            for r in routers
            if (r.get('is_online_display') is True)
            or (self.status_history.get(r['id'], {}).get('current') is True)
        )
        offline = total - online
        
        # Calculate average uptime
        uptime_percentage = (online / total * 100) if total > 0 else 0

        # Update modern metric cards
        self.total_routers_label.config(text=str(total))
        self.online_routers_label.config(text=str(online))
        self.offline_routers_label.config(text=str(offline))
        self.uptime_label.config(text=f"{uptime_percentage:.1f}%")
        
        # Ensure cards maintain their fixed size after content update
        self._enforce_card_sizes()
        
        # Update status indicators
        self._update_status_indicators(online, offline, uptime_percentage)
        
        # Update last update time
        from datetime import datetime
        current_time = datetime.now().strftime("%H:%M:%S")
        if hasattr(self, 'last_update_label'):
            self.last_update_label.config(text=current_time)

        # Update pie chart - optimized version
        if hasattr(self, 'pie_ax') and self.pie_ax:
            self.pie_ax.clear()
            if total > 0:
                # Optimized pie chart with better performance
                wedges, texts, autotexts = self.pie_ax.pie(
                    [online, offline],
                    labels=['Online', 'Offline'],
                    colors=['#28a745', '#dc3545'],
                    autopct='%1.0f%%',  # Simplified percentage format
                    startangle=90,
                    textprops={'fontsize': 9},
                    pctdistance=0.85  # Move percentage text closer to center
                )
                
                # Optimize text rendering
                for text in texts:
                    text.set_fontsize(9)
                for autotext in autotexts:
                    autotext.set_fontsize(9)
                    autotext.set_fontweight('bold')
            else:
                self.pie_ax.text(0.5, 0.5, 'No Data', ha='center', va='center', 
                               transform=self.pie_ax.transAxes, fontsize=11)
            self.pie_ax.axis('equal')
            self.pie_canvas.draw_idle()  # Use draw_idle for better performance

        # Update network health chart
        self._update_network_health_chart()
        
        # Update bandwidth chart
        self._update_bandwidth_chart()

    def _update_status_indicators(self, online, offline, uptime_percentage):
        """Update status indicators based on network health"""
        if not hasattr(self, 'status_label') or not self.status_label.winfo_exists():
            return
            
        if offline == 0 and uptime_percentage >= 95:
            # All systems operational
            self.status_label.config(text="🟢 All Systems Operational", bootstyle="success")
            if hasattr(self, 'status_indicator'):
                self.status_indicator.config(bootstyle="success")
        elif offline <= 1 and uptime_percentage >= 90:
            # Minor issues
            self.status_label.config(text="🟡 Minor Issues Detected", bootstyle="warning")
            if hasattr(self, 'status_indicator'):
                self.status_indicator.config(bootstyle="warning")
        else:
            # Major issues
            self.status_label.config(text="🔴 Major Issues Detected", bootstyle="danger")
            if hasattr(self, 'status_indicator'):
                self.status_indicator.config(bootstyle="danger")

    def _update_network_health_chart(self):
        """Update the network health trend chart with stable data"""
        if not hasattr(self, 'health_ax') or not self.health_ax:
            return
            
        self.health_ax.clear()
        
        # Create last 8 hours of data (every 2 hours = 4 data points)
        hours = [0, 2, 4, 6]  # 0, 2, 4, 6 hours ago

        # Calculate base health score from current router status
        routers = self.router_list or get_routers()
        total = len(routers)
        online = sum(
            1
            for r in routers
            if (r.get('is_online_display') is True)
            or (self.status_history.get(r['id'], {}).get('current') is True)
        )

        if total == 0:
            # No data yet — show placeholder text and return
            self.health_ax.text(0.5, 0.5, 'No Data', ha='center', va='center',
                                transform=self.health_ax.transAxes, fontsize=11)
            self.health_ax.set_xlabel('Hours Ago', fontsize=10)
            self.health_ax.set_ylabel('Health Score (%)', fontsize=10)
            self.health_ax.set_title('Network Health (Last 8 Hours)', fontsize=12, fontweight='bold', pad=10)
            self.health_ax.set_ylim(0, 100)
            self.health_ax.set_xticks(hours)
            self.health_ax.set_xticklabels([f'{h}h' for h in hours])
            self.health_ax.grid(True, alpha=0.15)
            self.health_canvas.draw_idle()
            return

        base_score = (online / total) * 100.0

        # Recompute fresh values each update to avoid stale cached zeros
        health_scores = []
        for hour in hours:
            # Decrease slightly as we go back in time; ensure small but visible variation
            hour_factor = (6 - hour) / 6.0  # 1.0 at 0h -> 0.0 at 6h
            # Use a minimal variation floor so flat 0 doesn't persist
            variation = max(1.0, base_score * 0.03) * hour_factor
            score = max(0.0, min(100.0, base_score - variation))
            health_scores.append(score)

        # Plot with optimized styling
        self.health_ax.plot(hours, health_scores, color='#28a745', linewidth=2.5, marker='o', markersize=5)
        self.health_ax.fill_between(hours, health_scores, alpha=0.15, color='#28a745')

        # Optimized styling
        self.health_ax.set_xlabel('Hours Ago', fontsize=10)
        self.health_ax.set_ylabel('Health Score (%)', fontsize=10)
        self.health_ax.set_title('Network Health (Last 8 Hours)', fontsize=12, fontweight='bold', pad=10)
        self.health_ax.grid(True, alpha=0.15)
        self.health_ax.set_ylim(0, 100)

        # Set x-axis labels
        self.health_ax.set_xticks(hours)
        self.health_ax.set_xticklabels([f'{h}h' for h in hours])
        self.health_ax.margins(x=0.1, y=0.05)

        # Optimize drawing
        self.health_canvas.draw_idle()  # Use draw_idle for better performance

    def _update_bandwidth_chart(self):
        """Update the dashboard 'Top 3 Routers by Bandwidth' bar chart with dynamic scaling and robust fallbacks."""
        try:
            if not hasattr(self, 'bandwidth_ax') or not self.bandwidth_ax or not hasattr(self, 'bandwidth_canvas'):
                return
            ax = self.bandwidth_ax
            ax.clear()

            # Early exit if we have no routers configured
            routers = self.router_list or get_routers()
            if not routers:
                ax.set_xlabel('Routers', fontsize=10)
                ax.set_ylabel('Bandwidth Usage (Mbps)', fontsize=10)
                ax.set_title('Top 3 Routers by Bandwidth', fontsize=12, fontweight='bold', pad=10)
                ax.grid(True, alpha=0.15, axis='y')
                ax.text(0.5, 0.5, 'No Router Data', ha='center', va='center',
                        transform=ax.transAxes, fontsize=12, color='#6c757d')
                # Style spines
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
                ax.spines['left'].set_color('#dee2e6')
                ax.spines['bottom'].set_color('#dee2e6')
                self.bandwidth_fig.tight_layout(pad=1.0)
                self.bandwidth_canvas.draw_idle()
                return

            # Query database for total bandwidth over last 7 days per router (matching report calculation)
            top_routers = []
            conn = None
            cursor = None
            try:
                conn = get_connection()
                cursor = conn.cursor(dictionary=True)
                # Calculate date range: last 7 complete days (matching report default)
                from datetime import datetime, timedelta
                end_date = datetime.now().replace(hour=23, minute=59, second=59)
                start_date = (end_date - timedelta(days=7)).replace(hour=0, minute=0, second=0)
                
                # Get total bandwidth using exact same logic as report_utils.get_bandwidth_usage
                cursor.execute(
                    """
                    SELECT 
                        r.id as router_id,
                        r.name as router_name,
                        (SELECT SUM(download_mbps + upload_mbps) 
                         FROM bandwidth_logs 
                         WHERE router_id = r.id 
                           AND timestamp BETWEEN %s AND %s) as total_bandwidth_mb
                    FROM routers r
                    WHERE EXISTS (
                        SELECT 1 FROM bandwidth_logs bl 
                        WHERE bl.router_id = r.id 
                          AND bl.timestamp BETWEEN %s AND %s
                    )
                    ORDER BY total_bandwidth_mb DESC
                    LIMIT 3
                    """,
                    (start_date, end_date, start_date, end_date)
                )
                top_routers = cursor.fetchall() or []
                
                # Debug: print actual values and verify against report
                if top_routers:
                    print(f"[Dashboard] Top 3 Bandwidth - Total from {start_date.strftime('%Y-%m-%d %H:%M:%S')} to {end_date.strftime('%Y-%m-%d %H:%M:%S')}:")
                    for r in top_routers:
                        total_mb = float(r['total_bandwidth_mb'] or 0)
                        total_gb = total_mb / 1024
                        if total_gb >= 1:
                            print(f"  {r['router_name']} (ID: {r['router_id']}): {total_gb:.2f} GB ({total_mb:.2f} MB)")
                        else:
                            print(f"  {r['router_name']} (ID: {r['router_id']}): {total_mb:.2f} MB")
            finally:
                try:
                    if cursor: cursor.close()
                finally:
                    if conn: conn.close()

            # Fallback is no longer needed since main query already uses latest sample
            # But keep it for edge cases where the above query might fail
            if not top_routers:
                conn = None
                cursor = None
                try:
                    conn = get_connection()
                    cursor = conn.cursor(dictionary=True)
                    cursor.execute(
                        """
                        SELECT 
                            r.id as router_id,
                            r.name as router_name,
                            COALESCE(bl_latest.download_mbps + bl_latest.upload_mbps, 0) as total_bandwidth_mbps
                        FROM routers r
                        LEFT JOIN bandwidth_logs bl_latest
                          ON bl_latest.router_id = r.id
                         AND bl_latest.timestamp = (
                              SELECT MAX(bl2.timestamp)
                              FROM bandwidth_logs bl2
                              WHERE bl2.router_id = r.id
                         )
                        WHERE COALESCE(bl_latest.download_mbps + bl_latest.upload_mbps, 0) > 0
                        ORDER BY total_bandwidth_mbps DESC
                        LIMIT 3
                        """
                    )
                    top_routers = cursor.fetchall() or []
                finally:
                    try:
                        if cursor: cursor.close()
                    finally:
                        if conn: conn.close()

            # Ensure we have data to display
            if not top_routers:
                ax.set_xlabel('Routers', fontsize=10)
                ax.set_ylabel('Bandwidth Usage (Mbps)', fontsize=10)
                ax.set_title('Top 3 Routers by Bandwidth', fontsize=12, fontweight='bold', pad=10)
                ax.grid(True, alpha=0.15, axis='y')
                ax.text(0.5, 0.5, 'No Bandwidth Data Available', ha='center', va='center',
                        transform=ax.transAxes, fontsize=12, color='#6c757d')
                # Style spines
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
                ax.spines['left'].set_color('#dee2e6')
                ax.spines['bottom'].set_color('#dee2e6')
                self.bandwidth_fig.tight_layout(pad=1.0)
                self.bandwidth_canvas.draw_idle()
                return

            # Extract router names and values (convert to GB for better readability)
            router_names = [r['router_name'][:18] if r['router_name'] else f"Router {r['router_id']}" for r in top_routers]
            bandwidth_values = [float(r['total_bandwidth_mb'] or 0) / 1024 for r in top_routers]  # Convert MB to GB

            # Compute a nice upper y-limit so small values are still visible
            def nice_upper(v):
                if v <= 0: return 1.0
                v *= 1.1  # headroom for labels
                import math
                exp = math.floor(math.log10(v))
                base = 10 ** exp
                for m in (1, 2, 5, 10):
                    if v <= m * base:
                        return float(m * base)
                return float(10 ** (exp + 1))

            max_bandwidth = max(bandwidth_values) if bandwidth_values else 0.0
            y_max = nice_upper(max_bandwidth)

            # Create bar chart
            colors = ['#007bff', '#28a745', '#ffc107']
            bars = ax.bar(range(len(router_names)), bandwidth_values,
                          color=colors[:len(router_names)], alpha=0.9, width=0.65)

            # Add value labels on bars
            for bar, value in zip(bars, bandwidth_values):
                if value > 0:
                    # Format based on size: use GB for values >= 1, otherwise MB
                    if value >= 1:
                        label = f"{value:.2f} GB"
                    else:
                        label = f"{value * 1024:.1f} MB"
                    ax.text(bar.get_x() + bar.get_width()/2., value + (y_max * 0.02),
                            label, ha='center', va='bottom', fontsize=9, color='#495057')

            # Styling
            ax.set_xlabel('Routers', fontsize=10)
            ax.set_ylabel('Total Bandwidth (GB)', fontsize=10)
            ax.set_title('Top 3 Routers by Bandwidth (Last 7 Days)', fontsize=12, fontweight='bold', pad=10)
            ax.set_xticks(range(len(router_names)))
            ax.set_xticklabels(router_names, fontsize=9, rotation=15, ha='right')
            ax.grid(True, alpha=0.15, axis='y')
            ax.set_ylim(0, y_max)
            ax.set_xlim(-0.5, len(router_names) - 0.5)
            ax.margins(x=0.15, y=0.05)

            # Re-apply styling after clear
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_color('#dee2e6')
            ax.spines['bottom'].set_color('#dee2e6')

            # Optimize drawing
            self.bandwidth_fig.tight_layout(pad=1.0)
            self.bandwidth_canvas.draw_idle()
        except Exception as e:
            # Fallback: show error message with proper axes
            try:
                ax = self.bandwidth_ax
                ax.clear()
                ax.text(0.5, 0.5, f'Error: {str(e)[:60]}', ha='center', va='center',
                        transform=ax.transAxes, fontsize=10, color='red')
                ax.set_xlabel('Routers', fontsize=10)
                ax.set_ylabel('Bandwidth Usage (Mbps)', fontsize=10)
                ax.set_title('Top 3 Routers by Bandwidth', fontsize=12, fontweight='bold', pad=10)
                self.bandwidth_fig.tight_layout(pad=1.0)
                self.bandwidth_canvas.draw_idle()
            except Exception:
                pass


    def apply_filter(self):
        """Live, case-insensitive, substring-matching filter for router cards.
        Matches any substring in any field (name, ip_address, location, brand) for every letter typed.
        """
        if not hasattr(self, 'router_widgets'):
            return

        src_var = getattr(self, 'routers_search_var', None)
        raw_query = (src_var.get() if src_var else '').strip().lower()

        # Determine which cards should be visible
        visible_ids_online = []
        visible_ids_offline = []
        
        for rid, widgets in self.router_widgets.items():
            card = widgets.get('card')
            if not card or not card.winfo_exists():
                continue
                
            # If query is empty, show all
            if raw_query == '':
                visible = True
            else:
                # Check if query matches any field
                data = widgets.get('data', {}) or {}
                name = str(data.get('name', '') or '').lower()
                ip = str(data.get('ip_address', '') or '').lower()
                loc = str(data.get('location', '') or '').lower()
                brand = str(data.get('brand', '') or '').lower()
                visible = (
                    raw_query in name or
                    raw_query in ip or
                    raw_query in loc or
                    raw_query in brand
                )
            
            if visible:
                # Add to appropriate list based on parent
                parent = widgets.get('parent')
                if parent is getattr(self, 'online_section_frame', None):
                    visible_ids_online.append(rid)
                elif parent is getattr(self, 'offline_section_frame', None):
                    visible_ids_offline.append(rid)
        
        # Hide all cards first
        for rid, widgets in self.router_widgets.items():
            card = widgets.get('card')
            if card and card.winfo_exists():
                card.grid_remove()
        
        # Re-layout only the visible cards
        try:
            if hasattr(self, 'online_section_frame') and visible_ids_online:
                self._layout_router_cards(self.online_section_frame, visible_ids_online, self._compute_max_cols(self.online_section_frame))
            if hasattr(self, 'offline_section_frame') and visible_ids_offline and self.sort_var.get() == 'online':
                self._layout_router_cards(self.offline_section_frame, visible_ids_offline, self._compute_max_cols(self.offline_section_frame))
        except Exception:
            pass

    def export_to_csv(self, export_type="routers"):
        """Export routers, reports, or tickets to CSV."""
        import csv
        from tkinter import filedialog, messagebox
        from datetime import datetime, timedelta
        from report_utils import get_uptime_percentage, get_bandwidth_usage  # ensure you have bandwidth function
        from db import get_connection
        import ticket_utils

        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )
        if not file_path:
            return

        data = []
        fieldnames = []

        if export_type == "routers":
            from router_utils import get_routers
            routers = get_routers()
            fieldnames = ['id', 'name', 'ip_address', 'mac_address', 'brand', 'location', 'last_seen', 'image_path']
            # Filter data to only include specified fields to avoid CSV DictWriter errors
            data = []
            for router in routers:
                filtered_router = {field: router.get(field, '') for field in fieldnames}
                data.append(filtered_router)

        elif export_type == "reports":
            # Use current date if no filter applied
            try:
                start_date = datetime.strptime(self.start_date.entry.get(), "%m/%d/%Y")
            except Exception:
                start_date = datetime.now() - timedelta(days=30)  # default last 30 days

            try:
                end_date = datetime.strptime(self.end_date.entry.get(), "%m/%d/%Y")
            except Exception:
                end_date = datetime.now()

            # Get all routers
            from router_utils import get_routers
            routers = get_routers()

            fieldnames = ["router", "uptime_percent", "downtime_hours", "bandwidth_mb"]
            # Helper functions to detect if there is any data; avoids misleading 0% uptime
            def _has_status_reference(router_id):
                conn = get_connection()
                cur = conn.cursor()
                try:
                    # Any logs in range?
                    cur.execute(
                        """
                        SELECT COUNT(*) FROM router_status_log
                        WHERE router_id = %s AND timestamp BETWEEN %s AND %s
                        """,
                        (router_id, start_date, end_date)
                    )
                    in_range = cur.fetchone()[0] or 0
                    if in_range:
                        return True
                    # Any log before start to establish prior status?
                    cur.execute(
                        """
                        SELECT COUNT(*) FROM router_status_log
                        WHERE router_id = %s AND timestamp < %s
                        LIMIT 1
                        """,
                        (router_id, start_date)
                    )
                    before = cur.fetchone()[0] or 0
                    return bool(before)
                finally:
                    cur.close()
                    conn.close()

            def _has_bandwidth_data(router_id):
                conn = get_connection()
                cur = conn.cursor()
                try:
                    cur.execute(
                        """
                        SELECT COUNT(*) FROM bandwidth_logs
                        WHERE router_id = %s AND timestamp BETWEEN %s AND %s
                        """,
                        (router_id, start_date, end_date)
                    )
                    cnt = cur.fetchone()[0] or 0
                    return cnt > 0
                finally:
                    cur.close()
                    conn.close()

            for r in routers:
                rid = r["id"]
                have_status = _has_status_reference(rid)
                have_bw = _has_bandwidth_data(rid)

                if have_status:
                    uptime = get_uptime_percentage(rid, start_date, end_date)
                    downtime_hours = round((100 - uptime) / 100 * (end_date - start_date).total_seconds() / 3600, 2)
                    uptime_out = round(uptime, 2)
                    downtime_out = downtime_hours
                else:
                    uptime_out = "N/A"
                    downtime_out = "N/A"

                if have_bw:
                    bandwidth = get_bandwidth_usage(rid, start_date, end_date)
                    bandwidth_out = round(bandwidth, 2)
                else:
                    bandwidth_out = "N/A"

                data.append({
                    "router": r["name"],
                    "uptime_percent": uptime_out,
                    "downtime_hours": downtime_out,
                    "bandwidth_mb": bandwidth_out
                })

        elif export_type == "loop_detection":
            # Export recent loop detection history
            from db import get_loop_detections_history
            history = get_loop_detections_history(limit=1000) or []
            fieldnames = ["id", "detection_time", "status", "severity", "offenders", "interface", "duration_s"]
            for row in history:
                # Normalize/format values safely
                det_time = row.get("detection_time")
                if hasattr(det_time, 'strftime'):
                    det_time = det_time.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    det_time = str(det_time)
                data.append({
                    "id": row.get("id"),
                    "detection_time": det_time,
                    "status": row.get("status"),
                    "severity": row.get("severity_score"),
                    "offenders": row.get("offenders_count"),
                    "interface": row.get("network_interface"),
                    "duration_s": row.get("detection_duration"),
                })

        elif export_type == "tickets":
            tickets = ticket_utils.fetch_tickets()
            # Add SRF column alongside ID in the export
            fieldnames = ["id", "srf", "router", "issue", "status", "created_by", "created_at", "updated_at"]
            for t in tickets:
                data.append({
                    "id": t.get("id"),
                    "srf": t.get("id"),  # SRF number maps to ticket id (ict_srf_no)
                    "router": t.get("router_name") or "General",
                    "issue": t.get("issue"),
                    "status": t.get("status"),
                    "created_by": t.get("created_by"),
                    "created_at": t.get("created_at").strftime("%Y-%m-%d %H:%M:%S") if hasattr(t.get("created_at"), 'strftime') else str(t.get("created_at")),
                    "updated_at": t.get("updated_at").strftime("%Y-%m-%d %H:%M:%S") if hasattr(t.get("updated_at"), 'strftime') else str(t.get("updated_at"))
                })

        else:
            messagebox.showerror("Error", f"Unknown export type: {export_type}")
            return

        # Write to CSV
        try:
            with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for row in data:
                    writer.writerow(row)
            messagebox.showinfo("Export", f"{export_type.capitalize()} exported successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export CSV:\n{e}")

    def open_export_menu(self):
        """Open an enhanced export dialog with options and date range for reports."""
        from tkinter import Toplevel

        modal = Toplevel(self.root)
        modal.title("⬇️ Export Data")
        modal.geometry("420x260")
        modal.resizable(False, False)
        modal.grab_set()

        outer = tb.Frame(modal, padding=15)
        outer.pack(fill="both", expand=True)

        tb.Label(outer, text="Select what to export", font=("Segoe UI", 12, "bold")).pack(anchor="w")

        # Export type
        type_frame = tb.LabelFrame(outer, text="Data Type", bootstyle="secondary", padding=10)
        type_frame.pack(fill="x", pady=(8, 10))

        export_var = tb.StringVar(value="routers")
        tb.Radiobutton(type_frame, text="Routers", variable=export_var, value="routers").pack(side="left", padx=5)
        tb.Radiobutton(type_frame, text="Reports", variable=export_var, value="reports").pack(side="left", padx=5)
        tb.Radiobutton(type_frame, text="Tickets", variable=export_var, value="tickets").pack(side="left", padx=5)
        tb.Radiobutton(type_frame, text="Loop Detection", variable=export_var, value="loop_detection").pack(side="left", padx=5)

        # Reports options (date range)
        reports_frame = tb.LabelFrame(outer, text="Report Options", bootstyle="info", padding=10)
        reports_frame.pack(fill="x")

        tb.Label(reports_frame, text="Start Date:").grid(row=0, column=0, sticky="w")
        start_picker = DateEntry(reports_frame, width=12, dateformat="%m/%d/%y")
        start_picker.grid(row=0, column=1, padx=(6, 15), pady=5, sticky="w")

        tb.Label(reports_frame, text="End Date:").grid(row=0, column=2, sticky="w")
        end_picker = DateEntry(reports_frame, width=12, dateformat="%m/%d/%y")
        end_picker.grid(row=0, column=3, padx=(6, 0), pady=5, sticky="w")

        def _toggle_reports_options(*_):
            if export_var.get() == "reports":
                if not reports_frame.winfo_ismapped():
                    reports_frame.pack(fill="x")
            else:
                if reports_frame.winfo_ismapped():
                    reports_frame.pack_forget()

        export_var.trace_add("write", _toggle_reports_options)
        _toggle_reports_options()

        # Footer buttons
        btns = tb.Frame(outer)
        btns.pack(fill="x", pady=(15, 0))

        def do_export():
            etype = export_var.get()
            # Parse dates for reports and start async export with progress
            start_dt = end_dt = None
            if etype == "reports":
                from datetime import datetime
                s = start_picker.entry.get().strip()
                e = end_picker.entry.get().strip()
                parsed = False
                for fmt in ("%m/%d/%Y", "%m/%d/%y"):
                    try:
                        start_dt = datetime.strptime(s, fmt)
                        end_dt = datetime.strptime(e, fmt)
                        parsed = True
                        break
                    except Exception:
                        continue
                if not parsed:
                    from tkinter import messagebox
                    messagebox.showerror("Date Error", "Please use MM/DD/YYYY format for dates.")
                    return
            modal.destroy()
            self.start_export_async(etype, start_dt, end_dt)

        tb.Button(btns, text="Cancel", bootstyle="secondary", command=modal.destroy).pack(side="right")
        tb.Button(btns, text="Export", bootstyle="primary", command=do_export).pack(side="right", padx=(0, 8))


    def start_export_async(self, export_type, start_dt=None, end_dt=None):
        """Start export in a background thread and show a progress dialog to keep UI responsive (Admin)."""
        # Ask for target file first (on main thread)
        from tkinter import filedialog, messagebox
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )
        if not file_path:
            return

        import threading, csv
        from datetime import datetime, timedelta

        cancel_event = threading.Event()
        prog = tb.Toplevel(self.root)
        prog.title("Exporting…")
        prog.geometry("360x140")
        prog.resizable(False, False)
        prog.transient(self.root)
        prog.grab_set()
        frame = tb.Frame(prog, padding=15)
        frame.pack(fill="both", expand=True)
        lbl = tb.Label(frame, text="Preparing…", font=("Segoe UI", 11))
        lbl.pack(anchor="w")
        pbar = tb.Progressbar(frame, mode="indeterminate", bootstyle="info-striped")
        pbar.pack(fill="x", pady=12)
        pbar.start(12)
        btns = tb.Frame(frame)
        btns.pack(fill="x")
        def cancel():
            cancel_event.set()
            lbl.config(text="Cancelling… (will stop after current step)")
        tb.Button(btns, text="Cancel", bootstyle="secondary", command=cancel).pack(side="right")

        def on_done(success, msg):
            try:
                pbar.stop()
                prog.destroy()
            except Exception:
                pass
            if success:
                messagebox.showinfo("Export", msg)
            else:
                messagebox.showerror("Export", msg)

        def worker():
            try:
                rows = []
                fieldnames = []
                if export_type == "routers":
                    lbl.after(0, lambda: lbl.config(text="Fetching routers…"))
                    from router_utils import get_routers
                    routers = get_routers()
                    fieldnames = ['id', 'name', 'ip_address', 'mac_address', 'brand', 'location', 'last_seen', 'image_path']
                    # Filter data to only include specified fields to avoid CSV DictWriter errors
                    rows = []
                    for router in (routers or []):
                        filtered_router = {field: router.get(field, '') for field in fieldnames}
                        rows.append(filtered_router)

                elif export_type == "tickets":
                    lbl.after(0, lambda: lbl.config(text="Fetching tickets…"))
                    import ticket_utils
                    tickets = ticket_utils.fetch_tickets() or []
                    # Include SRF column in async export as well
                    fieldnames = ["id", "srf", "router", "issue", "status", "created_by", "created_at", "updated_at"]
                    def fmt(dt):
                        try:
                            return dt.strftime("%Y-%m-%d %H:%M:%S") if hasattr(dt, 'strftime') else str(dt)
                        except Exception:
                            return str(dt)
                    for t in tickets:
                        if cancel_event.is_set():
                            break
                        rows.append({
                            "id": t.get("id"),
                            "srf": t.get("id"),  # SRF number maps to ticket id (ict_srf_no)
                            "router": t.get("router_name") or "General",
                            "issue": t.get("issue"),
                            "status": t.get("status"),
                            "created_by": t.get("created_by"),
                            "created_at": fmt(t.get("created_at")),
                            "updated_at": fmt(t.get("updated_at")),
                        })

                elif export_type == "loop_detection":
                    # Export loop detection history in async worker
                    lbl.after(0, lambda: lbl.config(text="Fetching loop detections…"))
                    from db import get_loop_detections_history
                    hist = get_loop_detections_history(limit=1000) or []
                    fieldnames = ["id", "detection_time", "status", "severity", "offenders", "interface", "duration_s"]
                    def fmt_dt(dt):
                        try:
                            return dt.strftime("%Y-%m-%d %H:%M:%S") if hasattr(dt, 'strftime') else str(dt)
                        except Exception:
                            return str(dt)
                    for r in hist:
                        if cancel_event.is_set():
                            break
                        rows.append({
                            "id": r.get("id"),
                            "detection_time": fmt_dt(r.get("detection_time")),
                            "status": r.get("status"),
                            "severity": r.get("severity_score"),
                            "offenders": r.get("offenders_count"),
                            "interface": r.get("network_interface"),
                            "duration_s": r.get("detection_duration"),
                        })

                else:  # reports
                    from report_utils import get_uptime_percentage, get_bandwidth_usage
                    from db import get_connection
                    from router_utils import get_routers
                    sdt = start_dt or (datetime.now() - timedelta(days=30))
                    edt = end_dt or datetime.now()
                    lbl.after(0, lambda: lbl.config(text="Loading routers…"))
                    routers = get_routers() or []
                    fieldnames = ["router", "uptime_percent", "downtime_hours", "bandwidth_mb"]

                    def _has_status_reference(router_id):
                        conn = get_connection()
                        cur = conn.cursor()
                        try:
                            cur.execute(
                                """
                                SELECT COUNT(*) FROM router_status_log
                                WHERE router_id = %s AND timestamp BETWEEN %s AND %s
                                """,
                                (router_id, sdt, edt)
                            )
                            in_range = cur.fetchone()[0] or 0
                            if in_range:
                                return True
                            cur.execute(
                                """
                                SELECT COUNT(*) FROM router_status_log
                                WHERE router_id = %s AND timestamp < %s
                                LIMIT 1
                                """,
                                (router_id, sdt)
                            )
                            before = cur.fetchone()[0] or 0
                            return bool(before)
                        finally:
                            cur.close()
                            conn.close()

                    def _has_bandwidth_data(router_id):
                        conn = get_connection()
                        cur = conn.cursor()
                        try:
                            cur.execute(
                                """
                                SELECT COUNT(*) FROM bandwidth_logs
                                WHERE router_id = %s AND timestamp BETWEEN %s AND %s
                                """,
                                (router_id, sdt, edt)
                            )
                            cnt = cur.fetchone()[0] or 0
                            return cnt > 0
                        finally:
                            cur.close()
                            conn.close()

                    total_hours = (edt - sdt).total_seconds() / 3600.0
                    lbl.after(0, lambda: lbl.config(text="Computing report…"))
                    for r in routers:
                        if cancel_event.is_set():
                            break
                        rid = r.get("id")
                        name = r.get("name")
                        have_status = _has_status_reference(rid)
                        have_bw = _has_bandwidth_data(rid)
                        if have_status:
                            uptime = get_uptime_percentage(rid, sdt, edt)
                            downtime_hours = round((100 - uptime) / 100.0 * total_hours, 2)
                            uptime_out = round(uptime, 2)
                            downtime_out = downtime_hours
                        else:
                            uptime_out = "N/A"
                            downtime_out = "N/A"
                        if have_bw:
                            bandwidth = get_bandwidth_usage(rid, sdt, edt)
                            bandwidth_out = round(bandwidth, 2)
                        else:
                            bandwidth_out = "N/A"
                        rows.append({
                            "router": name,
                            "uptime_percent": uptime_out,
                            "downtime_hours": downtime_out,
                            "bandwidth_mb": bandwidth_out
                        })

                if cancel_event.is_set():
                    self.root.after(0, lambda: on_done(False, "Export cancelled."))
                    return

                # Write CSV
                lbl.after(0, lambda: lbl.config(text="Writing CSV file…"))
                try:
                    with open(file_path, "w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        for r in rows:
                            if cancel_event.is_set():
                                break
                            writer.writerow(r)
                except Exception as e:
                    self.root.after(0, lambda e=e: on_done(False, f"Failed to write file: {e}"))
                    return

                if cancel_event.is_set():
                    self.root.after(0, lambda: on_done(False, "Export cancelled."))
                else:
                    self.root.after(0, lambda: on_done(True, f"{export_type.capitalize()} exported successfully!"))

            except Exception as e:
                self.root.after(0, lambda e=e: on_done(False, f"Export failed: {e}"))

        import threading
        threading.Thread(target=worker, daemon=True).start()


    def open_router_popup(self, mode="add", router=None):
        # Check if this is a UniFi device being edited
        is_unifi = router.get('is_unifi', False) if router else False
        
        # If editing a UniFi device, use the specialized popup
        if mode == 'edit' and is_unifi:
            return self.open_unifi_edit_popup(router)
        
        popup = Toplevel(self.root)
        popup.title("Edit Router" if mode=='edit' else "Add New Router")
        popup.geometry("400x450")
        popup.transient(self.root)
        popup.grab_set()

        # Center the popup relative to root
        self.root.update_idletasks()
        rx, ry = self.root.winfo_x(), self.root.winfo_y()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        pw, ph = 400, 450
        x = rx + (rw//2) - (pw//2)
        y = ry + (rh//2) - (ph//2)
        popup.geometry(f"{pw}x{ph}+{x}+{y}")

        outer = tb.Frame(popup, padding=20)
        outer.pack(fill="both", expand=True)

        labels = ["Name","IP Address","MAC Address","Brand","Location"]
        entries = []
        image_path_var = tb.StringVar()

        for i, text in enumerate(labels):
            tb.Label(outer, text=text, anchor="e", width=15).grid(
                row=i, column=0, sticky="e", pady=5, padx=(0,10)
            )
            e = tb.Entry(outer, width=30)
            e.grid(row=i, column=1, pady=5, sticky="w")
            entries.append(e)

        # Image upload row
        tb.Label(outer, text="Router Image:", anchor="e", width=15).grid(
            row=5, column=0, sticky="e", pady=5, padx=(0,10)
        )
        img_frame = tb.Frame(outer)
        img_frame.grid(row=5, column=1, sticky="w")
        image_label = tb.Label(img_frame, text="No image selected")
        image_label.pack(side="left")
        tb.Button(
            img_frame, text="Browse", bootstyle="secondary",
            command=lambda: choose_image()
        ).pack(side="left", padx=5)

        def choose_image():
            filetypes = [("Image files","*.png *.jpg *.jpeg *.gif")]
            fname = filedialog.askopenfilename(title="Select Router Image", filetypes=filetypes)
            if not fname:
                return
            os.makedirs(IMAGE_FOLDER, exist_ok=True)
            dest = os.path.join(IMAGE_FOLDER, os.path.basename(fname))
            shutil.copy2(fname, dest)
            image_path_var.set(dest)
            image_label.config(text=os.path.basename(dest))

        # Pre-fill in edit mode
        if mode=='edit' and router:
            entries[0].insert(0, router.get('name', ''))
            entries[1].insert(0, router.get('ip_address', ''))
            entries[2].insert(0, router.get('mac_address', ''))
            entries[3].insert(0, router.get('brand', ''))
            entries[4].insert(0, router.get('location', ''))
            if router.get('image_path'):
                image_path_var.set(router['image_path'])
                image_label.config(text=os.path.basename(router['image_path']))

        def submit():
            vals = [e.get() for e in entries]
            img_path = image_path_var.get()
            if not all(vals):
                messagebox.showerror("Error","All fields are required.")
                return
            if mode=='edit':
                # Make sure router has an ID
                if not router or 'id' not in router:
                    messagebox.showerror("Error", "Router ID not found. Cannot update.")
                    return
                update_router(router['id'], *vals, img_path)
                messagebox.showinfo("Updated","Router updated.")
                # Log activity for router edit
                try:
                    from device_utils import get_device_info
                    device_info = get_device_info()
                    log_activity(
                        user_id=self.current_user.get('id'),
                        action='Edit Router',
                        target=vals[0],  # Router name
                        ip_address=device_info.get('ip_address')
                    )
                except Exception as e:
                    print(f"Error logging router edit activity: {e}")
            else:
                insert_router(*vals, img_path)
                messagebox.showinfo("Success","Router added.")
                # Log activity for router add
                try:
                    from device_utils import get_device_info
                    device_info = get_device_info()
                    log_activity(
                        user_id=self.current_user.get('id'),
                        action='Add Router',
                        target=vals[0],  # Router name
                        ip_address=device_info.get('ip_address')
                    )
                except Exception as e:
                    print(f"Error logging router add activity: {e}")
            popup.destroy()
            # Clear snapshot hash to force refresh on next update
            self._routers_snapshot_hash = None
            self.reload_routers(force_reload=True)
            
            # If editing, reopen router details with fresh data
            if mode == 'edit' and router:
                # Fetch fresh router data from DB
                from router_utils import get_routers
                updated_router = None
                for r in get_routers():
                    if r.get('id') == router['id']:
                        updated_router = r
                        break
                if updated_router:
                    self.open_router_details(updated_router)

        btn_text = "Update Router" if mode=='edit' else "Add Router"
        tb.Button(
            outer, text=btn_text, bootstyle="success",
            command=submit
        ).grid(row=6, column=0, columnspan=2, pady=15)

    def open_unifi_edit_popup(self, router):
        """Specialized popup for editing UniFi devices - only name, location, and image"""
        popup = Toplevel(self.root)
        popup.title(f"Edit UniFi Device - {router.get('name', 'Unknown')}")
        popup.geometry("400x470")
        popup.transient(self.root)
        popup.grab_set()

        # Center the popup relative to root
        self.root.update_idletasks()
        rx, ry = self.root.winfo_x(), self.root.winfo_y()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        pw, ph = 400, 470
        x = rx + (rw//2) - (pw//2)
        y = ry + (rh//2) - (ph//2)
        popup.geometry(f"{pw}x{ph}+{x}+{y}")

        outer = tb.Frame(popup, padding=20)
        outer.pack(fill="both", expand=True)

        # Info banner
        info_frame = tb.Frame(outer, bootstyle="info")
        info_frame.pack(fill="x", pady=(0, 15))
        tb.Label(info_frame, text="ℹ️ Note: IP, MAC, and Brand are managed by UniFi Controller", 
                font=("Segoe UI", 9, "italic"), bootstyle="info", wraplength=400).pack(pady=5, padx=5)

        # Create a form frame for grid layout
        form_frame = tb.Frame(outer)
        form_frame.pack(fill="both", expand=True)

        # Name field (editable)
        tb.Label(form_frame, text="Name:", anchor="e", width=15).grid(
            row=0, column=0, sticky="e", pady=10, padx=(0,10)
        )
        name_entry = tb.Entry(form_frame, width=30)
        name_entry.grid(row=0, column=1, pady=10, sticky="w")
        name_entry.insert(0, router.get('name', ''))

        # Location field (editable)
        tb.Label(form_frame, text="Location:", anchor="e", width=15).grid(
            row=1, column=0, sticky="e", pady=10, padx=(0,10)
        )
        location_entry = tb.Entry(form_frame, width=30)
        location_entry.grid(row=1, column=1, pady=10, sticky="w")
        location_entry.insert(0, router.get('location', ''))

        # Read-only fields display
        readonly_frame = tb.LabelFrame(form_frame, text="📋 UniFi Managed Info (Read-Only)", bootstyle="secondary", padding=10)
        readonly_frame.grid(row=2, column=0, columnspan=2, pady=15, sticky="ew")
        
        tb.Label(readonly_frame, text=f"IP Address: {router.get('ip_address', 'N/A')}", 
                font=("Segoe UI", 9)).pack(anchor="w", pady=2)
        tb.Label(readonly_frame, text=f"MAC Address: {router.get('mac_address', 'N/A')}", 
                font=("Segoe UI", 9)).pack(anchor="w", pady=2)
        tb.Label(readonly_frame, text=f"Brand: {router.get('brand', 'UniFi')}", 
                font=("Segoe UI", 9)).pack(anchor="w", pady=2)

        # Image upload row (editable)
        tb.Label(form_frame, text="Device Image:", anchor="e", width=15).grid(
            row=3, column=0, sticky="e", pady=10, padx=(0,10)
        )
        img_frame = tb.Frame(form_frame)
        img_frame.grid(row=3, column=1, sticky="w", pady=10)
        
        image_path_var = tb.StringVar()
        image_label = tb.Label(img_frame, text="No image selected")
        image_label.pack(side="left")
        
        tb.Button(
            img_frame, text="Browse", bootstyle="secondary",
            command=lambda: choose_image()
        ).pack(side="left", padx=5)

        # Pre-fill image if exists
        if router.get('image_path'):
            image_path_var.set(router['image_path'])
            image_label.config(text=os.path.basename(router['image_path']))

        def choose_image():
            filetypes = [("Image files","*.png *.jpg *.jpeg *.gif")]
            fname = filedialog.askopenfilename(title="Select Device Image", filetypes=filetypes)
            if not fname:
                return
            os.makedirs(IMAGE_FOLDER, exist_ok=True)
            dest = os.path.join(IMAGE_FOLDER, os.path.basename(fname))
            shutil.copy2(fname, dest)
            image_path_var.set(dest)
            image_label.config(text=os.path.basename(dest))

        def submit():
            name = name_entry.get().strip()
            location = location_entry.get().strip()
            img_path = image_path_var.get()

            if not name:
                messagebox.showerror("Error", "Name is required.")
                return

            # Find the DB record by MAC address
            from db import get_connection
            current_mac = router.get('mac_address', '')
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM routers WHERE mac_address = %s", (current_mac,))
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            if not result:
                messagebox.showerror("Error", "Device not found in database.")
                return
            db_id = result[0]

            current_ip = router.get('ip_address', '')
            current_brand = router.get('brand', 'UniFi')
            from router_utils import update_router
            update_router(db_id, name, current_ip, current_mac, current_brand, location, img_path)
            messagebox.showinfo("Updated", "UniFi device updated successfully.")
            popup.destroy()
            self.router_list = None  # Clear cached list to force DB reload
            # Clear router_widgets so cards are rebuilt
            self.router_widgets.clear()
            # Clear snapshot hash to force refresh on next update
            self._routers_snapshot_hash = None
            self.reload_routers(force_reload=True)

            # Always fetch fresh router data from DB for details (with small delay to ensure DB is updated)
            def reopen_details():
                from router_utils import get_routers
                updated_router = None
                for r in get_routers():
                    if r.get('id') == db_id:
                        updated_router = r
                        break
                if updated_router:
                    self.open_router_details(updated_router)
            # Schedule reopen after UI updates
            self.root.after(100, reopen_details)

        # Buttons
        btn_frame = tb.Frame(form_frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=15)
        
        tb.Button(
            btn_frame, text="👥 See Clients", bootstyle="info",
            command=lambda: self.show_unifi_connected_clients(router), width=15
        ).pack(side="left", padx=5)
        
        tb.Button(
            btn_frame, text="Cancel", bootstyle="secondary",
            command=popup.destroy, width=15
        ).pack(side="left", padx=5)
        
        tb.Button(
            btn_frame, text="Update Device", bootstyle="success",
            command=submit, width=15
        ).pack(side="left", padx=5)

    def delete_selected_router(self, router):
        if messagebox.askyesno("Delete", f"Delete router '{router['name']}'?"):
            router_name = router.get('name', 'Unknown')
            delete_router(router['id'])
            # Log activity for router delete
            try:
                from device_utils import get_device_info
                device_info = get_device_info()
                log_activity(
                    user_id=self.current_user.get('id'),
                    action='Delete Router',
                    target=router_name,
                    ip_address=device_info.get('ip_address')
                )
            except Exception as e:
                print(f"Error logging router delete activity: {e}")
            self.reload_routers()

    def show_connected_clients_for_router(self, router):
        """Show connected clients for a specific router/AP"""
        is_unifi = router.get('is_unifi', False) or router.get('brand', '').lower() == 'unifi'
        
        if is_unifi:
            self.show_unifi_connected_clients(router)
        else:
            # Non-UniFi devices: fetch clients from database via API
            self.show_non_unifi_connected_clients(router)

    def show_non_unifi_connected_clients(self, router):
        """Show connected clients for a non-UniFi router/AP by scanning the router's specific subnet"""
        try:
            from network_utils import scan_router_subnet, get_default_iface, ping_latency
            from db import save_network_client, create_network_clients_table
            
            router_id = router.get('id')
            router_ip = router.get('ip_address')
            
            if not router_id:
                messagebox.showerror("Error", "Router ID not found.")
                return
            
            if not router_ip:
                messagebox.showerror("Error", "Router IP address not found. Please update the router information.")
                return
            
            # Create modal window
            modal = Toplevel(self.root)
            modal.title(f"👥 Connected Clients - {router.get('name', 'Router')}")
            modal.geometry("900x600")
            modal.transient(self.root)
            modal.grab_set()
            
            # Center window
            self._center_window(modal, 900, 600)
            
            # Main container
            main_container = tb.Frame(modal, padding=20)
            main_container.pack(fill="both", expand=True)
            
            # Header
            header_frame = tb.Frame(main_container)
            header_frame.pack(fill="x", pady=(0, 15))
            
            tb.Label(header_frame, text=f"📡 {router.get('name', 'Router')}", 
                    font=("Segoe UI", 16, "bold"), bootstyle="primary").pack(side="left")
            
            # Status label for loading
            status_label = tb.Label(header_frame, 
                                   text="⏳ Scanning network...", 
                                   font=("Segoe UI", 12), bootstyle="info")
            status_label.pack(side="right")
            
            # Info banner
            info_frame = tb.LabelFrame(main_container, text="ℹ️ Router Info", bootstyle="secondary", padding=10)
            info_frame.pack(fill="x", pady=(0, 15))
            
            info_text = f"IP: {router.get('ip_address', 'N/A')} | MAC: {router.get('mac_address', 'N/A')} | Location: {router.get('location', 'N/A')}"
            tb.Label(info_frame, text=info_text, font=("Segoe UI", 9)).pack()
            
            # Content frame that will hold the clients table
            content_frame = tb.Frame(main_container)
            content_frame.pack(fill="both", expand=True)
            
            # Loading label
            loading_label = tb.Label(content_frame, text="⏳ Scanning subnet for clients...", 
                                    font=("Segoe UI", 12), bootstyle="info")
            loading_label.pack(pady=50)
            
            # Footer with buttons
            footer_frame = tb.Frame(main_container)
            footer_frame.pack(fill="x", pady=(15, 0))
            
            refresh_btn = tb.Button(footer_frame, text="🔄 Refresh", bootstyle="info",
                                   command=lambda: [modal.destroy(), self.show_non_unifi_connected_clients(router)],
                                   width=15, state="disabled")
            refresh_btn.pack(side="left")
            
            tb.Button(footer_frame, text="Close", bootstyle="secondary",
                     command=modal.destroy, width=15).pack(side="right")
            
            # Scan network for clients in background thread
            def scan_clients():
                try:
                    # Ensure tables exist
                    create_network_clients_table()
                    
                    # Get network interface
                    iface = get_default_iface()
                    if not iface:
                        self.root.after(0, lambda: update_ui_error(
                            "No active network interface found."
                        ))
                        return
                    
                    # Perform network scan using ARP on the router's specific subnet
                    print(f"🔍 Scanning subnet for router {router.get('name')} (IP: {router_ip}) on interface {iface}...")
                    scanned_clients = scan_router_subnet(
                        router_ip=router_ip,
                        netmask="255.255.255.0",  # Default /24 subnet
                        iface=iface,
                        timeout=3
                    )
                    
                    if not scanned_clients:
                        self.root.after(0, lambda: update_ui_with_clients([]))
                        return
                    
                    # Process and save scanned clients to database
                    saved_clients = []
                    for mac, info in scanned_clients.items():
                        # Get ping latency
                        ping_lat = None
                        if info.get("ip"):
                            ping_lat = ping_latency(info["ip"], timeout=1000)
                        
                        # Determine vendor (simplified)
                        vendor = info.get("vendor", "Unknown")
                        
                        # Save to database with router association
                        try:
                            save_network_client(
                                mac_address=mac,
                                ip_address=info.get("ip"),
                                hostname=info.get("hostname", "Unknown"),
                                vendor=vendor,
                                ping_latency=ping_lat,
                                device_type=None,
                                notes=None,
                                router_id=router_id,
                                router_name=router.get('name')
                            )
                            
                            saved_clients.append({
                                "mac_address": mac,
                                "ip_address": info.get("ip"),
                                "hostname": info.get("hostname", "Unknown"),
                                "vendor": vendor,
                                "ping_latency": ping_lat,
                                "is_online": True,
                                "last_seen": info.get("last_seen").isoformat() if info.get("last_seen") else None
                            })
                        except Exception as e:
                            print(f"Error saving client {mac}: {e}")
                    
                    safe_emoji_print(f"[SUCCESS] Scanned and saved {len(saved_clients)} clients for router {router.get('name')}")
                    
                    # Update UI in main thread
                    self.root.after(0, lambda: update_ui_with_clients(saved_clients))
                    
                except Exception as e:
                    self.root.after(0, lambda: update_ui_error(f"Scan error:\n{str(e)}"))
            
            def update_ui_error(error_msg):
                loading_label.config(text=f"❌ {error_msg}", bootstyle="danger")
                refresh_btn.config(state="normal")
            
            def update_ui_with_clients(clients):
                # Clear loading message
                loading_label.destroy()
                
                # Update status label
                status_label.config(
                    text=f"{len(clients)} Client{'s' if len(clients) != 1 else ''} Saved to DB",
                    bootstyle="success"
                )
                
                # Enable refresh button
                refresh_btn.config(state="normal")
                
                if not clients:
                    # No clients found
                    no_clients_label = tb.Label(content_frame, 
                                               text="No clients found for this router in the database", 
                                               font=("Segoe UI", 12), bootstyle="secondary")
                    no_clients_label.pack(pady=50)
                    return
                
                # Create treeview for clients
                tree_frame = tb.Frame(content_frame)
                tree_frame.pack(fill="both", expand=True)
                
                # Define columns
                columns = ("Status", "IP Address", "MAC Address", "Hostname", "Vendor", "Last Seen")
                
                # Create Treeview
                tree = tb.Treeview(tree_frame, columns=columns, show="headings", 
                                  height=15, bootstyle="info")
                
                # Configure columns
                column_widths = [80, 120, 150, 180, 150, 150]
                for col, width in zip(columns, column_widths):
                    tree.heading(col, text=col)
                    tree.column(col, width=width, anchor="center")
                
                # Scrollbars
                v_scrollbar = tb.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
                h_scrollbar = tb.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
                tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
                
                # Grid layout for tree and scrollbars
                tree.grid(row=0, column=0, sticky="nsew")
                v_scrollbar.grid(row=0, column=1, sticky="ns")
                h_scrollbar.grid(row=1, column=0, sticky="ew")
                
                tree_frame.grid_rowconfigure(0, weight=1)
                tree_frame.grid_columnconfigure(0, weight=1)
                
                # Bind mouse wheel scrolling
                def on_mousewheel_vertical(event):
                    tree.yview_scroll(int(-1*(event.delta/120)), "units")
                    return "break"
                
                def on_mousewheel_horizontal(event):
                    tree.xview_scroll(int(-1*(event.delta/120)), "units")
                    return "break"
                
                tree.bind("<MouseWheel>", on_mousewheel_vertical)
                tree.bind("<Shift-MouseWheel>", on_mousewheel_horizontal)
                
                # Insert client data
                for client in clients:
                    is_online = client.get('is_online', False)
                    status = "🟢 Online" if is_online else "🔴 Offline"
                    
                    ip_address = client.get('ip_address', 'Unknown')
                    mac_address = client.get('mac_address', 'Unknown')
                    hostname = client.get('hostname', 'Unknown')
                    vendor = client.get('vendor', 'Unknown')
                    
                    # Format last_seen
                    last_seen = client.get('last_seen', 'N/A')
                    if last_seen and last_seen != 'N/A':
                        try:
                            from datetime import datetime
                            if isinstance(last_seen, str):
                                # Try to parse and reformat
                                dt = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
                                last_seen = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except:
                            pass
                    
                    tree.insert("", "end", values=(
                        status,
                        ip_address,
                        mac_address,
                        hostname,
                        vendor,
                        last_seen
                    ))
                
                # Add context menu for right-click
                context_menu = tk.Menu(modal, tearoff=0)
                context_menu.add_command(label="📋 Copy IP", command=lambda: copy_selected_ip(tree))
                context_menu.add_command(label="📋 Copy MAC", command=lambda: copy_selected_mac(tree))
                
                def show_context_menu(event):
                    try:
                        item = tree.selection()[0]
                        context_menu.post(event.x_root, event.y_root)
                    except IndexError:
                        pass
                
                tree.bind("<Button-3>", show_context_menu)
            
            def copy_selected_ip(tree):
                try:
                    item = tree.selection()[0]
                    values = tree.item(item, "values")
                    ip = values[1]  # IP is in column 1
                    modal.clipboard_clear()
                    modal.clipboard_append(ip)
                    messagebox.showinfo("Copied", f"IP address copied: {ip}")
                except IndexError:
                    messagebox.showwarning("No Selection", "Please select a client first.")
            
            def copy_selected_mac(tree):
                try:
                    item = tree.selection()[0]
                    values = tree.item(item, "values")
                    mac = values[2]  # MAC is in column 2
                    modal.clipboard_clear()
                    modal.clipboard_append(mac)
                    messagebox.showinfo("Copied", f"MAC address copied: {mac}")
                except IndexError:
                    messagebox.showwarning("No Selection", "Please select a client first.")
            
            # Start scanning clients in background thread
            import threading
            threading.Thread(target=scan_clients, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("Error", 
                               f"An unexpected error occurred:\n{str(e)}\n\n"
                               f"Please check the console for more details.")
            print(f"⚠️ Error in show_non_unifi_connected_clients: {str(e)}")

    def show_unifi_connected_clients(self, router):
        """Show connected clients for a UniFi AP with robust error handling"""
        try:
            import requests
            from requests.exceptions import ConnectionError, Timeout, RequestException
            
            # Fetch clients from UniFi API for this specific AP
            mac = router.get('mac_address', '')
            if not mac:
                messagebox.showerror("Error", "MAC address not found for this device.")
                return
            
            # Use reasonable timeout to prevent UI freeze but allow slow controllers
            response = requests.get(
                f"{self.unifi_api_url}/api/unifi/devices/{mac}/clients", 
                timeout=(2, 5)  # 2s connection, 5s read timeout
            )
            
            if response.status_code != 200:
                messagebox.showerror("Error", 
                                   f"Failed to fetch clients from UniFi API.\n"
                                   f"Status Code: {response.status_code}\n\n"
                                   f"Please check if the UniFi API server is running.")
                return
            
            clients = response.json() or []
            
            # Create modal window
            modal = Toplevel(self.root)
            modal.title(f"👥 Connected Clients - {router.get('name', 'UniFi AP')}")
            modal.geometry("900x600")
            modal.transient(self.root)
            modal.grab_set()
            
            # Center window
            self._center_window(modal, 900, 600)
            
            # Main container
            main_container = tb.Frame(modal, padding=20)
            main_container.pack(fill="both", expand=True)
            
            # Header
            header_frame = tb.Frame(main_container)
            header_frame.pack(fill="x", pady=(0, 15))
            
            tb.Label(header_frame, text=f"📡 {router.get('name', 'UniFi AP')}", 
                    font=("Segoe UI", 16, "bold"), bootstyle="primary").pack(side="left")
            
            client_count_label = tb.Label(header_frame, 
                                         text=f"{len(clients)} Connected Client{'s' if len(clients) != 1 else ''}", 
                                         font=("Segoe UI", 12), bootstyle="info")
            client_count_label.pack(side="right")
            
            # Info banner
            info_frame = tb.LabelFrame(main_container, text="ℹ️ Access Point Info", bootstyle="secondary", padding=10)
            info_frame.pack(fill="x", pady=(0, 15))
            
            info_text = f"IP: {router.get('ip_address', 'N/A')} | MAC: {router.get('mac_address', 'N/A')} | Location: {router.get('location', 'N/A')}"
            tb.Label(info_frame, text=info_text, font=("Segoe UI", 9)).pack()
            
            if not clients:
                # No clients connected
                no_clients_frame = tb.Frame(main_container)
                no_clients_frame.pack(fill="both", expand=True)
                tb.Label(no_clients_frame, text="No clients currently connected to this AP", 
                        font=("Segoe UI", 12), bootstyle="secondary").pack(pady=50)
            else:
                # Create scrollable frame for clients
                canvas_frame = tb.Frame(main_container)
                canvas_frame.pack(fill="both", expand=True)
                
                canvas = tb.Canvas(canvas_frame)
                scrollbar = tb.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
                clients_frame = tb.Frame(canvas)
                
                clients_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
                canvas.create_window((0, 0), window=clients_frame, anchor="nw")
                canvas.configure(yscrollcommand=scrollbar.set)
                
                canvas.pack(side="left", fill="both", expand=True)
                scrollbar.pack(side="right", fill="y")
                
                # Bind mouse wheel scrolling to canvas
                def on_mousewheel_clients(event):
                    canvas.yview_scroll(int(-1*(event.delta/120)), "units")
                    return "break"
                
                canvas.bind("<MouseWheel>", on_mousewheel_clients)
                clients_frame.bind("<MouseWheel>", on_mousewheel_clients)
                
                # Display each client as a card
                for idx, client in enumerate(clients):
                    client_card = tb.LabelFrame(clients_frame, text=f"Client {idx + 1}", 
                                               bootstyle="info", padding=15)
                    client_card.pack(fill="x", pady=5, padx=5)
                    
                    # Client info grid
                    info_grid = tb.Frame(client_card)
                    info_grid.pack(fill="x")
                    info_grid.grid_columnconfigure(1, weight=1)
                    info_grid.grid_columnconfigure(3, weight=1)
                    
                    # Client details
                    client_fields = [
                        ("👤 Hostname:", client.get('hostname', 'Unknown')),
                        ("📱 MAC:", client.get('mac', 'N/A')),
                        ("🌐 IP Address:", client.get('ip', 'N/A')),
                        ("📡 Signal:", f"{client.get('signal', 'N/A')} dBm"),
                        ("⬇️ RX Rate:", f"{client.get('rx_rate', 0) / 1000:.1f} Mbps"),
                        ("⬆️ TX Rate:", f"{client.get('tx_rate', 0) / 1000:.1f} Mbps"),
                        ("📊 Channel:", str(client.get('channel', 'N/A'))),
                        ("⏱️ Uptime:", self._format_uptime(client.get('uptime', 0))),
                    ]
                    
                    for i, (label, value) in enumerate(client_fields):
                        row, col = i // 2, (i % 2) * 2
                        tb.Label(info_grid, text=label, font=("Segoe UI", 10, "bold"), 
                                bootstyle="secondary").grid(row=row, column=col, sticky="w", padx=(0, 10), pady=5)
                        tb.Label(info_grid, text=value, font=("Segoe UI", 10), 
                                bootstyle="dark").grid(row=row, column=col+1, sticky="w", padx=(0, 30), pady=5)
            
            # Footer with refresh and close buttons
            footer_frame = tb.Frame(main_container)
            footer_frame.pack(fill="x", pady=(15, 0))
            
            tb.Button(footer_frame, text="🔄 Refresh", bootstyle="info",
                     command=lambda: [modal.destroy(), self.show_unifi_connected_clients(router)],
                     width=15).pack(side="left")
            
            tb.Button(footer_frame, text="Close", bootstyle="secondary",
                     command=modal.destroy, width=15).pack(side="right")
            
        except ConnectionError:
            messagebox.showerror("Connection Error", 
                               "Cannot connect to UniFi API server.\n\n"
                               "Please ensure the UniFi API server is running.\n"
                               f"Server URL: {self.unifi_api_url}")
        except Timeout:
            messagebox.showerror("Timeout Error",
                               "UniFi API server request timed out.\n\n"
                               "The server may be slow or overloaded.\n"
                               "Please try again later.")
        except RequestException as e:
            messagebox.showerror("Request Error",
                               f"Failed to communicate with UniFi API:\n{str(e)}")
        except Exception as e:
            messagebox.showerror("Error", 
                               f"An unexpected error occurred:\n{str(e)}\n\n"
                               f"Please check the console for more details.")
            print(f"⚠️ Error in show_unifi_connected_clients: {str(e)}")

    def _format_uptime(self, seconds):
        """Format uptime in seconds to human-readable format"""
        if not seconds or seconds == 0:
            return "N/A"
        
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

    def _show_context_menu(self, event, router):
        menu = Menu(self.root, tearoff=0)
        menu.add_command(
            label="Edit",
            command=lambda: [menu.unpost(), self.open_router_popup(mode='edit', router=router)]
        )
        menu.add_command(
            label="Delete",
            command=lambda: [menu.unpost(), self.delete_selected_router(router)]
        )
        menu.post(event.x_root, event.y_root)

    def open_router_details(self, router):
        # Creating the modern top-level window
        d = Toplevel(self.root)
        is_unifi = router.get('is_unifi', False)
        device_type = "UniFi Device" if is_unifi else "Router"
        d.title(f"{device_type} Details - {router['name']}")
        d.geometry("700x600")
        d.transient(self.root)
        d.grab_set()
        d.configure(bg='#f8f9fa')
        d.resizable(True, True)

        # --- Center window on parent ---
        self._center_window(d, 700, 600)

        # --- Main container with modern styling ---
        main_container = tb.Frame(d, bootstyle="light")
        main_container.pack(fill="both", expand=True, padx=20, pady=20)

        # --- Header Section with Gradient Effect ---
        header_frame = tb.LabelFrame(main_container, text="", bootstyle="primary", padding=20)
        header_frame.pack(fill="x", pady=(0, 20))

        # Router icon and title
        title_frame = tb.Frame(header_frame)
        title_frame.pack(fill="x")

        # Router status indicator circle
        status_indicator = tb.Frame(title_frame, width=20, height=20)
        status_indicator.pack(side="left", padx=(0, 15))
        
        self.status_circle = tb.Label(status_indicator, text="●", font=("Segoe UI", 24), 
                                     bootstyle="secondary")
        self.status_circle.pack()

        # Title and subtitle
        title_text_frame = tb.Frame(title_frame)
        title_text_frame.pack(side="left", fill="x", expand=True)

        # Use different icon for UniFi devices
        icon = "📡" if is_unifi else "🌐"
        router_title = tb.Label(title_text_frame, text=f"{icon} {router['name']}", 
                               font=("Segoe UI", 20, "bold"), bootstyle="primary")
        router_title.pack(anchor="w")

        # Show device type badge for UniFi
        subtitle_text = f"IP: {router['ip_address']}"
        if is_unifi:
            subtitle_text += " (UniFi Access Point)"
        router_subtitle = tb.Label(title_text_frame, text=subtitle_text, 
                                  font=("Segoe UI", 12), bootstyle="secondary")
        router_subtitle.pack(anchor="w")

        # Quick actions in header (only for non-UniFi devices)
        if not is_unifi:
            quick_actions = tb.Frame(header_frame)
            quick_actions.pack(fill="x", pady=(15, 0))

            tb.Button(quick_actions, text="✏️ Edit Router", bootstyle="success",
                      command=lambda: [d.destroy(), self.open_router_popup(mode='edit', router=router)],
                      width=15).pack(side="left", padx=(0, 10))

            tb.Button(quick_actions, text="🗑️ Delete Router", bootstyle="danger",
                      command=lambda: [d.destroy(), self.delete_selected_router(router)],
                      width=15).pack(side="left", padx=(0, 10))

            if router.get('image_path'):
                tb.Button(quick_actions, text="📷 View Image", bootstyle="info",
                          command=lambda: self.show_router_image(router['image_path']),
                          width=15).pack(side="left")
        else:
            # For UniFi devices, show edit and delete buttons
            unifi_actions = tb.Frame(header_frame)
            unifi_actions.pack(fill="x", pady=(15, 0))
            
            tb.Button(unifi_actions, text="✏️ Edit UniFi Device", bootstyle="success",
                      command=lambda: [d.destroy(), self.open_router_popup(mode='edit', router=router)],
                      width=18).pack(side="left", padx=(0, 10))
            
            tb.Button(unifi_actions, text="🗑️ Delete UniFi Device", bootstyle="danger",
                      command=lambda: [d.destroy(), self.delete_selected_router(router)],
                      width=18).pack(side="left", padx=(0, 10))
            
            # Add View Image button if image exists
            if router.get('image_path'):
                tb.Button(unifi_actions, text="📷 View Image", bootstyle="info",
                          command=lambda: self.show_router_image(router['image_path']),
                          width=15).pack(side="left", padx=(0, 10))
            
            # Add info note below buttons
            tb.Label(unifi_actions, text="ℹ️ UniFi Controller managed", 
                    font=("Segoe UI", 9, "italic"), bootstyle="info").pack(side="left", padx=(10, 0))

        # --- Scrollable Content Area ---
        canvas = tk.Canvas(main_container, highlightthickness=0, bg='#f8f9fa')
        scrollbar = tb.Scrollbar(main_container, orient="vertical", command=canvas.yview, bootstyle="secondary")
        scroll_frame = tb.Frame(canvas, bootstyle="light")

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Bind mouse wheel scrolling to canvas
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            return "break"
        
        canvas.bind("<MouseWheel>", on_mousewheel)
        scroll_frame.bind("<MouseWheel>", on_mousewheel)

        # --- Store labels for live update ---
        self.detail_status_lbl = None
        self.detail_download_lbl = None
        self.detail_upload_lbl = None
    # Removed Last Seen label per request (was self.detail_last_seen_lbl)
        self.detail_latency_lbl = None

        # --- Router Information Cards ---
        # Basic Information Card
        basic_info_card = tb.LabelFrame(scroll_frame, text="🔧 Basic Information", 
                                       bootstyle="info", padding=20)
        basic_info_card.pack(fill="x", pady=(0, 15))

        basic_grid = tb.Frame(basic_info_card)
        basic_grid.pack(fill="x")
        basic_grid.grid_columnconfigure(1, weight=1)
        basic_grid.grid_columnconfigure(3, weight=1)

        # Basic info fields in 2x2 grid
        basic_fields = [
            ("🏷️ Name:", router['name']),
            ("📍 Location:", router['location']),
            ("🏭 Brand:", router['brand']),
            ("📱 MAC Address:", router['mac_address']),
        ]

        for i, (label, value) in enumerate(basic_fields):
            row, col = i // 2, (i % 2) * 2
            tb.Label(basic_grid, text=label, font=("Segoe UI", 11, "bold"), 
                    bootstyle="secondary").grid(row=row, column=col, sticky="w", padx=(0, 10), pady=8)
            tb.Label(basic_grid, text=value, font=("Segoe UI", 11), 
                    bootstyle="dark").grid(row=row, column=col+1, sticky="w", padx=(0, 30), pady=8)

        # Connection Status Card
        status_card = tb.LabelFrame(scroll_frame, text="🌐 Connection Status", 
                                   bootstyle="success", padding=20)
        status_card.pack(fill="x", pady=(0, 15))

        status_grid = tb.Frame(status_card)
        status_grid.pack(fill="x")

        # Status row
        status_row = tb.Frame(status_grid)
        status_row.pack(fill="x", pady=(0, 15))

        tb.Label(status_row, text="📶 Current Status:", font=("Segoe UI", 12, "bold"), 
                bootstyle="secondary").pack(side="left")
        
        self.detail_status_lbl = tb.Label(status_row, text="🕒 Checking...", 
                                         font=("Segoe UI", 12, "bold"), bootstyle="warning")
        self.detail_status_lbl.pack(side="left", padx=(10, 0))

    # Last Seen section removed

        # Performance Metrics Card
        performance_card = tb.LabelFrame(scroll_frame, text="📊 Performance Metrics", 
                                        bootstyle="warning", padding=20)
        performance_card.pack(fill="x", pady=(0, 15))

        # Latency section
        latency_frame = tb.Frame(performance_card)
        latency_frame.pack(fill="x", pady=(0, 15))

        tb.Label(latency_frame, text="⚡ Latency:", font=("Segoe UI", 12, "bold"), 
                bootstyle="secondary").pack(side="left")
        
        self.detail_latency_lbl = tb.Label(latency_frame, text="📡 Measuring...", 
                                          font=("Segoe UI", 12), bootstyle="info")
        self.detail_latency_lbl.pack(side="left", padx=(10, 0))

        # Bandwidth section with modern progress-style layout
        bandwidth_frame = tb.LabelFrame(performance_card, text="🚀 Bandwidth Usage", 
                                       bootstyle="info", padding=15)
        bandwidth_frame.pack(fill="x")

        # Download speed
        download_frame = tb.Frame(bandwidth_frame)
        download_frame.pack(fill="x", pady=(0, 10))

        download_icon_label = tb.Label(download_frame, text="⬇️", font=("Segoe UI", 16))
        download_icon_label.pack(side="left", padx=(0, 10))

        download_text_frame = tb.Frame(download_frame)
        download_text_frame.pack(side="left", fill="x", expand=True)

        tb.Label(download_text_frame, text="Download Speed", font=("Segoe UI", 10, "bold"), 
                bootstyle="secondary").pack(anchor="w")
        
        self.detail_download_lbl = tb.Label(download_text_frame, text="📶 Fetching...", 
                                           font=("Segoe UI", 14, "bold"), bootstyle="success")
        self.detail_download_lbl.pack(anchor="w")

        # Upload speed
        upload_frame = tb.Frame(bandwidth_frame)
        upload_frame.pack(fill="x")

        upload_icon_label = tb.Label(upload_frame, text="⬆️", font=("Segoe UI", 16))
        upload_icon_label.pack(side="left", padx=(0, 10))

        upload_text_frame = tb.Frame(upload_frame)
        upload_text_frame.pack(side="left", fill="x", expand=True)

        tb.Label(upload_text_frame, text="Upload Speed", font=("Segoe UI", 10, "bold"), 
                bootstyle="secondary").pack(anchor="w")
        
        self.detail_upload_lbl = tb.Label(upload_text_frame, text="📶 Fetching...", 
                                         font=("Segoe UI", 14, "bold"), bootstyle="primary")
        self.detail_upload_lbl.pack(anchor="w")

        # Additional Actions Card
        actions_card = tb.LabelFrame(scroll_frame, text="⚙️ Additional Actions", 
                                    bootstyle="dark", padding=20)
        actions_card.pack(fill="x", pady=(0, 15))

        actions_grid = tb.Frame(actions_card)
        actions_grid.pack(fill="x")

        # Action buttons in grid
        action_buttons = [
            ("🔄 Refresh Data", "info", lambda: refresh_details()),
            ("📈 View History", "secondary", lambda: self.open_router_history(router)),
            ("👥 Connected Clients", "success", lambda: self.show_connected_clients_for_router(router)),
        ]

        for i, (text, style, cmd) in enumerate(action_buttons):
            row, col = i // 2, i % 2
            tb.Button(actions_grid, text=text, bootstyle=style, command=cmd,
                     width=25).grid(row=row, column=col, padx=10, pady=5, sticky="ew")
        
        actions_grid.grid_columnconfigure(0, weight=1)
        actions_grid.grid_columnconfigure(1, weight=1)

        # --- Auto Update Function ---
        def refresh_details():
            if not d.winfo_exists():
                return  # stop if closed

            # Check if this is a UniFi device
            is_unifi = router.get('is_unifi', False)
            
            if is_unifi:
                # For UniFi devices, fetch fresh data from API with graceful fallbacks
                try:
                    import requests
                    from requests.exceptions import ConnectionError, Timeout, RequestException
                    mac = router.get('mac_address', '')
                    # Allow a bit more time for slow controllers
                    response = requests.get(f"{self.unifi_api_url}/api/unifi/devices", timeout=(2, 5))
                    down = None
                    up = None
                    if response.status_code == 200:
                        devices = response.json() or []
                        # Find matching device by MAC address
                        matching_device = next((d for d in devices if d.get('mac') == mac), None)
                        if matching_device:
                            down = matching_device.get('xput_down')
                            up = matching_device.get('xput_up')
                            # Update status based on availability
                            self.detail_status_lbl.config(text="🟢 Online", bootstyle="success")
                            self.status_circle.config(text="●", bootstyle="success")
                    # Fallback to router cached speeds if API yielded nothing
                    if not isinstance(down, (int, float)):
                        down = float(router.get('download_speed') or 0.0)
                    if not isinstance(up, (int, float)):
                        up = float(router.get('upload_speed') or 0.0)

                    # Update bandwidth labels with whatever we have
                    self.detail_download_lbl.config(text=(f"{down:.2f} Mbps" if isinstance(down, (int, float)) else "N/A"))
                    self.detail_upload_lbl.config(text=(f"{up:.2f} Mbps" if isinstance(up, (int, float)) else "N/A"))

                    # Try ping latency via UniFi API helper
                    try:
                        ping_resp = requests.get(f"{self.unifi_api_url}/api/unifi/ping/{mac}", timeout=(1, 3))
                        if ping_resp.status_code == 200:
                            pdata = ping_resp.json()
                            lat = pdata.get('latency_ms')
                            if isinstance(lat, (int, float)):
                                self.detail_latency_lbl.config(text=f"{lat:.0f} ms", bootstyle="success")
                            else:
                                self.detail_latency_lbl.config(text="--", bootstyle="secondary")
                        else:
                            self.detail_latency_lbl.config(text="--", bootstyle="secondary")
                    except Exception:
                        self.detail_latency_lbl.config(text="--", bootstyle="secondary")

                    # Last Seen removed

                except (ConnectionError, Timeout):
                    # API not reachable; still show cached speeds if available
                    down = float(router.get('download_speed') or 0.0)
                    up = float(router.get('upload_speed') or 0.0)
                    self.detail_status_lbl.config(text="⚠️ API Unavailable", bootstyle="warning")
                    self.status_circle.config(text="●", bootstyle="warning")
                    self.detail_download_lbl.config(text=(f"{down:.2f} Mbps" if down else "N/A"))
                    self.detail_upload_lbl.config(text=(f"{up:.2f} Mbps" if up else "N/A"))
                    self.detail_latency_lbl.config(text="--")
                except RequestException as e:
                    self.detail_status_lbl.config(text="⚠️ API Error", bootstyle="warning")
                    self.status_circle.config(text="●", bootstyle="warning")
                    print(f"⚠️ UniFi API request error in refresh_details: {str(e)}")
                except Exception as e:
                    self.detail_status_lbl.config(text="⚠️ Error", bootstyle="danger")
                    self.status_circle.config(text="●", bootstyle="danger")
                    print(f"⚠️ Unexpected error in refresh_details (UniFi): {str(e)}")
            else:
                # Regular router - use existing logic
                rid = router['id']
                # Ensure we update the stored history dict, not a temporary copy
                hist = self.status_history.setdefault(rid, {"failures": 0, "current": None})
                bw = self.bandwidth_data.get(rid, {})

                # --- Update Status Circle and Label ---
                status = hist.get("current")
                if status is True:
                    self.detail_status_lbl.config(text="🟢 Online", bootstyle="success")
                    self.status_circle.config(text="●", bootstyle="success")
                    
                    # Update bandwidth if router is online
                    if bw and bw.get("download") is not None and bw.get("upload") is not None:
                        self.detail_download_lbl.config(text=f"{bw['download']:.2f} Mbps")
                        self.detail_upload_lbl.config(text=f"{bw['upload']:.2f} Mbps")
                        
                        # Update latency using effective latency (cached when dynamic ping skips)
                        if not hasattr(self, "_last_latency_by_router"):
                            self._last_latency_by_router = {}
                        new_latency = bw.get("latency")
                        if isinstance(new_latency, (int, float)):
                            effective_latency = new_latency
                            self._last_latency_by_router[rid] = new_latency
                        else:
                            effective_latency = self._last_latency_by_router.get(rid)
                        
                        if isinstance(effective_latency, (int, float)):
                            self.detail_latency_lbl.config(text=f"{effective_latency:.0f} ms", bootstyle="success")
                        else:
                            self.detail_latency_lbl.config(text="📡 Measuring...", bootstyle="info")
                    else:
                        # If bandwidth not fetched yet, trigger fetching it
                        self.fetch_and_update_bandwidth(rid, router['ip_address'])
                        self.detail_download_lbl.config(text="📶 Fetching...")
                        self.detail_upload_lbl.config(text="📶 Fetching...")
                        self.detail_latency_lbl.config(text="📡 Measuring...")
                        
                elif status is False:
                    self.detail_status_lbl.config(text="🔴 Offline", bootstyle="danger")
                    self.status_circle.config(text="●", bootstyle="danger")
                    self.detail_download_lbl.config(text="N/A - Offline")
                    self.detail_upload_lbl.config(text="N/A - Offline")
                    self.detail_latency_lbl.config(text="N/A - Offline", bootstyle="danger")
                else:
                    self.detail_status_lbl.config(text="🔄 Checking...", bootstyle="warning")
                    self.status_circle.config(text="●", bootstyle="warning")
                    self.detail_download_lbl.config(text="📶 Checking...")
                    self.detail_upload_lbl.config(text="📶 Checking...")
                    self.detail_latency_lbl.config(text="📡 Checking...")

                # Last Seen removed

            # Schedule next refresh (3s for UniFi, 3s for regular)
            d.after(3000, refresh_details)

        refresh_details()


    def show_router_image(self, image_path):
        if not image_path or not os.path.exists(image_path):
            return messagebox.showerror("Image Not Found","No image file found for this router.")
        img_win = Toplevel(self.root)
        img_win.title("Router Image")
        img_win.geometry("850x650")
        img_win.transient(self.root)
        img_win.grab_set()
        try:
            img = Image.open(image_path)
            img = img.resize((800,600), Image.Resampling.LANCZOS)
            ph = ImageTk.PhotoImage(img)
            lbl = tb.Label(img_win, image=ph)
            lbl.image = ph
            lbl.pack(padx=10, pady=10)
        except Exception as e:
            messagebox.showerror("Error","Could not display image.")

    def open_router_history(self, router):
        from tkinter import Toplevel
        from datetime import datetime, timedelta
        try:
            from report_utils import get_uptime_percentage, get_status_logs, get_bandwidth_usage
        except Exception:
            messagebox.showerror("Import Error", "report_utils helpers not found.")
            return

        # Modal window
        win = Toplevel(self.root)
        win.title(f"📈 History - {router.get('name', 'Router')}" )
        win.geometry("800x600")
        win.transient(self.root)
        win.grab_set()
        self._center_window(win, 800, 600)

        outer = tb.Frame(win, padding=15)
        outer.pack(fill="both", expand=True)

        # Date range controls (last 7 days by default)
        controls = tb.Frame(outer)
        controls.pack(fill="x", pady=(0, 10))
        tb.Label(controls, text="Start:").pack(side="left")
        start_var = tb.StringVar()
        end_var = tb.StringVar()
        default_end = datetime.now()
        default_start = default_end - timedelta(days=7)
        start_var.set(default_start.strftime("%m/%d/%Y"))
        end_var.set(default_end.strftime("%m/%d/%Y"))
        start_entry = tb.Entry(controls, textvariable=start_var, width=12)
        start_entry.pack(side="left", padx=5)
        tb.Label(controls, text="End:").pack(side="left")
        end_entry = tb.Entry(controls, textvariable=end_var, width=12)
        end_entry.pack(side="left", padx=5)

        tb.Button(controls, text="🔄 Refresh", bootstyle="info",
                  command=lambda: load_data()).pack(side="left", padx=10)

        # Summary cards
        cards = tb.Frame(outer)
        cards.pack(fill="x")
        cards.grid_columnconfigure(0, weight=1)
        cards.grid_columnconfigure(1, weight=1)
        cards.grid_columnconfigure(2, weight=1)

        uptime_card = tb.LabelFrame(cards, text="Uptime %", bootstyle="success", padding=10)
        uptime_card.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        uptime_lbl = tb.Label(uptime_card, text="-", font=("Segoe UI", 16, "bold"))
        uptime_lbl.pack()

        downtime_card = tb.LabelFrame(cards, text="Downtime (hrs)", bootstyle="danger", padding=10)
        downtime_card.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        downtime_lbl = tb.Label(downtime_card, text="-", font=("Segoe UI", 16, "bold"))
        downtime_lbl.pack()

        bw_card = tb.LabelFrame(cards, text="Bandwidth (MB)", bootstyle="warning", padding=10)
        bw_card.grid(row=0, column=2, padx=5, pady=5, sticky="nsew")
        bw_lbl = tb.Label(bw_card, text="-", font=("Segoe UI", 16, "bold"))
        bw_lbl.pack()

        # Logs table
        logs_frame = tb.LabelFrame(outer, text="Status Logs", bootstyle="secondary", padding=10)
        logs_frame.pack(fill="both", expand=True, pady=(10, 0))
        cols = ("timestamp", "status")
        tree = ttk.Treeview(logs_frame, columns=cols, show="headings")
        tree.heading("timestamp", text="Timestamp")
        tree.heading("status", text="Status")
        tree.column("timestamp", width=200, anchor="w")
        tree.column("status", width=120, anchor="center")
        vsb = ttk.Scrollbar(logs_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        
        # Bind mouse wheel scrolling
        def on_mousewheel_history(event):
            tree.yview_scroll(int(-1*(event.delta/120)), "units")
            return "break"
        
        tree.bind("<MouseWheel>", on_mousewheel_history)

        def load_data():
            # parse dates
            try:
                s = datetime.strptime(start_var.get(), "%m/%d/%Y")
                e = datetime.strptime(end_var.get(), "%m/%d/%Y")
                # include entire end day
                e = datetime.combine(e.date(), datetime.max.time())
            except Exception:
                messagebox.showerror("Date Error", "Please use MM/DD/YYYY format.")
                return

            rid = router.get('id')
            if not rid:
                messagebox.showerror("Error", "Router ID missing.")
                return

            # compute stats
            uptime = get_uptime_percentage(rid, s, e)
            total_secs = (e - s).total_seconds()
            downtime_hours = round(((100 - uptime) / 100.0) * total_secs / 3600.0, 2)
            bw = get_bandwidth_usage(rid, s, e)

            uptime_lbl.config(text=f"{uptime:.2f}%")
            downtime_lbl.config(text=f"{downtime_hours:.2f}")
            bw_lbl.config(text=f"{bw:.2f}")

            # populate logs
            for iid in tree.get_children():
                tree.delete(iid)
            logs = get_status_logs(rid, s, e)
            for ts, status in logs:
                # ts may already be datetime; format safely
                ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if hasattr(ts, 'strftime') else str(ts)
                tree.insert('', 'end', values=(ts_str, status.title()))

        load_data()

    # ------------------------
    # Loading animation for routers tab
    # ------------------------
    def _show_routers_loading(self):
        """Show loading animation for routers tab"""
        if hasattr(self, 'routers_loading_frame'):
            self.canvas.pack_forget()
            self.routers_loading_frame.pack(fill="both", expand=True)
            self.root.update_idletasks()
    
    def _hide_routers_loading(self):
        """Hide loading animation for routers tab"""
        if hasattr(self, 'routers_loading_frame'):
            self.routers_loading_frame.pack_forget()
            self.canvas.pack(side="left", fill="both", expand=True)
            self.root.update_idletasks()

    # ------------------------
    # Reload routers list and create/update router cards
    # ------------------------
    def reload_routers(self, force_reload=False):
        # Use loading animation only on first build or explicit force
        first_time = not hasattr(self, 'online_section_frame') or not hasattr(self, 'offline_section_frame')
        if force_reload or first_time:
            self._show_routers_loading()

        # Order preference: UniFi first within each status group
        unifi_first = True

        # 1) Fetch UniFi devices (may upsert to DB), then full router list
        unifi_devices = self._fetch_unifi_devices()
        db_routers = get_routers()

        # Build MAC->UniFi data map
        unifi_mac_to_data = {d.get('mac_address'): d for d in unifi_devices if d.get('mac_address')}

        # Merge UniFi API info into DB routers
        all_devices = []
        for router in db_routers:
            mac = router.get('mac_address')
            is_unifi = router.get('brand') == 'UniFi' or mac in unifi_mac_to_data
            router['is_unifi'] = is_unifi
            if is_unifi and mac in unifi_mac_to_data:
                api_dev = unifi_mac_to_data[mac]
                router['ip_address'] = api_dev.get('ip_address', router.get('ip_address'))
                router['brand'] = api_dev.get('brand', router.get('brand'))
                router['download_speed'] = api_dev.get('download_speed', 0)
                router['upload_speed'] = api_dev.get('upload_speed', 0)
                router['name'] = router.get('name', api_dev.get('name', ''))
                router['location'] = router.get('location', api_dev.get('location', ''))
                router['image_path'] = router.get('image_path', api_dev.get('image_path', None))
                # Compute online flag using ping (if present) and API status
                ping_online = None
                if 'latency' in router:
                    ping_online = router['latency'] is not None
                api_online = None
                for key in ('is_connected', 'connected', 'status', 'state'):
                    if key in api_dev:
                        val = api_dev[key]
                        if isinstance(val, bool):
                            api_online = val
                        elif isinstance(val, str):
                            api_online = val.lower() in ('connected', 'online', 'up', 'true', '1')
                        break
                if api_online is None:
                    api_online = True
                # If ping_online is None (latency not set yet), use api_online as primary indicator
                # and check status_history as fallback. Only require both when ping_online is available.
                if ping_online is None:
                    # Check status_history as fallback if API status is unclear
                    status_history_online = self.status_history.get(router['id'], {}).get('current')
                    if status_history_online is not None:
                        router['is_online_unifi'] = bool(status_history_online) and bool(api_online)
                    else:
                        # Use API status as primary indicator when ping is not available
                        router['is_online_unifi'] = bool(api_online)
                else:
                    # When ping_online is available, require both ping and API to be online
                    router['is_online_unifi'] = bool(ping_online) and bool(api_online)
            all_devices.append(router)

        # Helper: background latency update for UniFi
        def update_unifi_latency(router):
            try:
                from network_utils import ping_latency
                latency = ping_latency(router.get('ip_address'), is_unifi=False, use_manager=False)
                router['latency'] = latency
                from router_utils import update_router_status_in_db
                update_router_status_in_db(router['id'], latency is not None)
                # Update label if exists
                w = self.router_widgets.get(router['id'])
                if w and w.get('bandwidth_label') and w['bandwidth_label'].winfo_exists():
                    down = float(router.get('download_speed') or 0.0)
                    up = float(router.get('upload_speed') or 0.0)
                    latency_text = f"   ⚡ {latency:.1f} ms" if isinstance(latency, (int, float)) else "   ⚡ --"
                    speed_text = (
                        f"📶 ↓{down:.1f} Mbps ↑{up:.1f} Mbps" if (down > 0 or up > 0) else "📶 Bandwidth: --"
                    )
                    try:
                        w['bandwidth_label'].config(text=speed_text + latency_text, bootstyle=("info" if (down > 0 or up > 0) else "secondary"))
                    except Exception:
                        pass
            except Exception:
                router['latency'] = None

        # 2) Partition by UniFi/non and online/offline
        unifi_online, unifi_offline, nonunifi_online, nonunifi_offline = [], [], [], []
        type_filter = self.router_type_filter.get() if hasattr(self, 'router_type_filter') else "All"
        for r in all_devices:
            if type_filter == "UniFi" and not r.get('is_unifi'):
                continue
            if type_filter == "Non-UniFi" and r.get('is_unifi'):
                continue
            if r.get('is_unifi'):
                is_online = r.get('is_online_unifi')
                if is_online is None:
                    is_online = self.status_history.get(r['id'], {}).get('current') is True
                r['is_online_display'] = bool(is_online)
                (unifi_online if is_online else unifi_offline).append(r)
            else:
                is_online = self.status_history.get(r['id'], {}).get('current') is True
                r['is_online_display'] = bool(is_online)
                (nonunifi_online if is_online else nonunifi_offline).append(r)

        # Sort by name then combine respecting UniFi-first toggle
        key_name = lambda x: x.get('name', '').lower()
        for grp in (unifi_online, unifi_offline, nonunifi_online, nonunifi_offline):
            grp.sort(key=key_name)
        if unifi_first:
            online = unifi_online + nonunifi_online
            offline = unifi_offline + nonunifi_offline
        else:
            online = nonunifi_online + unifi_online
            offline = nonunifi_offline + unifi_offline

        # 3) Ensure section containers exist (created once)
        self._ensure_router_sections()
        # Update header visibility/content
        self.online_header_label.configure(text="🟢 Online Routers" if self.sort_var.get() == "online" else "Routers")
        self.offline_header_label.pack_forget() if self.sort_var.get() != "online" else self.offline_header_label.pack(anchor="w", padx=10, pady=(15, 5))
        self.offline_section_frame.pack_forget() if self.sort_var.get() != "online" else self.offline_section_frame.pack(fill="x", padx=10, pady=5)

        # 4) Diff sets: add, remove, update (always consider all routers)
        desired_ids = [r['id'] for r in (online + offline)]
        desired_set = set(desired_ids)
        existing_set = set(self.router_widgets.keys())

        # Remove cards that no longer exist or filtered out
        for rid in list(existing_set - desired_set):
            w = self.router_widgets.pop(rid, None)
            if w and w.get('card') and w['card'].winfo_exists():
                try:
                    w['card'].destroy()
                except Exception:
                    pass

        # Add missing cards
        for r in (online + offline):
            rid = r['id']
            if rid not in self.router_widgets:
                parent = self.online_section_frame if (self.sort_var.get() != 'online' or r.get('is_online_display')) else self.offline_section_frame
                self._create_router_card(parent, r)
            else:
                # Update data reference for future comparisons
                self.router_widgets[rid]['data'] = r

        # Move cards between sections if grouping changed
        if self.sort_var.get() == 'online':
            # Online routers must be under online_section_frame; offline under offline_section_frame
            for r in online:
                rid = r['id']
                w = self.router_widgets.get(rid)
                if w and w.get('parent') is not self.online_section_frame:
                    try:
                        # recreate under new parent (tk doesn't support changing master)
                        old = self.router_widgets.pop(rid)
                        if old.get('card') and old['card'].winfo_exists():
                            old['card'].destroy()
                        self._create_router_card(self.online_section_frame, r)
                    except Exception:
                        pass
            for r in offline:
                rid = r['id']
                w = self.router_widgets.get(rid)
                if w and w.get('parent') is not self.offline_section_frame:
                    try:
                        old = self.router_widgets.pop(rid)
                        if old.get('card') and old['card'].winfo_exists():
                            old['card'].destroy()
                        self._create_router_card(self.offline_section_frame, r)
                    except Exception:
                        pass
        else:
            # Default view: all routers should live in online_section_frame
            for r in (online + offline):
                rid = r['id']
                w = self.router_widgets.get(rid)
                if w and w.get('parent') is not self.online_section_frame:
                    try:
                        old = self.router_widgets.pop(rid)
                        if old.get('card') and old['card'].winfo_exists():
                            old['card'].destroy()
                        self._create_router_card(self.online_section_frame, r)
                    except Exception:
                        pass

        # Update existing card fields minimally
        for r in (online + offline):
            rid = r['id']
            w = self.router_widgets.get(rid)
            if w:
                try:
                    self._update_router_card(w, r)
                except Exception:
                    pass

        # 5) Re-layout cards with responsive columns without destroying
        def layout_container(container, ids):
            max_cols = self._compute_max_cols(container)
            self._layout_router_cards(container, ids, max_cols)
        online_ids = [r['id'] for r in online] if self.sort_var.get() == 'online' else desired_ids
        layout_container(self.online_section_frame, online_ids)
        if self.sort_var.get() == 'online':
            offline_ids = [r['id'] for r in offline]
            layout_container(self.offline_section_frame, offline_ids)

        # Batch any pending UniFi latency updates for freshly created routers
        import threading
        for r in (online + offline):
            if r.get('is_unifi'):
                threading.Thread(target=update_unifi_latency, args=(r,), daemon=True).start()

        # Trigger pings for online APs (non-blocking)
        self.ping_all_online_aps_once()

        # Hide loading if shown
        if force_reload or first_time:
            self._hide_routers_loading()
        
        # Re-apply filter if there's an active query
        if hasattr(self, 'routers_search_var'):
            query = self.routers_search_var.get().strip()
            if query:
                self.apply_filter()

    def _ensure_router_sections(self):
        """Create (once) the online/offline containers under the scrollable_frame.
        This allows us to diff and re-layout without rebuilding everything."""
        if hasattr(self, 'online_section_frame') and hasattr(self, 'offline_section_frame'):
            return
        # Clear any stray children from previous rebuild approach
        for w in list(self.scrollable_frame.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass
        # Online header + section
        self.online_header_label = tb.Label(
            self.scrollable_frame, text="🟢 Online Routers",
            font=("Segoe UI", 12, "bold"), bootstyle="secondary"
        )
        self.online_header_label.pack(anchor="w", padx=10, pady=(15, 5))
        self.online_section_frame = tb.Frame(self.scrollable_frame)
        self.online_section_frame.pack(fill="x", padx=10, pady=5)
        self.online_section_frame._last_cols = None
        self.online_section_frame.bind("<Configure>", lambda e: self._layout_router_cards(self.online_section_frame, None, self._compute_max_cols(self.online_section_frame)))
        # Offline header + section (may be hidden depending on sort)
        self.offline_header_label = tb.Label(
            self.scrollable_frame, text="🔴 Offline Routers",
            font=("Segoe UI", 12, "bold"), bootstyle="secondary"
        )
        self.offline_header_label.pack(anchor="w", padx=10, pady=(15, 5))
        self.offline_section_frame = tb.Frame(self.scrollable_frame)
        self.offline_section_frame.pack(fill="x", padx=10, pady=5)
        self.offline_section_frame._last_cols = None
        self.offline_section_frame.bind("<Configure>", lambda e: self._layout_router_cards(self.offline_section_frame, None, self._compute_max_cols(self.offline_section_frame)))

    def _compute_max_cols(self, container):
        width = container.winfo_width() or self.root.winfo_width() or 800
        if width <= 400:
            return 1
        if width <= 800:
            return 2
        if width <= 1200:
            return 3
        return 4

    def _create_router_card(self, parent, router):
        """Create a card for router and register it in self.router_widgets."""
        # Determine style by status and type
        online_flag = bool(router.get('is_online_display'))
        card_style = "primary" if (online_flag and router.get('is_unifi')) else ("success" if online_flag else "danger")
        card = tb.LabelFrame(parent, text=router.get('name') or '', bootstyle=card_style, padding=0)
        # Uniform sizing
        card.grid_propagate(False)
        card.config(width=280, height=200)

        inner = tb.Frame(card, padding=10)
        inner.pack(fill="both", expand=True)
        # Icon and meta
        if router.get('is_unifi'):
            tb.Label(inner, text="📡", font=("Segoe UI Emoji", 30)).pack()
            tb.Label(inner, text="UniFi Device", font=("Segoe UI", 8, "italic"), bootstyle="primary").pack()
        else:
            tb.Label(inner, text="⛀", font=("Segoe UI Emoji", 30)).pack()
        tb.Label(inner, text=router.get('ip_address') or '', font=("Segoe UI", 10)).pack(pady=(5, 0))

        # Status label
        if router.get('is_unifi'):
            status_text, status_style = (("🟢 Online", "success") if online_flag else ("🔴 Offline", "danger"))
        else:
            cur = self.status_history.get(router['id'], {}).get('current')
            status_text, status_style = (
                ("🟢 Online", "success") if cur is True else ("🔴 Offline", "danger") if cur is False else ("🕒 Checking...", "secondary")
            )
        status_label = tb.Label(inner, text=status_text, bootstyle=status_style, cursor="hand2")
        status_label.pack(pady=5)

        # Bandwidth/latency label
        if router.get('is_unifi'):
            down = float(router.get('download_speed') or 0.0)
            up = float(router.get('upload_speed') or 0.0)
            latency = router.get('latency')
            speed_text = (f"📶 ↓{down:.1f} Mbps ↑{up:.1f} Mbps" if (down > 0 or up > 0) else "📶 Bandwidth: --")
            latency_text = f"   ⚡ {latency:.1f} ms" if isinstance(latency, (int, float)) else "   ⚡ --"
            bw_label = tb.Label(inner, text=speed_text + latency_text, bootstyle=("info" if (down > 0 or up > 0) else "secondary"))
            bw_label.pack(pady=2)
        else:
            cur_status = self.status_history.get(router['id'], {}).get('current')
            if cur_status is True:
                bw_label = tb.Label(inner, text="… Checking...", bootstyle="secondary")
            elif cur_status is False:
                bw_label = tb.Label(inner, text="🔴 Device Offline", bootstyle="danger")
            else:
                bw_label = tb.Label(inner, text="… Checking...", bootstyle="secondary")
            bw_label.pack(pady=2)

        # Click bindings - use router ID to fetch fresh data on click
        def bind_card_click(widget, router_id):
            def on_click(e):
                # Fetch fresh router data at click time
                from router_utils import get_routers
                fresh_router = None
                for r in get_routers():
                    if r.get('id') == router_id:
                        fresh_router = r
                        break
                if fresh_router:
                    self.open_router_details(fresh_router)
            
            def on_right_click(e):
                # Fetch fresh router data at right-click time
                from router_utils import get_routers
                fresh_router = None
                for r in get_routers():
                    if r.get('id') == router_id:
                        fresh_router = r
                        break
                if fresh_router:
                    self._show_context_menu(e, fresh_router)
            
            widget.bind("<Button-1>", on_click)
            if not router.get('is_unifi'):
                widget.bind("<Button-3>", on_right_click)
        
        bind_card_click(inner, router['id'])
        for child in inner.winfo_children():
            bind_card_click(child, router['id'])

        self.router_widgets[router['id']] = {
            'card': card,
            'status_label': status_label,
            'bandwidth_label': bw_label,
            'data': router,
            'parent': parent,
        }
        return card

    def _update_router_card(self, w, router):
        """Update only changed bits of an existing router card."""
        # Title changes
        try:
            if w['card'].cget('text') != (router.get('name') or ''):
                w['card'].configure(text=(router.get('name') or ''))
        except Exception:
            pass
        # Status text/style
        online_flag = bool(router.get('is_online_display'))
        if router.get('is_unifi'):
            status_text, status_style = (("🟢 Online", "success") if online_flag else ("🔴 Offline", "danger"))
            card_style = "primary" if online_flag else "danger"
        else:
            cur = self.status_history.get(router['id'], {}).get('current')
            status_text, status_style = (
                ("🟢 Online", "success") if cur is True else ("🔴 Offline", "danger") if cur is False else ("🕒 Checking...", "secondary")
            )
            card_style = "success" if cur is True else ("danger" if cur is False else w['card'].cget('bootstyle'))
        try:
            if w['status_label'].cget('text') != status_text:
                w['status_label'].configure(text=status_text, bootstyle=status_style)
        except Exception:
            pass
        try:
            if w['card'].cget('bootstyle') != card_style:
                w['card'].configure(bootstyle=card_style)
        except Exception:
            pass
        # Bandwidth/latency text
        try:
            if router.get('is_unifi'):
                # Check if UniFi router is offline
                if not online_flag:
                    w['bandwidth_label'].configure(text='📶 Device Offline', bootstyle='danger')
                else:
                    down = float(router.get('download_speed') or 0.0)
                    up = float(router.get('upload_speed') or 0.0)
                    latency = router.get('latency')
                    latency_text = f"   ⚡ {latency:.1f} ms" if isinstance(latency, (int, float)) else "   ⚡ --"
                    speed_text = (f"📶 ↓{down:.1f} Mbps ↑{up:.1f} Mbps" if (down > 0 or up > 0) else "📶 Bandwidth: --")
                    new_text = speed_text + latency_text
                    if w['bandwidth_label'].cget('text') != new_text:
                        w['bandwidth_label'].configure(text=new_text, bootstyle=("info" if (down > 0 or up > 0) else "secondary"))
            else:
                cur_status = self.status_history.get(router['id'], {}).get('current')
                desired_text = "🔴 Device Offline" if cur_status is False else "… Checking..."
                desired_style = "danger" if cur_status is False else "secondary"
                if w['bandwidth_label'].cget('text') != desired_text:
                    w['bandwidth_label'].configure(text=desired_text, bootstyle=desired_style)
        except Exception:
            pass

    def _layout_router_cards(self, container, ids, max_cols):
        """Grid existing card frames without recreating; compute row/col from order and max_cols.
        If ids is None, infer from router_widgets that belong to container AND are currently visible (not filtered out)."""
        try:
            if ids is None:
                # Build ids in current order, but only include cards that should be visible
                # Check if there's an active filter
                if hasattr(self, 'routers_search_var'):
                    query = self.routers_search_var.get().strip().lower()
                    if query:
                        # Filter is active - only include matching cards
                        ids = []
                        for rid, w in self.router_widgets.items():
                            if w.get('parent') is not container:
                                continue
                            # Check if this router matches the filter
                            data = w.get('data', {}) or {}
                            name = str(data.get('name', '') or '').lower()
                            ip = str(data.get('ip_address', '') or '').lower()
                            loc = str(data.get('location', '') or '').lower()
                            brand = str(data.get('brand', '') or '').lower()
                            if query in name or query in ip or query in loc or query in brand:
                                ids.append(rid)
                    else:
                        # No filter - include all cards in this container
                        ids = [rid for rid, w in self.router_widgets.items() if w.get('parent') is container]
                else:
                    # No filter var - include all cards in this container
                    ids = [rid for rid, w in self.router_widgets.items() if w.get('parent') is container]
            # Deduplicate and keep order
            seen = set()
            ordered = [rid for rid in ids if (rid not in seen and not seen.add(rid))]
            # Skip re-layout if nothing changed since last layout for this container
            try:
                last_order = getattr(container, '_last_order', None)
                last_cols = getattr(container, '_last_cols', None)
                if last_order == ordered and last_cols == max_cols:
                    return
                container._last_order = ordered
                container._last_cols = max_cols
            except Exception:
                pass
            # Reset grid ONLY for cards we're about to re-grid
            for rid in ordered:
                w = self.router_widgets.get(rid)
                if w and w.get('card') and w['card'].winfo_exists():
                    w['card'].grid_forget()
            # Place cards
            for idx, rid in enumerate(ordered):
                w = self.router_widgets.get(rid)
                if not w:
                    continue
                row, col = divmod(idx, max_cols)
                w['card'].grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
                container.grid_columnconfigure(col, weight=1, uniform="router_cards")
                container.grid_rowconfigure(row, weight=0)
        except Exception:
            pass



    # ------------------------
    # Fetch bandwidth for a router in a separate thread
    def fetch_and_update_bandwidth(self, rid, ip):
        try:
            # Fetch bandwidth data (download/upload + latency)
            # Note: get_bandwidth already performs a dynamic ping and returns 'latency'.
            bw = get_bandwidth(ip)

            # Update the shared bandwidth data dictionary
            if not isinstance(self.bandwidth_data, dict):
                self.bandwidth_data = {}
            self.bandwidth_data[rid] = bw

            # Trigger UI update in the main thread
            self.root.after(0, self._update_bandwidth_label, rid, bw)
        except Exception as e:
            if not isinstance(self.bandwidth_data, dict):
                self.bandwidth_data = {}
            self.bandwidth_data[rid] = None  # Handle errors and mark as None if failed
            print(f"Error fetching bandwidth for {rid}: {e}")

            # Trigger UI update in the main thread with an error message
            self.root.after(0, self._update_bandwidth_label, rid, None)

    def _update_bandwidth_label(self, rid, bandwidth):
        """Update bandwidth label with UNIFIED formatting for both UniFi and non-UniFi devices"""
        # Ensure the router widget exists
        router_widget = self.router_widgets.get(rid)
        if not router_widget:
            return

        # Access the bandwidth label widget and router data
        bw_label = router_widget.get('bandwidth_label')
        if not bw_label or not bw_label.winfo_exists():
            return

        router_data = router_widget.get('data', {})
        is_unifi = router_data.get('is_unifi', False)

        # Check if device is offline
        is_offline = self.status_history.get(rid, {}).get('current') is False

        # Latency cache: store last known latency per AP
        if not hasattr(self, '_latency_cache'):
            self._latency_cache = {}

        # If device is offline, show offline status and clear cache
        if is_offline:
            bw_label.config(text="🔴 Device Offline", bootstyle="danger")
            self._latency_cache[rid] = None
            return

        # Handle bandwidth data - UNIFIED FORMAT FOR ALL DEVICES - ALL BLUE
        if bandwidth is None:
            # Fetch failed - show Not available, clear cache
            bw_label.config(text="📶 Bandwidth: Not available   |   ⚡ --", bootstyle="secondary")
            self._latency_cache[rid] = None
            return

        # Extract bandwidth data
        download = bandwidth.get("download")
        upload = bandwidth.get("upload")
        latency = bandwidth.get("latency")

        # Handle None values - can't fetch bandwidth (device unreachable)
        if download is None or upload is None:
            bw_label.config(text="📶 Bandwidth: Not available   |   ⚡ --", bootstyle="secondary")
            self._latency_cache[rid] = None
            return

        # Update latency cache if valid
        if latency is not None and isinstance(latency, (int, float)):
            self._latency_cache[rid] = latency
        # Use cached latency if available
        cached_latency = self._latency_cache.get(rid)

        # Update bandwidth label with UNIFIED format for all devices - ALL BLUE
        try:
            # UNIFIED FORMAT: "📶 ↓{down} Mbps ↑{up} Mbps   ⚡ {latency} ms" - ALL BLUE (info)
            if cached_latency is not None:
                bw_label.config(
                    text=f"📶 ↓{float(download):.1f} Mbps ↑{float(upload):.1f} Mbps   ⚡ {float(cached_latency):.1f} ms",
                    bootstyle="info"  # ALL BLUE
                )
            else:
                bw_label.config(
                    text=f"📶 ↓{float(download):.1f} Mbps ↑{float(upload):.1f} Mbps   ⚡ N/A",
                    bootstyle="info"  # ALL BLUE
                )
        except Exception as e:
            print(f"Error formatting bandwidth label for router {rid}: {e}")
            bw_label.config(text="⚠ Bandwidth: Format error", bootstyle="warning")



    def _background_status_updater(self):
        while self.app_running:
            with concurrent.futures.ThreadPoolExecutor() as pool:
                futures = {
                    pool.submit(is_online, w['data']['ip_address']): rid
                    for rid, w in self.router_widgets.items()
                }
                for fut in concurrent.futures.as_completed(futures):
                    if not self.app_running:
                        return  # Stop safely
                    rid = futures[fut]
                    online = fut.result()
                    hist = self.status_history[rid]
                    prev = hist['current']
                    if online:
                        hist['failures'] = 0
                        new = True
                    else:
                        hist['failures'] += 1
                        new = False if hist['failures'] >= 3 else prev
                    if new is not prev:
                        hist['current'] = new
                        update_router_status_in_db(rid, new)
                        
                        # Send notification for router status change
                        router_data = self.router_widgets.get(rid, {}).get('data', {})
                        router_name = router_data.get('name', f'Router {rid}')
                        router_ip = router_data.get('ip_address', 'Unknown')
                        
                        # Debug output
                        status_text = "Online" if new else "Offline"
                        safe_emoji_print(f"[ALERT] Router status change: {router_name} ({router_ip}) is now {status_text}")
                        
                        # Create notification in main thread to ensure toast notifications work
                        if self.app_running:
                            self.root.after(0, lambda: self._create_router_notification(router_name, router_ip, new))
                            self.root.after(0, lambda r=rid, s=new: self._update_gui_status(r, s))
                            # Update notification count
                            self.root.after(0, self.update_notification_count)
                            
                            # NEW: Trigger manual loop detection when router goes offline
                            if not new:  # Router is now offline
                                print(f"🔍 Router offline detected - triggering manual loop detection...")
                                self.root.after(0, lambda: self._trigger_loop_detection_on_router_offline(router_name, router_ip))
            # Immediately stop if app closed during processing
            for _ in range(30):  # sleep for 3 seconds total, but check every 0.1s
                if not self.app_running:
                    return
                time.sleep(0.1)

    def _background_bandwidth_updater(self):
        import time
        import concurrent.futures
        while self.app_running:
            # Only ping APs with high latency (>=150ms) or all online UniFi APs
            high_latency_ids = []
            unifi_online_ids = []
            # Use the latency cache to determine which APs to ping
            if not hasattr(self, '_latency_cache'):
                self._latency_cache = {}
            for rid, widget in self.router_widgets.items():
                router = widget.get('data', {})
                is_unifi = router.get('is_unifi', False)
                is_online = self.status_history.get(rid, {}).get('current') is True
                if not is_online:
                    continue
                if is_unifi:
                    unifi_online_ids.append((rid, router.get('ip_address')))
                else:
                    latency = self._latency_cache.get(rid)
                    # Retry if latency is None (N/A) or high
                    if latency is None or (latency is not None and latency >= 150):
                        high_latency_ids.append((rid, router.get('ip_address')))
            # Combine all targets
            targets = high_latency_ids + unifi_online_ids
            if not targets:
                time.sleep(2)
                continue
            # Fetch bandwidth in parallel for selected APs
            with concurrent.futures.ThreadPoolExecutor() as pool:
                futures = [
                    pool.submit(self.fetch_and_update_bandwidth, rid, ip)
                    for rid, ip in targets if ip
                ]
                concurrent.futures.wait(futures, timeout=5)
            time.sleep(2)

    def _update_gui_status(self, rid, online, bandwidth=None):
        if not self.app_running:
            return

        w = self.router_widgets.get(rid)
        if not w:
            return

        # Update status label
        lbl = w['status_label']
        if lbl.winfo_exists():
            lbl.config(
                text="🟢 Online" if online else "🔴 Offline",
                bootstyle="success" if online else "danger"
            )

        # Update card border color based on status and UniFi flag
        card = w.get('card')
        router_data = w.get('data', {})
        if card and card.winfo_exists():
            is_unifi = router_data.get('is_unifi', False)
            if online:
                new_style = "primary" if is_unifi else "success"
            else:
                new_style = "danger"
            try:
                card.configure(bootstyle=new_style)
            except Exception:
                pass

        # Update bandwidth/latency label
        bw_lbl = w.get('bandwidth_label')
        if bw_lbl and bw_lbl.winfo_exists():
            # CRITICAL: Check offline status FIRST to prevent "Checking..." on offline devices
            if not online:
                # Device is offline - show offline status, don't check bandwidth
                bw_lbl.config(text="🔴 Device Offline", bootstyle="danger")
            elif bandwidth is None:
                # Device is online but bandwidth not fetched yet - this should be rare
                # as bandwidth is triggered by online status in background updater
                bw_lbl.config(text="📶 Bandwidth: Not available   |   ⚡ --", bootstyle="secondary")
            else:
                # Device is online and bandwidth data available
                latency = bandwidth.get("latency")
                download = bandwidth.get("download")
                upload = bandwidth.get("upload")

                if latency is not None and download is not None and upload is not None:
                    bw_lbl.config(
                        text=f"📶 ↓{download:.1f} Mbps ↑{upload:.1f} Mbps   ⚡ {latency:.1f} ms",
                        bootstyle="info"
                    )
                else:
                    bw_lbl.config(text="📶 Bandwidth: Not available   |   ⚡ --", bootstyle="secondary")


    def _background_status_updater(self):
        safe_print("[INFO] Starting router status monitoring...")
        while self.app_running:
            try:
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    futures = {
                        pool.submit(is_online, w['data']['ip_address']): rid
                        for rid, w in self.router_widgets.items()
                    }
                    for fut in concurrent.futures.as_completed(futures):
                        if not self.app_running:
                            return  # Stop safely
                        try:
                            rid = futures[fut]
                            online = fut.result()
                            hist = self.status_history[rid]
                            prev = hist['current']
                            if online:
                                hist['failures'] = 0
                                new = True
                            else:
                                hist['failures'] += 1
                                new = False if hist['failures'] >= 3 else prev

                            # Debug output
                            router_data = self.router_widgets.get(rid, {}).get('data', {})
                            router_name = router_data.get('name', f'Router {rid}')
                            # Removed router status print statement

                            # Only update if state changes OR router is online (to refresh bandwidth)
                            if new is not prev or new is True:
                                hist['current'] = new
                                try:
                                    update_router_status_in_db(rid, new)
                                except Exception as db_error:
                                    print(f"⚠️ Failed to update DB for router {router_name}: {str(db_error)}")
                                
                                # Send notification for router status change
                                if new is not prev:
                                    router_data = self.router_widgets.get(rid, {}).get('data', {})
                                    router_name = router_data.get('name', f'Router {rid}')
                                    router_ip = router_data.get('ip_address', 'Unknown')
                                    
                                    # Debug output
                                    status_text = "Online" if new else "Offline"
                                    safe_emoji_print(f"[ALERT] Router status change: {router_name} ({router_ip}) is now {status_text}")
                                    
                                    # Create notification in main thread to ensure toast notifications work
                                    if self.app_running:
                                        self.root.after(0, lambda: self._create_router_notification(router_name, router_ip, new))
                                        self.root.after(0, lambda r=rid, s=new: self._update_gui_status(r, s))
                                        # Update notification count
                                        self.root.after(0, self.update_notification_count)

                            if self.app_running:
                                # fetch bandwidth in a thread if online
                                if new:
                                    threading.Thread(
                                        target=self.fetch_and_update_bandwidth,
                                        args=(rid, self.router_widgets[rid]['data']['ip_address']),
                                        daemon=True
                                    ).start()
                                else:
                                    # just update GUI to offline
                                    self.root.after(0, lambda r=rid, s=new: self._update_gui_status(r, s))
                        except Exception as e:
                            print(f"⚠️ Error processing router status for router {rid}: {str(e)}")
                            continue

            except Exception as e:
                print(f"⚠️ Error in background status updater: {str(e)}")
                # Continue running even if there's an error

            # Immediately stop if app closed during processing
            for _ in range(30):  # sleep for 3 seconds total, but check every 0.1s
                if not self.app_running:
                    return
                time.sleep(0.1)







    def open_user_mgmt(self):
        win = Toplevel(self.root)
        win.title("👥 User Management - Admin Panel")
        win.geometry("900x650")
        win.transient(self.root)
        win.grab_set()
        win.configure(bg='#f0f2f5')
        win.resizable(True, True)

        # Center the window
        self._center_window(win, 900, 650)

        # Main container with modern styling
        main_frame = tb.Frame(win, bootstyle="light")
        main_frame.pack(fill="both", expand=True, padx=15, pady=15)

        # Header section with gradient-like effect
        header_frame = tb.LabelFrame(main_frame, text="", bootstyle="primary", padding=20)
        header_frame.pack(fill="x", pady=(0, 20))
        
        # Title and subtitle
        title_frame = tb.Frame(header_frame)
        title_frame.pack(fill="x", pady=(0, 15))
        
        title_label = tb.Label(title_frame, text="👥 User Management", 
                              font=("Segoe UI", 24, "bold"), bootstyle="primary")
        title_label.pack(side="left")
        
        subtitle_label = tb.Label(title_frame, text="Admin Control Panel", 
                                 font=("Segoe UI", 12), bootstyle="secondary")
        subtitle_label.pack(side="left", padx=(10, 0))
        
        # Search and filter section with modern styling
        search_frame = tb.LabelFrame(header_frame, text="🔍 Search & Filter", bootstyle="info", padding=15)
        search_frame.pack(fill="x")
        
        # Search row
        search_row = tb.Frame(search_frame)
        search_row.pack(fill="x", pady=(0, 10))
        
        tb.Label(search_row, text="Search:", font=("Segoe UI", 11, "bold")).pack(side="left", padx=(0, 8))
        self.user_search_var = tb.StringVar()
        self.user_search_var.trace('w', self._filter_users)
        search_entry = tb.Entry(search_row, textvariable=self.user_search_var, width=25, 
                               font=("Segoe UI", 10), bootstyle="primary")
        search_entry.pack(side="left", padx=(0, 20))
        
        # Role filter row
        role_row = tb.Frame(search_frame)
        role_row.pack(fill="x")
        
        tb.Label(role_row, text="Role Filter:", font=("Segoe UI", 11, "bold")).pack(side="left", padx=(0, 8))
        self.role_filter_var = tb.StringVar(value="All")
        role_combo = tb.Combobox(role_row, textvariable=self.role_filter_var, 
                                values=["All", "admin", "user"], width=12, state="readonly",
                                font=("Segoe UI", 10), bootstyle="primary")
        role_combo.pack(side="left", padx=(0, 20))
        role_combo.bind("<<ComboboxSelected>>", self._filter_users)
        
        # Quick stats
        stats_frame = tb.Frame(search_frame)
        stats_frame.pack(side="right")
        
        self.stats_label = tb.Label(stats_frame, text="", font=("Segoe UI", 10, "bold"), 
                                   bootstyle="success")
        self.stats_label.pack()

        # Control buttons section with modern styling
        controls_frame = tb.LabelFrame(main_frame, text="⚡ Quick Actions", bootstyle="success", padding=15)
        controls_frame.pack(fill="x", pady=(0, 15))
        
        # Primary actions (left side)
        primary_actions = tb.Frame(controls_frame)
        primary_actions.pack(side="left")
        
        tb.Button(primary_actions, text="➕ Add User", bootstyle="success",
                  command=lambda: self._open_add_user(win, self.user_table),
                  width=14).pack(side="left", padx=(0, 8))
        
        tb.Button(primary_actions, text="✏️ Edit User", bootstyle="primary",
                  command=lambda: self._open_edit_user(win, self.user_table),
                  width=14).pack(side="left", padx=(0, 8))
        
        tb.Button(primary_actions, text="🔑 Reset Password", bootstyle="warning",
                  command=lambda: self._reset_user_password(win, self.user_table),
                  width=16).pack(side="left", padx=(0, 8))
        
        tb.Button(primary_actions, text="👁️ View Details", bootstyle="info",
                  command=lambda: self._view_user_details(win, self.user_table),
                  width=16).pack(side="left", padx=(0, 8))
        
        tb.Button(primary_actions, text="📋 Login History", bootstyle="secondary",
                  command=lambda: self._open_login_history(win),
                  width=16).pack(side="left", padx=(0, 8))
        
        # Secondary actions (right side)
        secondary_actions = tb.Frame(controls_frame)
        secondary_actions.pack(side="right")
        
        tb.Button(secondary_actions, text="📊 Bulk Actions", bootstyle="dark",
                  command=lambda: self._open_bulk_actions(win),
                  width=14).pack(side="left", padx=(0, 8))
        
        tb.Button(secondary_actions, text="🗑️ Delete Selected", bootstyle="danger",
                  command=lambda: self._delete_user(self.user_table),
                  width=16).pack(side="left", padx=(0, 8))
        
        tb.Button(secondary_actions, text="🔄 Refresh", bootstyle="secondary",
                  command=lambda: self._refresh_user_table(),
                  width=12).pack(side="left")

        # User table with enhanced styling
        table_container = tb.LabelFrame(main_frame, text="👥 Users List", bootstyle="info", padding=10)
        table_container.pack(fill="both", expand=True, pady=(0, 15))
        
        # Table frame with scrollbars
        table_frame = tb.Frame(table_container)
        table_frame.pack(fill="both", expand=True)
        
        # Create Treeview with modern styling
        cols = ("ID", "First Name", "Last Name", "Username", "Role", "Agent", "Status", "Last Login")
        self.user_table = ttk.Treeview(table_frame, columns=cols, show="headings", height=12)
        
        # Configure columns with better widths
        column_widths = [60, 130, 130, 130, 90, 70, 90, 140]
        for i, (col, width) in enumerate(zip(cols, column_widths)):
            self.user_table.heading(col, text=col, command=lambda c=col: self._sort_users_by_column(c))
            self.user_table.column(col, width=width, anchor="center")
        
        # Style the table
        style = ttk.Style()
        style.configure("Treeview", font=("Segoe UI", 10), rowheight=30)
        style.configure("Treeview.Heading", font=("Segoe UI", 11, "bold"))
        
        # Add scrollbars with modern styling
        v_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.user_table.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.user_table.xview)
        self.user_table.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack table and scrollbars
        self.user_table.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        # Bind mouse wheel scrolling
        def on_mousewheel_vertical(event):
            self.user_table.yview_scroll(int(-1*(event.delta/120)), "units")
            return "break"
        
        def on_mousewheel_horizontal(event):
            self.user_table.xview_scroll(int(-1*(event.delta/120)), "units")
            return "break"
        
        self.user_table.bind("<MouseWheel>", on_mousewheel_vertical)
        self.user_table.bind("<Shift-MouseWheel>", on_mousewheel_horizontal)
        
        # Bind interactions
        self.user_table.bind("<Double-1>", lambda e: self._view_user_details(win, self.user_table))
        self.user_table.bind("<Button-3>", self._show_user_context_menu)
        
        # Add hover effects
        def on_enter(event):
            self.user_table.configure(cursor="hand2")
        def on_leave(event):
            self.user_table.configure(cursor="")
        
        self.user_table.bind("<Enter>", on_enter)
        self.user_table.bind("<Leave>", on_leave)
        
        # Enhanced status bar
        status_frame = tb.LabelFrame(main_frame, text="📊 Status", bootstyle="secondary", padding=10)
        status_frame.pack(fill="x", pady=(0, 10))
        
        # Status information
        status_info = tb.Frame(status_frame)
        status_info.pack(fill="x")
        
        self.user_status_label = tb.Label(status_info, text="🟢 Ready", bootstyle="success", 
                                         font=("Segoe UI", 10, "bold"))
        self.user_status_label.pack(side="left")
        
        # Quick stats
        self.quick_stats_label = tb.Label(status_info, text="", bootstyle="info", 
                                         font=("Segoe UI", 10))
        self.quick_stats_label.pack(side="right")
        
        # Populate table
        self._refresh_user_table()
        
        # Store reference for other methods
        self.user_mgmt_window = win
        
        # Add window close handler
        def on_closing():
            if hasattr(self, 'user_mgmt_window'):
                self.user_mgmt_window = None
            win.destroy()
        
        win.protocol("WM_DELETE_WINDOW", on_closing)


    def _open_add_user(self, parent, table):
        popup = Toplevel(parent)
        popup.title("➕ Add New User")
        popup.geometry("640x600")
        popup.transient(parent)
        popup.grab_set()
        popup.configure(bg='#f0f2f5')
        self._center_window(popup, 640, 600)
        popup.minsize(600, 560)

        # Ensure clean teardown
        def _close():
            try:
                popup.grab_release()
            except Exception:
                pass
            popup.destroy()

        popup.protocol("WM_DELETE_WINDOW", _close)

        # Root layout: header (pack, fixed), scrollable content (pack, expands), footer (pack, fixed)
        header_frame = tb.LabelFrame(popup, text="", bootstyle="success", padding=16)
        header_frame.pack(fill="x", padx=12, pady=(12, 8))

        tb.Label(header_frame, text="➕ Add New User",
                 font=("Segoe UI", 20, "bold"), bootstyle="success").pack()
        tb.Label(header_frame, text="Create a new user account",
                 font=("Segoe UI", 11), bootstyle="secondary").pack(pady=(4, 0))

        # Scrollable content area
        body_container = tb.Frame(popup)
        body_container.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        canvas = tk.Canvas(body_container, highlightthickness=0, bg='#f0f2f5')
        vscroll = tb.Scrollbar(body_container, orient="vertical", command=canvas.yview, bootstyle="secondary")
        canvas.configure(yscrollcommand=vscroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        scroll_frame = tb.Frame(canvas)
        scroll_window = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")

        def _on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Keep inner width equal to canvas width to avoid clipping
            canvas.itemconfigure(scroll_window, width=canvas.winfo_width())

        scroll_frame.bind("<Configure>", _on_configure)
        canvas.bind("<Configure>", _on_configure)
        
        # Bind mouse wheel scrolling to canvas
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            return "break"
        
        canvas.bind("<MouseWheel>", on_mousewheel)
        scroll_frame.bind("<MouseWheel>", on_mousewheel)

        # Form area (grid-based, no pack inside)
        form_frame = tb.LabelFrame(scroll_frame, text="📝 User Information", bootstyle="info", padding=16)
        form_frame.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        form_frame.grid_columnconfigure(0, weight=0)
        form_frame.grid_columnconfigure(1, weight=1)

        fields = [
            ("First Name:", "first_name", False),
            ("Last Name:", "last_name", False),
            ("Username:", "username", False),
            ("Password:", "password", True),
            ("Confirm Password:", "confirm_password", True),
            ("Role:", "role", False),
                ("Enable as Subnet Agent:", "is_agent", False),
        ]

        vars_ = {}
        entries = {}

        for i, (label, field_name, is_password) in enumerate(fields):
            label_text = f"🔹 {label}" if not is_password else f"🔒 {label}"
            tb.Label(form_frame, text=label_text, font=("Segoe UI", 11, "bold"),
                     anchor="w").grid(row=i, column=0, sticky="w", padx=(2, 12), pady=8)

            if field_name == "role":
                # Fixed role: user. Disable dropdown so it can't be changed
                vars_[field_name] = tb.StringVar(value="user")
                widget = tb.Combobox(
                    form_frame,
                    textvariable=vars_[field_name],
                    values=["user"],
                    state="disabled",
                    width=24,
                    font=("Segoe UI", 11),
                    bootstyle="primary"
                )
            elif field_name == "is_agent":
                # Checkbox for agent status
                vars_[field_name] = tb.BooleanVar(value=False)
                widget = tb.Checkbutton(
                    form_frame,
                    text="Allow this user to scan their subnet",
                    variable=vars_[field_name],
                    bootstyle="success-round-toggle"
                )
            else:
                vars_[field_name] = tb.StringVar()
                widget = tb.Entry(
                    form_frame,
                    textvariable=vars_[field_name],
                    show="*" if is_password else None,
                    width=24,
                    font=("Segoe UI", 11),
                    bootstyle="primary"
                )

            widget.grid(row=i, column=1, sticky="ew", pady=8)
            entries[field_name] = widget

        # Password strength indicator (one row under password fields)
        strength_label = tb.Label(form_frame, text="", font=("Segoe UI", 10, "bold"))
        strength_label.grid(row=len(fields), column=0, columnspan=2, sticky="w", pady=(0, 6))

        def check_password_strength():
            password = vars_["password"].get()
            if len(password) < 6:
                strength_label.config(text="❌ Too short (minimum 6 characters)", bootstyle="danger")
            elif len(password) < 8:
                strength_label.config(text="⚠️ Weak password - add more characters", bootstyle="warning")
            elif any(c.isupper() for c in password) and any(c.islower() for c in password) and any(c.isdigit() for c in password):
                strength_label.config(text="✅ Strong password - excellent!", bootstyle="success")
            else:
                strength_label.config(text="⚠️ Medium strength - mix upper/lower/numbers", bootstyle="warning")

        # Trace password updates
        def _trace_cb(*_):
            check_password_strength()
        try:
            vars_["password"].trace_add('write', lambda *_: _trace_cb())
        except Exception:
            # Fallback for older Tk versions
            vars_["password"].trace('w', lambda *_: _trace_cb())

        # Validation function
        def validate_form():
            first = vars_["first_name"].get().strip()
            last = vars_["last_name"].get().strip()
            username = vars_["username"].get().strip()
            password = vars_["password"].get()
            confirm_password = vars_["confirm_password"].get()
            role = vars_["role"].get()

            if not all([first, last, username, password, confirm_password]):
                messagebox.showerror("Error", "All fields are required.")
                return False

            if len(username) < 3:
                messagebox.showerror("Error", "Username must be at least 3 characters long.")
                return False

            if password != confirm_password:
                messagebox.showerror("Error", "Passwords do not match.")
                return False

            if len(password) < 6:
                messagebox.showerror("Error", "Password must be at least 6 characters long.")
                return False

            # Check if username already exists
            from user_utils import get_user_by_username
            if get_user_by_username(username):
                messagebox.showerror("Error", "Username already exists. Please choose a different username.")
                return False

            return True

        def submit():
            if not validate_form():
                return

            first = vars_["first_name"].get().strip()
            last = vars_["last_name"].get().strip()
            username = vars_["username"].get().strip()
            password = vars_["password"].get()
            role = vars_["role"].get()
            is_agent = vars_["is_agent"].get()

            try:
                # Insert user first (existing function does not handle is_agent)
                user_id = insert_user(username, password, first, last, role=role)
                # Update agent status if selected
                if is_agent:
                    try:
                        from user_utils import update_user_agent_status
                        update_user_agent_status(user_id, True)
                    except Exception as agent_err:
                        print(f"Warning: could not set agent status: {agent_err}")
                messagebox.showinfo("Success", f"User '{username}' created successfully with {role} role.")
                # Log activity for user add
                try:
                    from device_utils import get_device_info
                    device_info = get_device_info()
                    log_activity(
                        user_id=self.current_user.get('id'),
                        action='Add User',
                        target=username,
                        ip_address=device_info.get('ip_address')
                    )
                except Exception as log_err:
                    print(f"Error logging user add activity: {log_err}")
                _close()
                self._refresh_user_table()
            except Exception as e:
                messagebox.showerror("Error", f"Could not create user:\n{e}")

        # Footer (fixed)
        footer = tb.Frame(popup)
        footer.pack(fill="x", padx=12, pady=(0, 12))
        tb.Separator(footer, bootstyle="secondary").pack(fill="x", pady=(0, 8))

        btns = tb.Frame(footer)
        btns.pack(fill="x")
        tb.Button(btns, text="❌ Cancel", bootstyle="secondary",
                  command=_close, width=14).pack(side="right")
        tb.Button(btns, text="➕ Create User", bootstyle="success",
                  command=submit, width=16).pack(side="right", padx=(0, 8))

        # Keyboard shortcuts and focus
        def _on_return(event):
            submit()
            return "break"

        def _on_escape(event):
            _close()
            return "break"

        popup.bind("<Return>", _on_return)
        popup.bind("<Escape>", _on_escape)

        # Focus first entry
        first_widget = entries.get("first_name")
        if first_widget and first_widget.winfo_exists():
            first_widget.focus_set()

    def _open_edit_user(self, parent, table):
        sel = table.selection()
        if not sel:
            messagebox.showerror("Error", "Please select a user to edit.")
            return

        user_data = table.item(sel[0])["values"]
        uid = user_data[0]
        first = user_data[1]
        last = user_data[2]
        usern = user_data[3]
        role = user_data[4]
        agent_flag = user_data[5] if len(user_data) > 5 else "No"

        popup = Toplevel(parent)
        popup.title("✏️ Edit User")
        popup.geometry("480x560")
        popup.minsize(480, 560)
        popup.transient(parent)
        popup.grab_set()
        self._center_window(popup, 480, 560)

        header_frame = tb.Frame(popup)
        header_frame.pack(fill="x", padx=20, pady=20)
        tb.Label(header_frame, text="✏️ Edit User", font=("Segoe UI", 16, "bold"), bootstyle="primary").pack()
        tb.Label(header_frame, text=f"Editing: {first} {last} ({usern})", font=("Segoe UI", 10), bootstyle="secondary").pack(pady=(5, 0))

        form_frame = tb.LabelFrame(popup, text="User Information", bootstyle="info", padding=20)
        form_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        fields = [
            ("First Name:", "first_name", False),
            ("Last Name:", "last_name", False),
            ("Username:", "username", False),
            ("New Password:", "password", True),
            ("Confirm Password:", "confirm_password", True),
            ("Role:", "role", False),
            ("Subnet Agent:", "is_agent", False)
        ]

        vars_ = {}
        entries = {}
        for label, field_name, is_password in fields:
            row_frame = tb.Frame(form_frame)
            row_frame.pack(fill="x", pady=8)
            tb.Label(row_frame, text=label, font=("Segoe UI", 10, "bold"), width=15, anchor="w").pack(side="left")
            if field_name == "role":
                vars_[field_name] = tb.StringVar(value=role.lower())
                widget = tb.Combobox(row_frame, textvariable=vars_[field_name], values=["user", "admin"], width=25, state="readonly")
                widget.pack(side="left", padx=(10, 0))
            elif field_name == "is_agent":
                initial_agent = str(agent_flag).lower() in ("yes", "true", "1")
                vars_[field_name] = tb.BooleanVar(value=initial_agent)
                widget = tb.Checkbutton(row_frame, text="Enable subnet scanning", variable=vars_[field_name], bootstyle="info-round-toggle")
                widget.pack(side="left", padx=(10,0))
            else:
                vars_[field_name] = tb.StringVar()
                if field_name in ("first_name", "last_name", "username"):
                    idx_map = {"first_name": 1, "last_name": 2, "username": 3}
                    vars_[field_name].set(user_data[idx_map[field_name]])
                widget = tb.Entry(row_frame, textvariable=vars_[field_name], show="*" if is_password else None, width=30, font=("Segoe UI", 10))
                widget.pack(side="left", padx=(10,0))
            entries[field_name] = widget

        strength_label = tb.Label(form_frame, text="", font=("Segoe UI", 8))
        strength_label.pack(anchor="w", pady=(0, 10))

        def check_password_strength():
            password = vars_["password"].get()
            if not password:
                strength_label.config(text="Leave blank to keep current password", bootstyle="info")
            elif len(password) < 6:
                strength_label.config(text="❌ Too short (minimum 6 characters)", bootstyle="danger")
            elif len(password) < 8:
                strength_label.config(text="⚠️ Weak password", bootstyle="warning")
            elif any(c.isupper() for c in password) and any(c.islower() for c in password) and any(c.isdigit() for c in password):
                strength_label.config(text="✅ Strong password", bootstyle="success")
            else:
                strength_label.config(text="⚠️ Medium strength", bootstyle="warning")

        vars_["password"].trace('w', lambda *args: check_password_strength())

        def validate_form():
            new_first = vars_["first_name"].get().strip()
            new_last = vars_["last_name"].get().strip()
            new_username = vars_["username"].get().strip()
            new_password = vars_["password"].get()
            confirm_password = vars_["confirm_password"].get()
            if not all([new_first, new_last, new_username]):
                messagebox.showerror("Error", "First name, last name, and username are required.")
                return False
            if len(new_username) < 3:
                messagebox.showerror("Error", "Username must be at least 3 characters long.")
                return False
            if new_username != usern:
                from user_utils import get_user_by_username
                if get_user_by_username(new_username):
                    messagebox.showerror("Error", "Username already exists. Please choose a different username.")
                    return False
            if new_password:
                if new_password != confirm_password:
                    messagebox.showerror("Error", "Passwords do not match.")
                    return False
                if len(new_password) < 6:
                    messagebox.showerror("Error", "Password must be at least 6 characters long.")
                    return False
            return True

        def submit_edit():
            if not validate_form():
                return
            new_first = vars_["first_name"].get().strip()
            new_last = vars_["last_name"].get().strip()
            new_username = vars_["username"].get().strip()
            new_password = vars_["password"].get()
            new_is_agent = vars_["is_agent"].get()
            try:
                if new_password:
                    update_user(uid, new_username, new_password, new_first, new_last)
                else:
                    update_user(uid, new_username, None, new_first, new_last)
                try:
                    from user_utils import update_user_agent_status
                    update_user_agent_status(uid, new_is_agent)
                except Exception as agent_err:
                    print(f"Warning: could not update agent status: {agent_err}")
                messagebox.showinfo("Success", f"User '{new_username}' updated successfully.")
                try:
                    from device_utils import get_device_info
                    device_info = get_device_info()
                    log_activity(user_id=self.current_user.get('id'), action='Edit User', target=new_username, ip_address=device_info.get('ip_address'))
                except Exception as log_err:
                    print(f"Error logging user edit activity: {log_err}")
                popup.destroy()
                self._refresh_user_table()
            except Exception as e:
                messagebox.showerror("Error", f"Could not update user:\n{e}")

        button_frame = tb.Frame(popup)
        button_frame.pack(fill="x", padx=20, pady=(0, 12))
        tb.Button(button_frame, text="💾 Save Changes", bootstyle="primary", command=submit_edit, width=15).pack(side="right", padx=(5,0))
        tb.Button(button_frame, text="Cancel", bootstyle="secondary", command=popup.destroy, width=10).pack(side="right")


    def _delete_user(self, table):
        sel = table.selection()
        if not sel:
            messagebox.showwarning("Warning", "Please select a user to delete.")
            return
        
        # Get user details
        user_data = table.item(sel[0])["values"]
        user_id, first_name, last_name, username, role = user_data[:5]
        
        # Prevent admin from deleting themselves
        if hasattr(self, 'current_user') and self.current_user.get('username') == username:
            messagebox.showerror("Error", "You cannot delete your own account.")
            return
        
        # Confirmation dialog with user details
        if messagebox.askyesno("Confirm Deletion", 
                              f"Are you sure you want to delete this user?\n\n"
                              f"Name: {first_name} {last_name}\n"
                              f"Username: {username}\n"
                              f"Role: {role}\n\n"
                              f"This action cannot be undone!"):
            try:
                delete_user(user_id)
                table.delete(sel[0])
                if hasattr(self, 'user_status_label'):
                    self.user_status_label.config(text=f"User '{username}' deleted successfully")
                messagebox.showinfo("Success", f"User '{username}' has been deleted.")
                # Log activity for user delete
                try:
                    from device_utils import get_device_info
                    device_info = get_device_info()
                    log_activity(
                        user_id=self.current_user.get('id'),
                        action='Delete User',
                        target=username,
                        ip_address=device_info.get('ip_address')
                    )
                except Exception as log_err:
                    print(f"Error logging user delete activity: {log_err}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete user: {str(e)}")

    def _refresh_user_table(self):
        """Refresh the user table with current data"""
        if not hasattr(self, 'user_table'):
            return
            
        # Clear existing data
        for item in self.user_table.get_children():
            self.user_table.delete(item)
        
        # Get all users
        users = get_all_users()
        
        # Add users to table
        for user in users:
            # Determine status (simplified - you can enhance this with actual login tracking)
            status = "Active"  # You can implement actual status tracking
            
            # Get actual last login from database
            last_login_dt = get_user_last_login(user["id"])
            if last_login_dt:
                # Format the datetime nicely
                from datetime import datetime
                if isinstance(last_login_dt, datetime):
                    last_login = last_login_dt.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    last_login = str(last_login_dt)
            else:
                last_login = "Never"
            
            self.user_table.insert("", "end", values=(
                user["id"],
                user["first_name"],
                user["last_name"],
                user["username"],
                user["role"].title(),
                ("Yes" if user.get("is_agent") else "No"),
                status,
                last_login
            ))
        
        if hasattr(self, 'user_status_label'):
            self.user_status_label.config(text=f"🟢 Loaded {len(users)} users")
        if hasattr(self, 'quick_stats_label'):
            admin_count = sum(1 for user in users if user['role'] == 'admin')
            user_count = len(users) - admin_count
            self.quick_stats_label.config(text=f"👑 Admins: {admin_count} | 👤 Users: {user_count}")
        if hasattr(self, 'stats_label'):
            self.stats_label.config(text=f"Total: {len(users)} users")

    def _filter_users(self, *args):
        """Filter users based on search and role criteria"""
        if not hasattr(self, 'user_table'):
            return
            
        search_term = self.user_search_var.get().lower()
        role_filter = self.role_filter_var.get()
        
        # Clear current selection
        self.user_table.selection_remove(self.user_table.selection())
        
        # Get all users
        users = get_all_users()
        filtered_count = 0
        
        # Clear table
        for item in self.user_table.get_children():
            self.user_table.delete(item)
        
        # Filter and add users
        for user in users:
            # Apply role filter
            if role_filter != "All" and user["role"] != role_filter:
                continue
                
            # Apply search filter
            if search_term:
                searchable_text = f"{user['first_name']} {user['last_name']} {user['username']}".lower()
                if search_term not in searchable_text:
                    continue
            
            # Determine status
            status = "Active"
            
            # Get actual last login from database
            last_login_dt = get_user_last_login(user["id"])
            if last_login_dt:
                # Format the datetime nicely
                from datetime import datetime
                if isinstance(last_login_dt, datetime):
                    last_login = last_login_dt.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    last_login = str(last_login_dt)
            else:
                last_login = "Never"
            
            self.user_table.insert("", "end", values=(
                user["id"],
                user["first_name"],
                user["last_name"],
                user["username"],
                user["role"].title(),
                status,
                last_login
            ))
            filtered_count += 1
        
        if hasattr(self, 'user_status_label'):
            self.user_status_label.config(text=f"🔍 Showing {filtered_count} users")
        if hasattr(self, 'quick_stats_label'):
            admin_count = sum(1 for user in users if user['role'] == 'admin' and 
                            (role_filter == "All" or user['role'] == role_filter) and
                            (not search_term or search_term in f"{user['first_name']} {user['last_name']} {user['username']}".lower()))
            user_count = filtered_count - admin_count
            self.quick_stats_label.config(text=f"👑 Admins: {admin_count} | 👤 Users: {user_count}")
        if hasattr(self, 'stats_label'):
            self.stats_label.config(text=f"Filtered: {filtered_count} users")

    def _sort_users_by_column(self, col):
        """Sort users by the specified column"""
        if not hasattr(self, 'user_table'):
            return
            
        # Get all items and their values
        items = [(self.user_table.set(child, col), child) for child in self.user_table.get_children('')]
        
        # Sort items
        items.sort(key=lambda x: x[0].lower() if isinstance(x[0], str) else x[0])
        
        # Reorder items in the treeview
        for index, (val, child) in enumerate(items):
            self.user_table.move(child, '', index)

    def _show_user_context_menu(self, event):
        """Show context menu for user table"""
        if not hasattr(self, 'user_table'):
            return
            
        # Select the item under the cursor
        item = self.user_table.identify_row(event.y)
        if item:
            self.user_table.selection_set(item)
            
            # Create context menu
            context_menu = tk.Menu(self.user_mgmt_window, tearoff=0)
            context_menu.add_command(label="👁️ View Details", 
                                   command=lambda: self._view_user_details(self.user_mgmt_window, self.user_table))
            context_menu.add_command(label="✏️ Edit User", 
                                   command=lambda: self._open_edit_user(self.user_mgmt_window, self.user_table))
            context_menu.add_command(label="🔑 Reset Password", 
                                   command=lambda: self._reset_user_password(self.user_mgmt_window, self.user_table))
            context_menu.add_separator()
            context_menu.add_command(label="🗑️ Delete User", 
                                   command=lambda: self._delete_user(self.user_table))
            
            # Show context menu
            try:
                context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                context_menu.grab_release()

    def _reset_user_password(self, parent, table):
        """Reset user password"""
        sel = table.selection()
        if not sel:
            messagebox.showwarning("Warning", "Please select a user to reset password.")
            return
        
        user_data = table.item(sel[0])["values"]
        user_id, first_name, last_name, username = user_data[:4]
        
        # Create password reset dialog
        reset_win = Toplevel(parent)
        reset_win.title("Reset Password")
        reset_win.geometry("400x250")
        reset_win.transient(parent)
        reset_win.grab_set()
        self._center_window(reset_win, 400, 250)
        
        # Header
        header_frame = tb.Frame(reset_win)
        header_frame.pack(fill="x", padx=20, pady=20)
        
        tb.Label(header_frame, text="🔑 Reset Password", 
                font=("Segoe UI", 14, "bold"), bootstyle="warning").pack()
        
        tb.Label(header_frame, text=f"User: {first_name} {last_name} ({username})", 
                font=("Segoe UI", 10), bootstyle="secondary").pack(pady=(5, 0))
        
        # Password input
        password_frame = tb.Frame(reset_win)
        password_frame.pack(fill="x", padx=20, pady=10)
        
        tb.Label(password_frame, text="New Password:", font=("Segoe UI", 10)).pack(anchor="w")
        new_password_var = tb.StringVar()
        new_password_entry = tb.Entry(password_frame, textvariable=new_password_var, 
                                    show="*", width=30, font=("Segoe UI", 10))
        new_password_entry.pack(fill="x", pady=(5, 0))
        
        # Confirm password input
        tb.Label(password_frame, text="Confirm Password:", font=("Segoe UI", 10)).pack(anchor="w", pady=(10, 0))
        confirm_password_var = tb.StringVar()
        confirm_password_entry = tb.Entry(password_frame, textvariable=confirm_password_var, 
                                        show="*", width=30, font=("Segoe UI", 10))
        confirm_password_entry.pack(fill="x", pady=(5, 0))
        
        # Password strength indicator
        strength_label = tb.Label(password_frame, text="", font=("Segoe UI", 8))
        strength_label.pack(anchor="w", pady=(2, 0))
        
        def check_password_strength():
            password = new_password_var.get()
            if len(password) < 6:
                strength_label.config(text="❌ Too short (minimum 6 characters)", bootstyle="danger")
            elif len(password) < 8:
                strength_label.config(text="⚠️ Weak password", bootstyle="warning")
            elif any(c.isupper() for c in password) and any(c.islower() for c in password) and any(c.isdigit() for c in password):
                strength_label.config(text="✅ Strong password", bootstyle="success")
            else:
                strength_label.config(text="⚠️ Medium strength", bootstyle="warning")
        
        new_password_var.trace('w', lambda *args: check_password_strength())
        
        # Buttons
        button_frame = tb.Frame(reset_win)
        button_frame.pack(fill="x", padx=20, pady=20)
        
        def reset_password():
            new_pw = new_password_var.get()
            confirm_pw = confirm_password_var.get()
            
            if not new_pw:
                messagebox.showerror("Error", "Please enter a new password.")
                return
            
            if new_pw != confirm_pw:
                messagebox.showerror("Error", "Passwords do not match.")
                return
            
            if len(new_pw) < 6:
                messagebox.showerror("Error", "Password must be at least 6 characters long.")
                return
            
            try:
                # Update user password
                from user_utils import update_user
                update_user(user_id, username, new_pw, first_name, last_name)
                messagebox.showinfo("Success", f"Password for '{username}' has been reset successfully.")
                reset_win.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to reset password: {str(e)}")
        
        tb.Button(button_frame, text="Reset Password", bootstyle="warning", 
                 command=reset_password, width=15).pack(side="right", padx=(5, 0))
        tb.Button(button_frame, text="Cancel", bootstyle="secondary", 
                 command=reset_win.destroy, width=10).pack(side="right")

    def _view_user_details(self, parent, table):
        """View detailed user information"""
        sel = table.selection()
        if not sel:
            messagebox.showwarning("Warning", "Please select a user to view details.")
            return
        
        user_data = table.item(sel[0])["values"]
        user_id = user_data[0]
        
        # Get full user details
        from user_utils import get_user_by_username
        user = get_user_by_username(user_data[3])  # username is at index 3
        
        if not user:
            messagebox.showerror("Error", "User not found.")
            return
        
        # Create details window
        details_win = Toplevel(parent)
        details_win.title("User Details")
        details_win.geometry("500x400")
        details_win.transient(parent)
        details_win.grab_set()
        self._center_window(details_win, 500, 400)
        
        # Header
        header_frame = tb.Frame(details_win)
        header_frame.pack(fill="x", padx=20, pady=20)
        
        tb.Label(header_frame, text="👤 User Details", 
                font=("Segoe UI", 16, "bold"), bootstyle="primary").pack()
        
        # Details frame
        details_frame = tb.LabelFrame(details_win, text="User Information", bootstyle="info", padding=20)
        details_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Get last login information
        from db import get_user_last_login_info
        last_login_info = None
        try:
            last_login_info = get_user_last_login_info(user["id"])
        except Exception as e:
            print(f"Error getting last login info: {e}")
            last_login_info = None
        
        # Format last login information
        if last_login_info:
            device_ip = last_login_info.get('device_ip', 'Unknown')
            device_mac = last_login_info.get('device_mac', 'Unknown')
            last_login_display = f"{device_ip} | {device_mac}"
        else:
            last_login_display = "No login data available"

        # User information
        info_items = [
            ("User ID:", str(user["id"])),
            ("First Name:", user["first_name"]),
            ("Last Name:", user["last_name"]),
            ("Username:", user["username"]),
            ("Role:", user["role"].title()),
            ("Account Status:", "Active"),
            ("Last Login:", last_login_display),
        ]
        
        for i, (label, value) in enumerate(info_items):
            row_frame = tb.Frame(details_frame)
            row_frame.pack(fill="x", pady=2)
            
            tb.Label(row_frame, text=label, font=("Segoe UI", 10, "bold"), 
                    width=15, anchor="w").pack(side="left")
            tb.Label(row_frame, text=value, font=("Segoe UI", 10), 
                    bootstyle="secondary").pack(side="left", padx=(10, 0))
        
        # Action buttons
        button_frame = tb.Frame(details_win)
        button_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        tb.Button(button_frame, text="✏️ Edit User", bootstyle="primary",
                 command=lambda: [details_win.destroy(), self._open_edit_user(parent, table)],
                 width=12).pack(side="left", padx=(0, 5))
        
        tb.Button(button_frame, text="🔑 Reset Password", bootstyle="warning",
                 command=lambda: [details_win.destroy(), self._reset_user_password(parent, table)],
                 width=15).pack(side="left", padx=(0, 5))
        
        tb.Button(button_frame, text="📋 Login History", bootstyle="info",
                 command=lambda: self._view_user_login_history(user, details_win),
                 width=15).pack(side="left", padx=(0, 5))
        
        tb.Button(button_frame, text="Close", bootstyle="secondary",
                 command=details_win.destroy, width=10).pack(side="right")

    def _view_user_login_history(self, user, parent):
        """View login history for a specific user"""
        from db import get_user_login_history
        
        # Create login history window
        history_win = Toplevel(parent)
        history_win.title(f"Login History - {user['username']}")
        history_win.geometry("1000x600")
        history_win.transient(parent)
        history_win.grab_set()
        history_win.configure(bg='#f0f2f5')
        history_win.resizable(True, True)

        # Center the window
        self._center_window(history_win, 1000, 600)

        # Main container
        main_frame = tb.Frame(history_win, bootstyle="light")
        main_frame.pack(fill="both", expand=True, padx=15, pady=15)

        # Header section
        header_frame = tb.LabelFrame(main_frame, text="", bootstyle="primary", padding=20)
        header_frame.pack(fill="x", pady=(0, 20))
        
        # Title and subtitle
        title_frame = tb.Frame(header_frame)
        title_frame.pack(fill="x", pady=(0, 15))
        
        title_label = tb.Label(title_frame, text=f"📋 Login History", 
                              font=("Segoe UI", 24, "bold"), bootstyle="primary")
        title_label.pack(side="left")
        
        subtitle_label = tb.Label(title_frame, text=f"User: {user['first_name']} {user['last_name']} ({user['username']})", 
                                 font=("Segoe UI", 12), bootstyle="secondary")
        subtitle_label.pack(side="left", padx=(10, 0))

        # Controls section
        controls_frame = tb.LabelFrame(header_frame, text="🔍 Controls", bootstyle="info", padding=15)
        controls_frame.pack(fill="x", pady=(10, 0))
        
        # Control buttons
        control_row = tb.Frame(controls_frame)
        control_row.pack(fill="x")
        
        tb.Button(control_row, text="🔄 Refresh", bootstyle="success",
                  command=lambda: self._refresh_user_login_history(user["id"]), width=12).pack(side="left", padx=(0, 8))
        
        tb.Button(control_row, text="📊 Export CSV", bootstyle="info",
                  command=lambda: self._export_user_login_history(user, history_win), width=14).pack(side="left", padx=(0, 8))
        
        # Stats display
        self.user_login_stats_label = tb.Label(control_row, text="", font=("Segoe UI", 10, "bold"), 
                                              bootstyle="success")
        self.user_login_stats_label.pack(side="right")

        # Login sessions table
        table_container = tb.LabelFrame(main_frame, text="📊 Login Sessions", bootstyle="info", padding=10)
        table_container.pack(fill="both", expand=True, pady=(0, 15))
        
        # Table frame with scrollbars
        table_frame = tb.Frame(table_container)
        table_frame.pack(fill="both", expand=True)
        
        # Create Treeview with columns
        cols = ("ID", "Device IP", "Device MAC", "Hostname", "Platform", 
                "Login Time", "Logout Time", "Duration", "Status", "Type")
        self.user_login_table = ttk.Treeview(table_frame, columns=cols, show="headings", height=12)
        
        # Configure columns
        column_widths = [50, 100, 120, 120, 80, 140, 140, 80, 80, 60]
        for i, (col, width) in enumerate(zip(cols, column_widths)):
            self.user_login_table.heading(col, text=col, command=lambda c=col: self._sort_user_login_by_column(c))
            self.user_login_table.column(col, width=width, anchor="center")
        
        # Style the table
        style = ttk.Style()
        style.configure("Treeview", font=("Segoe UI", 9), rowheight=25)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        
        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.user_login_table.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.user_login_table.xview)
        self.user_login_table.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack table and scrollbars
        self.user_login_table.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        # Bind mouse wheel scrolling
        def on_mousewheel_vertical(event):
            self.user_login_table.yview_scroll(int(-1*(event.delta/120)), "units")
            return "break"
        
        def on_mousewheel_horizontal(event):
            self.user_login_table.xview_scroll(int(-1*(event.delta/120)), "units")
            return "break"
        
        self.user_login_table.bind("<MouseWheel>", on_mousewheel_vertical)
        self.user_login_table.bind("<Shift-MouseWheel>", on_mousewheel_horizontal)
        
        # Bind interactions
        self.user_login_table.bind("<Double-1>", lambda e: self._view_user_login_details())
        
        # Add hover effects
        def on_enter(event):
            self.user_login_table.configure(cursor="hand2")
        def on_leave(event):
            self.user_login_table.configure(cursor="")
        
        self.user_login_table.bind("<Enter>", on_enter)
        self.user_login_table.bind("<Leave>", on_leave)
        
        # Status bar
        status_frame = tb.LabelFrame(main_frame, text="📊 Status", bootstyle="secondary", padding=10)
        status_frame.pack(fill="x", pady=(0, 10))
        
        self.user_login_status_label = tb.Label(status_frame, text="🟢 Loading login history...", 
                                               bootstyle="success", font=("Segoe UI", 10, "bold"))
        self.user_login_status_label.pack(side="left")
        
        # Store reference
        self.user_login_history_window = history_win
        self.current_user_for_login_history = user
        
        # Load initial data
        self._refresh_user_login_history(user["id"])
        
        # Add window close handler
        def on_closing():
            if hasattr(self, 'user_login_history_window'):
                self.user_login_history_window = None
            history_win.destroy()
        
        history_win.protocol("WM_DELETE_WINDOW", on_closing)

    def _refresh_user_login_history(self, user_id):
        """Refresh the user login history table"""
        try:
            from db import get_user_login_history
            
            # Clear existing items
            for item in self.user_login_table.get_children():
                self.user_login_table.delete(item)
            
            # Get login sessions for this user
            sessions = get_user_login_history(user_id, limit=100)
            
            # Populate table
            for session in sessions:
                # Format data for display
                login_time = session.get('login_timestamp', '')
                if login_time:
                    if isinstance(login_time, str):
                        login_time = login_time[:19]  # Remove microseconds
                    else:
                        login_time = login_time.strftime('%Y-%m-%d %H:%M:%S')
                
                logout_time = session.get('logout_timestamp', '')
                if logout_time:
                    if isinstance(logout_time, str):
                        logout_time = logout_time[:19]
                    else:
                        logout_time = logout_time.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    logout_time = "Active"
                
                duration = session.get('session_duration_seconds', 0)
                if duration:
                    hours = duration // 3600
                    minutes = (duration % 3600) // 60
                    duration_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                else:
                    duration_str = "Active" if session.get('is_active') else "N/A"
                
                status = "🟢 Active" if session.get('is_active') else "🔴 Completed"
                login_type = session.get('login_type', 'client').title()
                
                # Insert into table
                self.user_login_table.insert("", "end", values=(
                    session.get('id', ''),
                    session.get('device_ip', 'Unknown'),
                    session.get('device_mac', 'Unknown'),
                    session.get('device_hostname', 'Unknown'),
                    session.get('device_platform', 'Unknown'),
                    login_time,
                    logout_time,
                    duration_str,
                    status,
                    login_type
                ))
            
            # Update stats
            total_sessions = len(sessions)
            active_sessions = len([s for s in sessions if s.get('is_active')])
            self.user_login_stats_label.config(text=f"Total: {total_sessions} | Active: {active_sessions}")
            self.user_login_status_label.config(text=f"🟢 Loaded {total_sessions} login sessions")
            
        except Exception as e:
            print(f"Error refreshing user login history: {e}")
            self.user_login_status_label.config(text=f"🔴 Error loading login history: {str(e)}")

    def _sort_user_login_by_column(self, col):
        """Sort user login history by column"""
        # This is a placeholder - you can implement sorting logic here
        pass

    def _view_user_login_details(self):
        """View detailed information about a selected user login session"""
        selection = self.user_login_table.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a login session to view details.")
            return
        
        item = self.user_login_table.item(selection[0])
        values = item['values']
        
        # Create details window
        details_win = Toplevel(self.user_login_history_window)
        details_win.title("Login Session Details")
        details_win.geometry("500x400")
        details_win.transient(self.user_login_history_window)
        details_win.grab_set()
        details_win.configure(bg='#f0f2f5')
        
        # Center the window
        self._center_window(details_win, 500, 400)
        
        # Main container
        main_frame = tb.Frame(details_win, bootstyle="light")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        header_frame = tb.LabelFrame(main_frame, text="📋 Login Session Details", 
                                    bootstyle="primary", padding=15)
        header_frame.pack(fill="x", pady=(0, 15))
        
        # Details
        details_text = f"""
Session ID: {values[0]}
Device IP: {values[1]}
Device MAC: {values[2]}
Hostname: {values[3]}
Platform: {values[4]}
Login Time: {values[5]}
Logout Time: {values[6]}
Duration: {values[7]}
Status: {values[8]}
Type: {values[9]}
        """
        
        details_label = tb.Label(header_frame, text=details_text.strip(), 
                                font=("Segoe UI", 11), justify="left")
        details_label.pack(anchor="w")
        
        # Close button
        tb.Button(main_frame, text="Close", bootstyle="primary", 
                 command=details_win.destroy, width=15).pack(pady=(15, 0))

    def _export_user_login_history(self, user, parent):
        """Export user login history to CSV"""
        try:
            import csv
            from tkinter import filedialog
            from datetime import datetime
            
            # Get save location
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title=f"Export Login History - {user['username']}"
            )
            
            if filename:
                # Get all data from table
                data = []
                for item in self.user_login_table.get_children():
                    values = self.user_login_table.item(item)['values']
                    data.append({
                        'ID': values[0],
                        'Device IP': values[1],
                        'Device MAC': values[2],
                        'Hostname': values[3],
                        'Platform': values[4],
                        'Login Time': values[5],
                        'Logout Time': values[6],
                        'Duration': values[7],
                        'Status': values[8],
                        'Type': values[9]
                    })
                
                # Write to CSV
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ['ID', 'Device IP', 'Device MAC', 'Hostname', 'Platform', 
                                 'Login Time', 'Logout Time', 'Duration', 'Status', 'Type']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    
                    writer.writeheader()
                    for row in data:
                        writer.writerow(row)
                
                messagebox.showinfo("Success", f"Login history exported to {filename}")
                self.user_login_status_label.config(text=f"Exported {len(data)} login sessions to CSV")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export login history: {str(e)}")

    def _open_bulk_actions(self, parent):
        """Open bulk actions dialog"""
        bulk_win = Toplevel(parent)
        bulk_win.title("Bulk Actions")
        bulk_win.geometry("400x300")
        bulk_win.transient(parent)
        bulk_win.grab_set()
        self._center_window(bulk_win, 400, 300)
        
        # Header
        header_frame = tb.Frame(bulk_win)
        header_frame.pack(fill="x", padx=20, pady=20)
        
        tb.Label(header_frame, text="📊 Bulk Actions", 
                font=("Segoe UI", 16, "bold"), bootstyle="primary").pack()
        
        # Actions frame
        actions_frame = tb.LabelFrame(bulk_win, text="Select Action", bootstyle="info", padding=20)
        actions_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Bulk action options
        action_var = tb.StringVar()
        
        actions = [
            ("Change Role to Admin", "change_role_admin"),
            ("Change Role to User", "change_role_user"),
            ("Delete Selected Users", "delete_selected"),
            ("Export User List", "export_users"),
        ]
        
        for i, (text, value) in enumerate(actions):
            tb.Radiobutton(actions_frame, text=text, variable=action_var, 
                          value=value, bootstyle="primary").pack(anchor="w", pady=2)
        
        # Buttons
        button_frame = tb.Frame(bulk_win)
        button_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        def execute_bulk_action():
            action = action_var.get()
            if not action:
                messagebox.showwarning("Warning", "Please select an action.")
                return
            
            if action == "export_users":
                self._export_users()
                bulk_win.destroy()
            else:
                messagebox.showinfo("Info", f"Bulk action '{action}' selected. This feature can be implemented based on your specific requirements.")
                bulk_win.destroy()
        
        tb.Button(button_frame, text="Execute", bootstyle="primary",
                 command=execute_bulk_action, width=12).pack(side="right", padx=(5, 0))
        tb.Button(button_frame, text="Cancel", bootstyle="secondary",
                 command=bulk_win.destroy, width=10).pack(side="right")

    def _export_users(self):
        """Export user list to CSV"""
        try:
            import csv
            from tkinter import filedialog
            
            # Get save location
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Export Users"
            )
            
            if filename:
                users = get_all_users()
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ['ID', 'First Name', 'Last Name', 'Username', 'Role']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    
                    writer.writeheader()
                    for user in users:
                        writer.writerow({
                            'ID': user['id'],
                            'First Name': user['first_name'],
                            'Last Name': user['last_name'],
                            'Username': user['username'],
                            'Role': user['role']
                        })
                
                messagebox.showinfo("Success", f"Users exported to {filename}")
                if hasattr(self, 'user_status_label'):
                    self.user_status_label.config(text=f"Exported {len(users)} users to CSV")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export users: {str(e)}")

    def _open_login_history(self, parent):
        """Open comprehensive login history window for all users"""
        from db import get_all_login_sessions
        
        login_win = Toplevel(parent)
        login_win.title("📋 Login History - Admin Panel")
        login_win.geometry("1200x700")
        login_win.transient(parent)
        login_win.grab_set()
        login_win.configure(bg='#f0f2f5')
        login_win.resizable(True, True)

        # Center the window
        self._center_window(login_win, 1200, 700)

        # Main container with modern styling
        main_frame = tb.Frame(login_win, bootstyle="light")
        main_frame.pack(fill="both", expand=True, padx=15, pady=15)

        # Header section
        header_frame = tb.LabelFrame(main_frame, text="", bootstyle="primary", padding=20)
        header_frame.pack(fill="x", pady=(0, 20))
        
        # Title and subtitle
        title_frame = tb.Frame(header_frame)
        title_frame.pack(fill="x", pady=(0, 15))
        
        title_label = tb.Label(title_frame, text="📋 Login History", 
                              font=("Segoe UI", 24, "bold"), bootstyle="primary")
        title_label.pack(side="left")
        
        subtitle_label = tb.Label(title_frame, text="All User Sessions", 
                                 font=("Segoe UI", 12), bootstyle="secondary")
        subtitle_label.pack(side="left", padx=(10, 0))

        # Controls section
        controls_frame = tb.LabelFrame(header_frame, text="🔍 Filters & Controls", bootstyle="info", padding=15)
        controls_frame.pack(fill="x", pady=(10, 0))
        
        # Filter controls row
        filter_row = tb.Frame(controls_frame)
        filter_row.pack(fill="x", pady=(0, 10))
        
        # User filter
        tb.Label(filter_row, text="User:", font=("Segoe UI", 11, "bold")).pack(side="left", padx=(0, 8))
        self.login_user_filter_var = tb.StringVar(value="All Users")
        user_combo = tb.Combobox(filter_row, textvariable=self.login_user_filter_var, 
                                values=["All Users"], width=15, state="readonly",
                                font=("Segoe UI", 10), bootstyle="primary")
        user_combo.pack(side="left", padx=(0, 20))
        
        # Login type filter
        tb.Label(filter_row, text="Type:", font=("Segoe UI", 11, "bold")).pack(side="left", padx=(0, 8))
        self.login_type_filter_var = tb.StringVar(value="All Types")
        type_combo = tb.Combobox(filter_row, textvariable=self.login_type_filter_var, 
                                values=["All Types", "admin", "client"], width=12, state="readonly",
                                font=("Segoe UI", 10), bootstyle="primary")
        type_combo.pack(side="left", padx=(0, 20))
        
        # Status filter
        tb.Label(filter_row, text="Status:", font=("Segoe UI", 11, "bold")).pack(side="left", padx=(0, 8))
        self.login_status_filter_var = tb.StringVar(value="All Sessions")
        status_combo = tb.Combobox(filter_row, textvariable=self.login_status_filter_var, 
                                  values=["All Sessions", "Active Only", "Completed Only"], width=15, state="readonly",
                                  font=("Segoe UI", 10), bootstyle="primary")
        status_combo.pack(side="left", padx=(0, 20))
        
        # Date range filter
        tb.Label(filter_row, text="Days:", font=("Segoe UI", 11, "bold")).pack(side="left", padx=(0, 8))
        self.login_days_filter_var = tb.StringVar(value="Last 30 Days")
        days_combo = tb.Combobox(filter_row, textvariable=self.login_days_filter_var, 
                                values=["Last 7 Days", "Last 30 Days", "Last 90 Days", "All Time"], width=15, state="readonly",
                                font=("Segoe UI", 10), bootstyle="primary")
        days_combo.pack(side="left", padx=(0, 20))
        
        # Action buttons row
        action_row = tb.Frame(controls_frame)
        action_row.pack(fill="x")
        
        tb.Button(action_row, text="🔄 Refresh", bootstyle="success",
                  command=lambda: self._refresh_login_history(), width=12).pack(side="left", padx=(0, 8))
        
        tb.Button(action_row, text="📊 Export CSV", bootstyle="info",
                  command=lambda: self._export_login_history(), width=14).pack(side="left", padx=(0, 8))
        
        tb.Button(action_row, text="🗑️ Clear Old", bootstyle="warning",
                  command=lambda: self._clear_old_login_sessions(), width=14).pack(side="left", padx=(0, 8))
        
        # Stats display
        self.login_stats_label = tb.Label(action_row, text="", font=("Segoe UI", 10, "bold"), 
                                         bootstyle="success")
        self.login_stats_label.pack(side="right")

        # Login sessions table
        table_container = tb.LabelFrame(main_frame, text="📊 Login Sessions", bootstyle="info", padding=10)
        table_container.pack(fill="both", expand=True, pady=(0, 15))
        
        # Table frame with scrollbars
        table_frame = tb.Frame(table_container)
        table_frame.pack(fill="both", expand=True)
        
        # Create Treeview with comprehensive columns
        cols = ("ID", "User", "Username", "Device IP", "Device MAC", "Hostname", "Platform", 
                "Login Time", "Logout Time", "Duration", "Status", "Type")
        self.login_table = ttk.Treeview(table_frame, columns=cols, show="headings", height=15)
        
        # Configure columns with appropriate widths
        column_widths = [50, 120, 100, 100, 120, 120, 80, 140, 140, 80, 80, 60]
        for i, (col, width) in enumerate(zip(cols, column_widths)):
            self.login_table.heading(col, text=col, command=lambda c=col: self._sort_login_by_column(c))
            self.login_table.column(col, width=width, anchor="center")
        
        # Style the table
        style = ttk.Style()
        style.configure("Treeview", font=("Segoe UI", 9), rowheight=25)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        
        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.login_table.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.login_table.xview)
        self.login_table.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack table and scrollbars
        self.login_table.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        # Bind mouse wheel scrolling
        def on_mousewheel_vertical(event):
            self.login_table.yview_scroll(int(-1*(event.delta/120)), "units")
            return "break"
        
        def on_mousewheel_horizontal(event):
            self.login_table.xview_scroll(int(-1*(event.delta/120)), "units")
            return "break"
        
        self.login_table.bind("<MouseWheel>", on_mousewheel_vertical)
        self.login_table.bind("<Shift-MouseWheel>", on_mousewheel_horizontal)
        
        # Bind interactions
        self.login_table.bind("<Double-1>", lambda e: self._view_login_details())
        self.login_table.bind("<Button-3>", self._show_login_context_menu)
        
        # Add hover effects
        def on_enter(event):
            self.login_table.configure(cursor="hand2")
        def on_leave(event):
            self.login_table.configure(cursor="")
        
        self.login_table.bind("<Enter>", on_enter)
        self.login_table.bind("<Leave>", on_leave)
        
        # Bind filter changes
        user_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_login_history())
        type_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_login_history())
        status_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_login_history())
        days_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_login_history())
        
        # Status bar
        status_frame = tb.LabelFrame(main_frame, text="📊 Status", bootstyle="secondary", padding=10)
        status_frame.pack(fill="x", pady=(0, 10))
        
        self.login_status_label = tb.Label(status_frame, text="🟢 Loading login history...", 
                                          bootstyle="success", font=("Segoe UI", 10, "bold"))
        self.login_status_label.pack(side="left")
        
        # Store reference
        self.login_history_window = login_win
        
        # Load initial data
        self._load_user_list_for_filter()
        self._refresh_login_history()
        
        # Add window close handler
        def on_closing():
            if hasattr(self, 'login_history_window'):
                self.login_history_window = None
            login_win.destroy()
        
        login_win.protocol("WM_DELETE_WINDOW", on_closing)

    def _load_user_list_for_filter(self):
        """Load user list for the filter dropdown"""
        try:
            from user_utils import get_all_users
            users = get_all_users()
            
            # Update the combobox values
            user_values = ["All Users"]
            for user in users:
                display_name = f"{user['first_name']} {user['last_name']} ({user['username']})"
                user_values.append(display_name)
            
            # Find the combobox and update its values
            for child in self.login_history_window.winfo_children():
                if isinstance(child, tb.Frame):
                    for grandchild in child.winfo_children():
                        if isinstance(grandchild, tb.LabelFrame):
                            for great_grandchild in grandchild.winfo_children():
                                if isinstance(great_grandchild, tb.Frame):
                                    for widget in great_grandchild.winfo_children():
                                        if isinstance(widget, tb.Combobox) and widget.cget('width') == 15:
                                            widget['values'] = user_values
                                            break
        except Exception as e:
            print(f"Error loading user list: {e}")

    def _refresh_login_history(self):
        """Refresh the login history table with current filters"""
        try:
            from db import get_all_login_sessions
            from datetime import datetime, timedelta
            
            # Clear existing items
            for item in self.login_table.get_children():
                self.login_table.delete(item)
            
            # Get filter values
            user_filter = self.login_user_filter_var.get()
            type_filter = self.login_type_filter_var.get()
            status_filter = self.login_status_filter_var.get()
            days_filter = self.login_days_filter_var.get()
            
            # Calculate date range
            if days_filter == "Last 7 Days":
                days = 7
            elif days_filter == "Last 30 Days":
                days = 30
            elif days_filter == "Last 90 Days":
                days = 90
            else:
                days = None
            
            # Get login sessions
            if days:
                # For date filtering, we'll need to implement this in the database function
                sessions = get_all_login_sessions(limit=1000)
                cutoff_date = datetime.now() - timedelta(days=days)
                sessions = [s for s in sessions if s['login_timestamp'] and 
                           datetime.fromisoformat(str(s['login_timestamp']).replace('Z', '+00:00')) >= cutoff_date]
            else:
                sessions = get_all_login_sessions(limit=1000)
            
            # Apply filters
            filtered_sessions = []
            for session in sessions:
                # User filter
                if user_filter != "All Users":
                    user_display = f"{session.get('first_name', '')} {session.get('last_name', '')} ({session.get('username', '')})"
                    if user_display != user_filter:
                        continue
                
                # Type filter
                if type_filter != "All Types" and session.get('login_type') != type_filter:
                    continue
                
                # Status filter
                if status_filter == "Active Only" and not session.get('is_active'):
                    continue
                elif status_filter == "Completed Only" and session.get('is_active'):
                    continue
                
                filtered_sessions.append(session)
            
            # Populate table
            for session in filtered_sessions:
                # Format data for display
                user_name = f"{session.get('first_name', '')} {session.get('last_name', '')}".strip()
                if not user_name:
                    user_name = session.get('username', 'Unknown')
                
                login_time = session.get('login_timestamp', '')
                if login_time:
                    if isinstance(login_time, str):
                        login_time = login_time[:19]  # Remove microseconds
                    else:
                        login_time = login_time.strftime('%Y-%m-%d %H:%M:%S')
                
                logout_time = session.get('logout_timestamp', '')
                if logout_time:
                    if isinstance(logout_time, str):
                        logout_time = logout_time[:19]
                    else:
                        logout_time = logout_time.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    logout_time = "Active"
                
                duration = session.get('session_duration_seconds', 0)
                if duration:
                    hours = duration // 3600
                    minutes = (duration % 3600) // 60
                    duration_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                else:
                    duration_str = "Active" if session.get('is_active') else "N/A"
                
                status = "🟢 Active" if session.get('is_active') else "🔴 Completed"
                login_type = session.get('login_type', 'client').title()
                
                # Insert into table
                self.login_table.insert("", "end", values=(
                    session.get('id', ''),
                    user_name,
                    session.get('username', ''),
                    session.get('device_ip', 'Unknown'),
                    session.get('device_mac', 'Unknown'),
                    session.get('device_hostname', 'Unknown'),
                    session.get('device_platform', 'Unknown'),
                    login_time,
                    logout_time,
                    duration_str,
                    status,
                    login_type
                ))
            
            # Update stats
            total_sessions = len(filtered_sessions)
            active_sessions = len([s for s in filtered_sessions if s.get('is_active')])
            self.login_stats_label.config(text=f"Total: {total_sessions} | Active: {active_sessions}")
            self.login_status_label.config(text=f"🟢 Loaded {total_sessions} login sessions")
            
        except Exception as e:
            print(f"Error refreshing login history: {e}")
            self.login_status_label.config(text=f"🔴 Error loading login history: {str(e)}")

    def _sort_login_by_column(self, col):
        """Sort login history by column"""
        # This is a placeholder - you can implement sorting logic here
        pass

    def _view_login_details(self):
        """View detailed information about a selected login session"""
        selection = self.login_table.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a login session to view details.")
            return
        
        item = self.login_table.item(selection[0])
        values = item['values']
        
        # Create details window
        details_win = Toplevel(self.login_history_window)
        details_win.title("Login Session Details")
        details_win.geometry("600x500")
        details_win.transient(self.login_history_window)
        details_win.grab_set()
        details_win.configure(bg='#f0f2f5')
        
        # Center the window
        self._center_window(details_win, 600, 500)
        
        # Main container
        main_frame = tb.Frame(details_win, bootstyle="light")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        header_frame = tb.LabelFrame(main_frame, text="📋 Login Session Details", 
                                    bootstyle="primary", padding=15)
        header_frame.pack(fill="x", pady=(0, 15))
        
        # Details
        details_text = f"""
Session ID: {values[0]}
User: {values[1]}
Username: {values[2]}
Device IP: {values[3]}
Device MAC: {values[4]}
Hostname: {values[5]}
Platform: {values[6]}
Login Time: {values[7]}
Logout Time: {values[8]}
Duration: {values[9]}
Status: {values[10]}
Type: {values[11]}
        """
        
        details_label = tb.Label(header_frame, text=details_text.strip(), 
                                font=("Segoe UI", 11), justify="left")
        details_label.pack(anchor="w")
        
        # Close button
        tb.Button(main_frame, text="Close", bootstyle="primary", 
                 command=details_win.destroy, width=15).pack(pady=(15, 0))

    def _show_login_context_menu(self, event):
        """Show context menu for login history table"""
        # This is a placeholder - you can implement context menu here
        pass

    def _export_login_history(self):
        """Export login history to CSV"""
        try:
            import csv
            from tkinter import filedialog
            from datetime import datetime
            
            # Get save location
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Export Login History"
            )
            
            if filename:
                # Get all data from table
                data = []
                for item in self.login_table.get_children():
                    values = self.login_table.item(item)['values']
                    data.append({
                        'ID': values[0],
                        'User': values[1],
                        'Username': values[2],
                        'Device IP': values[3],
                        'Device MAC': values[4],
                        'Hostname': values[5],
                        'Platform': values[6],
                        'Login Time': values[7],
                        'Logout Time': values[8],
                        'Duration': values[9],
                        'Status': values[10],
                        'Type': values[11]
                    })
                
                # Write to CSV
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ['ID', 'User', 'Username', 'Device IP', 'Device MAC', 
                                 'Hostname', 'Platform', 'Login Time', 'Logout Time', 
                                 'Duration', 'Status', 'Type']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    
                    writer.writeheader()
                    for row in data:
                        writer.writerow(row)
                
                messagebox.showinfo("Success", f"Login history exported to {filename}")
                self.login_status_label.config(text=f"Exported {len(data)} login sessions to CSV")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export login history: {str(e)}")

    def _clear_old_login_sessions(self):
        """Clear old login sessions (older than 90 days)"""
        try:
            from db import get_connection
            from datetime import datetime, timedelta
            
            # Calculate cutoff date (90 days ago)
            cutoff_date = datetime.now() - timedelta(days=90)
            
            # Ask for confirmation
            result = messagebox.askyesno(
                "Confirm Clear", 
                f"This will permanently delete all login sessions older than {cutoff_date.strftime('%Y-%m-%d')}.\n\nThis action cannot be undone. Continue?"
            )
            
            if result:
                conn = get_connection()
                cursor = conn.cursor()
                
                # Delete old sessions
                cursor.execute("""
                    DELETE FROM login_sessions 
                    WHERE login_timestamp < %s
                """, (cutoff_date,))
                
                deleted_count = cursor.rowcount
                conn.commit()
                cursor.close()
                conn.close()
                
                messagebox.showinfo("Success", f"Deleted {deleted_count} old login sessions")
                self._refresh_login_history()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to clear old sessions: {str(e)}")

    # Example function to update bandwidth label for a router
    def update_bandwidth_label(bw_lbl, bandwidth):
        """
        Update the bandwidth label in the router card.
        bandwidth: dict returned by get_bandwidth() or None
        """
        if not bandwidth:
            bw_lbl.config(text="⏳ Bandwidth: checking...", bootstyle="secondary")
        else:
            download = bandwidth.get("download", 0)
            upload = bandwidth.get("upload", 0)
            bw_lbl.config(
                text=f"⬇ {download} Mbps | ⬆ {upload} Mbps",
                bootstyle="info"
            )

    def build_bandwidth_tab(self):
        # Header with title and auto-update controls
        header_frame = tb.Frame(self.bandwidth_frame)
        header_frame.pack(fill="x", padx=20, pady=(20, 0))
        
        tb.Label(header_frame, text="📊 Bandwidth Monitoring",
                 font=("Segoe UI", 16)).pack(side="left")
        
        # Auto-update controls
        auto_update_frame = tb.Frame(header_frame)
        auto_update_frame.pack(side="right")
        
        self.bandwidth_auto_update_var = tb.BooleanVar(value=True)
        auto_update_check = tb.Checkbutton(auto_update_frame, text="Auto Update", 
                                         variable=self.bandwidth_auto_update_var,
                                         command=self.toggle_bandwidth_auto_update,
                                         bootstyle="success")
        auto_update_check.pack(side="right")
        
        # Update interval selector
        interval_frame = tb.Frame(auto_update_frame)
        interval_frame.pack(side="right", padx=(0, 10))
        tb.Label(interval_frame, text="Interval:", font=("Segoe UI", 8)).pack(side="left")
        self.bandwidth_interval_var = tb.StringVar(value="30s")
        interval_combo = tb.Combobox(interval_frame, textvariable=self.bandwidth_interval_var, 
                                   values=["10s", "30s", "1m", "2m", "5m"], 
                                   width=6, state="readonly")
        interval_combo.pack(side="left", padx=(2, 0))
        interval_combo.bind("<<ComboboxSelected>>", self.on_bandwidth_interval_changed)
        
        self.bandwidth_last_update_label = tb.Label(auto_update_frame, text="", 
                                        font=("Segoe UI", 8), bootstyle="secondary")
        self.bandwidth_last_update_label.pack(side="right", padx=(0, 10))

        # Controls section
        controls_frame = tb.LabelFrame(self.bandwidth_frame, text="📋 Bandwidth Controls", 
                                     bootstyle="info", padding=10)
        controls_frame.pack(fill="x", padx=20, pady=10)

        # Router selector
        router_frame = tb.Frame(controls_frame)
        router_frame.pack(fill="x", pady=(0, 10))
        
        tb.Label(router_frame, text="Select Router:", font=("Segoe UI", 10)).pack(side="left")
        self.router_var = tk.StringVar(value="All Routers")
        try:
            routers = get_routers()
            router_names = ["All Routers"] + [r["name"] for r in routers if r.get("name")]
        except Exception:
            router_names = ["All Routers"]
        
        self.router_picker = tb.Combobox(
            router_frame,
            textvariable=self.router_var,
            values=router_names if router_names else ["No routers available"],
            state="readonly",
            width=30
        )
        self.router_picker.current(0)  # Default to All Routers
        self.router_picker.pack(side="left", padx=(10, 0))
        self.router_picker.bind("<<ComboboxSelected>>", lambda e: self.refresh_total_bandwidth_chart())
        
        # Helper method to refresh router list (can be called when routers are added/removed)
        def refresh_router_list():
            try:
                routers = get_routers()
                router_names = ["All Routers"] + [r["name"] for r in routers if r.get("name")]
                current_value = self.router_var.get()
                self.router_picker['values'] = router_names if router_names else ["No routers available"]
                # Restore selection if it still exists, otherwise default to "All Routers"
                if current_value in router_names:
                    self.router_picker.set(current_value)
                else:
                    self.router_picker.current(0)
            except Exception as e:
                print(f"Error refreshing router list in bandwidth tab: {e}")
        
        # Store refresh method for external calls
        self.refresh_bandwidth_router_list = refresh_router_list

        # Date range filter
        date_frame = tb.Frame(controls_frame)
        date_frame.pack(fill="x", pady=(0, 10))

        # From date
        tb.Label(date_frame, text="From:", font=("Segoe UI", 10)).pack(side="left")
        initial_start = datetime.now().date() - timedelta(days=7)
        self.start_date = DateEntry(date_frame, width=12, dateformat="%m/%d/%Y", bootstyle="primary")
        self.start_date.entry.delete(0, tk.END)
        self.start_date.entry.insert(0, initial_start.strftime("%m/%d/%Y"))
        self.start_date.pack(side="left", padx=(10, 5))
        # Trigger refresh when user picks a date or edits manually
        def _on_start_date_change(e=None):
            self.refresh_total_bandwidth_chart()
        try:
            # Bind to the DateEntry widget itself for calendar selection
            self.start_date.bind("<<DateEntrySelected>>", _on_start_date_change)
            # Also bind to entry for manual edits
            self.start_date.entry.bind("<Return>", _on_start_date_change)
            self.start_date.entry.bind("<FocusOut>", _on_start_date_change)
        except Exception:
            pass

        # To date
        tb.Label(date_frame, text="To:", font=("Segoe UI", 10)).pack(side="left", padx=(20, 0))
        initial_end = datetime.now().date()
        self.end_date = DateEntry(date_frame, width=12, dateformat="%m/%d/%Y", bootstyle="primary")
        self.end_date.entry.delete(0, tk.END)
        self.end_date.entry.insert(0, initial_end.strftime("%m/%d/%Y"))
        self.end_date.pack(side="left", padx=(10, 5))
        # Trigger refresh when user picks a date or edits manually
        def _on_end_date_change(e=None):
            self.refresh_total_bandwidth_chart()
        try:
            # Bind to the DateEntry widget itself for calendar selection
            self.end_date.bind("<<DateEntrySelected>>", _on_end_date_change)
            # Also bind to entry for manual edits
            self.end_date.entry.bind("<Return>", _on_end_date_change)
            self.end_date.entry.bind("<FocusOut>", _on_end_date_change)
        except Exception:
            pass

        # Action buttons
        button_frame = tb.Frame(controls_frame)
        button_frame.pack(fill="x")
        
        tb.Button(button_frame, text="🔍 Apply Filter", bootstyle="primary",
                 command=self.refresh_total_bandwidth_chart).pack(side="left", padx=(0, 10))
        tb.Button(button_frame, text="🔄 Refresh", bootstyle="info",
                 command=self.refresh_total_bandwidth_chart).pack(side="left", padx=(0, 10))
        tb.Button(button_frame, text="📅 Last 7 Days", bootstyle="secondary",
                 command=self.load_last_7_days_bandwidth).pack(side="left")

        # Inline bandwidth loading spinner (hidden by default)
        self.bandwidth_loading_spinner = tb.Progressbar(
            button_frame,
            mode="indeterminate",
            bootstyle="info-striped",
            length=120
        )
        # We'll pack/place it only when needed

        # Statistics cards
        self.bandwidth_stats_frame = tb.Frame(self.bandwidth_frame)
        self.bandwidth_stats_frame.pack(fill="x", padx=20, pady=10)
        
        # Create statistics cards
        self.avg_download_card = tb.LabelFrame(self.bandwidth_stats_frame, text="Avg Download", bootstyle="primary", padding=10)
        self.avg_download_card.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.avg_download_label = tb.Label(self.avg_download_card, text="—", font=("Segoe UI", 14, "bold"))
        self.avg_download_label.pack()
        
        self.avg_upload_card = tb.LabelFrame(self.bandwidth_stats_frame, text="Avg Upload", bootstyle="success", padding=10)
        self.avg_upload_card.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.avg_upload_label = tb.Label(self.avg_upload_card, text="—", font=("Segoe UI", 14, "bold"))
        self.avg_upload_label.pack()
        
        self.avg_latency_card = tb.LabelFrame(self.bandwidth_stats_frame, text="Avg Latency", bootstyle="info", padding=10)
        self.avg_latency_card.grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        self.avg_latency_label = tb.Label(self.avg_latency_card, text="—", font=("Segoe UI", 14, "bold"))
        self.avg_latency_label.pack()
        
        self.max_download_card = tb.LabelFrame(self.bandwidth_stats_frame, text="Max Download", bootstyle="warning", padding=10)
        self.max_download_card.grid(row=0, column=3, padx=5, pady=5, sticky="ew")
        self.max_download_label = tb.Label(self.max_download_card, text="—", font=("Segoe UI", 14, "bold"))
        self.max_download_label.pack()
        
        # Configure grid weights
        for i in range(4):
            self.bandwidth_stats_frame.grid_columnconfigure(i, weight=1)

        # Chart frame - add chart above the table
        self.bandwidth_chart_frame = tb.Frame(self.bandwidth_frame)
        self.bandwidth_chart_frame.pack(fill="both", expand=True, padx=20, pady=(10, 10))
        
        # Initialize matplotlib figure and axes for bandwidth chart
        self.bandwidth_chart_fig, (self.bandwidth_chart_ax1, self.bandwidth_chart_ax2) = plt.subplots(
            1, 2, figsize=(12, 4), dpi=100
        )
        self.bandwidth_chart_fig.patch.set_facecolor('#ffffff')
        self.bandwidth_chart_fig.tight_layout(pad=2.0)
        
        # Embed canvas in Tkinter
        self.bandwidth_chart_canvas = FigureCanvasTkAgg(self.bandwidth_chart_fig, master=self.bandwidth_chart_frame)
        self.bandwidth_chart_canvas.get_tk_widget().pack(fill="both", expand=True)

        # Main content area - data table below the chart
        # Table container (no notebook needed since we only have the table now)
        self.bandwidth_table_frame = tb.Frame(self.bandwidth_frame)
        self.bandwidth_table_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Table with scrollbars
        table_container = tb.Frame(self.bandwidth_table_frame)
        table_container.pack(fill="both", expand=True, padx=10, pady=10)

        # Subheading label describing current table context
        self.bandwidth_table_subtitle = tb.Label(table_container, text="", font=("Segoe UI", 10, "bold"), bootstyle="secondary")
        self.bandwidth_table_subtitle.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))

        # Create treeview (without Router column)
        columns = ("timestamp", "download", "upload", "latency")
        self.bandwidth_table = ttk.Treeview(table_container, columns=columns, show="headings", height=20)

        # Configure columns
        self.bandwidth_table.column("timestamp", width=180, anchor="center")
        self.bandwidth_table.column("download", width=120, anchor="center")
        self.bandwidth_table.column("upload", width=120, anchor="center")
        self.bandwidth_table.column("latency", width=100, anchor="center")

        # Configure headers
        self.bandwidth_table.heading("timestamp", text="Timestamp", command=lambda: self._reverse_column("timestamp"))
        self.bandwidth_table.heading("download", text="Download (Mbps)", command=lambda: self._reverse_column("download"))
        self.bandwidth_table.heading("upload", text="Upload (Mbps)", command=lambda: self._reverse_column("upload"))
        self.bandwidth_table.heading("latency", text="Latency (ms)", command=lambda: self._reverse_column("latency"))

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(table_container, orient="vertical", command=self.bandwidth_table.yview)
        h_scrollbar = ttk.Scrollbar(table_container, orient="horizontal", command=self.bandwidth_table.xview)
        self.bandwidth_table.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Grid layout for table and scrollbars
        self.bandwidth_table.grid(row=1, column=0, sticky="nsew")
        v_scrollbar.grid(row=1, column=1, sticky="ns")
        h_scrollbar.grid(row=2, column=0, sticky="ew")
        
        table_container.grid_rowconfigure(1, weight=1)
        table_container.grid_columnconfigure(0, weight=1)
        
        # Bind mouse wheel scrolling
        def on_mousewheel_vertical(event):
            self.bandwidth_table.yview_scroll(int(-1*(event.delta/120)), "units")
            return "break"
        
        def on_mousewheel_horizontal(event):
            self.bandwidth_table.xview_scroll(int(-1*(event.delta/120)), "units")
            return "break"
        
        self.bandwidth_table.bind("<MouseWheel>", on_mousewheel_vertical)
        self.bandwidth_table.bind("<Shift-MouseWheel>", on_mousewheel_horizontal)

        # Initialize sort flags for column header toggles
        if not hasattr(self, "_reverse_flags"):
            self._reverse_flags = {}

        # Initialize storage for bandwidth rows
        self._bandwidth_rows = []
        
        # Initialize auto-update
        self.bandwidth_auto_update_interval = 30000  # 30 seconds
        self.bandwidth_auto_update_job = None

        # After job tracker for auto-refresh
        self._bandwidth_after_job = None
        
        # Load initial data immediately after UI is built
        self.root.after(800, self.refresh_total_bandwidth_chart)
        
        # Start auto-update after initial load
        self.root.after(1500, self.start_bandwidth_auto_update)

    # Auto-update methods for reports tab
    def start_report_auto_update(self):
        """Start auto-updating reports"""
        if self.report_auto_update_var.get():
            self.auto_update_reports()

    def stop_report_auto_update(self):
        """Stop auto-updating reports"""
        if self.report_auto_update_job:
            self.root.after_cancel(self.report_auto_update_job)
            self.report_auto_update_job = None

    def toggle_report_auto_update(self):
        """Toggle auto-update for reports"""
        if self.report_auto_update_var.get():
            self.start_report_auto_update()
        else:
            self.stop_report_auto_update()

    def auto_update_reports(self):
        """Auto-update reports data"""
        # Check if app is running and window still exists
        if not self.app_running:
            return
        
        try:
            if not self.root.winfo_exists():
                return
        except Exception:
            return
        
        if self.report_auto_update_var.get():
            # Incremental update to avoid full table redraw flicker
            self.generate_report_table(filter_mode=self.report_mode.get().lower(), incremental=True)
            self.update_report_last_update_display()
            self.report_auto_update_job = self.root.after(self.report_auto_update_interval, self.auto_update_reports)

    def update_report_last_update_display(self):
        """Update the last update time display for reports"""
        if hasattr(self, 'report_last_update_label'):
            now = datetime.now()
            self.report_last_update_label.config(text=f"Last updated: {now.strftime('%H:%M:%S')}")

    def on_report_interval_changed(self, event=None):
        """Handle interval change for reports"""
        interval_str = self.report_interval_var.get()
        if interval_str == "10s":
            self.report_auto_update_interval = 10000
        elif interval_str == "30s":
            self.report_auto_update_interval = 30000
        elif interval_str == "1m":
            self.report_auto_update_interval = 60000
        elif interval_str == "2m":
            self.report_auto_update_interval = 120000
        elif interval_str == "5m":
            self.report_auto_update_interval = 300000
        
        if self.report_auto_update_var.get():
            self.stop_report_auto_update()
            self.start_report_auto_update()

    def refresh_reports(self):
        """Refresh reports data with inline loader."""
        self._show_reports_loading()
        self.root.after(50, lambda: self._refresh_reports_inner())

    def _refresh_reports_inner(self):
        try:
            self.generate_report_table(filter_mode=self.report_mode.get().lower())
        finally:
            self._hide_reports_loading()

    # Auto-update methods for bandwidth tab
    def start_bandwidth_auto_update(self):
        """Start auto-updating bandwidth"""
        if self.bandwidth_auto_update_var.get():
            self.auto_update_bandwidth()

    def stop_bandwidth_auto_update(self):
        """Stop auto-updating bandwidth"""
        if self.bandwidth_auto_update_job:
            self.root.after_cancel(self.bandwidth_auto_update_job)
            self.bandwidth_auto_update_job = None

    def toggle_bandwidth_auto_update(self):
        """Toggle auto-update for bandwidth"""
        if self.bandwidth_auto_update_var.get():
            self.start_bandwidth_auto_update()
        else:
            self.stop_bandwidth_auto_update()

    def auto_update_bandwidth(self):
        """Auto-update bandwidth data"""
        # Check if app is running and window still exists
        if not self.app_running:
            return
        
        try:
            if not self.root.winfo_exists():
                return
        except Exception:
            return
        
        # Only continue if auto-update is still enabled
        if not hasattr(self, 'bandwidth_auto_update_var') or not self.bandwidth_auto_update_var.get():
            return
        
        try:
            self.refresh_total_bandwidth_chart()
            self.update_bandwidth_last_update_display()
            # Schedule next update
            self.bandwidth_auto_update_job = self.root.after(self.bandwidth_auto_update_interval, self.auto_update_bandwidth)
        except Exception as e:
            print(f"Error in auto_update_bandwidth: {e}")
            import traceback
            traceback.print_exc()

    def update_bandwidth_last_update_display(self):
        """Update the last update time display for bandwidth"""
        if hasattr(self, 'bandwidth_last_update_label'):
            now = datetime.now()
            self.bandwidth_last_update_label.config(text=f"Last updated: {now.strftime('%H:%M:%S')}")

    def on_bandwidth_interval_changed(self, event=None):
        """Handle interval change for bandwidth"""
        interval_str = self.bandwidth_interval_var.get()
        if interval_str == "10s":
            self.bandwidth_auto_update_interval = 10000
        elif interval_str == "30s":
            self.bandwidth_auto_update_interval = 30000
        elif interval_str == "1m":
            self.bandwidth_auto_update_interval = 60000
        elif interval_str == "2m":
            self.bandwidth_auto_update_interval = 120000
        elif interval_str == "5m":
            self.bandwidth_auto_update_interval = 300000
        
        if self.bandwidth_auto_update_var.get():
            self.stop_bandwidth_auto_update()
            self.start_bandwidth_auto_update()

    def load_last_7_days_bandwidth(self):
        """Load last 7 days of bandwidth data"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
        self.start_date.entry.delete(0, tk.END)
        self.start_date.entry.insert(0, start_date.strftime("%m/%d/%Y"))
        self.end_date.entry.delete(0, tk.END)
        self.end_date.entry.insert(0, end_date.strftime("%m/%d/%Y"))
        self.refresh_total_bandwidth_chart()

    def update_reports_summary_cards(self, total_routers, total_uptime, total_bandwidth, router_count):
        """Update the reports summary cards"""
        if hasattr(self, 'total_routers_label'):
            self.total_routers_label.config(text=str(total_routers))
        
        if hasattr(self, 'avg_uptime_label') and router_count > 0:
            avg_uptime = total_uptime / router_count
            self.avg_uptime_label.config(text=f"{avg_uptime:.1f}%")
        
        if hasattr(self, 'total_bandwidth_label'):
            if total_bandwidth >= 1024:
                bandwidth_str = f"{total_bandwidth / 1024:.2f} GB"
            else:
                bandwidth_str = f"{total_bandwidth:.2f} MB"
            self.total_bandwidth_label.config(text=bandwidth_str)

    def update_bandwidth_statistics(self):
        """Update bandwidth statistics cards"""
        try:
            # Get bandwidth data from stored rows (more reliable than parsing table)
            if not hasattr(self, '_bandwidth_rows') or not self._bandwidth_rows:
                # Fallback to table if rows not available
                if not hasattr(self, 'bandwidth_table'):
                    return
                    
                downloads = []
                uploads = []
                latencies = []
                
                for item in self.bandwidth_table.get_children():
                    values = self.bandwidth_table.item(item)['values']
                    if len(values) >= 4:
                        try:
                            # Column order: timestamp(0), download(1), upload(2), latency(3)
                            # Values may be strings like "12.34" or "12.34 Mbps"
                            download_str = str(values[1]).replace(' Mbps', '').strip()
                            upload_str = str(values[2]).replace(' Mbps', '').strip()
                            latency_str = str(values[3]).replace(' ms', '').strip()
                            
                            download_val = float(download_str)
                            upload_val = float(upload_str)
                            latency_val = float(latency_str)
                            
                            downloads.append(download_val)
                            uploads.append(upload_val)
                            latencies.append(latency_val)
                        except (ValueError, IndexError, AttributeError):
                            continue
            else:
                # Use stored rows directly (more efficient)
                downloads = []
                uploads = []
                latencies = []
                
                for row in self._bandwidth_rows:
                    if len(row) >= 4:
                        try:
                            downloads.append(float(row[1]))
                            uploads.append(float(row[2]))
                            latencies.append(float(row[3]))
                        except (ValueError, TypeError):
                            continue
            
            # Update statistics cards
            if downloads and hasattr(self, 'avg_download_label'):
                avg_download = sum(downloads) / len(downloads)
                self.avg_download_label.config(text=f"{avg_download:.2f} Mbps")
                
                if hasattr(self, 'max_download_label'):
                    max_download = max(downloads)
                    self.max_download_label.config(text=f"{max_download:.2f} Mbps")
            else:
                if hasattr(self, 'avg_download_label'):
                    self.avg_download_label.config(text="—")
                if hasattr(self, 'max_download_label'):
                    self.max_download_label.config(text="—")
            
            if uploads and hasattr(self, 'avg_upload_label'):
                avg_upload = sum(uploads) / len(uploads)
                self.avg_upload_label.config(text=f"{avg_upload:.2f} Mbps")
            else:
                if hasattr(self, 'avg_upload_label'):
                    self.avg_upload_label.config(text="—")
            
            if latencies and hasattr(self, 'avg_latency_label'):
                avg_latency = sum(latencies) / len(latencies)
                self.avg_latency_label.config(text=f"{avg_latency:.1f} ms")
            else:
                if hasattr(self, 'avg_latency_label'):
                    self.avg_latency_label.config(text="—")
                
        except Exception as e:
            print(f"Error updating bandwidth statistics: {e}")
            import traceback
            traceback.print_exc()

    # Add this helper method inside Dashboard class
    def _reverse_column(self, col_name):
        """Toggles sorting when column header clicked."""
        if not hasattr(self, "_reverse_flags"):
            self._reverse_flags = {}
        reverse = self._reverse_flags.get(col_name, False)
        self._refresh_bandwidth_table(sort_column=col_name, reverse=reverse)
        self._reverse_flags[col_name] = not reverse

    def _show_calendar(self, entry_widget):
        """Legacy helper replaced by DatePickerDialog; kept for compatibility."""
        dialog = DatePickerDialog(self.root)
        date = dialog.date_selected
        if date:
            entry_widget.delete(0, 'end')
            entry_widget.insert(0, date.strftime("%m/%d/%Y"))
            self.refresh_total_bandwidth_chart()


    # Removed custom popup calendar; DateEntry provides anchored dropdown

    def load_bandwidth_data_by_name(self, router_name):
        """Load bandwidth data for a router by its name."""
        if router_name == "All Routers":
            # Handle "All Routers" selection
            # Use the aggregated-by-date filter refresh path
            self.refresh_total_bandwidth_chart()
            return
        # Single router selection
        routers = get_routers()
        router = next((r for r in routers if r['name'] == router_name), None)
        if not router:
            messagebox.showerror("Error", f"Router '{router_name}' not found.")
            return
        # Cancel previous scheduled call
        if hasattr(self, "_bandwidth_after_job") and self._bandwidth_after_job:
            self.bandwidth_frame.after_cancel(self._bandwidth_after_job)
        # Use unified path so chart and table come from the same dataset
        self.refresh_total_bandwidth_chart()



    def load_bandwidth_data(self, router_id, start_date=None, end_date=None):
        """
        Load bandwidth logs for a given router, optionally filtered by start and end dates.
        Updates both the chart and the table, and schedules auto-refresh.
        """
        self._show_bandwidth_loading()
        try:
            # Cancel previous scheduled refresh
            if hasattr(self, "_bandwidth_after_job") and self._bandwidth_after_job:
                self.bandwidth_frame.after_cancel(self._bandwidth_after_job)

            # Build SQL query
            conn = get_connection()
            cur = conn.cursor(dictionary=True)
            routers = get_routers()
            router_map = {r['id']: r['name'] for r in routers}

            if router_id is None:
                # All routers: fetch all logs in date range
                if start_date and end_date:
                    start = datetime.strptime(start_date, "%m/%d/%Y")
                    end = datetime.strptime(end_date, "%m/%d/%Y")
                    start_str = start.strftime("%Y-%m-%d")
                    end_str = end.strftime("%Y-%m-%d")
                    query = """
                            SELECT 
                                DATE_FORMAT(timestamp, '%Y-%m-%d %H:00:00') as timestamp,
                                SUM(download_mbps) as download_mbps,
                                SUM(upload_mbps) as upload_mbps,
                                AVG(latency_ms) as latency_ms
                        FROM bandwidth_logs
                        WHERE DATE(timestamp) >= %s AND DATE(timestamp) <= %s
                            GROUP BY DATE_FORMAT(timestamp, '%Y-%m-%d %H:00:00')
                        ORDER BY timestamp DESC
                            LIMIT 500
                    """
                    cur.execute(query, (start_str, end_str))
                else:
                    query = """
                            SELECT 
                                DATE_FORMAT(timestamp, '%Y-%m-%d %H:00:00') as timestamp,
                                SUM(download_mbps) as download_mbps,
                                SUM(upload_mbps) as upload_mbps,
                                AVG(latency_ms) as latency_ms
                        FROM bandwidth_logs
                            GROUP BY DATE_FORMAT(timestamp, '%Y-%m-%d %H:00:00')
                        ORDER BY timestamp DESC
                            LIMIT 500
                    """
                    cur.execute(query)
                rows = cur.fetchall()
                cur.close()
                conn.close()
                if not rows:
                    # Clear chart if it exists
                    if hasattr(self, 'bandwidth_chart_ax1') and hasattr(self, 'bandwidth_chart_ax2'):
                        self.bandwidth_chart_ax1.clear()
                        self.bandwidth_chart_ax2.clear()
                        if hasattr(self, 'bandwidth_chart_canvas'):
                            self.bandwidth_chart_canvas.draw()
                    self.bandwidth_table.delete(*self.bandwidth_table.get_children())
                    messagebox.showinfo("No Data", "No bandwidth data available for the selected period.")
                    return
                rows.reverse()
                # Prepare chart/table data
                def _nz(val):
                    try:
                        return 0.0 if val is None else float(val)
                    except Exception:
                        return 0.0
                
                # For "All Routers", store aggregated data (no router_id column)
                self._bandwidth_rows = [
                    (
                        r["timestamp"] if isinstance(r["timestamp"], str) else r["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                        _nz(r.get("download_mbps")),
                        _nz(r.get("upload_mbps")),
                        _nz(r.get("latency_ms"))
                    )
                    for r in rows
                ]
                
                # Chart: use aggregated data directly
                timestamps = [r["timestamp"] if isinstance(r["timestamp"], str) else r["timestamp"].strftime("%H:%M:%S") for r in rows]
                downloads = [_nz(r.get("download_mbps")) for r in rows]
                uploads = [_nz(r.get("upload_mbps")) for r in rows]
                latencies = [_nz(r.get("latency_ms")) for r in rows]
            else:
                # Single router
                params = [router_id]
                if start_date and end_date:
                    start = datetime.strptime(start_date, "%m/%d/%Y")
                    end = datetime.strptime(end_date, "%m/%d/%Y")
                    start_str = start.strftime("%Y-%m-%d")
                    end_str = end.strftime("%Y-%m-%d")
                    query = """
                        SELECT timestamp, download_mbps, upload_mbps, latency_ms
                        FROM bandwidth_logs
                        WHERE router_id = %s AND DATE(timestamp) >= %s AND DATE(timestamp) <= %s
                        ORDER BY timestamp DESC
                        LIMIT 1000
                    """
                    params.extend([start_str, end_str])
                else:
                    query = """
                        SELECT timestamp, download_mbps, upload_mbps, latency_ms
                        FROM bandwidth_logs
                        WHERE router_id = %s
                        ORDER BY timestamp DESC
                        LIMIT 1000
                    """
                cur.execute(query, tuple(params))
                rows = cur.fetchall()
                cur.close()
                conn.close()
                if not rows:
                    # Clear chart if it exists
                    if hasattr(self, 'bandwidth_chart_ax1') and hasattr(self, 'bandwidth_chart_ax2'):
                        self.bandwidth_chart_ax1.clear()
                        self.bandwidth_chart_ax2.clear()
                        if hasattr(self, 'bandwidth_chart_canvas'):
                            self.bandwidth_chart_canvas.draw()
                    self.bandwidth_table.delete(*self.bandwidth_table.get_children())
                    messagebox.showinfo("No Data", "No bandwidth data available for the selected period.")
                    return
                rows.reverse()
                def _nz(val):
                    try:
                        return 0.0 if val is None else float(val)
                    except Exception:
                        return 0.0
                router_name = router_map.get(router_id, str(router_id))
                self._bandwidth_rows = [
                    (
                        r["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                        _nz(r.get("download_mbps")),
                        _nz(r.get("upload_mbps")),
                        _nz(r.get("latency_ms"))
                    )
                    for r in rows
                ]
                timestamps = [r["timestamp"].strftime("%H:%M:%S") for r in rows]
                downloads  = [float(r["download_mbps"] or 0) for r in rows]
                uploads    = [float(r["upload_mbps"] or 0) for r in rows]
                latencies  = [float(r["latency_ms"] or 0) for r in rows]

            # Refresh table (this will also render the chart from the same data)
            self._refresh_bandwidth_table()
            
            # Update chart with the same data
            self._update_bandwidth_tab_chart()

            # Update subtitle label
            if hasattr(self, 'bandwidth_table_subtitle'):
                if router_id is None:
                    self.bandwidth_table_subtitle.config(text="📊 Viewing: All Routers (Hourly Aggregated)")
                else:
                    router_name = router_map.get(router_id, str(router_id))
                    self.bandwidth_table_subtitle.config(text=f"📊 Viewing: {router_name}")

            # Update last updated label
            now = datetime.now().strftime("%H:%M:%S")
            if hasattr(self, 'bandwidth_last_update_label'):
                self.bandwidth_last_update_label.config(text=f"Last updated: {now}")

            # Schedule next refresh using unified filtered pipeline
            self._bandwidth_after_job = self.bandwidth_frame.after(
                5000,
                self.refresh_total_bandwidth_chart
            )
            self._hide_bandwidth_loading()
            
        except Exception as e:
            self._hide_bandwidth_loading()
            messagebox.showerror("Error", f"Failed to load bandwidth data: {str(e)}")

    def refresh_total_bandwidth_chart_with_dates(self):
        router_name = self.router_var.get()
        start = self.start_date.entry.get()  # returns string 'YYYY-MM-DD'
        end   = self.end_date.entry.get()

        routers = get_routers()
        router = next((r for r in routers if r['name'] == router_name), None)

        if router:
            # Cancel previous scheduled refresh
            if hasattr(self, "_bandwidth_after_job") and self._bandwidth_after_job:
                self.bandwidth_frame.after_cancel(self._bandwidth_after_job)
            # Use the unified refresh path (reads dates from the pickers)
            self.refresh_total_bandwidth_chart()


    def show_last_7_days_for_selected_router(self):
        """DEPRECATED: Use load_last_7_days_bandwidth() instead.
        This function resets dates to last 7 days - only call explicitly when intended."""
        # Cancel any scheduled refresh
        if hasattr(self, "_bandwidth_after_job") and self._bandwidth_after_job:
            try:
                self.bandwidth_frame.after_cancel(self._bandwidth_after_job)
            except Exception:
                pass

        # Reset date pickers to last 7 days
        today = datetime.now().date()
        last_7 = today - timedelta(days=7)
        try:
            self.start_date.entry.delete(0, tk.END)
            self.start_date.entry.insert(0, last_7.strftime("%m/%d/%Y"))
        except Exception:
            pass
        try:
            self.end_date.entry.delete(0, tk.END)
            self.end_date.entry.insert(0, today.strftime("%m/%d/%Y"))
        except Exception:
            pass

        # Determine selection
        selected_name = self.router_var.get()
        if selected_name == "All Routers":
            # Aggregate last 7 days for all routers using existing date-aware method
            self.refresh_total_bandwidth_chart()
            return

        routers = get_routers()
        router = next((r for r in routers if r['name'] == selected_name), None)
        if not router:
            return

        # Load last 7 days via the unified path (dates already updated above)
        self.refresh_total_bandwidth_chart()


    def _refresh_bandwidth_table(self, sort_column=None, reverse=False):
        """
        Clears and repopulates the bandwidth table.
        Sorts by column if requested.
        """
        self.bandwidth_table.delete(*self.bandwidth_table.get_children())

        data = list(getattr(self, "_bandwidth_rows", []))  # Use the correct stored rows

        if sort_column:
            idx_map = {"timestamp": 0, "download": 1, "upload": 2, "latency": 3}
            idx = idx_map.get(sort_column, 0)

            if sort_column == "timestamp":
                def parse_ts(val):
                    # Try multiple timestamp formats
                    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:00:00", "%Y-%m-%d"]:
                        try:
                            return datetime.strptime(val, fmt)
                        except ValueError:
                            continue
                    # If all fail, return a default date
                    return datetime(1970, 1, 1)
                data.sort(key=lambda x: parse_ts(x[idx]), reverse=reverse)
            else:
                def _nz_sort(v):
                    try:
                        return float(v) if v is not None else 0.0
                    except Exception:
                        return 0.0
                data.sort(key=lambda x: _nz_sort(x[idx]), reverse=reverse)

        for row in data:
            # Format the values properly for table display
            timestamp, download, upload, latency = row
            def _fmt2(v, places=2):
                try:
                    return f"{float(v):.{places}f}"
                except Exception:
                    return f"{0.0:.{places}f}"
            formatted_row = (
                timestamp,
                _fmt2(download, 2),
                _fmt2(upload, 2),
                _fmt2(latency, 1)
            )
            self.bandwidth_table.insert("", "end", values=formatted_row)

        # Update statistics cards
        try:
            self.update_bandwidth_statistics()
        except Exception as e:
            print(f"Error updating bandwidth statistics: {e}")

    def _update_bandwidth_tab_chart(self):
        """
        Updates the bandwidth chart with data from self._bandwidth_rows.
        Creates line charts for download/upload and latency over time.
        """
        import matplotlib.dates as mdates
        
        if not hasattr(self, 'bandwidth_chart_fig') or not hasattr(self, '_bandwidth_rows'):
            return
        
        data = list(getattr(self, "_bandwidth_rows", []))
        if not data:
            # Clear charts if no data
            self.bandwidth_chart_ax1.clear()
            self.bandwidth_chart_ax2.clear()
            self.bandwidth_chart_canvas.draw()
            return
        
        # Lock canvas/frame size to avoid resizing jitter during redraw
        try:
            widget = self.bandwidth_chart_canvas.get_tk_widget()
            try:
                widget.update_idletasks()
            except Exception:
                pass
            w = int(widget.winfo_width() or 0)
            h = int(widget.winfo_height() or 0)
            if w < 10 or h < 10:
                try:
                    parent = widget.master
                    w = int(parent.winfo_width() or 900)
                    h = int(parent.winfo_height() or 320)
                except Exception:
                    w, h = 900, 320
            try:
                widget.master.pack_propagate(False)
            except Exception:
                pass
            dpi = float(self.bandwidth_chart_fig.get_dpi() or 100.0)
            self.bandwidth_chart_fig.set_size_inches(max(w, 10)/dpi, max(h, 10)/dpi, forward=True)
        except Exception:
            pass

        # Parse data from rows: (timestamp, download, upload, latency)
        timestamps = []
        downloads = []
        uploads = []
        latencies = []
        
        for row in data:
            timestamp_str, download, upload, latency = row
            try:
                # Parse timestamp - handle different formats
                if isinstance(timestamp_str, str):
                    # Try multiple timestamp formats
                    ts = None
                    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:00:00", "%Y-%m-%d"]:
                        try:
                            ts = datetime.strptime(timestamp_str, fmt)
                            break
                        except ValueError:
                            continue
                    if ts is None:
                        continue
                else:
                    ts = timestamp_str
                
                timestamps.append(ts)
                downloads.append(float(download) if download is not None else 0.0)
                uploads.append(float(upload) if upload is not None else 0.0)
                latencies.append(float(latency) if latency is not None else 0.0)
            except Exception as e:
                continue
        
        if not timestamps:
            return
        
        # Clear previous plots
        self.bandwidth_chart_ax1.clear()
        self.bandwidth_chart_ax2.clear()
        
        # Plot 1: Download and Upload (Mbps)
        self.bandwidth_chart_ax1.plot(timestamps, downloads, label="Download (Mbps)", 
                                     color="#dc3545", linewidth=2, marker='o', markersize=3)
        self.bandwidth_chart_ax1.plot(timestamps, uploads, label="Upload (Mbps)", 
                                     color="#28a745", linewidth=2, marker='s', markersize=3)
        self.bandwidth_chart_ax1.set_title("Bandwidth Usage", fontsize=12, fontweight='bold')
        self.bandwidth_chart_ax1.set_xlabel("Time", fontsize=10)
        self.bandwidth_chart_ax1.set_ylabel("Mbps", fontsize=10)
        self.bandwidth_chart_ax1.legend(loc='upper left', fontsize=9)
        self.bandwidth_chart_ax1.grid(True, alpha=0.3)
        self.bandwidth_chart_ax1.tick_params(axis="x", rotation=45, labelsize=8)
        
        # Format x-axis dates
        if len(timestamps) > 1:
            # Use appropriate date formatter based on time range
            time_span = (timestamps[-1] - timestamps[0]).total_seconds()
            if time_span < 86400:  # Less than 1 day
                self.bandwidth_chart_ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
            elif time_span < 604800:  # Less than 1 week
                self.bandwidth_chart_ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
            else:
                self.bandwidth_chart_ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        
        # Plot 2: Latency (ms)
        self.bandwidth_chart_ax2.plot(timestamps, latencies, label="Latency (ms)", 
                                     color="#007bff", linewidth=2, marker='^', markersize=3)
        self.bandwidth_chart_ax2.set_title("Latency", fontsize=12, fontweight='bold')
        self.bandwidth_chart_ax2.set_xlabel("Time", fontsize=10)
        self.bandwidth_chart_ax2.set_ylabel("ms", fontsize=10)
        self.bandwidth_chart_ax2.legend(loc='upper left', fontsize=9)
        self.bandwidth_chart_ax2.grid(True, alpha=0.3)
        self.bandwidth_chart_ax2.tick_params(axis="x", rotation=45, labelsize=8)
        
        # Format x-axis dates for latency chart
        if len(timestamps) > 1:
            time_span = (timestamps[-1] - timestamps[0]).total_seconds()
            if time_span < 86400:
                self.bandwidth_chart_ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
            elif time_span < 604800:
                self.bandwidth_chart_ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
            else:
                self.bandwidth_chart_ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        
        # Adjust layout and redraw
        self.bandwidth_chart_fig.tight_layout(pad=2.0)
        self.bandwidth_chart_canvas.draw()


    def build_total_bandwidth_tab(self):
        # Chart frame
        self.total_bandwidth_frame = tb.Frame(self.bandwidth_frame)
        self.total_bandwidth_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Initialize Figure and Axes only once
        self.total_fig, (self.total_ax1, self.total_ax2) = plt.subplots(1, 2, figsize=(10, 4), dpi=100)

        # Embed canvas in Tkinter
        self.total_canvas = FigureCanvasTkAgg(self.total_fig, master=self.total_bandwidth_frame)
        self.total_canvas.get_tk_widget().pack(fill="both", expand=True)

        # After job tracker
        self._total_bandwidth_after_job = None

        # Initial load
        self.load_total_bandwidth_chart()

    def load_total_bandwidth_chart(self):
        """Draws/refreshes the Total Bandwidth chart & table (with loader).
        Chart now derives from the same table rows for accurate filtering and consistency.
        """
        # Delegate to the unified refresh path that respects date pickers and router selection
        self.refresh_total_bandwidth_chart()


    def load_bandwidth_chart(self):
        import matplotlib.dates as mdates

        # Query DB
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT timestamp,
                SUM(download_mbps) AS total_download,
                SUM(upload_mbps) AS total_upload,
                AVG(latency_ms)   AS avg_latency
            FROM bandwidth_logs
            GROUP BY timestamp
            ORDER BY timestamp DESC
            LIMIT 20
        """)
        rows = cur.fetchall()
        conn.close()

        if not rows:
            return

        # reverse → oldest to newest
        rows.reverse()

        # Extract data
        timestamps = [r["timestamp"] for r in rows]  # keep as datetime
        downloads  = [float(r["total_download"] or 0) for r in rows]
        uploads    = [float(r["total_upload"] or 0) for r in rows]
        latencies  = [float(r["avg_latency"] or 0) for r in rows]

        # ✅ First run → create fig and axes
        if not hasattr(self, "bandwidth_fig"):
            self.bandwidth_fig, (self.bandwidth_ax1, self.bandwidth_ax2) = plt.subplots(
                1, 2, figsize=(10, 4), dpi=100
            )
            self.bandwidth_canvas = FigureCanvasTkAgg(self.bandwidth_fig, master=self.bandwidth_frame)
            self.bandwidth_canvas.get_tk_widget().pack(fill="both", expand=True, pady=10)
        else:
            self.bandwidth_ax1.clear()
            self.bandwidth_ax2.clear()

        # Bandwidth subplot
        self.bandwidth_ax1.plot(timestamps, downloads, label="Total Download (Mbps)", color="blue")
        self.bandwidth_ax1.plot(timestamps, uploads, label="Total Upload (Mbps)", color="green")
        self.bandwidth_ax1.set_title("Total Bandwidth Usage")
        self.bandwidth_ax1.set_xlabel("Time")
        self.bandwidth_ax1.set_ylabel("Mbps")
        self.bandwidth_ax1.tick_params(axis="x", rotation=45)
        self.bandwidth_ax1.legend()

        # Format x-axis as HH:MM:SS
        self.bandwidth_ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))

        # Latency subplot
        self.bandwidth_ax2.plot(timestamps, latencies, label="Avg Ping (ms)", color="red", marker="o")
        self.bandwidth_ax2.set_title("Average Latency (Ping)")
        self.bandwidth_ax2.set_xlabel("Time")
        self.bandwidth_ax2.set_ylabel("ms")
        self.bandwidth_ax2.tick_params(axis="x", rotation=45)
        self.bandwidth_ax2.legend()
        self.bandwidth_ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))

        self.bandwidth_canvas.draw()

        # ✅ Cancel old auto-refresh if exists, then restart
        if hasattr(self, "_bandwidth_after_job") and self._bandwidth_after_job:
            self.bandwidth_frame.after_cancel(self._bandwidth_after_job)
        self._bandwidth_after_job = self.bandwidth_frame.after(5000, self.load_bandwidth_chart)

    def refresh_total_bandwidth_chart(self):
        """
        Optimized: Refreshes the bandwidth chart and table, fixes redraw, empty data, and timer issues.
        """
        try:
            self._show_bandwidth_loading()
            # Cancel any scheduled refresh (auto-update job)
            if hasattr(self, "_bandwidth_after_job") and self._bandwidth_after_job:
                try:
                    self.root.after_cancel(self._bandwidth_after_job)
                except Exception:
                    pass
                self._bandwidth_after_job = None
            # Also cancel auto-update job if running
            if hasattr(self, 'bandwidth_auto_update_job') and self.bandwidth_auto_update_job:
                try:
                    self.root.after_cancel(self.bandwidth_auto_update_job)
                except Exception:
                    pass
                self.bandwidth_auto_update_job = None
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._hide_bandwidth_loading()
            return

        try:
            # Get current router and date picker values directly from UI
            router_name = self.router_var.get() if hasattr(self, 'router_var') else "All Routers"
            start_date_str = self.start_date.entry.get() if hasattr(self, 'start_date') else None
            end_date_str = self.end_date.entry.get() if hasattr(self, 'end_date') else None

            # Parse dates
            try:
                start_date = datetime.strptime(start_date_str, "%m/%d/%Y").date() if start_date_str else None
            except Exception:
                start_date = None
            try:
                end_date = datetime.strptime(end_date_str, "%m/%d/%Y").date() if end_date_str else None
            except Exception:
                end_date = None

            # Default to last 7 days if empty (only if dates are None, don't modify the UI)
            today = datetime.now().date()
            if not start_date:
                start_date = today - timedelta(days=7)
            if not end_date:
                end_date = today

            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")

            # Get router ID if not "All Routers"
            router_id = None
            routers = get_routers()
            for r in routers:
                if r["name"] == router_name:
                    router_id = r["id"]
                    break

            # Build SQL query
            query_params = []
            if router_id:
                query = (
                    "SELECT timestamp, download_mbps AS total_download, "
                    "upload_mbps AS total_upload, latency_ms AS avg_latency "
                    "FROM bandwidth_logs "
                    "WHERE router_id=%s AND DATE(timestamp) BETWEEN %s AND %s "
                    "ORDER BY timestamp ASC LIMIT 500"
                )
                query_params.extend([router_id, start_str, end_str])
            else:
                query = (
                    "SELECT DATE_FORMAT(timestamp, '%Y-%m-%d %H:00:00') AS timestamp, "
                    "SUM(download_mbps) AS total_download, "
                    "SUM(upload_mbps) AS total_upload, "
                    "AVG(latency_ms) AS avg_latency "
                    "FROM bandwidth_logs "
                    "WHERE DATE(timestamp) BETWEEN %s AND %s "
                    "GROUP BY DATE_FORMAT(timestamp, '%Y-%m-%d %H:00:00') "
                    "ORDER BY timestamp ASC LIMIT 500"
                )
                query_params.extend([start_str, end_str])

            # Execute query
            conn = get_connection()
            cur = conn.cursor(dictionary=True)
            cur.execute(query, query_params)
            rows = cur.fetchall()
            cur.close()
            conn.close()

            # Prepare data for chart & table
            filtered_rows = []
            for r in rows:
                if router_id:
                    ts_display = r["timestamp"].strftime("%Y-%m-%d %H:%M:%S") if hasattr(r["timestamp"], 'strftime') else str(r["timestamp"])
                else:
                    ts_display = r["timestamp"] if isinstance(r["timestamp"], str) else r["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                row_tuple = (
                    ts_display,
                    float(r["total_download"] or 0),
                    float(r["total_upload"] or 0),
                    float(r["avg_latency"] or 0)
                )
                filtered_rows.append(row_tuple)
            
            # Store filtered rows for table use
            self._bandwidth_rows = filtered_rows

            # Update subtitle label
            if hasattr(self, 'bandwidth_table_subtitle'):
                if router_id:
                    self.bandwidth_table_subtitle.config(text=f"📊 Viewing: {router_name}")
                else:
                    self.bandwidth_table_subtitle.config(text="📊 Viewing: All Routers (Hourly Aggregated)")

            # Update last updated label
            now = datetime.now().strftime("%H:%M:%S")
            if hasattr(self, 'bandwidth_last_update_label'):
                self.bandwidth_last_update_label.config(text=f"Last updated: {now}")

            # Refresh table
            try:
                self._refresh_bandwidth_table(sort_column=None, reverse=False)
            except Exception as e:
                import traceback
                traceback.print_exc()

            # Update the bandwidth charts with the same filtered rows
            try:
                if hasattr(self, '_update_bandwidth_tab_chart'):
                    self._update_bandwidth_tab_chart()
            except Exception:
                # Keep the table visible even if chart update fails
                pass

            # Schedule auto-refresh (interval from UI) - only if auto-update is enabled
            if getattr(self, 'bandwidth_auto_update_var', None) and self.bandwidth_auto_update_var.get():
                interval_map = {"10s": 10000, "30s": 30000, "1m": 60000, "2m": 120000, "5m": 300000}
                interval_str = self.bandwidth_interval_var.get() if hasattr(self, 'bandwidth_interval_var') else "30s"
                interval_ms = interval_map.get(interval_str, 30000)
                self._bandwidth_after_job = self.root.after(interval_ms, self.refresh_total_bandwidth_chart)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to refresh bandwidth data: {str(e)}")
        finally:
            self._hide_bandwidth_loading()
    

    # Helper: force chart refresh and cancel any pending auto-refresh
    def force_total_bandwidth_chart_refresh(self):
        if hasattr(self, '_bandwidth_after_job') and self._bandwidth_after_job:
            self.bandwidth_frame.after_cancel(self._bandwidth_after_job)
            self._bandwidth_after_job = None
        self.refresh_total_bandwidth_chart()



    def build_reports_tab(self):
        # Header with title and auto-update controls
        header_frame = tb.Frame(self.reports_frame)
        header_frame.pack(fill="x", padx=20, pady=(20, 0))
        
        tb.Label(header_frame, text="📊 Network Reports & Statistics",
                 font=("Segoe UI", 16)).pack(side="left")
        
        # Auto-update controls
        auto_update_frame = tb.Frame(header_frame)
        auto_update_frame.pack(side="right")
        
        self.report_auto_update_var = tb.BooleanVar(value=True)
        auto_update_check = tb.Checkbutton(auto_update_frame, text="Auto Update", 
                                         variable=self.report_auto_update_var,
                                         command=self.toggle_report_auto_update,
                                         bootstyle="success")
        auto_update_check.pack(side="right")
        
        # Update interval selector
        interval_frame = tb.Frame(auto_update_frame)
        interval_frame.pack(side="right", padx=(0, 10))
        tb.Label(interval_frame, text="Interval:", font=("Segoe UI", 8)).pack(side="left")
        self.report_interval_var = tb.StringVar(value="30s")
        interval_combo = tb.Combobox(interval_frame, textvariable=self.report_interval_var, 
                                   values=["10s", "30s", "1m", "2m", "5m"], 
                                   width=6, state="readonly")
        interval_combo.pack(side="left", padx=(2, 0))
        interval_combo.bind("<<ComboboxSelected>>", self.on_report_interval_changed)
        
        self.report_last_update_label = tb.Label(auto_update_frame, text="", 
                                        font=("Segoe UI", 8), bootstyle="secondary")
        self.report_last_update_label.pack(side="right", padx=(0, 10))

        # Controls section
        controls_frame = tb.LabelFrame(self.reports_frame, text="📋 Report Controls", 
                                     bootstyle="info", padding=10)
        controls_frame.pack(fill="x", padx=20, pady=10)

        # Date range filter
        date_frame = tb.Frame(controls_frame)
        date_frame.pack(fill="x", pady=(0, 10))
        
        # Start Date
        tb.Label(date_frame, text="Start Date:", font=("Segoe UI", 10)).pack(side="left")
        initial_start = datetime.now().date() - timedelta(days=7)
        self.report_start_date = DateEntry(date_frame, width=12, dateformat="%m/%d/%Y", bootstyle="primary")
        self.report_start_date.entry.delete(0, tk.END)
        self.report_start_date.entry.insert(0, initial_start.strftime("%m/%d/%Y"))
        self.report_start_date.pack(side="left", padx=(10, 5))
        
        # End Date
        tb.Label(date_frame, text="End Date:", font=("Segoe UI", 10)).pack(side="left", padx=(20, 0))
        initial_end = datetime.now().date()
        self.report_end_date = DateEntry(date_frame, width=12, dateformat="%m/%d/%Y", bootstyle="primary")
        self.report_end_date.entry.delete(0, tk.END)
        self.report_end_date.entry.insert(0, initial_end.strftime("%m/%d/%Y"))
        self.report_end_date.pack(side="left", padx=(10, 5))

        # View Mode selector
        tb.Label(date_frame, text="View Mode:", font=("Segoe UI", 10)).pack(side="left", padx=(20, 0))
        self.report_mode = tb.Combobox(
            date_frame,
            values=["Daily", "Weekly", "Monthly"],
            state="readonly",
            width=10
        )
        self.report_mode.current(1)  # default = Weekly
        self.report_mode.pack(side="left", padx=(10, 0))

        # Action buttons
        button_frame = tb.Frame(controls_frame)
        button_frame.pack(fill="x")
        
        # Store references to control which buttons are disabled during loading
        self.generate_report_btn = tb.Button(button_frame, text="📊 Generate Report", bootstyle="primary",
            command=lambda: self.generate_report_table(
                filter_mode=self.report_mode.get().lower()
                 ))
        self.generate_report_btn.pack(side="left", padx=(0, 10))

        self.open_tickets_btn = tb.Button(button_frame, text="🎫 Open Tickets Management", bootstyle="warning",
                 command=self.open_ticket_window)
        self.open_tickets_btn.pack(side="left", padx=(0, 10))

        self.print_report_btn = tb.Button(button_frame, text="🖨️ Print Report", bootstyle="info",
                 command=self.print_report)
        self.print_report_btn.pack(side="left", padx=(0, 10))

        self.refresh_reports_btn = tb.Button(button_frame, text="🔄 Refresh", bootstyle="secondary",
                 command=self.refresh_reports)
        self.refresh_reports_btn.pack(side="left")

        # Inline reports loading spinner (hidden by default)
        self.reports_loading_spinner = tb.Progressbar(
            button_frame,
            mode="indeterminate",
            bootstyle="info-striped",
            length=120
        )
        # Will be packed dynamically right after the Generate Report button

        # Summary cards
        self.summary_frame = tb.Frame(self.reports_frame)
        self.summary_frame.pack(fill="x", padx=20, pady=10)
        
        # Create summary cards
        self.total_routers_card = tb.LabelFrame(self.summary_frame, text="Total Routers", bootstyle="primary", padding=10)
        self.total_routers_card.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.total_routers_label = tb.Label(self.total_routers_card, text="—", font=("Segoe UI", 14, "bold"))
        self.total_routers_label.pack()
        # Initialize with actual router count so it doesn't remain as '—'
        try:
            total_routers_now = len(get_routers())
            self.total_routers_label.config(text=str(total_routers_now))
        except Exception:
            # If fetching routers fails at build time, it will be updated later by report generation
            pass
        
        self.avg_uptime_card = tb.LabelFrame(self.summary_frame, text="Avg Uptime", bootstyle="success", padding=10)
        self.avg_uptime_card.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.avg_uptime_label = tb.Label(self.avg_uptime_card, text="—", font=("Segoe UI", 14, "bold"))
        self.avg_uptime_label.pack()
        
        self.total_bandwidth_card = tb.LabelFrame(self.summary_frame, text="Total Bandwidth", bootstyle="info", padding=10)
        self.total_bandwidth_card.grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        self.total_bandwidth_label = tb.Label(self.total_bandwidth_card, text="—", font=("Segoe UI", 14, "bold"))
        self.total_bandwidth_label.pack()
        
        # Configure grid weights
        for i in range(3):
            self.summary_frame.grid_columnconfigure(i, weight=1)

        # Main content area with notebook
        self.reports_notebook = tb.Notebook(self.reports_frame)
        self.reports_notebook.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Data table tab
        self.reports_table_frame = tb.Frame(self.reports_notebook)
        self.reports_notebook.add(self.reports_table_frame, text="📋 Data Table")

        # Table with scrollbars
        table_container = tb.Frame(self.reports_table_frame)
        table_container.pack(fill="both", expand=True, padx=10, pady=10)

        # Create treeview
        columns = ("router_name", "uptime_percentage", "downtime", "bandwidth_usage")
        self.uptime_tree = ttk.Treeview(table_container, columns=columns, show="headings", height=20)
        
        # Configure columns
        self.uptime_tree.column("router_name", width=200, anchor="center")
        self.uptime_tree.column("uptime_percentage", width=150, anchor="center")
        self.uptime_tree.column("downtime", width=150, anchor="center")
        self.uptime_tree.column("bandwidth_usage", width=150, anchor="center")

        # Configure headers
        self.uptime_tree.heading("router_name", text="Router Name")
        self.uptime_tree.heading("uptime_percentage", text="Uptime %")
        self.uptime_tree.heading("downtime", text="Downtime")
        self.uptime_tree.heading("bandwidth_usage", text="Bandwidth Usage")

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(table_container, orient="vertical", command=self.uptime_tree.yview)
        h_scrollbar = ttk.Scrollbar(table_container, orient="horizontal", command=self.uptime_tree.xview)
        self.uptime_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Grid layout for table and scrollbars
        self.uptime_tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        table_container.grid_rowconfigure(0, weight=1)
        table_container.grid_columnconfigure(0, weight=1)
        
        # Bind mouse wheel scrolling
        def on_mousewheel_vertical(event):
            self.uptime_tree.yview_scroll(int(-1*(event.delta/120)), "units")
            return "break"
        
        def on_mousewheel_horizontal(event):
            self.uptime_tree.xview_scroll(int(-1*(event.delta/120)), "units")
            return "break"
        
        self.uptime_tree.bind("<MouseWheel>", on_mousewheel_vertical)
        self.uptime_tree.bind("<Shift-MouseWheel>", on_mousewheel_horizontal)

        # Charts tab
        self.reports_charts_frame = tb.Frame(self.reports_notebook)
        self.reports_notebook.add(self.reports_charts_frame, text="📈 Charts")

        # Create charts container
        charts_container = tb.Frame(self.reports_charts_frame)
        charts_container.pack(fill='both', expand=True, padx=10, pady=10)

        # Uptime chart
        self.uptime_chart_frame = tb.LabelFrame(charts_container, text="Uptime Trend", padding=10)
        self.uptime_chart_frame.pack(fill='both', expand=True, pady=(0, 10))

        # Initialize empty chart
        self.reports_fig, self.reports_ax = plt.subplots(figsize=(8, 4), dpi=100)
        self.reports_canvas = FigureCanvasTkAgg(self.reports_fig, master=self.uptime_chart_frame)
        self.reports_canvas.get_tk_widget().pack(fill='both', expand=True)

        # Initial empty chart
        self.reports_ax.set_title("Uptime Trend - Generate a report to view data")
        self.reports_ax.set_xlabel("Date")
        self.reports_ax.set_ylabel("Uptime %")
        self.reports_ax.grid(True, alpha=0.3)
        self.reports_canvas.draw()

        # Initialize auto-update
        self.report_auto_update_interval = 30000  # 30 seconds
        self.report_auto_update_job = None
        # Start auto-update after a short delay to ensure UI is fully built
        self.root.after(1000, self.start_report_auto_update)


    def generate_report_table(self, filter_mode="weekly", incremental=False):
        """Generate or incrementally update the reports table and charts.
        When incremental=True, only changed rows are updated/inserted/removed,
        and the spinner is not shown to avoid flicker during auto-refresh.
        """
        import threading
        # Prevent multiple overlapping generations
        if getattr(self, '_report_generation_thread', None) and self._report_generation_thread.is_alive():
            return
        if not incremental:
            self._show_reports_loading()
        try:
            self.root.update_idletasks()
        except Exception:
            pass

        def worker():
            try:
                from datetime import datetime, time, timedelta
                import matplotlib.pyplot as plt
                from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
                import mplcursors
                # Phase 1: parse dates
                self.root.after(0, self._update_reports_phase, "Parsing dates...")
                start_str = self.report_start_date.entry.get()
                end_str = self.report_end_date.entry.get()
                try:
                    start_date = datetime.combine(datetime.strptime(start_str, "%m/%d/%Y"), time.min)
                    end_date = datetime.combine(datetime.strptime(end_str, "%m/%d/%Y"), time.max)
                except ValueError:
                    start_date = datetime.combine(datetime.strptime(start_str, "%m/%d/%Y"), time.min)
                    end_date = datetime.combine(datetime.strptime(end_str, "%m/%d/%Y"), time.max)
                if start_date > end_date:
                    from tkinter import messagebox
                    self.root.after(0, lambda: messagebox.showerror("Invalid Date Range", "Start date cannot be after end date."))
                    self.root.after(0, self._hide_reports_loading)
                    return
                if getattr(self, '_report_cancel_requested', False) or not getattr(self, 'app_running', True):
                    self.root.after(0, self._hide_reports_loading)
                    return

                # Phase 2: fetch routers
                self.root.after(0, self._update_reports_phase, "Loading routers...")
                routers = get_routers()
                if getattr(self, '_report_cancel_requested', False) or not getattr(self, 'app_running', True):
                    self.root.after(0, self._hide_reports_loading)
                    return

                # Initialize incremental caches
                if not hasattr(self, '_reports_row_items'):
                    self._reports_row_items = {}
                if not hasattr(self, '_reports_last_rows'):
                    self._reports_last_rows = {}

                # Clear previous table in full refresh only
                if not incremental and hasattr(self, 'uptime_tree'):
                    def _clear_all():
                        try:
                            self.uptime_tree.delete(*self.uptime_tree.get_children())
                            self._reports_row_items.clear()
                            self._reports_last_rows.clear()
                        except Exception:
                            pass
                    self.root.after(0, _clear_all)

                total_uptime = 0
                total_bandwidth = 0
                router_count = len(routers)

                # Phase 3: per-router stats
                # Build new snapshot for change detection
                new_rows = {}
                for idx, r in enumerate(routers, start=1):
                    if getattr(self, '_report_cancel_requested', False) or not getattr(self, 'app_running', True):
                        break
                    self.root.after(0, self._update_reports_phase, f"Processing router {idx}/{router_count}...")
                    router_id = r['id']
                    uptime = get_uptime_percentage(router_id, start_date, end_date)
                    downtime_seconds = (1 - uptime / 100) * (end_date - start_date).total_seconds()
                    bandwidth = get_bandwidth_usage(router_id, start_date, end_date)
                    total_uptime += uptime
                    total_bandwidth += bandwidth
                    # Prepare display values
                    def insert_row(r=r, uptime=uptime, downtime_seconds=downtime_seconds, bandwidth=bandwidth):
                        if not hasattr(self, 'uptime_tree'):
                            return
                        def format_downtime(seconds):
                            days, remainder = divmod(seconds, 86400)
                            hours, remainder = divmod(remainder, 3600)
                            minutes, sec = divmod(remainder, 60)
                            if days > 0: return f"{days}d {hours}h {minutes}m"
                            elif hours > 0: return f"{hours}h {minutes}m"
                            elif minutes > 0: return f"{minutes}m {sec}s"
                            else: return f"{sec}s"
                        bandwidth_str = f"{bandwidth / 1024:.2f} GB" if bandwidth >= 1024 else f"{bandwidth:.2f} MB"
                        key = r.get('id')
                        values = (
                            r['name'],
                            f"{uptime:.2f}%",
                            format_downtime(int(downtime_seconds)),
                            bandwidth_str
                        )
                        new_rows[key] = values
                        # Incremental upsert
                        def upsert():
                            try:
                                items = getattr(self, '_reports_row_items', {})
                                last = getattr(self, '_reports_last_rows', {})
                                if incremental and key in items:
                                    if last.get(key) != values:
                                        self.uptime_tree.item(items[key], values=values)
                                else:
                                    iid = self.uptime_tree.insert("", "end", values=values)
                                    items[key] = iid
                                last[key] = values
                            except Exception:
                                pass
                        self.root.after(0, upsert)

                    self.root.after(0, insert_row)

                if getattr(self, '_report_cancel_requested', False) or not getattr(self, 'app_running', True):
                    # Silently exit if app is closing (app_running=False)
                    if not getattr(self, 'app_running', True):
                        return
                    # Show cancelled message only if user explicitly cancelled
                    self.root.after(0, self._update_reports_phase, "Cancelled")
                    self.root.after(0, self._hide_reports_loading)
                    return

                # After rows, prune removed routers during incremental update
                if incremental:
                    def prune_removed():
                        try:
                            items = getattr(self, '_reports_row_items', {})
                            last = getattr(self, '_reports_last_rows', {})
                            existing_keys = set(items.keys())
                            new_keys = set(new_rows.keys())
                            for removed in list(existing_keys - new_keys):
                                try:
                                    self.uptime_tree.delete(items[removed])
                                except Exception:
                                    pass
                                items.pop(removed, None)
                                last.pop(removed, None)
                        except Exception:
                            pass
                    self.root.after(0, prune_removed)

                # Summary cards
                self.root.after(0, self._update_reports_phase, "Updating summary...")
                self.root.after(0, lambda: self.update_reports_summary_cards(router_count, total_uptime, total_bandwidth, router_count))

                # Phase 4: daily averages
                self.root.after(0, self._update_reports_phase, "Aggregating daily data...")
                def get_daily_avg_uptime(start_date, end_date):
                    days = (end_date - start_date).days + 1
                    results = []
                    for i in range(days):
                        day_start = start_date + timedelta(days=i)
                        day_end = day_start.replace(hour=23, minute=59, second=59)
                        uptimes = [get_uptime_percentage(r['id'], day_start, day_end) for r in routers]
                        avg_uptime = sum(uptimes) / len(uptimes) if uptimes else 0
                        results.append((day_start, avg_uptime))
                    return results
                daily_data = get_daily_avg_uptime(start_date, end_date)
                if getattr(self, '_report_cancel_requested', False) or not getattr(self, 'app_running', True):
                    self.root.after(0, self._hide_reports_loading)
                    return

                # Phase 5: aggregate by filter
                self.root.after(0, self._update_reports_phase, "Grouping data...")
                aggregated = {}
                for date, uptime in daily_data:
                    if filter_mode == "weekly":
                        key = date.strftime("Week %U (%Y)")
                    elif filter_mode == "monthly":
                        key = date.strftime("%B %Y")
                    else:
                        key = date.strftime("%m-%d")
                    aggregated.setdefault(key, []).append(uptime)
                agg_dates = list(aggregated.keys())
                agg_uptimes = [sum(vals) / len(vals) for vals in aggregated.values()]
                self.agg_dates = agg_dates
                self.agg_uptimes = agg_uptimes

                # Phase 6: rendering chart
                self.root.after(0, self._update_reports_phase, "Rendering chart...")
                def draw_chart():
                    # Check if the reports_charts_frame still exists
                    if not hasattr(self, 'reports_charts_frame') or not self.reports_charts_frame.winfo_exists():
                        return
                    for widget in self.reports_charts_frame.winfo_children():
                        widget.destroy()
                    # Close any previously open figure to avoid accumulating pyplot figures
                    try:
                        import matplotlib.pyplot as plt
                        if hasattr(self, 'current_fig') and getattr(self, 'current_fig') is not None:
                            plt.close(self.current_fig)
                    except Exception:
                        pass
                    fig, ax = plt.subplots(figsize=(8, 4))
                    line, = ax.plot(range(len(agg_dates)), agg_uptimes, marker="o", linestyle="-", color="blue", label="Avg Uptime %")
                    ax.set_ylim(0, 100)
                    ax.set_ylabel("Uptime %")
                    if filter_mode == "weekly":
                        ax.set_title("Average Router Uptime (Weekly)")
                        ax.set_xlabel("Week #")
                        x_labels = [f"W{i+1}" for i in range(len(agg_dates))]
                    elif filter_mode == "monthly":
                        ax.set_title("Average Router Uptime (Monthly)")
                        ax.set_xlabel("Month")
                        x_labels = agg_dates
                    else:
                        ax.set_title("Average Router Uptime (Daily)")
                        ax.set_xlabel("Date")
                        x_labels = agg_dates
                    ax.set_xticks(range(len(agg_dates)))
                    ax.set_xticklabels(x_labels, rotation=45, ha="right")
                    ax.grid(True)
                    fig.tight_layout()
                    cursor = mplcursors.cursor(line, hover=True)
                    @cursor.connect("add")
                    def on_hover(sel):
                        idx = int(round(sel.index))
                        if 0 <= idx < len(agg_dates):
                            sel.annotation.set_text(f"{agg_dates[idx]}\nUptime: {agg_uptimes[idx]:.2f}%")
                            sel.annotation.get_bbox_patch().set(fc="white", alpha=0.8)
                    canvas = FigureCanvasTkAgg(fig, master=self.reports_charts_frame)
                    canvas.draw()
                    canvas.get_tk_widget().pack(fill="both", expand=True)
                    self.current_fig = fig
                def finish():
                    # Check if the reports_charts_frame still exists before proceeding
                    if not hasattr(self, 'reports_charts_frame') or not self.reports_charts_frame.winfo_exists():
                        return
                    if not hasattr(self, 'chart_visible'):
                        self.chart_visible = True
                    if not hasattr(self, 'toggle_btn'):
                        import ttkbootstrap as tb
                        self.toggle_btn = tb.Button(self.reports_charts_frame, text="Hide Chart", command=lambda: self.toggle_chart(), bootstyle="secondary")
                        self.toggle_btn.pack(anchor="ne", padx=5, pady=2)
                    if self.chart_visible and not getattr(self, '_report_cancel_requested', False):
                        draw_chart()
                    if getattr(self, '_report_cancel_requested', False) or not getattr(self, 'app_running', True):
                        # Silently exit if app is closing
                        if not getattr(self, 'app_running', True):
                            return
                        # Show cancelled message only if user explicitly cancelled
                        self._update_reports_phase("Cancelled")
                    else:
                        self._update_reports_phase("Done")
                    if not incremental:
                        self._hide_reports_loading()
                self.root.after(0, finish)
            except Exception as e:
                from tkinter import messagebox
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
                self.root.after(0, self._hide_reports_loading)

        self._report_generation_thread = threading.Thread(target=worker, daemon=True)
        self._report_generation_thread.start()
            
    def print_report(self):
        """Show print preview window with report and charts - uses fresh DB data"""
        try:
            if not hasattr(self, 'uptime_tree'):
                from tkinter import messagebox
                messagebox.showwarning("No Data", "No data to print. Please generate a report first.")
                return
            
            # Get fresh data from database using current report filters
            from report_utils import get_uptime_percentage, get_bandwidth_usage
            from datetime import timedelta
            
            # Get date range from UI
            if hasattr(self, 'report_start_date'):
                start_date = datetime.strptime(self.report_start_date.entry.get(), "%m/%d/%Y")
            else:
                start_date = datetime.now() - timedelta(days=7)
            
            if hasattr(self, 'report_end_date'):
                end_date = datetime.strptime(self.report_end_date.entry.get(), "%m/%d/%Y")
            else:
                end_date = datetime.now()
            
            # Get filter mode
            filter_mode = self.report_mode.get().lower() if hasattr(self, 'report_mode') else "all"
            
            # Fetch routers based on filter
            from router_utils import get_routers
            if filter_mode == "all":
                routers = get_routers()
            elif filter_mode == "online_only":
                routers = [r for r in get_routers() if r.get('status') == 'online']
            elif filter_mode == "offline_only":
                routers = [r for r in get_routers() if r.get('status') != 'online']
            else:
                routers = get_routers()
            
            if not routers:
                from tkinter import messagebox
                messagebox.showwarning("No Data", "No routers found matching the current filter.")
                return
            
            # Build fresh data from database queries
            data = []
            for r in routers:
                router_id = r['id']
                uptime = get_uptime_percentage(router_id, start_date, end_date)
                downtime_seconds = (1 - uptime / 100) * (end_date - start_date).total_seconds()
                bandwidth = get_bandwidth_usage(router_id, start_date, end_date)
                
                # Format values matching display format
                def format_downtime(seconds):
                    days, remainder = divmod(seconds, 86400)
                    hours, remainder = divmod(remainder, 3600)
                    minutes, sec = divmod(remainder, 60)
                    if days > 0: return f"{days}d {hours}h {minutes}m"
                    elif hours > 0: return f"{hours}h {minutes}m"
                    elif minutes > 0: return f"{minutes}m {sec}s"
                    else: return f"{sec}s"
                
                bandwidth_str = f"{bandwidth / 1024:.2f} GB" if bandwidth >= 1024 else f"{bandwidth:.2f} MB"
                
                values = (
                    r['name'],
                    f"{uptime:.2f}%",
                    format_downtime(int(downtime_seconds)),
                    bandwidth_str
                )
                data.append(values)
            
            if data:
                # Show print preview window with fresh data
                self._show_print_preview(data)
            else:
                from tkinter import messagebox
                messagebox.showwarning("No Data", "No data to print. Please generate a report first.")
                
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error", f"Error showing print preview: {e}")

    def _show_print_preview(self, data):
        """Show print preview window with report and charts"""
        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from datetime import datetime
            
            # Create preview window
            preview_window = tb.Toplevel(self.root)
            preview_window.title("Print Preview - Network Report")
            
            # Set window size and center it
            window_width = 900
            window_height = 600
            screen_width = preview_window.winfo_screenwidth()
            screen_height = preview_window.winfo_screenheight()
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            preview_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
            preview_window.resizable(True, True)
            
            # Set minimum size
            preview_window.minsize(800, 500)
            
            # Create main frame with scrollbar
            main_frame = tb.Frame(preview_window)
            main_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Create canvas and scrollbar for scrolling
            canvas = tb.Canvas(main_frame, highlightthickness=0)
            v_scrollbar = tb.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
            h_scrollbar = tb.Scrollbar(main_frame, orient="horizontal", command=canvas.xview)
            scrollable_frame = tb.Frame(canvas)
            
            # Configure scrolling
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
            
            # Mouse wheel scrolling (widget-scoped; avoids global bind_all)
            def _on_mousewheel(event):
                try:
                    if event.delta:
                        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                except tk.TclError:
                    pass

            def _on_button4(event):
                try:
                    canvas.yview_scroll(-1, "units")
                except tk.TclError:
                    pass

            def _on_button5(event):
                try:
                    canvas.yview_scroll(1, "units")
                except tk.TclError:
                    pass

            canvas.bind("<MouseWheel>", _on_mousewheel)
            canvas.bind("<Button-4>", _on_button4)
            canvas.bind("<Button-5>", _on_button5)
            
            # Header section
            header_frame = tb.LabelFrame(scrollable_frame, text="Report Header", padding=10)
            header_frame.pack(fill="x", pady=(0, 10))
            
            # Title
            title_label = tb.Label(header_frame, text="WINYFI Network Monitoring Report", 
                                 font=("Segoe UI", 16, "bold"))
            title_label.pack()
            
            # Report info
            report_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            view_mode = self.report_mode.get() if hasattr(self, 'report_mode') else "Weekly"
            info_text = f"Generated on: {report_date} | View Mode: {view_mode} | Total Routers: {len(data)}"
            info_label = tb.Label(header_frame, text=info_text, font=("Segoe UI", 10))
            info_label.pack(pady=(5, 0))
            
            # Data table section
            table_frame = tb.LabelFrame(scrollable_frame, text="Report Data", padding=10)
            table_frame.pack(fill="x", pady=(0, 10))
            
            # Create table
            columns = ("Router Name", "Uptime %", "Downtime", "Bandwidth Usage")
            table = ttk.Treeview(table_frame, columns=columns, show="headings", height=min(len(data), 15))
            
            # Configure columns
            table.column("Router Name", width=200, anchor="center")
            table.column("Uptime %", width=120, anchor="center")
            table.column("Downtime", width=150, anchor="center")
            table.column("Bandwidth Usage", width=150, anchor="center")
            
            # Configure headers
            table.heading("Router Name", text="Router Name")
            table.heading("Uptime %", text="Uptime %")
            table.heading("Downtime", text="Downtime")
            table.heading("Bandwidth Usage", text="Bandwidth Usage")
            
            # Add data to table
            for row in data:
                table.insert("", "end", values=row)
            
            table.pack(fill="x")
            
            # Charts section
            charts_frame = tb.LabelFrame(scrollable_frame, text="Charts", padding=10)
            charts_frame.pack(fill="both", expand=True, pady=(0, 10))
            
            # Create charts based on view mode
            self._create_preview_charts(charts_frame, data, view_mode)
            
            # Summary section
            summary_frame = tb.LabelFrame(scrollable_frame, text="Summary", padding=10)
            summary_frame.pack(fill="x", pady=(0, 10))
            
            # Calculate summary statistics
            if data:
                uptime_values = [float(row[1].replace('%', '')) for row in data if row[1] != '—' and row[1] != '']
                if uptime_values:
                    avg_uptime = sum(uptime_values) / len(uptime_values)
                    max_uptime = max(uptime_values)
                    min_uptime = min(uptime_values)
                    
                    summary_text = f"Average Uptime: {avg_uptime:.1f}% | Max Uptime: {max_uptime:.1f}% | Min Uptime: {min_uptime:.1f}%"
                    summary_label = tb.Label(summary_frame, text=summary_text, font=("Segoe UI", 10, "bold"))
                    summary_label.pack()
            
            # Clean up binding when window closes
            def _on_close():
                try:
                    canvas.unbind("<MouseWheel>")
                    canvas.unbind("<Button-4>")
                    canvas.unbind("<Button-5>")
                except Exception:
                    pass
                preview_window.destroy()
            
            # Action buttons
            button_frame = tb.Frame(scrollable_frame)
            button_frame.pack(fill="x", pady=(10, 0))
            
            tb.Button(button_frame, text="🖨️ Print to PDF", bootstyle="primary",
                     command=lambda: self._print_preview_to_pdf(data, view_mode)).pack(side="left", padx=(0, 10))
            tb.Button(button_frame, text="📄 Print to Text", bootstyle="info",
                     command=lambda: self._print_preview_to_text(data, view_mode)).pack(side="left", padx=(0, 10))
            tb.Button(button_frame, text="❌ Close", bootstyle="secondary",
                     command=_on_close).pack(side="right")
            
            # Pack canvas and scrollbars
            canvas.grid(row=0, column=0, sticky="nsew")
            v_scrollbar.grid(row=0, column=1, sticky="ns")
            h_scrollbar.grid(row=1, column=0, sticky="ew")
            
            # Configure grid weights
            main_frame.grid_rowconfigure(0, weight=1)
            main_frame.grid_columnconfigure(0, weight=1)
            
            # Bind close event
            preview_window.protocol("WM_DELETE_WINDOW", _on_close)
            
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error", f"Error creating print preview: {e}")

    def _create_preview_charts(self, parent_frame, data, view_mode):
        """Create charts for the preview window"""
        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            import numpy as np
            
            # Create figure with subplots (3 charts: bar, pie, line) - arranged vertically for portrait
            fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(8, 12))
            fig.suptitle(f"Network Report Charts - {view_mode} View", fontsize=14, fontweight='bold')
            
            # Extract data for charts
            router_names = [row[0] for row in data]
            uptime_values = []
            for row in data:
                try:
                    uptime = float(row[1].replace('%', '')) if row[1] != '—' and row[1] != '' else 0
                    uptime_values.append(uptime)
                except (ValueError, IndexError):
                    uptime_values.append(0)
            
            # Chart 1: Uptime Bar Chart
            ax1.bar(range(len(router_names)), uptime_values, color='skyblue', edgecolor='navy', alpha=0.7)
            ax1.set_title('Router Uptime Comparison')
            ax1.set_xlabel('Routers')
            ax1.set_ylabel('Uptime %')
            ax1.set_ylim(0, 100)
            ax1.set_xticks(range(len(router_names)))
            ax1.set_xticklabels(router_names, rotation=45, ha='right')
            ax1.grid(True, alpha=0.3)
            
            # Add value labels on bars
            for i, v in enumerate(uptime_values):
                ax1.text(i, v + 1, f'{v:.1f}%', ha='center', va='bottom', fontsize=8)
            
            # Chart 2: Uptime Distribution Pie Chart
            if uptime_values:
                # Categorize uptime levels
                excellent = len([x for x in uptime_values if x >= 95])
                good = len([x for x in uptime_values if 80 <= x < 95])
                fair = len([x for x in uptime_values if 60 <= x < 80])
                poor = len([x for x in uptime_values if x < 60])
                
                categories = ['Excellent (≥95%)', 'Good (80-94%)', 'Fair (60-79%)', 'Poor (<60%)']
                values = [excellent, good, fair, poor]
                colors = ['green', 'lightgreen', 'orange', 'red']
                
                # Only show categories with data
                filtered_categories = []
                filtered_values = []
                filtered_colors = []
                for i, val in enumerate(values):
                    if val > 0:
                        filtered_categories.append(categories[i])
                        filtered_values.append(val)
                        filtered_colors.append(colors[i])
                
                if filtered_values:
                    ax2.pie(filtered_values, labels=filtered_categories, colors=filtered_colors, 
                           autopct='%1.1f%%', startangle=90)
                    ax2.set_title('Uptime Distribution')
                else:
                    ax2.text(0.5, 0.5, 'No Data', ha='center', va='center', transform=ax2.transAxes)
                    ax2.set_title('Uptime Distribution')
            
            # Chart 3: Uptime Trend Line Chart
            try:
                # Use existing aggregated data from generate_report_table
                if hasattr(self, 'agg_dates') and hasattr(self, 'agg_uptimes') and self.agg_dates and self.agg_uptimes:
                    dates = self.agg_dates
                    uptimes = self.agg_uptimes
                    
                    # Create line chart
                    ax3.plot(range(len(dates)), uptimes, marker='o', linewidth=2, markersize=6, color='#2c7be5')
                    ax3.set_title(f'Average Uptime Trend - {view_mode.title()}')
                    ax3.set_xlabel('Period')
                    ax3.set_ylabel('Uptime %')
                    ax3.grid(True, alpha=0.3)
                    ax3.set_ylim(0, 100)
                    ax3.set_xticks(range(len(dates)))
                    ax3.set_xticklabels(dates, rotation=45, ha='right')
                    
                    # Add value labels on points
                    for i, v in enumerate(uptimes):
                        ax3.text(i, v + 2, f'{v:.1f}%', ha='center', va='bottom', fontsize=8)
                else:
                    ax3.text(0.5, 0.5, 'No Trend Data Available', ha='center', va='center', 
                            transform=ax3.transAxes, fontsize=12)
                    ax3.set_title(f'Average Uptime Trend - {view_mode.title()}')
            except Exception as e:
                print(f"Error creating line chart in preview: {e}")
                ax3.text(0.5, 0.5, 'Error Loading Trend Data', ha='center', va='center', 
                        transform=ax3.transAxes, fontsize=12)
                ax3.set_title(f'Average Uptime Trend - {view_mode.title()}')
            
            plt.tight_layout()
            
            # Embed chart in tkinter
            chart_canvas = FigureCanvasTkAgg(fig, parent_frame)
            chart_canvas.get_tk_widget().pack(fill="both", expand=True)
            
        except Exception as e:
            print(f"Error creating preview charts: {e}")

    def _print_preview_to_pdf(self, data, view_mode):
        """Print preview data to PDF"""
        try:
            from tkinter import filedialog
            from datetime import datetime
            
            # Ask user where to save the file
            filename = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                title="Save Report As PDF"
            )
            
            if not filename:
                return  # User cancelled
            
            # Generate PDF with charts
            self._generate_pdf_report_with_charts(data, view_mode, filename)
            
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error", f"Error saving PDF: {e}")

    def _print_preview_to_text(self, data, view_mode):
        """Print preview data to text file"""
        try:
            from tkinter import filedialog
            from datetime import datetime
            
            # Ask user where to save the file
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                title="Save Report As Text"
            )
            
            if not filename:
                return  # User cancelled
            
            # Generate text report
            self._generate_text_report(data, filename)
            
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error", f"Error saving text file: {e}")

    def _generate_pdf_report_with_charts(self, data, view_mode, filename):
        """Generate PDF report with charts"""
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
            from reportlab.lib.units import inch
            import matplotlib.pyplot as plt
            import io
            import base64
            import tempfile
            import os
            import time
            
            # Create PDF document
            doc = SimpleDocTemplate(filename, pagesize=A4)
            story = []
            styles = getSampleStyleSheet()
            
            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                spaceAfter=30,
                alignment=1
            )
            title = Paragraph("WINYFI Network Monitoring Report", title_style)
            story.append(title)
            
            # Report info
            info_style = ParagraphStyle(
                'Info',
                parent=styles['Normal'],
                fontSize=10,
                spaceAfter=20,
                alignment=1
            )
            report_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            info_text = f"Generated on: {report_date}<br/>View Mode: {view_mode}<br/>Total Routers: {len(data)}"
            info = Paragraph(info_text, info_style)
            story.append(info)
            story.append(Spacer(1, 20))
            
            # Create table data
            table_data = [['Router Name', 'Uptime %', 'Downtime', 'Bandwidth Usage']]
            for row in data:
                table_data.append(row)
            
            # Create table
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
            ]))
            
            story.append(table)
            story.append(Spacer(1, 30))
            
            # Summary statistics
            if data:
                uptime_values = [float(row[1].replace('%', '')) for row in data if row[1] != '—' and row[1] != '']
                if uptime_values:
                    avg_uptime = sum(uptime_values) / len(uptime_values)
                    max_uptime = max(uptime_values)
                    min_uptime = min(uptime_values)
                    summary_text = f"Average Uptime: {avg_uptime:.1f}% | Max Uptime: {max_uptime:.1f}% | Min Uptime: {min_uptime:.1f}%"
                    summary = Paragraph(summary_text, info_style)
                    story.append(summary)
            
            # Generate and add charts
            story.append(Spacer(1, 20))
            charts_heading = Paragraph("Charts", styles['Heading2'])
            story.append(charts_heading)
            story.append(Spacer(1, 10))
            
            # Create charts and save as images
            chart_images = self._create_pdf_charts(data, view_mode)
            
            # If no charts were created successfully, add a fallback text summary
            if not chart_images:
                print("No charts created successfully, adding text summary instead")
                fallback_text = "Chart generation failed. Here's a text summary:\n\n"
                if data:
                    uptime_values = []
                    for row in data:
                        try:
                            uptime = float(row[1].replace('%', '')) if row[1] != '—' and row[1] != '' else 0
                            uptime_values.append(uptime)
                        except (ValueError, IndexError):
                            uptime_values.append(0)
                    
                    if uptime_values:
                        avg_uptime = sum(uptime_values) / len(uptime_values)
                        max_uptime = max(uptime_values)
                        min_uptime = min(uptime_values)
                        fallback_text += f"Average Uptime: {avg_uptime:.1f}%\n"
                        fallback_text += f"Highest Uptime: {max_uptime:.1f}%\n"
                        fallback_text += f"Lowest Uptime: {min_uptime:.1f}%\n"
                        fallback_text += f"Total Routers: {len(data)}"
                
                fallback_para = Paragraph(fallback_text, styles['Normal'])
                story.append(fallback_para)
                story.append(Spacer(1, 20))
            
            # Add charts to PDF with robust file handling
            accessible_chart_paths = []  # Keep track of accessible files for cleanup later
            
            for chart_path in chart_images:
                if os.path.exists(chart_path) and os.path.getsize(chart_path) > 0:
                    try:
                        # Create a copy of the file in a more accessible location
                        import tempfile
                        import shutil
                        
                        # Create a new temporary file with a more accessible name
                        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                        accessible_chart_path = temp_file.name
                        temp_file.close()
                        
                        # Copy the original file to the new location
                        shutil.copy2(chart_path, accessible_chart_path)
                        
                        # Wait and verify the copy is accessible
                        time.sleep(0.3)
                        
                        # Verify the copied file
                        if os.path.exists(accessible_chart_path) and os.path.getsize(accessible_chart_path) > 0:
                            # Try to open and read the file to ensure it's accessible
                            with open(accessible_chart_path, 'rb') as test_file:
                                test_data = test_file.read(1024)
                                if len(test_data) > 0:
                                    print(f"File copy verified, size: {os.path.getsize(accessible_chart_path)} bytes")
                                    
                                    # Create ReportLab Image with the accessible path - optimized for portrait
                                    img = Image(accessible_chart_path, width=5.5*inch, height=4*inch)
                                    img.hAlign = 'CENTER'
                                    story.append(img)
                                    story.append(Spacer(1, 15))
                                    print(f"Successfully added chart to PDF: {accessible_chart_path}")
                                    
                                    # Keep track of the accessible file for later cleanup
                                    accessible_chart_paths.append(accessible_chart_path)
                                else:
                                    print(f"Warning: Copied file is empty: {accessible_chart_path}")
                        else:
                            print(f"Warning: File copy failed: {accessible_chart_path}")
                        
                    except Exception as e:
                        print(f"Warning: Could not add chart {chart_path}: {e}")
                        import traceback
                        traceback.print_exc()
                        continue
                    finally:
                        # Clean up original temporary directory
                        try:
                            chart_dir = os.path.dirname(chart_path)
                            if chart_dir and os.path.exists(chart_dir):
                                shutil.rmtree(chart_dir)
                                print(f"Cleaned up chart directory: {chart_dir}")
                        except Exception as cleanup_error:
                            print(f"Error cleaning up chart directory: {cleanup_error}")
                else:
                    print(f"Warning: Chart file not found or empty: {chart_path}")
            
            # Build PDF first, then clean up accessible files
            print("Building PDF...")
            doc.build(story)
            print("PDF built successfully!")
            
            # Now clean up the accessible chart files
            for accessible_path in accessible_chart_paths:
                try:
                    if os.path.exists(accessible_path):
                        os.unlink(accessible_path)
                        print(f"Cleaned up accessible chart file: {accessible_path}")
                except Exception as cleanup_error:
                    print(f"Error cleaning up accessible chart file {accessible_path}: {cleanup_error}")
            
            from tkinter import messagebox
            messagebox.showinfo("Success", f"PDF report with charts saved successfully!\nLocation: {filename}")
            
        except ImportError:
            # Fallback to text if ReportLab not available
            self._generate_text_report(data, filename)
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error", f"Error generating PDF: {e}")

    def _create_pdf_charts(self, data, view_mode):
        """Create charts for PDF and return image file paths"""
        try:
            import matplotlib.pyplot as plt
            import tempfile
            import os
            import time
            
            chart_paths = []
            
            # Extract data for charts
            router_names = [row[0] for row in data]
            uptime_values = []
            for row in data:
                try:
                    uptime = float(row[1].replace('%', '')) if row[1] != '—' and row[1] != '' else 0
                    uptime_values.append(uptime)
                except (ValueError, IndexError):
                    uptime_values.append(0)
            
            # Chart 1: Uptime Bar Chart
            fig1, ax1 = plt.subplots(figsize=(8, 5))
            bars = ax1.bar(range(len(router_names)), uptime_values, color='skyblue', edgecolor='navy', alpha=0.7)
            ax1.set_title(f'Router Uptime Comparison - {view_mode} View', fontsize=14, fontweight='bold')
            ax1.set_xlabel('Routers', fontsize=12)
            ax1.set_ylabel('Uptime %', fontsize=12)
            ax1.set_ylim(0, 100)
            ax1.set_xticks(range(len(router_names)))
            ax1.set_xticklabels(router_names, rotation=45, ha='right')
            ax1.grid(True, alpha=0.3)
            
            # Add value labels on bars
            for i, v in enumerate(uptime_values):
                ax1.text(i, v + 1, f'{v:.1f}%', ha='center', va='bottom', fontsize=8)
            
            plt.tight_layout()
            
            # Save bar chart with robust file handling
            temp_dir1 = tempfile.mkdtemp()
            temp_path1 = os.path.join(temp_dir1, 'bar_chart.png')
            
            try:
                # Ensure figure is properly rendered
                fig1.canvas.draw()
                plt.savefig(temp_path1, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none', format='png')
                plt.close(fig1)
                
                # Force matplotlib to flush all buffers
                import matplotlib.pyplot as plt
                plt.close('all')
                
                # Wait and verify file creation with retries
                max_retries = 5
                for attempt in range(max_retries):
                    time.sleep(0.3)  # Longer wait between attempts
                    if os.path.exists(temp_path1) and os.path.getsize(temp_path1) > 0:
                        try:
                            # Simple file verification
                            with open(temp_path1, 'rb') as test_file:
                                test_data = test_file.read(1024)  # Read more data
                                if len(test_data) > 0:
                                    # File is readable and has content
                                    pass
                            
                            # Additional verification - try to open with PIL if available
                            try:
                                from PIL import Image as PILImage
                                with PILImage.open(temp_path1) as pil_img:
                                    pil_img.verify()  # Verify the image is valid
                                print(f"Bar chart verified with PIL: {temp_path1}")
                            except ImportError:
                                print(f"PIL not available, using basic verification")
                            except Exception as pil_error:
                                print(f"PIL verification failed: {pil_error}")
                            
                            chart_paths.append(temp_path1)
                            print(f"Bar chart saved successfully: {temp_path1}")
                            break
                        except Exception as read_error:
                            print(f"Attempt {attempt + 1}: Bar chart file not readable: {read_error}")
                            if attempt < max_retries - 1:
                                time.sleep(0.5)
                                continue
                    else:
                        print(f"Attempt {attempt + 1}: Bar chart file not found or empty")
                        if attempt < max_retries - 1:
                            time.sleep(0.5)
                            continue
                else:
                    print(f"Warning: Bar chart file not created properly after all retries")
                    # Clean up failed attempt
                    try:
                        shutil.rmtree(temp_dir1)
                    except:
                        pass
            except Exception as e:
                print(f"Error saving bar chart: {e}")
                plt.close(fig1)
                try:
                    shutil.rmtree(temp_dir1)
                except:
                    pass
            
            # Chart 2: Uptime Distribution Pie Chart
            if uptime_values:
                fig2, ax2 = plt.subplots(figsize=(8, 5))
                
                # Categorize uptime levels
                excellent = len([x for x in uptime_values if x >= 95])
                good = len([x for x in uptime_values if 80 <= x < 95])
                fair = len([x for x in uptime_values if 60 <= x < 80])
                poor = len([x for x in uptime_values if x < 60])
                
                categories = ['Excellent (≥95%)', 'Good (80-94%)', 'Fair (60-79%)', 'Poor (<60%)']
                values = [excellent, good, fair, poor]
                colors = ['#2E8B57', '#90EE90', '#FFA500', '#FF6347']
                
                # Only show categories with data
                filtered_categories = []
                filtered_values = []
                filtered_colors = []
                for i, val in enumerate(values):
                    if val > 0:
                        filtered_categories.append(categories[i])
                        filtered_values.append(val)
                        filtered_colors.append(colors[i])
                
                if filtered_values:
                    wedges, texts, autotexts = ax2.pie(filtered_values, labels=filtered_categories, 
                                                      colors=filtered_colors, autopct='%1.1f%%', 
                                                      startangle=90, textprops={'fontsize': 10})
                    ax2.set_title(f'Uptime Distribution - {view_mode} View', fontsize=14, fontweight='bold')
                    
                    # Enhance text visibility
                    for autotext in autotexts:
                        autotext.set_color('white')
                        autotext.set_fontweight('bold')
                else:
                    ax2.text(0.5, 0.5, 'No Data Available', ha='center', va='center', 
                            transform=ax2.transAxes, fontsize=12)
                    ax2.set_title(f'Uptime Distribution - {view_mode} View', fontsize=14, fontweight='bold')
                
                plt.tight_layout()
                
                # Save pie chart with robust file handling
                temp_dir2 = tempfile.mkdtemp()
                temp_path2 = os.path.join(temp_dir2, 'pie_chart.png')
                
                try:
                    # Ensure figure is properly rendered
                    fig2.canvas.draw()
                    plt.savefig(temp_path2, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none', format='png')
                    plt.close(fig2)
                    
                    # Force matplotlib to flush all buffers
                    import matplotlib.pyplot as plt
                    plt.close('all')
                    
                    # Wait and verify file creation with retries
                    max_retries = 5
                    for attempt in range(max_retries):
                        time.sleep(0.3)  # Longer wait between attempts
                        if os.path.exists(temp_path2) and os.path.getsize(temp_path2) > 0:
                            try:
                                # Simple file verification
                                with open(temp_path2, 'rb') as test_file:
                                    test_data = test_file.read(1024)  # Read more data
                                    if len(test_data) > 0:
                                        # File is readable and has content
                                        pass
                                
                                # Additional verification - try to open with PIL if available
                                try:
                                    from PIL import Image as PILImage
                                    with PILImage.open(temp_path2) as pil_img:
                                        pil_img.verify()  # Verify the image is valid
                                    print(f"Pie chart verified with PIL: {temp_path2}")
                                except ImportError:
                                    print(f"PIL not available, using basic verification")
                                except Exception as pil_error:
                                    print(f"PIL verification failed: {pil_error}")
                                
                                chart_paths.append(temp_path2)
                                print(f"Pie chart saved successfully: {temp_path2}")
                                break
                            except Exception as read_error:
                                print(f"Attempt {attempt + 1}: Pie chart file not readable: {read_error}")
                                if attempt < max_retries - 1:
                                    time.sleep(0.5)
                                    continue
                        else:
                            print(f"Attempt {attempt + 1}: Pie chart file not found or empty")
                            if attempt < max_retries - 1:
                                time.sleep(0.5)
                                continue
                    else:
                        print(f"Warning: Pie chart file not created properly after all retries")
                        # Clean up failed attempt
                        try:
                            shutil.rmtree(temp_dir2)
                        except:
                            pass
                except Exception as e:
                    print(f"Error saving pie chart: {e}")
                    plt.close(fig2)
                    try:
                        shutil.rmtree(temp_dir2)
                    except:
                        pass
            
            # Chart 3: Uptime Trend Line Chart
            try:
                # Use existing aggregated data from generate_report_table
                if hasattr(self, 'agg_dates') and hasattr(self, 'agg_uptimes') and self.agg_dates and self.agg_uptimes:
                    fig3, ax3 = plt.subplots(figsize=(8, 5))
                    
                    dates = self.agg_dates
                    uptimes = self.agg_uptimes
                    
                    # Create line chart
                    ax3.plot(range(len(dates)), uptimes, marker='o', linewidth=2, markersize=6, color='#2c7be5')
                    ax3.set_title(f'Average Uptime Trend - {view_mode} View', fontsize=14, fontweight='bold')
                    ax3.set_xlabel('Period', fontsize=12)
                    ax3.set_ylabel('Uptime %', fontsize=12)
                    ax3.grid(True, alpha=0.3)
                    ax3.set_ylim(0, 100)
                    ax3.set_xticks(range(len(dates)))
                    ax3.set_xticklabels(dates, rotation=45, ha='right')
                    
                    # Add value labels on points
                    for i, v in enumerate(uptimes):
                        ax3.text(i, v + 2, f'{v:.1f}%', ha='center', va='bottom', fontsize=10)
                    
                    plt.tight_layout()
                    
                    # Save line chart with robust file handling
                    temp_dir3 = tempfile.mkdtemp()
                    temp_path3 = os.path.join(temp_dir3, 'line_chart.png')
                    
                    try:
                        # Ensure figure is properly rendered
                        fig3.canvas.draw()
                        plt.savefig(temp_path3, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none', format='png')
                        plt.close(fig3)
                        
                        # Force matplotlib to flush all buffers
                        import matplotlib.pyplot as plt
                        plt.close('all')
                        
                        # Wait and verify file creation with retries
                        max_retries = 5
                        for attempt in range(max_retries):
                            time.sleep(0.3)
                            if os.path.exists(temp_path3) and os.path.getsize(temp_path3) > 0:
                                try:
                                    # Simple file verification
                                    with open(temp_path3, 'rb') as test_file:
                                        test_data = test_file.read(1024)
                                        if len(test_data) > 0:
                                            pass
                                    
                                    # Additional verification - try to open with PIL if available
                                    try:
                                        from PIL import Image as PILImage
                                        with PILImage.open(temp_path3) as pil_img:
                                            pil_img.verify()
                                        print(f"Line chart verified with PIL: {temp_path3}")
                                    except ImportError:
                                        print(f"PIL not available, using basic verification")
                                    except Exception as pil_error:
                                        print(f"PIL verification failed: {pil_error}")
                                    
                                    chart_paths.append(temp_path3)
                                    print(f"Line chart saved successfully: {temp_path3}")
                                    break
                                except Exception as read_error:
                                    print(f"Attempt {attempt + 1}: Line chart file not readable: {read_error}")
                                    if attempt < max_retries - 1:
                                        time.sleep(0.5)
                                        continue
                            else:
                                print(f"Attempt {attempt + 1}: Line chart file not found or empty")
                                if attempt < max_retries - 1:
                                    time.sleep(0.5)
                                    continue
                        else:
                            print(f"Warning: Line chart file not created properly after all retries")
                            # Clean up failed attempt
                            try:
                                shutil.rmtree(temp_dir3)
                            except:
                                pass
                    except Exception as e:
                        print(f"Error saving line chart: {e}")
                        plt.close(fig3)
                        try:
                            shutil.rmtree(temp_dir3)
                        except:
                            pass
                else:
                    print("No aggregated data available for line chart")
            except Exception as e:
                print(f"Error creating line chart: {e}")
                import traceback
                traceback.print_exc()
            
            return chart_paths
            
        except Exception as e:
            print(f"Error creating PDF charts: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _fetch_chart_data_for_pdf(self, view_mode):
        """Fetch chart data from API for PDF line chart"""
        try:
            import requests
            from datetime import datetime, timedelta
            
            # Get date range based on view mode
            if view_mode == "daily":
                start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
                end_date = datetime.now().strftime("%Y-%m-%d")
            elif view_mode == "weekly":
                start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
                end_date = datetime.now().strftime("%Y-%m-%d")
            else:  # monthly
                start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
                end_date = datetime.now().strftime("%Y-%m-%d")
            
            # Make API request
            params = {
                "start_date": start_date,
                "end_date": end_date,
                "mode": view_mode
            }
            
            # Try to get API base URL from the dashboard instance
            api_base_url = getattr(self, 'api_base_url', 'http://localhost:5000')
            response = requests.get(f"{api_base_url}/api/reports/uptime", params=params, timeout=10)
            
            if response.ok:
                data = response.json()
                chart_data = data.get("chart_data", {})
                print(f"Fetched chart data: {len(chart_data.get('dates', []))} data points")
                return chart_data
            else:
                print(f"API request failed: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error fetching chart data: {e}")
            return None

    def _generate_pdf_report(self, data):
        """Generate a PDF report from the data"""
        try:
            from tkinter import filedialog
            import os
            from datetime import datetime
            
            # Ask user where to save the file
            filename = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                title="Save Report As"
            )
            
            if not filename:
                return  # User cancelled
            
            # Try to import reportlab, fallback to basic PDF if not available
            try:
                from reportlab.pdfgen import canvas
                from reportlab.lib.pagesizes import letter, A4
                from reportlab.lib import colors
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
                from reportlab.lib.units import inch
                
                # Create PDF document
                doc = SimpleDocTemplate(filename, pagesize=A4)
                story = []
                styles = getSampleStyleSheet()
                
                # Title
                title_style = ParagraphStyle(
                    'CustomTitle',
                    parent=styles['Heading1'],
                    fontSize=18,
                    spaceAfter=30,
                    alignment=1  # Center alignment
                )
                title = Paragraph("WINYFI Network Monitoring Report", title_style)
                story.append(title)
                
                # Report info
                info_style = ParagraphStyle(
                    'Info',
                    parent=styles['Normal'],
                    fontSize=10,
                    spaceAfter=20,
                    alignment=1
                )
                report_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                info_text = f"Generated on: {report_date}<br/>Total Routers: {len(data)}"
                info = Paragraph(info_text, info_style)
                story.append(info)
                story.append(Spacer(1, 20))
                
                # Create table data
                table_data = [['Router Name', 'Uptime %', 'Downtime', 'Bandwidth Usage']]
                for row in data:
                    table_data.append(row)
                
                # Create table
                table = Table(table_data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 12),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('FONTSIZE', (0, 1), (-1, -1), 10),
                ]))
                
                story.append(table)
                story.append(Spacer(1, 30))
                
                # Summary statistics
                if data:
                    avg_uptime = sum(float(row[1].replace('%', '')) for row in data if row[1] != '—') / len([row for row in data if row[1] != '—'])
                    summary_text = f"Average Uptime: {avg_uptime:.1f}%"
                    summary = Paragraph(summary_text, info_style)
                    story.append(summary)
                
                # Build PDF
                doc.build(story)
                
                from tkinter import messagebox
                messagebox.showinfo("Success", f"PDF report saved successfully!\nLocation: {filename}")
                
            except ImportError:
                # Fallback: Create a simple text file
                self._generate_text_report(data, filename)
                
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error", f"Error generating PDF report: {e}")

    def _generate_text_report(self, data, filename):
        """Generate a simple text report as fallback"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("="*80 + "\n")
                f.write("WINYFI NETWORK MONITORING REPORT\n")
                f.write("="*80 + "\n")
                f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total Routers: {len(data)}\n")
                f.write("="*80 + "\n")
                f.write(f"{'Router Name':<20} {'Uptime %':<12} {'Downtime':<15} {'Bandwidth Usage':<15}\n")
                f.write("-"*80 + "\n")
                
                for row in data:
                    f.write(f"{row[0]:<20} {row[1]:<12} {row[2]:<15} {row[3]:<15}\n")
                
                f.write("="*80 + "\n")
                
                if data:
                    avg_uptime = sum(float(row[1].replace('%', '')) for row in data if row[1] != '—') / len([row for row in data if row[1] != '—'])
                    f.write(f"Average Uptime: {avg_uptime:.1f}%\n")
                    f.write("="*80 + "\n")
            
            from tkinter import messagebox
            messagebox.showinfo("Success", f"Text report saved successfully!\nLocation: {filename}")
            
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error", f"Error generating text report: {e}")

    def toggle_chart(self):
        """Toggle chart visibility"""
        try:
            if hasattr(self, 'chart_visible'):
                self.chart_visible = not self.chart_visible
                
                if hasattr(self, 'toggle_btn'):
                    if self.chart_visible:
                        self.toggle_btn.config(text="Hide Chart")
                        # Redraw the chart
                        self.generate_report_table(filter_mode=self.report_mode.get().lower())
                    else:
                        self.toggle_btn.config(text="Show Chart")
                        # Clear the chart area
                        for widget in self.reports_charts_frame.winfo_children():
                            if isinstance(widget, FigureCanvasTkAgg) or hasattr(widget, 'winfo_children'):
                                widget.destroy()
                        # Also close current matplotlib figure to free resources
                        try:
                            import matplotlib.pyplot as plt
                            if hasattr(self, 'current_fig') and getattr(self, 'current_fig') is not None:
                                plt.close(self.current_fig)
                                self.current_fig = None
                        except Exception:
                            pass
        except Exception as e:
            print(f"Error toggling chart: {e}")
            
    def print_report_preview(self):
        try:
            import os, tempfile
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import landscape, letter
            from reportlab.lib import colors
            import matplotlib.pyplot as plt

            # -----------------------------
            # Prepare temporary PDF
            # -----------------------------
            temp_pdf_path = os.path.join(tempfile.gettempdir(), "router_report_preview.pdf")
            if os.path.exists(temp_pdf_path):
                os.unlink(temp_pdf_path)

            c = canvas.Canvas(temp_pdf_path, pagesize=landscape(letter))
            width, height = landscape(letter)

            # -----------------------------
            # Title and info
            # -----------------------------
            c.setFont("Helvetica-Bold", 16)
            c.drawString(30, height - 40, "📑 Router Report Preview")

            start_str = self.start_date.entry.get()
            end_str = self.end_date.entry.get()
            mode = self.report_mode.get()
            c.setFont("Helvetica", 12)
            c.drawString(30, height - 60, f"Date Range: {start_str} → {end_str} | View Mode: {mode}")

            # -----------------------------
            # Table
            # -----------------------------
            c.setFont("Helvetica", 10)
            columns = ["Router", "Start Date", "Uptime %", "Downtime", "Bandwidth"]
            col_widths = [120, 90, 70, 90, 90]
            x_start = 30
            y_start = height - 90
            row_height = 18

            # Header
            for i, col in enumerate(columns):
                c.setFillColor(colors.lightgrey)
                c.rect(x_start + sum(col_widths[:i]), y_start, col_widths[i], row_height, fill=1)
                c.setFillColor(colors.black)
                c.drawString(x_start + sum(col_widths[:i]) + 2, y_start + 4, col)

            # Rows
            y = y_start - row_height
            for item in self.report_table.get_children():
                values = self.report_table.item(item)["values"]
                for i, val in enumerate(values):
                    c.drawString(x_start + sum(col_widths[:i]) + 2, y + 4, str(val))
                y -= row_height
                if y < 200:  # leave space for chart
                    c.showPage()
                    y = height - 40

            # -----------------------------
            # Include chart (reuse figure)
            # -----------------------------
            if hasattr(self, "chart_visible") and self.chart_visible and hasattr(self, "current_fig"):
                # Create a more robust temporary file handling
                import tempfile
                import time
                import shutil
                
                # Create temporary directory for better control
                temp_dir = tempfile.mkdtemp()
                temp_img_path = os.path.join(temp_dir, "chart_image.png")
                
                try:
                    # Ensure the figure is properly rendered
                    self.current_fig.canvas.draw()
                    
                    # Save the figure to the temporary file with explicit settings
                    self.current_fig.savefig(temp_img_path, 
                                           dpi=150, 
                                           bbox_inches='tight', 
                                           facecolor='white',
                                           edgecolor='none',
                                           format='png',
                                           pad_inches=0.1)
                    
                    # Force matplotlib to flush all buffers
                    import matplotlib.pyplot as plt
                    plt.close(self.current_fig)
                    plt.close('all')  # Close all figures to free memory
                    
                    # Wait and verify file creation with retries
                    max_retries = 5
                    for attempt in range(max_retries):
                        time.sleep(0.2)  # Wait longer between attempts
                        
                        if os.path.exists(temp_img_path) and os.path.getsize(temp_img_path) > 0:
                            # Try to open the file to ensure it's readable
                            try:
                                with open(temp_img_path, 'rb') as test_file:
                                    test_file.read(1)  # Try to read at least one byte
                                print(f"Chart image file verified successfully: {temp_img_path}")
                                break
                            except Exception as read_error:
                                print(f"Attempt {attempt + 1}: File not readable yet: {read_error}")
                                if attempt < max_retries - 1:
                                    time.sleep(0.3)
                                    continue
                        else:
                            print(f"Attempt {attempt + 1}: File not found or empty")
                            if attempt < max_retries - 1:
                                time.sleep(0.3)
                                continue
                    else:
                        print("Warning: Chart image file was not created properly after all retries")
                        return  # Skip chart if file creation failed
                    
                    # Draw the image to PDF
                    try:
                        c.drawImage(temp_img_path, x_start, 40, width=700, height=200)
                        print("Chart successfully added to PDF")
                    except Exception as draw_error:
                        print(f"Error drawing image to PDF: {draw_error}")
                        # Continue without chart rather than failing completely
                        
                except Exception as img_error:
                    print(f"Error saving chart image: {img_error}")
                    import traceback
                    traceback.print_exc()
                finally:
                    # Clean up the temporary directory
                    try:
                        if os.path.exists(temp_dir):
                            shutil.rmtree(temp_dir)
                            print(f"Cleaned up temporary directory: {temp_dir}")
                    except Exception as cleanup_error:
                        print(f"Error cleaning up temporary directory: {cleanup_error}")

            # -----------------------------
            # Save and open PDF
            # -----------------------------
            c.save()

            if os.name == "nt":
                os.startfile(temp_pdf_path)
            elif os.name == "posix":
                os.system(f"xdg-open {temp_pdf_path}")
            else:
                from tkinter import messagebox
                messagebox.showinfo("Info", f"Preview PDF saved at: {temp_pdf_path}")

        except Exception as e:
            from tkinter import messagebox
            error_msg = f"Error generating PDF: {str(e)}"
            print(f"PDF Generation Error: {error_msg}")  # Also print to console for debugging
            messagebox.showerror("Error", error_msg)


    def _get_aggregated_chart_data(self):
        """
        Returns aggregated chart data (dates/labels and average uptimes)
        based on current table/filter selections.
        Output:
            agg_dates: list of labels (daily: datetime, weekly/monthly: str)
            agg_uptimes: list of average uptime percentages
        """
        from datetime import datetime, time, timedelta

        # Read date range
        start_str = self.start_date.entry.get()
        end_str = self.end_date.entry.get()
        start_date = datetime.combine(datetime.strptime(start_str, "%m/%d/%Y"), time.min)
        end_date = datetime.combine(datetime.strptime(end_str, "%m/%d/%Y"), time.max)

        # Get filter mode
        filter_mode = self.report_mode.get().lower()

        # Get routers
        routers = get_routers()

        # Compute daily average uptimes
        days = (end_date - start_date).days + 1
        daily_data = []
        for i in range(days):
            day_start = start_date + timedelta(days=i)
            day_end = day_start.replace(hour=23, minute=59, second=59)
            uptimes = [get_uptime_percentage(r["id"], day_start, day_end) for r in routers]
            avg_uptime = sum(uptimes) / len(uptimes) if uptimes else 0
            daily_data.append((day_start, avg_uptime))

        # Aggregate by filter mode
        aggregated = {}
        for date, uptime in daily_data:
            if filter_mode == "weekly":
                key = date.strftime("Week %U (%Y)")
            elif filter_mode == "monthly":
                key = date.strftime("%B %Y")
            else:  # daily
                key = date.strftime("%m-%d")
            aggregated.setdefault(key, []).append(uptime)

        agg_dates = list(aggregated.keys())
        agg_uptimes = [sum(vals) / len(vals) for vals in aggregated.values()]

        return agg_dates, agg_uptimes


#---------------------------------------------------------------
    def open_ticket_window(self):
        """Open a separate window for ICT Service Request management."""
        window = tb.Toplevel(self.root)
        window.title("ICT Service Request Management")
        window.geometry("1200x700")
        window.minsize(900, 500)
        
        # Center the window
        window.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (1200 // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (700 // 2)
        window.geometry(f"+{x}+{y}")
        
        window.transient(self.root)
        window.grab_set()

        # Main container with modern styling
        main_container = tb.Frame(window)
        main_container.pack(fill="both", expand=True, padx=15, pady=15)

        # Enhanced Header with gradient-like styling
        header_frame = tb.LabelFrame(main_container, text="", bootstyle="primary", padding=15)
        header_frame.pack(fill="x", pady=(0, 15))

        # Header content
        header_content = tb.Frame(header_frame)
        header_content.pack(fill="x")

        # Title with icon and subtitle
        title_frame = tb.Frame(header_content)
        title_frame.pack(side="left", fill="x", expand=True)
        
        tb.Label(title_frame, text="🎫 ICT Service Request Management", 
                font=("Segoe UI", 18, "bold"), bootstyle="inverse-primary").pack(anchor="w")
        tb.Label(title_frame, text="Manage and track all ICT service requests efficiently", 
                font=("Segoe UI", 10), bootstyle="inverse-secondary").pack(anchor="w", pady=(2, 0))

        # Action buttons container
        action_frame = tb.Frame(header_content)
        action_frame.pack(side="right")

        tb.Button(
            action_frame,
            text="➕ New Request",
            bootstyle="success",
            command=self.open_new_ticket_modal,
            width=12
        ).pack(side="right", padx=(5, 0))

        tb.Button(
            action_frame,
            text="🔄 Refresh",
            bootstyle="info",
            command=self.load_tickets,
            width=10
        ).pack(side="right", padx=(5, 0))

        # Statistics and filter section
        stats_filter_frame = tb.Frame(main_container)
        stats_filter_frame.pack(fill="x", pady=(0, 15))

        # Statistics cards
        stats_frame = tb.LabelFrame(stats_filter_frame, text="📊 Quick Statistics", 
                                   bootstyle="info", padding=10)
        stats_frame.pack(side="left", fill="y")

        # Create statistics display
        self._create_ticket_stats(stats_frame)

        # Filter and search section
        filter_frame = tb.LabelFrame(stats_filter_frame, text="🔍 Filter & Search", 
                                   bootstyle="secondary", padding=10)
        filter_frame.pack(side="right", fill="both", expand=True, padx=(15, 0))

        # Filter controls
        filter_row1 = tb.Frame(filter_frame)
        filter_row1.pack(fill="x", pady=(0, 10))

        tb.Label(filter_row1, text="Status:", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.status_filter = tb.Combobox(filter_row1, values=["All", "Open", "Resolved"], 
                                        state="readonly", width=12)
        self.status_filter.set("All")
        self.status_filter.pack(side="left", padx=(5, 15))
        self.status_filter.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())

        tb.Label(filter_row1, text="Campus:", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.campus_filter = tb.Combobox(filter_row1, values=["All", "Main", "Alangilan", "Lipa", "Nasugbu"], 
                                        state="readonly", width=12)
        self.campus_filter.set("All")
        self.campus_filter.pack(side="left", padx=(5, 0))
        self.campus_filter.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())

        # Search row
        filter_row2 = tb.Frame(filter_frame)
        filter_row2.pack(fill="x")

        tb.Label(filter_row2, text="Search:", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.search_var = tb.StringVar()
        search_entry = tb.Entry(filter_row2, textvariable=self.search_var, width=25)
        search_entry.pack(side="left", padx=(5, 10))
        search_entry.bind("<KeyRelease>", lambda e: self.apply_filters())

        tb.Button(filter_row2, text="Clear", bootstyle="secondary-outline",
                 command=self.clear_filters, width=8).pack(side="left")

        # Enhanced Table Section
        table_container = tb.LabelFrame(main_container, text="📋 Service Requests", 
                                       bootstyle="success", padding=10)
        table_container.pack(fill="both", expand=True)

        # Table frame with improved styling
        table_frame = tb.Frame(table_container)
        table_frame.pack(fill="both", expand=True)

        # Column configuration with better widths and headers
        columns = ("ict_srf_no", "campus", "services", "status", "priority", "created_by", "created_at", "updated_at")
        column_config = {
            "ict_srf_no": {"text": "SRF No.", "width": 80, "anchor": "center"},
            "campus": {"text": "Campus", "width": 100, "anchor": "center"},
            "services": {"text": "Service Description", "width": 250, "anchor": "w"},
            "status": {"text": "Status", "width": 100, "anchor": "center"},
            "priority": {"text": "Priority", "width": 80, "anchor": "center"},
            "created_by": {"text": "Requested By", "width": 120, "anchor": "center"},
            "created_at": {"text": "Created", "width": 130, "anchor": "center"},
            "updated_at": {"text": "Last Updated", "width": 130, "anchor": "center"}
        }

        self.tickets_table = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=16
        )

        # Configure columns with improved settings
        for col in columns:
            config = column_config.get(col, {"text": col.replace("_", " ").title(), "width": 120, "anchor": "center"})
            self.tickets_table.heading(col, text=config["text"])
            self.tickets_table.column(col, anchor=config["anchor"], width=config["width"], minwidth=50)

        # Add sorting functionality
        for col in columns:
            self.tickets_table.heading(col, command=lambda c=col: self.sort_tickets_by_column(c))

        self.tickets_table.pack(fill="both", expand=True, side="left")

        # Enhanced scrollbars
        v_scrollbar = tb.Scrollbar(table_frame, orient="vertical", command=self.tickets_table.yview)
        h_scrollbar = tb.Scrollbar(table_frame, orient="horizontal", command=self.tickets_table.xview)
        
        self.tickets_table.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Convert to grid layout
        self.tickets_table.grid_forget()  # Remove pack
        self.tickets_table.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        # Bind mouse wheel scrolling
        def on_mousewheel_vertical(event):
            self.tickets_table.yview_scroll(int(-1*(event.delta/120)), "units")
            return "break"
        
        def on_mousewheel_horizontal(event):
            self.tickets_table.xview_scroll(int(-1*(event.delta/120)), "units")
            return "break"
        
        self.tickets_table.bind("<MouseWheel>", on_mousewheel_vertical)
        self.tickets_table.bind("<Shift-MouseWheel>", on_mousewheel_horizontal)

        # Enhanced row styling with alternating colors
        self.tickets_table.tag_configure("even", background="#f8f9fa")
        self.tickets_table.tag_configure("odd", background="white")
        self.tickets_table.tag_configure("urgent", background="#fff3cd", foreground="#856404")
        self.tickets_table.tag_configure("resolved", background="#d4edda", foreground="#155724")

        # Footer with actions and info
        footer_frame = tb.Frame(main_container)
        footer_frame.pack(fill="x", pady=(15, 0))

        # Context menu actions
        context_frame = tb.Frame(footer_frame)
        context_frame.pack(side="left")

        tb.Label(context_frame, text="💡 Tip: Double-click a row to view details, right-click for more options", 
                font=("Segoe UI", 9), bootstyle="secondary").pack()

        # Auto-refresh controls
        refresh_frame = tb.Frame(footer_frame)
        refresh_frame.pack(side="right")

        self.auto_refresh_var = tb.BooleanVar(value=True)
        tb.Checkbutton(refresh_frame, text="Auto-refresh", variable=self.auto_refresh_var,
                      command=self.toggle_auto_refresh).pack(side="right", padx=(0, 10))

        self.last_refresh_label = tb.Label(refresh_frame, text="", font=("Segoe UI", 8), bootstyle="secondary")
        self.last_refresh_label.pack(side="right", padx=(0, 10))

        # Load tickets and start auto-refresh
        self.load_tickets()
        self.update_last_refresh_time()

        # Enhanced event bindings
        self.tickets_table.bind("<Double-1>", self._on_ticket_row_click)
        self.tickets_table.bind("<Button-3>", self._show_ticket_context_menu)  # Right-click menu
        
        # Initialize auto-refresh
        if self.auto_refresh_var.get():
            self.start_ticket_auto_refresh()


    def load_tickets(self, status=None):
        """Fetch SRFs from DB and display in the table with enhanced formatting."""
        try:
            self.tickets_table.delete(*self.tickets_table.get_children())
            srfs = ticket_utils.fetch_srfs()
            
            row_count = 0
            for srf in srfs:
                # Determine row styling
                tag = "even" if row_count % 2 == 0 else "odd"
                
                # Special styling for status - handle missing status column gracefully
                status = srf.get("status", "open")
                if status is None:
                    status = "open"
                status = status.lower()
                
                if status == "resolved":
                    tag = "resolved"
                elif srf.get("priority", "").lower() == "urgent":
                    tag = "urgent"
                
                # Format dates nicely
                created_at = srf["created_at"].strftime("%m/%d/%Y %H:%M") if srf.get("created_at") else "N/A"
                updated_at = srf["updated_at"].strftime("%m/%d/%Y %H:%M") if srf.get("updated_at") else "N/A"
                
                # Truncate long service descriptions
                services = srf.get("services_requirements", "")
                if len(services) > 35:
                    services = services[:32] + "..."
                
                self.tickets_table.insert(
                    "",
                    "end",
                    values=(
                        srf["ict_srf_no"],
                        srf.get("campus", ""),
                        services,
                        status.title(),
                        srf.get("priority", "Normal"),
                        srf.get("created_by_username", "Unknown"),
                        created_at,
                        updated_at
                    ),
                    tags=(tag,)
                )
                row_count += 1
            
            # Update statistics
            self._update_ticket_statistics()
            self.update_last_refresh_time()
            
        except Exception as e:
            print(f"Error loading tickets: {e}")
            # Show a user-friendly message
            from tkinter import messagebox
            messagebox.showerror("Database Error", 
                               "Error loading tickets. Please run the database migration script (migrate_ticket_schema.py) if this is your first time using the enhanced ticket system.")

    def _create_ticket_stats(self, parent):
        """Create statistics cards for tickets."""
        stats_container = tb.Frame(parent)
        stats_container.pack(fill="both", expand=True)
        
        # Total tickets
        total_frame = tb.Frame(stats_container)
        total_frame.pack(fill="x", pady=(0, 5))
        tb.Label(total_frame, text="Total:", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.total_tickets_label = tb.Label(total_frame, text="0", font=("Segoe UI", 12, "bold"), bootstyle="info")
        self.total_tickets_label.pack(side="right")
        
        # Open tickets
        open_frame = tb.Frame(stats_container)
        open_frame.pack(fill="x", pady=(0, 5))
        tb.Label(open_frame, text="Open:", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.open_tickets_label = tb.Label(open_frame, text="0", font=("Segoe UI", 12, "bold"), bootstyle="warning")
        self.open_tickets_label.pack(side="right")
        
        # Resolved tickets
        resolved_frame = tb.Frame(stats_container)
        resolved_frame.pack(fill="x")
        tb.Label(resolved_frame, text="Resolved:", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.resolved_tickets_label = tb.Label(resolved_frame, text="0", font=("Segoe UI", 12, "bold"), bootstyle="success")
        self.resolved_tickets_label.pack(side="right")

    def _update_ticket_statistics(self):
        """Update the statistics display."""
        try:
            # Get current table items for statistics
            all_items = self.tickets_table.get_children()
            total_count = len(all_items)
            
            open_count = 0
            resolved_count = 0
            
            for item in all_items:
                status = self.tickets_table.item(item)['values'][3].lower()
                if status in ['open', 'in progress']:
                    open_count += 1
                elif status == 'resolved':
                    resolved_count += 1
            
            # Update labels
            self.total_tickets_label.config(text=str(total_count))
            self.open_tickets_label.config(text=str(open_count))
            self.resolved_tickets_label.config(text=str(resolved_count))
            
        except Exception as e:
            print(f"Error updating ticket statistics: {e}")

    def apply_filters(self):
        """Apply filters to the ticket table."""
        try:
            # Get filter values
            status_filter = self.status_filter.get()
            campus_filter = self.campus_filter.get()
            search_text = self.search_var.get().lower()
            
            # Clear current display
            for item in self.tickets_table.get_children():
                self.tickets_table.delete(item)
            
            # Reload and filter data
            srfs = ticket_utils.fetch_srfs()
            row_count = 0
            
            for srf in srfs:
                # Apply status filter
                if status_filter != "All" and srf.get("status", "open").title() != status_filter:
                    continue
                
                # Apply campus filter
                if campus_filter != "All" and srf.get("campus", "") != campus_filter:
                    continue
                
                # Apply search filter
                if search_text:
                    searchable_text = f"{srf.get('ict_srf_no', '')} {srf.get('campus', '')} {srf.get('services_requirements', '')} {srf.get('created_by_username', '')}".lower()
                    if search_text not in searchable_text:
                        continue
                
                # Add filtered item
                tag = "even" if row_count % 2 == 0 else "odd"
                status = srf.get("status", "open").lower()
                if status == "resolved":
                    tag = "resolved"
                elif srf.get("priority", "").lower() == "urgent":
                    tag = "urgent"
                
                created_at = srf["created_at"].strftime("%m/%d/%Y %H:%M") if srf.get("created_at") else "N/A"
                updated_at = srf["updated_at"].strftime("%m/%d/%Y %H:%M") if srf.get("updated_at") else "N/A"
                
                services = srf.get("services_requirements", "")
                if len(services) > 35:
                    services = services[:32] + "..."
                
                self.tickets_table.insert(
                    "",
                    "end",
                    values=(
                        srf["ict_srf_no"],
                        srf.get("campus", ""),
                        services,
                        srf.get("status", "open").title(),
                        srf.get("priority", "Normal"),
                        srf.get("created_by_username", "Unknown"),
                        created_at,
                        updated_at
                    ),
                    tags=(tag,)
                )
                row_count += 1
            
            self._update_ticket_statistics()
            
        except Exception as e:
            print(f"Error applying filters: {e}")

    def clear_filters(self):
        """Clear all filters and reload data."""
        self.status_filter.set("All")
        self.campus_filter.set("All")
        self.search_var.set("")
        self.load_tickets()

    def sort_tickets_by_column(self, col):
        """Sort tickets by the selected column."""
        try:
            # Get current data
            data = []
            for item in self.tickets_table.get_children():
                values = self.tickets_table.item(item)['values']
                data.append(values)
            
            # Sort data
            if hasattr(self, f'_sort_{col}_reverse'):
                reverse = getattr(self, f'_sort_{col}_reverse')
                setattr(self, f'_sort_{col}_reverse', not reverse)
            else:
                reverse = False
                setattr(self, f'_sort_{col}_reverse', True)
            
            col_index = list(self.tickets_table['columns']).index(col)
            
            # Custom sorting for different column types
            if col in ['created_at', 'updated_at']:
                data.sort(key=lambda x: x[col_index], reverse=reverse)
            elif col == 'ict_srf_no':
                data.sort(key=lambda x: int(x[col_index]) if x[col_index].isdigit() else 0, reverse=reverse)
            else:
                data.sort(key=lambda x: str(x[col_index]).lower(), reverse=reverse)
            
            # Clear and repopulate table
            for item in self.tickets_table.get_children():
                self.tickets_table.delete(item)
            
            for i, values in enumerate(data):
                tag = "even" if i % 2 == 0 else "odd"
                if values[3].lower() == "resolved":
                    tag = "resolved"
                elif len(values) > 4 and values[4].lower() == "urgent":
                    tag = "urgent"
                    
                self.tickets_table.insert("", "end", values=values, tags=(tag,))
                
        except Exception as e:
            print(f"Error sorting tickets: {e}")

    def update_last_refresh_time(self):
        """Update the last refresh time display."""
        from datetime import datetime
        current_time = datetime.now().strftime("%H:%M:%S")
        self.last_refresh_label.config(text=f"Last updated: {current_time}")

    def toggle_auto_refresh(self):
        """Toggle auto-refresh functionality."""
        if self.auto_refresh_var.get():
            self.start_ticket_auto_refresh()
        else:
            self.stop_ticket_auto_refresh()

    def start_ticket_auto_refresh(self):
        """Start auto-refresh for tickets."""
        if hasattr(self, '_ticket_refresh_job'):
            self.root.after_cancel(self._ticket_refresh_job)
        self._ticket_refresh_job = self.root.after(30000, self._auto_refresh_tickets)  # 30 seconds

    def stop_ticket_auto_refresh(self):
        """Stop auto-refresh for tickets."""
        if hasattr(self, '_ticket_refresh_job'):
            self.root.after_cancel(self._ticket_refresh_job)
            delattr(self, '_ticket_refresh_job')

    def _auto_refresh_tickets(self):
        """Internal method for auto-refreshing tickets."""
        if self.auto_refresh_var.get():
            self.apply_filters()  # Reapply current filters
            self.start_ticket_auto_refresh()  # Schedule next refresh

    def _show_ticket_context_menu(self, event):
        """Show context menu on right-click."""
        try:
            selected_item = self.tickets_table.selection()
            if not selected_item:
                return
            
            # Create context menu
            context_menu = tk.Menu(self.root, tearoff=0)
            context_menu.add_command(label="📄 View Details", command=lambda: self._on_ticket_row_click(event))
            context_menu.add_command(label="✏️ Edit Request", command=lambda: self._edit_selected_ticket())
            context_menu.add_separator()
            context_menu.add_command(label="✅ Mark as Resolved", command=lambda: self._mark_ticket_resolved())
            context_menu.add_command(label="🔄 Refresh", command=self.load_tickets)
            
            # Show menu
            context_menu.post(event.x_root, event.y_root)
            
        except Exception as e:
            print(f"Error showing context menu: {e}")

    def _edit_selected_ticket(self):
        """Edit the selected ticket."""
        try:
            selected_item = self.tickets_table.selection()
            if not selected_item:
                return
            
            ticket_id = self.tickets_table.item(selected_item[0])["values"][0]
            # Find the SRF data
            srfs = ticket_utils.fetch_srfs()
            srf = next((s for s in srfs if s["ict_srf_no"] == ticket_id), None)
            if srf:
                self.open_edit_ticket_modal(srf)
                
        except Exception as e:
            print(f"Error editing ticket: {e}")

    def _mark_ticket_resolved(self):
        """Mark selected ticket as resolved."""
        try:
            selected_item = self.tickets_table.selection()
            if not selected_item:
                return
            
            ticket_id = self.tickets_table.item(selected_item[0])["values"][0]
            
            # Confirm action
            from tkinter import messagebox
            if messagebox.askyesno("Confirm Resolution", 
                                 f"Mark Service Request #{ticket_id} as resolved?\n\nThis action will update the ticket status."):
                # Update in database using utility function
                ticket_utils.update_ticket_status(ticket_id, "resolved")
                
                # Refresh display
                self.load_tickets()
                messagebox.showinfo("Success", f"Service Request #{ticket_id} has been marked as resolved!")
                
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error", f"Error marking ticket as resolved: {e}")
            print(f"Error marking ticket as resolved: {e}")
    def collect_ticket_form_data(self):
        """Collect all values from SRF form fields."""
        data = {k: v.get() for k, v in self.form_vars.items()}
        data["services_requirements"] = self.service_req_text.get("1.0", "end").strip()
        data["remarks"] = self.remarks_text.get("1.0", "end").strip()
        return data


    def auto_refresh_tickets(self, interval=30000):
        """Legacy method for backward compatibility - redirects to new auto-refresh system."""
        if not hasattr(self, 'auto_refresh_var'):
            self.auto_refresh_var = tb.BooleanVar(value=True)
        
        if self.auto_refresh_var.get():
            self.load_tickets()
            self.root.after(interval, self.auto_refresh_tickets)

    def _on_ticket_row_click(self, event):
        """Open ticket detail modal when a row is double-clicked."""
        selected_item = self.tickets_table.selection()
        if not selected_item:
            return
        ticket_id = self.tickets_table.item(selected_item[0])["values"][0]
        self.open_ticket_detail_modal(ticket_id)


    def build_ticket_form(self, modal, initial_data=None, is_edit=False):
        """Reusable SRF form builder for both New & Edit. Returns a container to place buttons."""
        if initial_data is None:
            initial_data = {}

        # ---------- SCROLLABLE FRAME ----------
        container = tb.Frame(modal)
        container.pack(fill="both", expand=True)

        canvas = tb.Canvas(container)
        vscroll = tb.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = tb.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=vscroll.set)

        canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        # Optional: smooth scrolling bindings (widget-scoped)
        def _on_mousewheel(event):
            try:
                if event.delta:
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except tk.TclError:
                pass
        canvas.bind("<MouseWheel>", _on_mousewheel)
        canvas.bind("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

        def _cleanup_scroll_bindings():
            try:
                canvas.unbind("<MouseWheel>")
                canvas.unbind("<Button-4>")
                canvas.unbind("<Button-5>")
            except Exception:
                pass
        # Ensure cleanup when modal is destroyed
        modal.bind("<Destroy>", lambda e: _cleanup_scroll_bindings(), add="+")

        # ---------- HEADER WITH LOGO ----------
        header_frame = tb.Frame(scrollable_frame)
        header_frame.pack(fill="x", padx=20, pady=10)

        logo_path = "assets/images/bsu_logo.png"
        try:
            img = Image.open(logo_path).resize((80, 80))
            logo_img = ImageTk.PhotoImage(img)
            logo_label = tb.Label(header_frame, image=logo_img)
            logo_label.image = logo_img
            logo_label.grid(row=0, column=0, rowspan=2, padx=5, pady=5, sticky="ns")
        except Exception:
            tb.Label(header_frame, text="LOGO", width=10, relief="solid").grid(row=0, column=0, rowspan=2, padx=5, pady=5)

        tb.Label(header_frame, text="Reference No.: BatStateU-FO-ICT-01", font=("Segoe UI", 10, "bold")).grid(row=0, column=1, sticky="w", padx=10)
        tb.Label(header_frame, text="Effectivity Date: May 18, 2022", font=("Segoe UI", 10, "bold")).grid(row=0, column=2, sticky="w", padx=10)
        tb.Label(header_frame, text="Revision No.: 02", font=("Segoe UI", 10, "bold")).grid(row=0, column=3, sticky="w", padx=10)

        tb.Label(scrollable_frame, text="ICT SERVICE REQUEST FORM", font=("Segoe UI", 14, "bold")).pack(fill="x", pady=(10, 20), padx=20)

        # ---------- FORM FIELDS (grid ONLY inside form_frame) ----------
        form_frame = tb.Frame(scrollable_frame)
        form_frame.pack(fill="both", expand=True, padx=20)

        for col in range(4):
            form_frame.columnconfigure(col, weight=1)

        # Variables aligned with backend keys
        self.form_vars = {
            "campus": tb.StringVar(value=initial_data.get("campus", "")),
            "office_building": tb.StringVar(value=initial_data.get("office_building", "")),
            "client_name": tb.StringVar(value=initial_data.get("client_name", "")),
            "date_time_call": tb.StringVar(value=initial_data.get("date_time_call", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))),
            "ict_srf_no": tb.StringVar(value=initial_data.get("ict_srf_no", "")),
            "technician_assigned": tb.StringVar(value=initial_data.get("technician_assigned", "")),
            "required_response_time": tb.StringVar(value=initial_data.get("required_response_time", "")),
            "response_time": tb.StringVar(value=initial_data.get("response_time", "")),
            "service_time": tb.StringVar(value=initial_data.get("service_time", "")),
        }

        # Text widgets MUST be children of form_frame (not scrollable_frame)
        self.service_req_text = tb.Text(form_frame, height=4, wrap="word")
        self.remarks_text = tb.Text(form_frame, height=4, wrap="word")
        if is_edit:
            self.service_req_text.insert("1.0", initial_data.get("services_requirements", ""))
            self.remarks_text.insert("1.0", initial_data.get("remarks", ""))

        # Validation for numbers (SRF No.)
        vcmd = self.root.register(lambda P: P.isdigit() or P == "")

        def add_row(label1, key1, label2=None, key2=None, row_idx=0, numeric2=False):
            tb.Label(form_frame, text=label1, anchor="w").grid(row=row_idx, column=0, sticky="w", padx=5, pady=5)
            tb.Entry(form_frame, textvariable=self.form_vars[key1]).grid(row=row_idx, column=1, sticky="ew", padx=5, pady=5)

            if label2 and key2:
                tb.Label(form_frame, text=label2, anchor="w").grid(row=row_idx, column=2, sticky="w", padx=5, pady=5)
                if numeric2:
                    tb.Entry(form_frame, textvariable=self.form_vars[key2], validate="key", validatecommand=(vcmd, "%P")) \
                        .grid(row=row_idx, column=3, sticky="ew", padx=5, pady=5)
                else:
                    tb.Entry(form_frame, textvariable=self.form_vars[key2]).grid(row=row_idx, column=3, sticky="ew", padx=5, pady=5)

        # Rows
        add_row("Campus:", "campus", "ICT SRF NO.:", "ict_srf_no", row_idx=0, numeric2=True)
        add_row("Office/Building:", "office_building", "Technician Assigned:", "technician_assigned", row_idx=1)
        add_row("Client’s Name:", "client_name", None, None, row_idx=2)
        add_row("Date/Time of Call:", "date_time_call", "Required Response Time:", "required_response_time", row_idx=3)

        tb.Label(form_frame, text="Services Requirements:").grid(row=4, column=0, sticky="w", padx=5, pady=5)
        self.service_req_text.grid(row=5, column=0, columnspan=4, sticky="ew", padx=5, pady=(0, 10))

        tb.Label(form_frame, text="ACCOMPLISHMENT (to be accomplished by the assigned technician)",
                font=("Segoe UI", 12, "bold")).grid(row=6, column=0, columnspan=4, sticky="w", pady=(10, 5))

        add_row("Response Time:", "response_time", "Service Time:", "service_time", row_idx=7)

        tb.Label(form_frame, text="Remarks:").grid(row=8, column=0, sticky="w", padx=5, pady=5)
        self.remarks_text.grid(row=9, column=0, columnspan=4, sticky="ew", padx=5, pady=(0, 10))

        # Return a safe parent that uses PACK for action buttons
        return scrollable_frame



    def _open_edit_profile_modal(self):
        modal = tb.Toplevel(self.root)
        modal.title("Edit Profile")
        modal.geometry("400x400")
        modal.resizable(False, False)
        modal.transient(self.root)
        modal.grab_set()

        # Center modal on screen
        modal.update_idletasks()
        x = (modal.winfo_screenwidth() - 400) // 2
        y = (modal.winfo_screenheight() - 400) // 2
        modal.geometry(f"400x400+{x}+{y}")

        frame = tb.Frame(modal, padding=20)
        frame.pack(fill="both", expand=True)

        tb.Label(frame, text="Edit Profile", font=("Segoe UI", 16, "bold"), bootstyle="success").pack(pady=(0, 20))

        # Fetch current user data safely
        user_data = self.current_user if self.current_user else {}
        first_name_var = tk.StringVar(value=user_data.get('first_name', ''))
        last_name_var = tk.StringVar(value=user_data.get('last_name', ''))
        username_var = tk.StringVar(value=user_data.get('username', ''))

        # First Name
        tb.Label(frame, text="First Name:", font=("Segoe UI", 11)).pack(anchor="w")
        first_name_entry = tb.Entry(frame, textvariable=first_name_var)
        first_name_entry.pack(fill="x", pady=(0, 10))

        # Last Name
        tb.Label(frame, text="Last Name:", font=("Segoe UI", 11)).pack(anchor="w")
        last_name_entry = tb.Entry(frame, textvariable=last_name_var)
        last_name_entry.pack(fill="x", pady=(0, 10))

        # Username
        tb.Label(frame, text="Username:", font=("Segoe UI", 11)).pack(anchor="w")
        username_entry = tb.Entry(frame, textvariable=username_var)
        username_entry.pack(fill="x", pady=(0, 10))

        # Button frame for proper layout
        btn_frame = tb.Frame(frame)
        btn_frame.pack(fill="x", pady=(20, 0))

        def submit_edit():
            new_profile = {
                'first_name': first_name_var.get(),
                'last_name': last_name_var.get(),
                'username': username_var.get()
            }
            user_id = self.current_user.get('id') if self.current_user else None
            if not user_id:
                messagebox.showerror("Error", "User ID not found.")
                return
            success = self.backend_edit_profile(user_id, new_profile)
            if success:
                messagebox.showinfo("Success", "Profile updated successfully.")
                modal.destroy()

        save_btn = tb.Button(btn_frame, text="Save Changes", bootstyle="success", command=submit_edit)
        save_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))
        cancel_btn = tb.Button(btn_frame, text="Cancel", bootstyle="secondary", command=modal.destroy)
        cancel_btn.pack(side="right", fill="x", expand=True)
    def submit_edit_ticket(self, ticket_id, modal):
        """Update an existing ICT Service Request Form in the database."""
        updated_data = self.collect_ticket_form_data()

        try:
            conn = get_connection()
            cursor = conn.cursor()

            update_query = """
                UPDATE ict_service_requests
                SET campus=%s,
                    office_building=%s,
                    client_name=%s,
                    date_time_call=%s,
                    technician_assigned=%s,
                    required_response_time=%s,
                    services_requirements=%s,
                    response_time=%s,
                    service_time=%s,
                    remarks=%s
                WHERE ict_srf_no=%s
            """
            cursor.execute(update_query, (
                updated_data["campus"],
                updated_data["office_building"],
                updated_data["client_name"],
                updated_data["date_time_call"],
                updated_data["technician_assigned"],
                updated_data["required_response_time"],
                updated_data["services_requirements"],
                updated_data["response_time"],
                updated_data["service_time"],
                updated_data["remarks"],
                ticket_id
            ))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Service Request updated successfully!")
            modal.destroy()
            self.load_tickets()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update Service Request:\n{e}")




    def open_ticket_detail_modal(self, srf_no):
        """Open an enhanced modal showing SRF details with modern styling."""
        srf = next((s for s in ticket_utils.fetch_srfs() if s["ict_srf_no"] == srf_no), None)
        if not srf:
            messagebox.showerror("Error", "Service Request not found!")
            return

        modal = tb.Toplevel(self.root)
        modal.title(f"Service Request #{srf_no} - Details")
        modal.geometry("800x650")
        modal.minsize(700, 500)
        
        # Center the modal
        modal.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (800 // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (650 // 2)
        modal.geometry(f"+{x}+{y}")
        
        modal.transient(self.root)
        modal.grab_set()

        # Main container with modern styling
        main_container = tb.Frame(modal)
        main_container.pack(fill="both", expand=True, padx=15, pady=15)

        # Enhanced Header Section
        header_frame = tb.LabelFrame(main_container, text="", bootstyle="primary", padding=15)
        header_frame.pack(fill="x", pady=(0, 15))

        header_content = tb.Frame(header_frame)
        header_content.pack(fill="x")

        # Logo and title section
        logo_title_frame = tb.Frame(header_content)
        logo_title_frame.pack(fill="x")

        try:
            logo_img = Image.open("assets/images/bsu_logo.png").resize((70, 70))
            self.logo_photo = ImageTk.PhotoImage(logo_img)
            logo_label = tb.Label(logo_title_frame, image=self.logo_photo)
            logo_label.pack(side="left", padx=(0, 15))
        except:
            logo_placeholder = tb.Label(logo_title_frame, text="🏛️", font=("Segoe UI", 40))
            logo_placeholder.pack(side="left", padx=(0, 15))

        # Title and SRF info
        title_info_frame = tb.Frame(logo_title_frame)
        title_info_frame.pack(side="left", fill="x", expand=True)

        tb.Label(title_info_frame, text="ICT Service Request Form", 
                font=("Segoe UI", 18, "bold"), bootstyle="inverse-primary").pack(anchor="w")
        
        # SRF number with status badge
        srf_status_frame = tb.Frame(title_info_frame)
        srf_status_frame.pack(anchor="w", pady=(5, 0))
        
        tb.Label(srf_status_frame, text=f"SRF #{srf['ict_srf_no']}", 
                font=("Segoe UI", 14, "bold")).pack(side="left")
        
        # Status badge
        status = srf.get('status', 'open').lower()
        status_style = "success" if status == "resolved" else "warning" if status == "in progress" else "info"
        tb.Label(srf_status_frame, text=status.title(), 
                font=("Segoe UI", 10, "bold"), bootstyle=f"inverse-{status_style}").pack(side="left", padx=(10, 0))

        # Quick info bar
        info_bar = tb.Frame(header_content)
        info_bar.pack(fill="x", pady=(10, 0))
        
        quick_info = f"📅 Created: {srf['created_at'].strftime('%m/%d/%Y %H:%M')} | 👤 By: {srf.get('created_by_username', 'Unknown')} | 🏢 Campus: {srf.get('campus', 'N/A')}"
        tb.Label(info_bar, text=quick_info, font=("Segoe UI", 9), bootstyle="inverse-secondary").pack()

        # Content with notebook tabs for better organization
        content_notebook = tb.Notebook(main_container)
        content_notebook.pack(fill="both", expand=True, pady=(0, 15))

        # Tab 1: Request Details
        details_tab = tb.Frame(content_notebook)
        content_notebook.add(details_tab, text="📋 Request Details")

        # Scrollable content for details
        details_canvas = tb.Canvas(details_tab)
        details_scrollbar = tb.Scrollbar(details_tab, orient="vertical", command=details_canvas.yview)
        details_scrollable = tb.Frame(details_canvas)

        details_scrollable.bind("<Configure>", lambda e: details_canvas.configure(scrollregion=details_canvas.bbox("all")))
        details_canvas.create_window((0, 0), window=details_scrollable, anchor="nw")
        details_canvas.configure(yscrollcommand=details_scrollbar.set)

        details_canvas.pack(side="left", fill="both", expand=True)
        details_scrollbar.pack(side="right", fill="y")
        
        # Bind mouse wheel scrolling to canvas
        def on_mousewheel_details(event):
            details_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            return "break"
        
        details_canvas.bind("<MouseWheel>", on_mousewheel_details)
        details_scrollable.bind("<MouseWheel>", on_mousewheel_details)

        # Request Information Section
        self._create_detail_section(details_scrollable, "🏢 Request Information", [
            ("Campus", srf.get('campus', 'N/A')),
            ("Office/Building", srf.get('office_building', 'N/A')),
            ("Client Name", srf.get('client_name', 'N/A')),
            ("Date/Time of Call", srf.get('date_time_call', 'N/A')),
            ("Required Response Time", srf.get('required_response_time', 'N/A'))
        ])

        # Service Description Section
        services_frame = tb.LabelFrame(details_scrollable, text="🔧 Service Requirements", 
                                     bootstyle="info", padding=15)
        services_frame.pack(fill="x", padx=10, pady=10)

        services_text = tb.Text(services_frame, height=4, wrap="word", state="disabled",
                               font=("Segoe UI", 10))
        services_text.pack(fill="x")
        services_text.config(state="normal")
        services_text.insert("1.0", srf.get('services_requirements', 'No description provided'))
        services_text.config(state="disabled")

        # Technician Information Section
        self._create_detail_section(details_scrollable, "👨‍💻 Technician Information", [
            ("Assigned Technician", srf.get('technician_assigned', 'Not assigned')),
            ("Response Time", srf.get('response_time', 'N/A')),
            ("Service Time", srf.get('service_time', 'N/A'))
        ])

        # Tab 2: Status & Timeline
        status_tab = tb.Frame(content_notebook)
        content_notebook.add(status_tab, text="📊 Status & Timeline")

        # Status overview
        status_overview = tb.LabelFrame(status_tab, text="📈 Current Status", 
                                       bootstyle="success", padding=15)
        status_overview.pack(fill="x", padx=10, pady=10)

        status_grid = tb.Frame(status_overview)
        status_grid.pack(fill="x")

        # Status cards
        current_status = srf.get('status', 'open').title()
        priority = srf.get('priority', 'Normal')
        
        self._create_status_card(status_grid, "Status", current_status, 0, 0, status_style)
        self._create_status_card(status_grid, "Priority", priority, 0, 1, "warning" if priority == "High" else "info")

        # Timeline section
        timeline_frame = tb.LabelFrame(status_tab, text="⏰ Timeline", 
                                     bootstyle="secondary", padding=15)
        timeline_frame.pack(fill="both", expand=True, padx=10, pady=10)

        timeline_items = [
            ("📝 Created", srf['created_at'].strftime('%m/%d/%Y %H:%M:%S'), "Created by " + srf.get('created_by_username', 'Unknown')),
            ("🔄 Last Updated", srf.get('updated_at', srf['created_at']).strftime('%m/%d/%Y %H:%M:%S') if srf.get('updated_at') else "N/A", "Last modification")
        ]

        for i, (icon_title, timestamp, description) in enumerate(timeline_items):
            timeline_item = tb.Frame(timeline_frame)
            timeline_item.pack(fill="x", pady=5)
            
            tb.Label(timeline_item, text=icon_title, font=("Segoe UI", 11, "bold")).pack(side="left")
            tb.Label(timeline_item, text=timestamp, font=("Segoe UI", 10)).pack(side="left", padx=(10, 0))
            tb.Label(timeline_item, text=f"({description})", font=("Segoe UI", 9), 
                    bootstyle="secondary").pack(side="left", padx=(5, 0))

        # Tab 3: Remarks & Notes
        remarks_tab = tb.Frame(content_notebook)
        content_notebook.add(remarks_tab, text="📝 Remarks")

        remarks_frame = tb.LabelFrame(remarks_tab, text="💬 Remarks & Notes", 
                                    bootstyle="warning", padding=15)
        remarks_frame.pack(fill="both", expand=True, padx=10, pady=10)

        remarks_text = tb.Text(remarks_frame, wrap="word", state="disabled",
                             font=("Segoe UI", 10), height=10)
        remarks_text.pack(fill="both", expand=True)
        remarks_text.config(state="normal")
        remarks_content = srf.get('remarks', 'No remarks available')
        remarks_text.insert("1.0", remarks_content)
        remarks_text.config(state="disabled")

        # Enhanced Action Buttons
        action_frame = tb.Frame(main_container)
        action_frame.pack(fill="x")

        # Left side buttons
        left_buttons = tb.Frame(action_frame)
        left_buttons.pack(side="left")

        tb.Button(left_buttons, text="✏️ Edit Request", bootstyle="warning",
                 command=lambda: self.open_edit_ticket_modal(srf), width=15).pack(side="left", padx=(0, 10))

        if status != "resolved":
            tb.Button(left_buttons, text="✅ Mark Resolved", bootstyle="success",
                     command=lambda: self._mark_single_ticket_resolved(srf['ict_srf_no'], modal), 
                     width=15).pack(side="left", padx=(0, 10))

        # Right side buttons
        right_buttons = tb.Frame(action_frame)
        right_buttons.pack(side="right")

        tb.Button(right_buttons, text="🖨️ Print", bootstyle="info",
                 command=lambda: print_srf_form(srf, logo_path="assets/images/bsu_logo.png"), 
                 width=12).pack(side="right", padx=(10, 0))

        tb.Button(right_buttons, text="❌ Close", bootstyle="secondary",
                 command=modal.destroy, width=10).pack(side="right")

    def _create_detail_section(self, parent, title, fields):
        """Create a detail section with fields."""
        section = tb.LabelFrame(parent, text=title, bootstyle="primary", padding=15)
        section.pack(fill="x", padx=10, pady=10)

        for i, (label, value) in enumerate(fields):
            field_frame = tb.Frame(section)
            field_frame.pack(fill="x", pady=2)
            field_frame.columnconfigure(1, weight=1)

            tb.Label(field_frame, text=f"{label}:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", padx=(0, 10))
            tb.Label(field_frame, text=str(value), font=("Segoe UI", 10)).grid(row=0, column=1, sticky="w")

    def _create_status_card(self, parent, title, value, row, col, style="info"):
        """Create a status card widget."""
        card = tb.LabelFrame(parent, text=title, bootstyle=style, padding=10)
        card.grid(row=row, column=col, padx=5, pady=5, sticky="ew")
        parent.columnconfigure(col, weight=1)

        tb.Label(card, text=str(value), font=("Segoe UI", 14, "bold"), 
                bootstyle=f"inverse-{style}").pack()

    def _mark_single_ticket_resolved(self, ticket_id, modal):
        """Mark a single ticket as resolved from the detail modal."""
        try:
            from tkinter import messagebox
            if messagebox.askyesno("Confirm Resolution", 
                                 f"Mark Service Request #{ticket_id} as resolved?\n\nThis action cannot be undone."):
                # Update in database using utility function
                ticket_utils.update_ticket_status(ticket_id, "resolved")
                
                messagebox.showinfo("Success", f"Service Request #{ticket_id} has been marked as resolved!")
                modal.destroy()
                
                # Refresh the main tickets table if it exists
                if hasattr(self, 'tickets_table'):
                    self.load_tickets()
                    
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error", f"Failed to update ticket status: {e}")
            print(f"Error updating ticket status: {e}")

    def enable_edit_srf(self, srf, modal):
        """Turn detail labels into editable fields and allow saving."""
        for key, widget in self.detail_widgets.items():
            if isinstance(widget, tb.Label):  # replace label with entry
                value = widget.cget("text")
                widget.destroy()
                entry = tb.Entry(widget.master)
                entry.insert(0, value)
                entry.grid(row=widget.grid_info()["row"], column=1, sticky="ew", padx=5, pady=5)
                self.detail_widgets[key] = entry

        tb.Button(modal, text="💾 Save", bootstyle="success",
                command=lambda: self.save_srf_changes(srf["ict_srf_no"], modal)).pack(pady=10)

    def open_edit_ticket_modal(self, srf):
        """Open modal for editing an existing SRF."""
        modal = tb.Toplevel(self.root)
        modal.title("Edit ICT Service Request Form")
        modal.geometry("725x600")
        modal.resizable(False, False)
        modal.grab_set()

        # Build the form with pre-filled data
        button_host = self.build_ticket_form(modal, initial_data=srf, is_edit=True)

        # Save button
        tb.Button(
            button_host,
            text="Save Changes",
            bootstyle="success",
            command=lambda: self.submit_edit_ticket(srf["ict_srf_no"], modal)
        ).pack(pady=20)

    def open_new_ticket_modal(self):
        """Open modal for creating a new ICT Service Request."""
        modal = tb.Toplevel(self.root)
        modal.title("New ICT Service Request Form")
        modal.geometry("725x600")
        modal.resizable(False, False)
        modal.grab_set()

        # Build empty form
        button_host = self.build_ticket_form(modal, initial_data={}, is_edit=False)

        # Save button for create
        tb.Button(
            button_host,
            text="Create Request",
            bootstyle="success",
            command=lambda: self.submit_new_ticket(modal)
        ).pack(pady=20)

    def submit_new_ticket(self, modal):
        """Collect form and create a new SRF entry."""
        try:
            data = self.collect_ticket_form_data()
            # Basic validation
            ict_srf_no_str = str(data.get("ict_srf_no", "")).strip()
            if not ict_srf_no_str.isdigit():
                from tkinter import messagebox
                messagebox.showerror("Validation Error", "ICT SRF NO. must be a number.")
                return
            data["ict_srf_no"] = int(ict_srf_no_str)
            # Created by current user id if available
            created_by = None
            try:
                created_by = int(self.current_user.get('id')) if getattr(self, 'current_user', None) else None
            except Exception:
                created_by = None
            if not created_by:
                created_by = 1  # fallback admin id
            # Create via utils
            ticket_utils.create_srf(data, created_by)
            from tkinter import messagebox
            messagebox.showinfo("Success", f"Service Request #{data['ict_srf_no']} created successfully!")
            try:
                modal.destroy()
            except Exception:
                pass
            # Refresh table if present
            if hasattr(self, 'load_tickets'):
                self.load_tickets()
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error", f"Failed to create Service Request:\n{e}")


    def save_srf_changes(self, srf_no, modal):
        """Save edited SRF values to DB."""
        update_data = {k: w.get() for k, w in self.detail_widgets.items() if isinstance(w, tb.Entry)}
        try:
            ticket_utils.update_srf(srf_no, update_data)
            messagebox.showinfo("Success", "SRF updated successfully!")
            modal.destroy()
            self.load_tickets()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update SRF:\n{e}")


    def _mark_ticket_done_modal(self, ticket_id, modal):
        """Helper to mark ticket resolved from modal."""
        try:
            from tkinter import messagebox
            
            # Update in database using utility function
            ticket_utils.update_ticket_status(ticket_id, "resolved")

            messagebox.showinfo("Success", "Service Request has been marked as resolved!")
            modal.destroy()
            
            # Refresh the ticket table if it exists
            if hasattr(self, 'tickets_table'):
                self.load_tickets()
                
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error", f"Failed to mark ticket as resolved: {e}")
            print(f"Error in _mark_ticket_done_modal: {e}")
#---------------------------------------------------------------

    def open_loop_test_modal(self):
        modal = tb.Toplevel(self.root)
        modal.title("🔄 Loop Detection Monitor")
        modal.geometry("900x600")
        modal.resizable(True, True)

        # Center modal on parent
        modal.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (900 // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (600 // 2)
        modal.geometry(f"+{x}+{y}")

        modal.transient(self.root)
        modal.grab_set()

        # Create main container with notebook for tabs
        main_container = tb.Frame(modal)
        main_container.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Header
        header_frame = tb.Frame(main_container)
        header_frame.pack(fill='x', pady=(0, 10))
        
        tb.Label(header_frame, text="🔄 Loop Detection Monitor", 
                font=("Segoe UI", 16, "bold")).pack(side='left')
        
        # Control buttons
        control_frame = tb.Frame(header_frame)
        control_frame.pack(side='right')
        
        self.loop_start_btn = tb.Button(control_frame, text="▶ Start Auto", bootstyle="success",
                                       command=lambda: self.start_automatic_loop_detection(modal), width=10)
        self.loop_start_btn.pack(side='left', padx=(0, 5))
        
        self.loop_stop_btn = tb.Button(control_frame, text="⏹ Stop Auto", bootstyle="danger",
                                      command=lambda: self.stop_automatic_loop_detection(modal), width=10)
        self.loop_stop_btn.pack(side='left', padx=(0, 5))
        
        

        # Create notebook for tabs
        notebook = tb.Notebook(main_container)
        notebook.pack(fill='both', expand=True)
        
        # Tab 1: Manual Scan
        manual_tab = tb.Frame(notebook)
        notebook.add(manual_tab, text="🔍 Manual Scan")
        
        # Manual scan content
        manual_content = tb.LabelFrame(manual_tab, text="Network Loop Detection", 
                                     bootstyle="primary", padding=15)
        manual_content.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Status and controls
        status_frame = tb.Frame(manual_content)
        status_frame.pack(fill='x', pady=(0, 15))
        
        self.loop_status_lbl = tb.Label(status_frame, text="⏳ Ready to scan...", 
                                       font=("Segoe UI", 12, "bold"))
        self.loop_status_lbl.pack(side='left')
        
        # Spinner
        self.spinner_lbl = tb.Label(status_frame, text="", font=("Segoe UI", 14))
        self.spinner_lbl.pack(side='left', padx=(10, 0))
        
        # Manual scan buttons
        manual_btn_frame = tb.Frame(manual_content)
        manual_btn_frame.pack(fill='x', pady=(0, 15))
        
        tb.Button(manual_btn_frame, text="▶ Run Manual Scan", bootstyle="success",
                 command=lambda: self.start_loop_scan(modal), width=15).pack(side='left', padx=(0, 10))
        
        tb.Button(manual_btn_frame, text="🔄 Clear Results", bootstyle="secondary",
                 command=lambda: self.clear_loop_results(), width=15).pack(side='left')
        
        # Results box - made more prominent
        results_frame = tb.LabelFrame(manual_content, text="📊 Scan Results", 
                                    bootstyle="info", padding=10)
        results_frame.pack(fill='both', expand=True)
        
        self.loop_results = tk.Text(results_frame, height=12, width=80, state="disabled",
                                   font=("Consolas", 10), wrap=tk.WORD)
        self.loop_results.pack(fill='both', expand=True)
        
        # Tab 2: Statistics & History
        stats_tab = tb.Frame(notebook)
        notebook.add(stats_tab, text="📊 Statistics & History")
        
        # Statistics cards
        stats_container = tb.Frame(stats_tab)
        stats_container.pack(fill='x', padx=10, pady=10)
        
        # Statistics cards in a grid
        stats_grid = tb.Frame(stats_container)
        stats_grid.pack(fill='x', pady=(0, 15))
        
        # Total detections card
        total_card = tb.LabelFrame(stats_grid, text="📈 Total Detections", 
                                 bootstyle="info", padding=15)
        total_card.grid(row=0, column=0, padx=(0, 10), pady=5, sticky='ew')
        
        self.total_detections_label = tb.Label(total_card, text=str(self.loop_detection_stats["total_detections"]), 
                                              font=("Segoe UI", 20, "bold"))
        self.total_detections_label.pack()
        
        # Loops detected card
        loops_card = tb.LabelFrame(stats_grid, text="⚠️ Loops Detected", 
                                 bootstyle="danger", padding=15)
        loops_card.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        
        self.loops_detected_label = tb.Label(loops_card, text=str(self.loop_detection_stats["loops_detected"]), 
                                           font=("Segoe UI", 20, "bold"))
        self.loops_detected_label.pack()
        
        # Suspicious activity card
        suspicious_card = tb.LabelFrame(stats_grid, text="🔍 Suspicious", 
                                      bootstyle="warning", padding=15)
        suspicious_card.grid(row=0, column=2, padx=5, pady=5, sticky='ew')
        
        self.suspicious_label = tb.Label(suspicious_card, text=str(self.loop_detection_stats["suspicious_activity"]), 
                                       font=("Segoe UI", 20, "bold"))
        self.suspicious_label.pack()
        
        # Clean detections card
        clean_card = tb.LabelFrame(stats_grid, text="✅ Clean", 
                                 bootstyle="success", padding=15)
        clean_card.grid(row=0, column=3, padx=(10, 0), pady=5, sticky='ew')
        
        self.clean_label = tb.Label(clean_card, text=str(self.loop_detection_stats["clean_detections"]), 
                                  font=("Segoe UI", 20, "bold"))
        self.clean_label.pack()
        
        # Configure grid weights
        stats_grid.columnconfigure(0, weight=1)
        stats_grid.columnconfigure(1, weight=1)
        stats_grid.columnconfigure(2, weight=1)
        stats_grid.columnconfigure(3, weight=1)
        
        # History table
        history_frame = tb.LabelFrame(stats_container, text="📜 Detection History", 
                                    bootstyle="success", padding=10)
        history_frame.pack(fill='both', expand=True)
        
        # History controls
        history_controls = tb.Frame(history_frame)
        history_controls.pack(fill='x', pady=(0, 10))
        
        tb.Button(history_controls, text="🔄 Refresh History", bootstyle="info",
                 command=self._refresh_loop_detection_history, width=15).pack(side='left')
        
        tb.Button(history_controls, text="🔍 View Details", bootstyle="primary",
                 command=self._show_selected_detection_details, width=15).pack(side='left', padx=(10, 0))
        
        # Create treeview for history
        columns = ("Time", "Status", "Packets", "Offenders", "Severity", "Interface")
        self.loop_detection_tree = ttk.Treeview(history_frame, columns=columns, show="headings", height=10)
        
        # Double-click to view details
        self.loop_detection_tree.bind("<Double-Button-1>", lambda e: self._show_selected_detection_details())
        
        # Configure columns
        for col in columns:
            self.loop_detection_tree.heading(col, text=col)
            self.loop_detection_tree.column(col, width=120, anchor="center")
        
        # Scrollbar
        tree_scrollbar = ttk.Scrollbar(history_frame, orient="vertical", command=self.loop_detection_tree.yview)
        self.loop_detection_tree.configure(yscrollcommand=tree_scrollbar.set)
        
        self.loop_detection_tree.pack(side="left", fill="both", expand=True)
        tree_scrollbar.pack(side="right", fill="y")
        
        # Tab 3: Configuration
        config_tab = tb.Frame(notebook)
        notebook.add(config_tab, text="⚙️ Configuration")
        
        # Configuration content
        config_content = tb.LabelFrame(config_tab, text="Loop Detection Settings", 
                                     bootstyle="primary", padding=20)
        config_content.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Interval setting
        interval_frame = tb.Frame(config_content)
        interval_frame.pack(fill='x', pady=(0, 20))
        
        tb.Label(interval_frame, text="Auto Detection Interval (minutes):", 
                font=("Segoe UI", 12, "bold")).pack(anchor='w')
        
        interval_input_frame = tb.Frame(interval_frame)
        interval_input_frame.pack(fill='x', pady=(10, 0))
        
        self.interval_var = tk.StringVar(value=str(self.loop_detection_interval // 60))
        interval_entry = tb.Entry(interval_input_frame, textvariable=self.interval_var, width=10)
        interval_entry.pack(side='left')
        
        tb.Button(interval_input_frame, text="Update Interval", bootstyle="info",
                 command=lambda: self.update_loop_interval_modal(modal)).pack(side='left', padx=(10, 0))
        
        # Current status display
        status_display_frame = tb.LabelFrame(config_content, text="Current Status", 
                                           bootstyle="secondary", padding=15)
        status_display_frame.pack(fill='x', pady=(0, 20))
        
        self.status_text = tb.Text(status_display_frame, height=6, state="disabled",
                                 font=("Consolas", 10))
        self.status_text.pack(fill='x')
        
        # Close button
        close_frame = tb.Frame(main_container)
        close_frame.pack(fill='x', pady=(10, 0))
        
        tb.Button(close_frame, text="❌ Close", bootstyle="danger",
                 command=modal.destroy, width=15).pack(side='right')
        
        # Load existing history
        self._load_loop_detection_history_modal()
        
        # Update status display
        self._update_loop_status_display_modal(modal)

    def start_automatic_loop_detection(self, modal):
        """Start automatic loop detection from modal."""
        if not self.loop_detection_running:
            self.start_loop_detection()
            self.loop_start_btn.config(state="disabled")
            self.loop_stop_btn.config(state="normal")
            messagebox.showinfo("Success", "Automatic loop detection started!")

    def stop_automatic_loop_detection(self, modal):
        """Stop automatic loop detection from modal."""
        if self.loop_detection_running:
            self.stop_loop_detection()
            self.loop_start_btn.config(state="normal")
            self.loop_stop_btn.config(state="disabled")
            messagebox.showinfo("Success", "Automatic loop detection stopped!")

    def update_loop_interval_modal(self, modal):
        """Update loop detection interval from modal."""
        try:
            interval = int(self.interval_var.get())
            if 1 <= interval <= 60:
                self.set_loop_detection_interval(interval)
                self._update_loop_status_display_modal(modal)
                messagebox.showinfo("Success", f"Detection interval updated to {interval} minutes")
            else:
                messagebox.showerror("Error", "Interval must be between 1 and 60 minutes")
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number")

    def _load_loop_detection_history_modal(self):
        """Load existing loop detection history into the modal table."""
        try:
            # Clear existing items
            for item in self.loop_detection_tree.get_children():
                self.loop_detection_tree.delete(item)
            
            # Add history records
            for record in self.loop_detection_history:
                # Handle both database records and in-memory records
                if "detection_time" in record:
                    # Database record
                    record_id = record.get("id")
                    timestamp = record["detection_time"].strftime("%Y-%m-%d %H:%M:%S") if hasattr(record["detection_time"], 'strftime') else str(record["detection_time"])[:19]
                    status = record["status"]
                    packets = record["total_packets"]
                    offenders = record["offenders_count"]
                    severity = record["severity_score"]
                    interface = record["network_interface"]
                else:
                    # In-memory record
                    record_id = record.get("id")
                    timestamp = record["timestamp"][:19]  # Format timestamp
                    status = record["status"]
                    packets = record["total_packets"]
                    # Handle both integer and list offenders
                    if isinstance(record["offenders"], list):
                        offenders = len(record["offenders"])
                    else:
                        offenders = record["offenders"]  # Already an integer
                    severity = record["severity_score"]
                    interface = record.get("interface", "Wi-Fi")
                
                # Format status with emoji
                status_emoji = {
                    'clean': '✅ Clean',
                    'suspicious': '🔍 Suspicious',
                    'loop_detected': '⚠️ Loop Detected'
                }.get(status, f'❓ {status}')
                
                # Insert with record ID as tag for retrieval
                self.loop_detection_tree.insert("", "end", values=(
                    timestamp,
                    status_emoji,
                    packets,
                    offenders,
                    f"{severity:.2f}",
                    interface
                ), tags=(str(record_id),))
                
        except Exception as e:
            print(f"Error loading loop detection history: {e}")

    def _update_loop_status_display_modal(self, modal):
        """Update the status display in modal with current information."""
        try:
            # Update statistics labels
            self.total_detections_label.config(text=str(self.loop_detection_stats["total_detections"]))
            self.loops_detected_label.config(text=str(self.loop_detection_stats["loops_detected"]))
            self.suspicious_label.config(text=str(self.loop_detection_stats["suspicious_activity"]))
            self.clean_label.config(text=str(self.loop_detection_stats["clean_detections"]))
            
            # Update button states
            if self.loop_detection_running:
                self.loop_start_btn.config(state="disabled")
                self.loop_stop_btn.config(state="normal")
            else:
                self.loop_start_btn.config(state="normal")
                self.loop_stop_btn.config(state="disabled")
                
        except Exception as e:
            print(f"Error updating status display: {e}")

    def _analyze_loop_problem(self, record, stats, sorted_stats):
        """Analyze the detection and provide insights about potential problems."""
        analysis = []
        
        analysis.append("=== PROBLEM ANALYSIS ===\n")
        analysis.append(f"Detection Status: {record['status'].upper()}\n")
        analysis.append(f"Severity Score: {record['severity_score']:.2f}\n")
        analysis.append(f"Threshold: Clean < 7.5, Suspicious 7.5-22.5, Loop > 22.5\n\n")

        if record['status'] == 'clean':
            analysis.append("✅ NETWORK STATUS: CLEAN\n")
            analysis.append("No significant loop activity detected. The network is operating normally.\n\n")
            
            if stats:
                analysis.append("📊 TRAFFIC SUMMARY:\n")
                for mac, mac_stats in sorted_stats[:3]:
                    ips = ', '.join(mac_stats.get('ips', ['N/A']))
                    analysis.append(f"  • {mac} ({ips})\n")
                    analysis.append(f"    - Total: {mac_stats.get('count', 0)} packets\n")
                    analysis.append(f"    - ARP: {mac_stats.get('arp_count', 0)}, Broadcast: {mac_stats.get('broadcast_count', 0)}\n")
                    sev = mac_stats.get('severity', 0)
                    if isinstance(sev, dict):
                        sev = sev.get('total', 0)
                    analysis.append(f"    - Severity: {sev:.2f}\n\n")

        elif record['status'] == 'suspicious':
            analysis.append("🟡 NETWORK STATUS: SUSPICIOUS ACTIVITY\n")
            analysis.append("Elevated traffic detected but below loop threshold. This could be:\n")
            analysis.append("  • Normal network activity during high usage\n")
            analysis.append("  • A device performing legitimate operations (DHCP, ARP discovery)\n")
            analysis.append("  • Early signs of a developing loop\n\n")

            if sorted_stats:
                top_offender = sorted_stats[0]
                mac = top_offender[0]
                mac_stats = top_offender[1]
                ips = ', '.join(mac_stats.get('ips', ['N/A']))

                analysis.append("🔍 TOP SUSPICIOUS DEVICE:\n")
                analysis.append(f"  MAC: {mac}\n")
                analysis.append(f"  IP: {ips}\n")
                sev = mac_stats.get('severity', 0)
                if isinstance(sev, dict):
                    sev = sev.get('total', 0)
                analysis.append(f"  Severity: {sev:.2f}\n")
                analysis.append(f"  Total Packets: {mac_stats.get('count', 0)}\n")
                analysis.append(f"  ARP Count: {mac_stats.get('arp_count', 0)}\n")
                analysis.append(f"  Broadcast: {mac_stats.get('broadcast_count', 0)}\n\n")

                analysis.append("💡 RECOMMENDATIONS:\n")
                if mac_stats.get('arp_count', 0) > 15:
                    analysis.append("  • High ARP traffic detected - device may be scanning network\n")
                if mac_stats.get('broadcast_count', 0) > 20:
                    analysis.append("  • High broadcast traffic - check for misconfigured applications\n")
                if mac == "3c:91:80:80:ac:97":
                    analysis.append("  • This is your whitelisted laptop - traffic is legitimate\n")
                else:
                    analysis.append("  • Monitor this device - if severity increases, investigate further\n")
                    analysis.append("  • Check if device is a router, server, or IoT device\n")

        else:  # loop_detected
            analysis.append("🔴 NETWORK STATUS: LOOP DETECTED!\n")
            analysis.append("CRITICAL: A network loop has been detected. This will cause:\n")
            analysis.append("  • Network performance degradation\n")
            analysis.append("  • Broadcast storms\n")
            analysis.append("  • Potential network outage\n\n")

            if sorted_stats:
                analysis.append("⚠️ OFFENDING DEVICES:\n")
                for i, (mac, mac_stats) in enumerate(sorted_stats[:5], 1):
                    ips = ', '.join(mac_stats.get('ips', ['N/A']))
                    analysis.append(f"\n{i}. {mac} ({ips})\n")
                    sev = mac_stats.get('severity', 0)
                    if isinstance(sev, dict):
                        sev = sev.get('total', 0)
                    analysis.append(f"   Severity: {sev:.2f}\n")
                    analysis.append(f"   Packets: {mac_stats.get('count', 0)}\n")
                    analysis.append(f"   ARP: {mac_stats.get('arp_count', 0)}, ")
                    analysis.append(f"Broadcast: {mac_stats.get('broadcast_count', 0)}, ")
                    analysis.append(f"STP: {mac_stats.get('stp_count', 0)}\n")

                top_offender = sorted_stats[0]
                mac_stats = top_offender[1]

                analysis.append("\n💡 IMMEDIATE ACTIONS REQUIRED:\n")
                analysis.append("  1. Locate the physical connections for devices listed above\n")
                analysis.append("  2. Check for cable loops between switches/routers\n")
                analysis.append("  3. Verify STP (Spanning Tree Protocol) is enabled on switches\n")
                
                if mac_stats.get('broadcast_count', 0) > 50:
                    analysis.append("  4. HIGH BROADCAST TRAFFIC - Disconnect suspected switch immediately\n")
                if mac_stats.get('arp_count', 0) > 50:
                    analysis.append("  4. HIGH ARP TRAFFIC - Check for duplicate IP addresses\n")
                if mac_stats.get('stp_count', 0) > 10:
                    analysis.append("  4. STP PACKETS DETECTED - Check switch STP configuration\n")

                analysis.append("\n🔧 TROUBLESHOOTING STEPS:\n")
                analysis.append("  • Disconnect one cable at a time from switches\n")
                analysis.append("  • Run detection again after each disconnection\n")
                analysis.append("  • Once severity drops, you've found the loop\n")
                analysis.append("  • Configure STP on all switches to prevent future loops\n")

        analysis.append("\n" + "="*60 + "\n")
        
        return ''.join(analysis)

    def _show_selected_detection_details(self):
        """Show details for the currently selected detection in the history tree."""
        selected = self.loop_detection_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a detection record to view details.")
            return
        
        # Get record ID from the item tags
        item = selected[0]
        tags = self.loop_detection_tree.item(item, 'tags')
        if not tags:
            messagebox.showerror("Error", "Could not find record ID.")
            return
        
        try:
            record_id = int(tags[0])
            
            # Find record in in-memory history
            record = None
            for hist_record in self.loop_detection_history:
                if hist_record.get('id') == record_id:
                    record = hist_record
                    break
            
            if record:
                self._show_detection_details_modal(record)
            else:
                messagebox.showerror("Error", f"Record #{record_id} not found in history.")
        except (ValueError, IndexError) as e:
            messagebox.showerror("Error", f"Invalid record ID: {e}")

    def _show_detection_details_modal(self, record):
        """Show detailed information about a detection record."""
        if not record:
            messagebox.showerror("Error", "Record not found!")
            return
        
        record_id = record['id']

        try:
            # Create detail modal
            detail_modal = tb.Toplevel(self.root)
            detail_modal.title(f"🔍 Detection Details - ID #{record_id}")
            detail_modal.geometry("700x550")
            detail_modal.resizable(True, True)
            detail_modal.transient(self.root)

            # Make it truly modal and focused to avoid going behind the parent
            try:
                detail_modal.grab_set()
            except Exception:
                pass
            try:
                detail_modal.focus_set()
            except Exception:
                pass
            # Nudge window to front briefly; then release topmost so it behaves normally
            try:
                detail_modal.attributes('-topmost', True)
                detail_modal.after(200, lambda: detail_modal.attributes('-topmost', False))
            except Exception:
                pass

            # Center modal (calculate before showing)
            x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 350
            y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 275
            detail_modal.geometry(f"700x550+{x}+{y}")

            # Simple scrollable container
            main_canvas = tk.Canvas(detail_modal, highlightthickness=0)
            main_scrollbar = tb.Scrollbar(detail_modal, orient="vertical", command=main_canvas.yview)
            scrollable_frame = tb.Frame(main_canvas)

            scrollable_frame.bind("<Configure>", 
                lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all")))

            main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=680)
            main_canvas.configure(yscrollcommand=main_scrollbar.set)

            main_canvas.pack(side="left", fill="both", expand=True)
            main_scrollbar.pack(side="right", fill="y")

            content = tb.Frame(scrollable_frame)
            content.pack(fill='both', expand=True, padx=15, pady=10)

            # Header (no top-right X close icon)
            header_frame = tb.Frame(content)
            header_frame.pack(fill='x', pady=(0, 10))
            
            status_emoji = {
                'clean': '✅',
                'suspicious': '🟡',
                'loop_detected': '🔴'
            }.get(record['status'], '❓')

            tb.Label(header_frame, text=f"{status_emoji} ID #{record_id} - {record['status'].replace('_', ' ').title()}",
                    font=("Segoe UI", 13, "bold")).pack(side='left')

            # Basic Information Card - compact
            basic_info = tb.LabelFrame(content, text="📋 Basic Information", padding=10, bootstyle="info")
            basic_info.pack(fill='x', pady=(0, 8))

            basic_grid = tb.Frame(basic_info)
            basic_grid.pack(fill='x')

            # Row 1
            tb.Label(basic_grid, text="Time:", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky='w', pady=3)
            tb.Label(basic_grid, text=record['detection_time'].strftime('%Y-%m-%d %H:%M:%S'),
                    font=("Segoe UI", 9)).grid(row=0, column=1, sticky='w', padx=(5, 0), pady=3)

            tb.Label(basic_grid, text="Severity:", font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky='w', padx=(15, 0), pady=3)
            severity_color = "danger" if record['severity_score'] > 22.5 else ("warning" if record['severity_score'] > 7.5 else "success")
            tb.Label(basic_grid, text=f"{record['severity_score']:.2f}",
                    font=("Segoe UI", 9, "bold"), bootstyle=severity_color).grid(row=0, column=3, sticky='w', padx=(5, 0), pady=3)

            # Row 2
            tb.Label(basic_grid, text="Interface:", font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky='w', pady=3)
            tb.Label(basic_grid, text=record['network_interface'] or "N/A",
                    font=("Segoe UI", 9)).grid(row=1, column=1, sticky='w', padx=(5, 0), pady=3)

            tb.Label(basic_grid, text="Duration:", font=("Segoe UI", 9, "bold")).grid(row=1, column=2, sticky='w', padx=(15, 0), pady=3)
            tb.Label(basic_grid, text=f"{record['detection_duration']}s",
                    font=("Segoe UI", 9)).grid(row=1, column=3, sticky='w', padx=(5, 0), pady=3)

            # Row 3
            tb.Label(basic_grid, text="Packets:", font=("Segoe UI", 9, "bold")).grid(row=2, column=0, sticky='w', pady=3)
            tb.Label(basic_grid, text=str(record['total_packets']),
                    font=("Segoe UI", 9)).grid(row=2, column=1, sticky='w', padx=(5, 0), pady=3)

            tb.Label(basic_grid, text="Offenders:", font=("Segoe UI", 9, "bold")).grid(row=2, column=2, sticky='w', padx=(15, 0), pady=3)
            tb.Label(basic_grid, text=str(record['offenders_count']),
                    font=("Segoe UI", 9)).grid(row=2, column=3, sticky='w', padx=(5, 0), pady=3)

            # Offenders Information - compact (async-loaded for responsiveness)
            offenders_frame = tb.LabelFrame(content, text="⚠️ Top Offenders", padding=8, bootstyle="warning")
            offenders_frame.pack(fill='both', expand=True, pady=(0, 8))

            # Placeholder loading UI to keep modal responsive
            loading_frame = tb.Frame(offenders_frame)
            loading_frame.pack(fill='x', pady=(5, 5))
            tb.Label(loading_frame, text="Loading details...", font=("Segoe UI", 10)).pack(side='left')
            try:
                pb = tb.Progressbar(loading_frame, mode='indeterminate', bootstyle='info-striped')
                pb.pack(side='left', padx=(10, 0))
                pb.start(10)
            except Exception:
                pb = None

            # Container where final widgets will be placed
            details_container = tb.Frame(offenders_frame)
            details_container.pack(fill='both', expand=True)

            # Also prepare a container for the analysis section
            analysis_frame = tb.LabelFrame(content, text="🔍 Analysis", padding=8, bootstyle="danger")
            analysis_frame.pack(fill='x', pady=(0, 8))
            analysis_text = tb.Text(analysis_frame, height=6, wrap=tk.WORD, font=("Segoe UI", 8))
            analysis_text.insert("1.0", "Preparing analysis...")
            analysis_text.config(state='disabled')
            analysis_text.pack(fill='both', expand=True)

            # Track closed state to abort background updates quickly
            closed = {"v": False}

            def _on_destroy():
                closed["v"] = True
                # Stop progress animation if running
                try:
                    if pb:
                        pb.stop()
                except Exception:
                    pass
                # Release grab if set
                try:
                    detail_modal.grab_release()
                except Exception:
                    pass

            def _on_close():
                # Ensure resources stop before actual destroy
                _on_destroy()
                try:
                    if detail_modal.winfo_exists():
                        # Hide immediately for instant feedback
                        try:
                            detail_modal.withdraw()
                        except Exception:
                            pass
                        # Destroy on next loop to avoid race with callbacks
                        self.root.after(0, lambda: detail_modal.winfo_exists() and detail_modal.destroy())
                except Exception:
                    pass

            # Wire close handlers
            try:
                detail_modal.protocol("WM_DELETE_WINDOW", _on_close)
            except Exception:
                pass
            # Also catch any destroy events
            detail_modal.bind("<Destroy>", lambda e: _on_destroy(), add="+")

            # Heavy work: parse JSON and prepare data off the UI thread
            def _load_details_worker():
                import json
                try:
                    offenders_data = json.loads(record.get('offenders_data') or '{}')
                    stats = offenders_data.get('stats', {}) or {}

                    # Normalize severity to numeric for sorting/display
                    def _sev_num(mac_stats):
                        s = mac_stats.get('severity', 0)
                        return s.get('total', 0) if isinstance(s, dict) else s

                    # Sort once in worker by numeric severity
                    sorted_stats = sorted(stats.items(), key=lambda x: _sev_num(x[1]), reverse=True)

                    # Build rows for top N only to limit UI work
                    top_n = 10
                    rows = []
                    for mac, mac_stats in sorted_stats[:top_n]:
                        ips = ', '.join(mac_stats.get('ips', ['N/A']))[:20]
                        sev_val = _sev_num(mac_stats)
                        rows.append((
                            mac[-17:],
                            ips,
                            mac_stats.get('count', 0),
                            mac_stats.get('arp_count', 0),
                            mac_stats.get('broadcast_count', 0),
                            f"{sev_val:.1f}"
                        ))

                    # Prepare analysis string
                    analysis_str = self._analyze_loop_problem(record, stats, sorted_stats) if stats else "No offenders detected in this scan."

                    def _apply_details_to_ui():
                        # Skip if closed or modal gone
                        if closed["v"] or not detail_modal.winfo_exists():
                            return
                        # Skip if modal was closed
                        try:
                            # Stop and remove loading UI
                            if pb:
                                try:
                                    pb.stop()
                                except Exception:
                                    pass
                            if loading_frame and loading_frame.winfo_exists():
                                loading_frame.destroy()

                            # If no stats, show a simple label
                            if not rows:
                                tb.Label(details_container, text="No offenders detected in this scan.",
                                         font=("Segoe UI", 10)).pack()
                            else:
                                offenders_tree_frame = tb.Frame(details_container)
                                offenders_tree_frame.pack(fill='both', expand=True)

                                offenders_scroll = tb.Scrollbar(offenders_tree_frame, orient="vertical")
                                offenders_scroll.pack(side='right', fill='y')

                                offenders_cols = ("MAC", "IP", "Packets", "ARP", "Broadcast", "Severity")
                                offenders_tree = tb.Treeview(offenders_tree_frame, columns=offenders_cols,
                                                            show="headings", yscrollcommand=offenders_scroll.set,
                                                            height=4)
                                offenders_scroll.config(command=offenders_tree.yview)

                                for col, text in zip(offenders_cols, ["MAC", "IP", "Pkts", "ARP", "Bcast", "Score"]):
                                    offenders_tree.heading(col, text=text)
                                offenders_tree.column("MAC", width=130)
                                offenders_tree.column("IP", width=120)
                                offenders_tree.column("Packets", width=60, anchor='center')
                                offenders_tree.column("ARP", width=50, anchor='center')
                                offenders_tree.column("Broadcast", width=50, anchor='center')
                                offenders_tree.column("Severity", width=60, anchor='center')

                                # Batch insert rows to minimize redraws
                                for r in rows:
                                    offenders_tree.insert("", "end", values=r)
                                offenders_tree.pack(fill='both', expand=True)

                            # Update analysis text
                            analysis_text.config(state='normal')
                            analysis_text.delete("1.0", tk.END)
                            analysis_text.insert("1.0", analysis_str)
                            analysis_text.config(state='disabled')
                        except Exception as _ui_e:
                            # As a last resort, show an inline error but don't crash
                            try:
                                analysis_text.config(state='normal')
                                analysis_text.delete("1.0", tk.END)
                                analysis_text.insert("1.0", f"Failed to render details: {_ui_e}")
                                analysis_text.config(state='disabled')
                            except Exception:
                                pass

                    # Apply on UI thread
                    if not closed["v"]:
                        self.root.after(0, _apply_details_to_ui)

                except Exception as worker_e:
                    def _apply_error():
                        if closed["v"] or not detail_modal.winfo_exists():
                            return
                        try:
                            if pb:
                                try:
                                    pb.stop()
                                except Exception:
                                    pass
                            if loading_frame and loading_frame.winfo_exists():
                                loading_frame.destroy()
                            tb.Label(details_container, text=f"Error loading details: {worker_e}",
                                     font=("Segoe UI", 10), bootstyle="danger").pack()
                        except Exception:
                            pass
                    if not closed["v"]:
                        self.root.after(0, _apply_error)

            # Kick off worker thread
            threading.Thread(target=_load_details_worker, daemon=True).start()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load detection details: {e}")
            print(f"Error loading detection details: {e}")
            import traceback
            traceback.print_exc()

    def _analyze_loop_problem(self, record, stats, sorted_stats):
        """Analyze the detection and provide insights about potential problems."""
        analysis = []
        
        analysis.append("=== PROBLEM ANALYSIS ===\n")
        analysis.append(f"Detection Status: {record['status'].upper()}\n")
        analysis.append(f"Severity Score: {record['severity_score']:.2f}\n")
        analysis.append(f"Threshold: Clean < 7.5, Suspicious 7.5-22.5, Loop > 22.5\n\n")

        if record['status'] == 'clean':
            analysis.append("✅ NETWORK STATUS: CLEAN\n")
            analysis.append("No significant loop activity detected. The network is operating normally.\n\n")
            
            if stats:
                analysis.append("📊 TRAFFIC SUMMARY:\n")
                for mac, mac_stats in sorted_stats[:3]:
                    ips = ', '.join(mac_stats.get('ips', ['N/A']))
                    analysis.append(f"  • {mac} ({ips})\n")
                    analysis.append(f"    - Total: {mac_stats.get('count', 0)} packets\n")
                    analysis.append(f"    - ARP: {mac_stats.get('arp_count', 0)}, Broadcast: {mac_stats.get('broadcast_count', 0)}\n")
                    sev = mac_stats.get('severity', 0)
                    if isinstance(sev, dict):
                        sev = sev.get('total', 0)
                    analysis.append(f"    - Severity: {sev:.2f}\n\n")

        elif record['status'] == 'suspicious':
            analysis.append("🟡 NETWORK STATUS: SUSPICIOUS ACTIVITY\n")
            analysis.append("Elevated traffic detected but below loop threshold. This could be:\n")
            analysis.append("  • Normal network activity during high usage\n")
            analysis.append("  • A device performing legitimate operations (DHCP, ARP discovery)\n")
            analysis.append("  • Early signs of a developing loop\n\n")

            if sorted_stats:
                top_offender = sorted_stats[0]
                mac = top_offender[0]
                mac_stats = top_offender[1]
                ips = ', '.join(mac_stats.get('ips', ['N/A']))

                analysis.append("🔍 TOP SUSPICIOUS DEVICE:\n")
                analysis.append(f"  MAC: {mac}\n")
                analysis.append(f"  IP: {ips}\n")
                sev = mac_stats.get('severity', 0)
                if isinstance(sev, dict):
                    sev = sev.get('total', 0)
                analysis.append(f"  Severity: {sev:.2f}\n")
                analysis.append(f"  Total Packets: {mac_stats.get('count', 0)}\n")
                analysis.append(f"  ARP Count: {mac_stats.get('arp_count', 0)}\n")
                analysis.append(f"  Broadcast: {mac_stats.get('broadcast_count', 0)}\n\n")

                analysis.append("💡 RECOMMENDATIONS:\n")
                if mac_stats.get('arp_count', 0) > 15:
                    analysis.append("  • High ARP traffic detected - device may be scanning network\n")
                if mac_stats.get('broadcast_count', 0) > 20:
                    analysis.append("  • High broadcast traffic - check for misconfigured applications\n")
                if mac == "3c:91:80:80:ac:97":
                    analysis.append("  • This is your whitelisted laptop - traffic is legitimate\n")
                else:
                    analysis.append("  • Monitor this device - if severity increases, investigate further\n")
                    analysis.append("  • Check if device is a router, server, or IoT device\n")

        else:  # loop_detected
            analysis.append("🔴 NETWORK STATUS: LOOP DETECTED!\n")
            analysis.append("CRITICAL: A network loop has been detected. This will cause:\n")
            analysis.append("  • Network performance degradation\n")
            analysis.append("  • Broadcast storms\n")
            analysis.append("  • Potential network outage\n\n")

            if sorted_stats:
                analysis.append("⚠️ OFFENDING DEVICES:\n")
                for i, (mac, mac_stats) in enumerate(sorted_stats[:5], 1):
                    ips = ', '.join(mac_stats.get('ips', ['N/A']))
                    analysis.append(f"\n{i}. {mac} ({ips})\n")
                    sev = mac_stats.get('severity', 0)
                    if isinstance(sev, dict):
                        sev = sev.get('total', 0)
                    analysis.append(f"   Severity: {sev:.2f}\n")
                    analysis.append(f"   Packets: {mac_stats.get('count', 0)}\n")
                    analysis.append(f"   ARP: {mac_stats.get('arp_count', 0)}, ")
                    analysis.append(f"Broadcast: {mac_stats.get('broadcast_count', 0)}, ")
                    analysis.append(f"STP: {mac_stats.get('stp_count', 0)}\n")

                top_offender = sorted_stats[0]
                mac_stats = top_offender[1]

                analysis.append("\n💡 IMMEDIATE ACTIONS REQUIRED:\n")
                analysis.append("  1. Locate the physical connections for devices listed above\n")
                analysis.append("  2. Check for cable loops between switches/routers\n")
                analysis.append("  3. Verify STP (Spanning Tree Protocol) is enabled on switches\n")
                
                if mac_stats.get('broadcast_count', 0) > 50:
                    analysis.append("  4. HIGH BROADCAST TRAFFIC - Disconnect suspected switch immediately\n")
                if mac_stats.get('arp_count', 0) > 50:
                    analysis.append("  4. HIGH ARP TRAFFIC - Check for duplicate IP addresses\n")
                if mac_stats.get('stp_count', 0) > 10:
                    analysis.append("  4. STP PACKETS DETECTED - Check switch STP configuration\n")

                analysis.append("\n🔧 TROUBLESHOOTING STEPS:\n")
                analysis.append("  • Disconnect one cable at a time from switches\n")
                analysis.append("  • Run detection again after each disconnection\n")
                analysis.append("  • Once severity drops, you've found the loop\n")
                analysis.append("  • Configure STP on all switches to prevent future loops\n")

        analysis.append("\n" + "="*60 + "\n")
        
        return ''.join(analysis)

    def start_loop_scan(self, modal):
        # Update UI
        self.loop_status_lbl.config(text="⏳ Scanning network for loops...")
        self.loop_results.config(state="normal")
        self.loop_results.delete("1.0", tk.END)
        self.loop_results.config(state="disabled")

        # Start spinner
        self._spinner_running = True
        threading.Thread(target=self._animate_spinner, daemon=True).start()

        # Run loop detection in background
        threading.Thread(target=self._run_loop_scan_thread, args=(modal,), daemon=True).start()


    def _animate_spinner(self):
        for frame in itertools.cycle(["◐", "◓", "◑", "◒"]):
            if not getattr(self, "_spinner_running", False):
                break
            self.spinner_lbl.config(text=frame)
            time.sleep(0.2)


    def _trigger_loop_detection_on_router_offline(self, router_name, router_ip):
        """Trigger manual loop detection when a router goes offline (runs in background thread)."""
        def run_detection():
            try:
                print(f"🔍 Running loop detection triggered by router offline: {router_name} ({router_ip})")
                from network_utils import detect_loops, get_default_iface
                
                # Get the primary network interface
                iface = get_default_iface()
                print(f"🔍 Router offline scan - scanning interface: {iface}")
                
                # Run detection on primary interface with advanced engine (same as manual)
                total_packets, offenders, stats, advanced_metrics = detect_loops(
                    timeout=5,  # 5 seconds for thorough scan
                    threshold=100,  # Threshold for severity
                    iface=iface,
                    enable_advanced=True  # Use advanced detection
                )
                
                # Extract status from advanced detection
                max_severity = 0
                for mac, info in stats.items():
                    if isinstance(info.get("severity"), dict):
                        severity_value = info["severity"]["total"]
                    else:
                        severity_value = info.get("severity", 0)
                    max_severity = max(max_severity, severity_value)
                
                # Determine status
                if advanced_metrics.get("arp_storm_detected") or advanced_metrics.get("broadcast_flood_detected"):
                    status = "loop_detected"
                elif max_severity > 250:
                    status = "loop_detected"
                elif max_severity > 100:
                    status = "suspicious"
                else:
                    status = "clean"
                
                # Build efficiency metrics
                efficiency_metrics = {
                    "detection_method": "ADVANCED",
                    "interfaces_scanned": [iface],
                    "total_interfaces": 1,
                    "detection_duration": advanced_metrics.get("duration", 5),
                    "packets_per_second": total_packets / max(1, advanced_metrics.get("duration", 5)),
                    "unique_macs": advanced_metrics.get("total_unique_macs", 0),
                    "arp_storm_detected": advanced_metrics.get("arp_storm_detected", False),
                    "broadcast_flood_detected": advanced_metrics.get("broadcast_flood_detected", False),
                    "storm_rate": advanced_metrics.get("storm_rate", 0),
                    "early_exit": advanced_metrics.get("early_exit", False),
                    "early_exit_reason": advanced_metrics.get("early_exit_reason", None),
                    "actual_duration": advanced_metrics.get("duration", 5),
                    "interface_results": [{
                        "interface": iface,
                        "packets": total_packets,
                        "offenders": offenders,
                        "status": status
                    }],
                    "triggered_by": f"Router offline: {router_name} ({router_ip})"
                }
                
                interface_str = iface
                
                # Save to database
                from db import save_loop_detection
                detection_id = save_loop_detection(
                    total_packets=total_packets,
                    offenders=offenders,
                    stats=stats,
                    status=status,
                    severity_score=max_severity,
                    interface=interface_str,
                    duration=efficiency_metrics.get('detection_duration', 5),
                    efficiency_metrics=efficiency_metrics
                )
                
                # Send notification if loop detected
                if status in ["loop_detected", "suspicious"]:
                    from notification_utils import notify_loop_detected
                    notify_loop_detected(max_severity, offenders, interface_str)
                    self.root.after(0, self.update_notification_count)
                    
                    # Show popup alert for loop detected
                    if status == "loop_detected":
                        self.root.after(0, lambda: messagebox.showwarning(
                            "⚠️ Network Loop Detected!",
                            f"A network loop has been detected after router {router_name} went offline!\n\n"
                            f"Severity Score: {max_severity:.1f}\n"
                            f"Offending Devices: {len(offenders)}\n"
                            f"Interface: {interface_str}\n\n"
                            f"Click 'Loop Test' button to view details."
                        ))
                
                # Reload stats and history from database
                from db import get_loop_detection_stats, get_loop_detections_history
                self.loop_detection_stats = get_loop_detection_stats()
                self.loop_detection_history = get_loop_detections_history(100)
                
                # Print status
                safe_emoji_print(f"[SUCCESS] Router offline loop detection complete: status={status}, severity={max_severity:.2f}, offenders={len(offenders)}")
                
            except Exception as e:
                import traceback
                safe_emoji_print(f"[ERROR] Router offline loop detection error: {e}")
                traceback.print_exc()
        
        # Run in background thread
        threading.Thread(target=run_detection, daemon=True).start()

    def _run_loop_scan_thread(self, modal):
        try:
            # LOOP DETECTION FIX: Use default interface first, then multi-interface if needed
            from network_utils import detect_loops, get_default_iface
            
            # Get the primary network interface (same as test script)
            iface = get_default_iface()
            print(f"🔍 Dashboard scanning primary interface: {iface}")
            
            # Run detection on primary interface with advanced engine
            total_packets, offenders, stats, advanced_metrics = detect_loops(
                timeout=5,  # 5 seconds for thorough manual scan
                threshold=100,  # Threshold for severity
                iface=iface,  # Use same interface as test script
                enable_advanced=True  # Use advanced detection like test script
            )
            
            # Extract status from advanced detection
            max_severity = 0
            for mac, info in stats.items():
                if isinstance(info.get("severity"), dict):
                    severity_value = info["severity"]["total"]
                else:
                    severity_value = info.get("severity", 0)
                max_severity = max(max_severity, severity_value)
            
            # Determine status
            if advanced_metrics.get("arp_storm_detected") or advanced_metrics.get("broadcast_flood_detected"):
                status = "loop_detected"
            elif max_severity > 250:
                status = "loop_detected"
            elif max_severity > 100:
                status = "suspicious"
            else:
                status = "clean"
            
            # Build efficiency metrics compatible with dashboard
            efficiency_metrics = {
                "detection_method": "ADVANCED",
                "interfaces_scanned": [iface],
                "total_interfaces": 1,
                "detection_duration": advanced_metrics.get("duration", 5),
                "packets_per_second": total_packets / max(1, advanced_metrics.get("duration", 5)),
                "unique_macs": advanced_metrics.get("total_unique_macs", 0),
                "arp_storm_detected": advanced_metrics.get("arp_storm_detected", False),
                "broadcast_flood_detected": advanced_metrics.get("broadcast_flood_detected", False),
                "storm_rate": advanced_metrics.get("storm_rate", 0),
                "early_exit": advanced_metrics.get("early_exit", False),
                "early_exit_reason": advanced_metrics.get("early_exit_reason", None),
                "actual_duration": advanced_metrics.get("duration", 5),
                "interface_results": [{
                    "interface": iface,
                    "packets": total_packets,
                    "offenders": offenders,
                    "status": status
                }]
            }

            modal.after(0, self._finish_loop_scan_lightweight, total_packets, offenders, stats, status, max_severity, efficiency_metrics)

        except Exception as e:
            import traceback
            safe_emoji_print(f"[ERROR] Loop detection error: {e}")
            traceback.print_exc()
            modal.after(0, self._finish_loop_scan_lightweight, None, None, None, None, None, None, str(e))


    def _finish_loop_scan_lightweight(self, total_packets, offenders, stats, status, severity_score, efficiency_metrics=None, error=None):
        """Finish lightweight loop scan with proper status handling and efficiency metrics."""
        # Stop spinner
        self._spinner_running = False
        self.spinner_lbl.config(text="")

        self.loop_results.config(state="normal")
        self.loop_results.delete("1.0", tk.END)

        if error:
            self.loop_status_lbl.config(text="❌ Error during scan", bootstyle="danger")
            self.loop_results.insert(tk.END, f"Error: {error}\n")
        else:
            # Get scanned interfaces info
            interfaces = efficiency_metrics.get('interfaces_scanned', ['Unknown']) if efficiency_metrics else ['Unknown']
            interface_str = ', '.join(interfaces)
            duration = efficiency_metrics.get('detection_duration', 3) if efficiency_metrics else 3
            
            # Save to database with efficiency metrics
            from db import save_loop_detection
            detection_id = save_loop_detection(
                total_packets=total_packets,
                offenders=offenders,
                stats=stats,
                status=status,
                severity_score=severity_score,
                interface=interface_str,  # All scanned interfaces
                duration=duration,
                efficiency_metrics=efficiency_metrics  # Pass efficiency metrics
            )
            
            # Send notification for loop detection
            if status in ["loop_detected", "suspicious"]:
                notify_loop_detected(severity_score, offenders, interface_str)
                # Update notification count
                self.update_notification_count()
            
            # Reload stats and history from database
            from db import get_loop_detection_stats, get_loop_detections_history
            self.loop_detection_stats = get_loop_detection_stats()
            self.loop_detection_history = get_loop_detections_history(100)
            
            # Update statistics display in modal
            self._update_loop_status_display_modal(None)
            
            # Refresh history table if modal is open
            try:
                if hasattr(self, 'loop_detection_tree') and self.loop_detection_tree.winfo_exists():
                    self._load_loop_detection_history_modal()
            except:
                pass  # Modal might not be open
            
            # LOOP DETECTION UPDATE: Check for early exit
            early_exit_info = ""
            if efficiency_metrics and efficiency_metrics.get('early_exit', False):
                early_exit_info = f"\n⚡ EARLY EXIT: {efficiency_metrics.get('early_exit_reason', 'Severe loop detected')}\n"
                early_exit_info += f"   Duration: {efficiency_metrics.get('actual_duration', 0):.2f}s (stopped early)\n"
                early_exit_info += f"   Storm Rate: {efficiency_metrics.get('storm_rate', 0):.0f} packets/sec\n\n"
            
            # Display results based on status
            if status == "loop_detected":
                self.loop_status_lbl.config(text="⚠️ Loop Detected!", bootstyle="danger")
                self.loop_results.insert(tk.END, f"⚠️ LOOP DETECTED!\n")
                if early_exit_info:
                    self.loop_results.insert(tk.END, early_exit_info)
                self.loop_results.insert(tk.END, f"Severity Score: {severity_score:.2f}\n")
                self.loop_results.insert(tk.END, f"Total Packets: {total_packets}\n")
                self.loop_results.insert(tk.END, f"Offenders: {len(offenders)}\n\n")
                
                # LOOP DETECTION UPDATE: Show ARP storm/broadcast flood flags
                if efficiency_metrics:
                    if efficiency_metrics.get('arp_storm_detected', False):
                        self.loop_results.insert(tk.END, f"🚨 ARP STORM DETECTED! Rate: {efficiency_metrics.get('storm_rate', 0):.0f} ARP/sec\n")
                    if efficiency_metrics.get('broadcast_flood_detected', False):
                        self.loop_results.insert(tk.END, f"🚨 BROADCAST FLOOD DETECTED! Rate: {efficiency_metrics.get('storm_rate', 0):.0f} PPS\n")
                    if efficiency_metrics.get('arp_storm_detected') or efficiency_metrics.get('broadcast_flood_detected'):
                        self.loop_results.insert(tk.END, "\n")
                
                # Show offender details
                for mac in offenders:
                    info = stats.get(mac, {})
                    ips = ", ".join(info.get("ips", [])) if info.get("ips") else "Unknown"
                    
                    # Handle severity as dict or number
                    if isinstance(info.get("severity"), dict):
                        severity_value = info["severity"]["total"]
                    else:
                        severity_value = info.get("severity", 0)
                    
                    self.loop_results.insert(tk.END, f"• {mac} → {ips} (Severity: {severity_value:.2f})\n")
                    
                    # LOOP DETECTION UPDATE: Show single-router loop info
                    if info.get('loop_on_single_router', False):
                        self.loop_results.insert(tk.END, f"  ⚠️  SINGLE-ROUTER LOOP DETECTED!\n")
                        self.loop_results.insert(tk.END, f"  📌 Reason: {info.get('loop_reason', 'Unknown')}\n")
                        self.loop_results.insert(tk.END, f"  🔧 Action: {info.get('suggested_action', 'Investigate')}\n")
                    
            elif status == "suspicious":
                self.loop_status_lbl.config(text="🔍 Suspicious Activity", bootstyle="warning")
                self.loop_results.insert(tk.END, f"🔍 Suspicious activity detected\n")
                if early_exit_info:
                    self.loop_results.insert(tk.END, early_exit_info)
                self.loop_results.insert(tk.END, f"Severity Score: {severity_score:.2f}\n")
                self.loop_results.insert(tk.END, f"Total Packets: {total_packets}\n")
                self.loop_results.insert(tk.END, f"Offenders: {len(offenders)}\n\n")
                
                # Show offender details
                for mac in offenders:
                    info = stats.get(mac, {})
                    ips = ", ".join(info.get("ips", [])) if info.get("ips") else "Unknown"
                    # Handle severity as dict or number
                    sev = info.get("severity", 0)
                    if isinstance(sev, dict):
                        sev = sev.get("total", 0)
                    self.loop_results.insert(tk.END, f"• {mac} → {ips} (Severity: {sev:.2f})\n")
                    
                    # LOOP DETECTION UPDATE: Show single-router loop info for suspicious too
                    if info.get('loop_on_single_router', False):
                        self.loop_results.insert(tk.END, f"  ⚠️  Possible single-router loop\n")
                        self.loop_results.insert(tk.END, f"  📌 Reason: {info.get('loop_reason', 'Unknown')}\n")
                        self.loop_results.insert(tk.END, f"  🔧 Action: {info.get('suggested_action', 'Investigate')}\n")
                    
            else:  # status == "clean"
                self.loop_status_lbl.config(text="✅ Network Clean", bootstyle="success")
                self.loop_results.insert(tk.END, f"✅ Network is clean\n")
                self.loop_results.insert(tk.END, f"Severity Score: {severity_score:.2f}\n")
                self.loop_results.insert(tk.END, f"Total Packets: {total_packets}\n")
                self.loop_results.insert(tk.END, f"No suspicious activity detected\n")
            
            # Show efficiency metrics if available
            if efficiency_metrics:
                self.loop_results.insert(tk.END, f"\n⚡ Multi-Interface Scan Metrics:\n")
                self.loop_results.insert(tk.END, f"• Detection Method: {efficiency_metrics.get('detection_method', 'Unknown').upper()}\n")
                self.loop_results.insert(tk.END, f"• Interfaces Scanned: {len(interfaces)}/{efficiency_metrics.get('total_interfaces', 0)}\n")
                self.loop_results.insert(tk.END, f"• Interface Names: {interface_str}\n")
                self.loop_results.insert(tk.END, f"• Scan Duration: {duration:.2f}s\n")
                self.loop_results.insert(tk.END, f"• Packets/Second: {efficiency_metrics.get('packets_per_second', 0):.1f}\n")
                self.loop_results.insert(tk.END, f"• Cross-Interface Activity: {'⚠️ YES!' if efficiency_metrics.get('cross_interface_activity', False) else 'No'}\n")
                self.loop_results.insert(tk.END, f"• Unique MACs Detected: {efficiency_metrics.get('unique_macs', 0)}\n")
                
                # Show per-interface breakdown
                interface_results = efficiency_metrics.get('interface_results', [])
                if interface_results:
                    self.loop_results.insert(tk.END, f"\n📡 Per-Interface Results:\n")
                    for result in interface_results:
                        iface_name = result.get('interface', 'Unknown')
                        iface_packets = result.get('packets', 0)
                        iface_offenders = len(result.get('offenders', []))
                        iface_status = result.get('status', 'unknown')
                        status_icon = "⚠️" if iface_status in ["loop_detected", "suspicious"] else "✓"
                        self.loop_results.insert(tk.END, f"  {status_icon} {iface_name}: {iface_packets} packets, {iface_offenders} offenders\n")

            # Show detailed stats
            if stats:
                self.loop_results.insert(tk.END, f"\n📊 Detailed Statistics:\n")
                for mac, info in stats.items():
                    ips = ", ".join(info.get("ips", [])) if info.get("ips") else "Unknown"
                    self.loop_results.insert(tk.END, f"• {mac}:\n")
                    self.loop_results.insert(tk.END, f"  - IPs: {ips}\n")
                    self.loop_results.insert(tk.END, f"  - Total packets: {info.get('count', 0)}\n")
                    self.loop_results.insert(tk.END, f"  - ARP packets: {info.get('arp_count', 0)}\n")
                    self.loop_results.insert(tk.END, f"  - Broadcast packets: {info.get('broadcast_count', 0)}\n")
                    # Handle severity as dict or number
                    sev_detail = info.get('severity', 0)
                    if isinstance(sev_detail, dict):
                        sev_detail = sev_detail.get('total', 0)
                    self.loop_results.insert(tk.END, f"  - Severity: {sev_detail:.2f}\n")
                    
                    # LOOP DETECTION UPDATE: Show loop details in stats
                    if info.get('loop_on_single_router', False):
                        self.loop_results.insert(tk.END, f"  - ⚠️ Loop Type: Single-Router Cable Loop\n")
                        self.loop_results.insert(tk.END, f"  - Reason: {info.get('loop_reason', 'Unknown')}\n")
                        self.loop_results.insert(tk.END, f"  - Action: {info.get('suggested_action', 'Investigate')}\n")
                    self.loop_results.insert(tk.END, f"  - IPs: {ips}\n\n")

        self.loop_results.config(state="disabled")

    def _finish_loop_scan(self, count, offenders, stats=None, error=None):
        """Legacy method for backward compatibility."""
        # Stop spinner
        self._spinner_running = False
        self.spinner_lbl.config(text="")

        self.loop_results.config(state="normal")
        self.loop_results.delete("1.0", tk.END)

        if error:
            self.loop_status_lbl.config(text="❌ Error during scan", bootstyle="danger")
            self.loop_results.insert(tk.END, f"Error: {error}\n")
        elif offenders:
            flagged = False
            for mac in offenders:
                info = stats.get(mac, {})
                ips = ", ".join(info.get("ips", [])) if info.get("ips") else "Unknown"
                hosts = ", ".join(info.get("hosts", [])) if info.get("hosts") else "Unknown"

                # Only consider MACs with repeated identical packets above threshold
                repeated = [sig for sig, cnt in info.get("fingerprints", {}).items() if cnt > 30]

                if repeated:
                    flagged = True
                    self.loop_results.insert(
                        tk.END,
                        f"⚠ Loop suspected from {mac} → {ips} ({hosts}) "
                        f"[Repeated {len(repeated)} identical frames]\n"
                    )

                    # Detailed breakdown
                    self.loop_results.insert(
                        tk.END,
                        f"   - ARP: {info.get('arp_count', 0)} packets\n"
                        f"   - IP Broadcast: {info.get('ip_count', 0)} packets\n"
                        f"   - Other Broadcasts: {info.get('other_count', 0)} packets\n\n"
                    )

            if flagged:
                self.loop_status_lbl.config(text="⚠ Loops detected!", bootstyle="danger")
            else:
                # Normal background traffic; do not flag
                self.loop_status_lbl.config(text="✔ No loop detected", bootstyle="success")
                self.loop_results.insert(tk.END, "✔ Network is clean.\n")

        elif count and count > 100:
            # Catch only extreme traffic spikes
            self.loop_status_lbl.config(text="⚠ Broadcast storm!", bootstyle="danger")
            self.loop_results.insert(tk.END, f"⚠ High broadcast traffic ({count} packets)\n")
        else:
            self.loop_status_lbl.config(text="✔ No loop detected", bootstyle="success")
            self.loop_results.insert(tk.END, "✔ Network is clean.\n")

        # Show overall stats if available
        if stats:
            self.loop_results.insert(tk.END, "\n📊 Stats (packets per MAC/IP):\n")
            total_arp = total_ip = total_other = 0

            for mac, info in stats.items():
                ip_list = ", ".join(info.get("ips", [])) if info.get("ips") else "Unknown"
                hosts = ", ".join(info.get("hosts", [])) if info.get("hosts") else "Unknown"

                self.loop_results.insert(
                    tk.END,
                    f"- {mac}: {info['count']} packets → {ip_list} ({hosts})\n"
                )

                total_arp += info.get("arp_count", 0)
                total_ip += info.get("ip_count", 0)
                total_other += info.get("other_count", 0)

            # Summary
            self.loop_results.insert(
                tk.END,
                f"\n📌 Network Summary:\n"
                f"   • Total Packets: {count}\n"
                f"   • ARP Broadcasts: {total_arp}\n"
                f"   • IP Broadcasts: {total_ip}\n"
                f"   • Other Broadcasts: {total_other}\n"
            )

        self.loop_results.config(state="disabled")

    def _show_detection_details_from_stats_tree(self):
        """Show detailed information from the stats tree (wrapper for _show_detection_details)."""
        selection = self.loop_detection_tree.selection()
        if not selection:
            return
        
        # Get the record ID from tags
        item = self.loop_detection_tree.item(selection[0])
        tags = item.get('tags', ())
        
        if not tags or tags[0] == 'None':
            messagebox.showwarning("No Details", "This record doesn't have detailed information available.")
            return
        
        try:
            record_id = int(tags[0])
            
            # Fetch and display details from in-memory history
            record = None
            for hist_record in self.loop_detection_history:
                if hist_record.get('id') == record_id:
                    record = hist_record
                    break
            
            if record:
                self._show_detection_details_modal(record)
            else:
                messagebox.showerror("Error", "Record not found in history!")
                
        except (ValueError, TypeError):
            messagebox.showwarning("No Details", "This record doesn't have a valid ID.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load details: {e}")
            print(f"Error loading details: {e}")

    def _refresh_loop_detection_history(self):
        """Refresh loop detection history from database."""
        try:
            from db import get_loop_detections_history, get_loop_detection_stats
            self.loop_detection_history = get_loop_detections_history(100)
            self.loop_detection_stats = get_loop_detection_stats()
            self._load_loop_detection_history_modal()
            self._update_loop_status_display_modal(None)
            safe_print("[SUCCESS] Loop detection history refreshed from database")
        except Exception as e:
            safe_print(f"[ERROR] Error refreshing history: {e}")

    def clear_loop_results(self):
        """Clear the loop detection results."""
        self.loop_results.config(state="normal")
        self.loop_results.delete("1.0", tk.END)
        self.loop_results.config(state="disabled")
        self.loop_status_lbl.config(text="⏳ Ready to scan...", bootstyle="default")
        self.spinner_lbl.config(text="")


    def show_clients(self):
        """Enhanced popup modal that shows discovered network clients with modern UI."""
        # Check if modal is already open using flag
        if self.client_modal_is_open:
            print("⚠️ Client modal already open - bringing to front")
            if self.client_modal and self.client_modal.winfo_exists():
                try:
                    self.client_modal.lift()
                    self.client_modal.focus_force()
                    self.client_modal.attributes('-topmost', True)
                    self.client_modal.after(100, lambda: self.client_modal.attributes('-topmost', False))
                except:
                    # Modal might have been destroyed, reset flag
                    self.client_modal_is_open = False
                    self.client_modal = None
                    safe_print("[WARNING] Modal was destroyed, resetting flag")
            return
        
        # Set flag immediately to prevent multiple openings
        safe_print("[SUCCESS] Opening new client modal")
        self.client_modal_is_open = True
        
        modal = tb.Toplevel(self.root)
        self.client_modal = modal  # Store reference
        modal.title("🌐 Network Clients Monitor")
        modal.resizable(True, True)
        modal.configure(bg='#f8f9fa')
        
        # Make it a proper modal window
        modal.transient(self.root)
        
        # Set size and center BEFORE grab_set to avoid positioning issues
        modal_width = 1100
        modal_height = 700
        screen_width = modal.winfo_screenwidth()
        screen_height = modal.winfo_screenheight()
        x = (screen_width - modal_width) // 2
        y = (screen_height - modal_height) // 2
        modal.geometry(f"{modal_width}x{modal_height}+{x}+{y}")
        
        # Grab set after positioning
        modal.grab_set()

        # Main container
        main_container = tb.Frame(modal, bootstyle="light")
        main_container.pack(fill="both", expand=True, padx=10, pady=10)

        # Header section (no top-right X close icon)
        header_frame = tb.Frame(main_container, bootstyle="info")
        header_frame.pack(fill="x", pady=(0, 10))

        # Title and stats
        title_frame = tb.Frame(header_frame)
        title_frame.pack(fill="x", padx=15, pady=15)

        tb.Label(title_frame, text="🌐 Network Clients Monitor", 
                 font=("Segoe UI", 16, "bold"), bootstyle="inverse-info").pack(side="left")

        # Stats frame
        stats_frame = tb.Frame(title_frame)
        stats_frame.pack(side="right", padx=(0, 10))

        self.client_stats_online = tb.Label(stats_frame, text="Online: 0", 
                                          font=("Segoe UI", 10, "bold"), bootstyle="success")
        self.client_stats_online.pack(side="left", padx=(0, 15))

        self.client_stats_total = tb.Label(stats_frame, text="Total: 0", 
                                         font=("Segoe UI", 10, "bold"), bootstyle="info")
        self.client_stats_total.pack(side="left", padx=(0, 15))

        # Control panel
        control_frame = tb.Frame(main_container)
        control_frame.pack(fill="x", pady=(0, 10))

        # Search and filter section
        search_frame = tb.Frame(control_frame)
        search_frame.pack(side="left", fill="x", expand=True)

        tb.Label(search_frame, text="🔍 Search:", font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 5))
        
        self.client_search_var = tb.StringVar()
        self.client_search_var.trace_add("write", lambda *_: self.filter_clients())
        search_entry = tb.Entry(search_frame, textvariable=self.client_search_var, width=30)
        search_entry.pack(side="left", padx=(0, 10))

        # Filter options
        tb.Label(search_frame, text="Filter:", font=("Segoe UI", 10, "bold")).pack(side="left", padx=(20, 5))
        
        self.client_filter_var = tb.StringVar(value="all")
        filter_combo = tb.Combobox(search_frame, textvariable=self.client_filter_var, 
                                 values=["All", "Online Only", "Offline Only"], 
                                 state="readonly", width=12)
        filter_combo.pack(side="left", padx=(0, 10))
        filter_combo.bind("<<ComboboxSelected>>", lambda e: self.filter_clients())

        # Control buttons
        btn_frame = tb.Frame(control_frame)
        btn_frame.pack(side="right")

        self.scan_btn = tb.Button(btn_frame, text="🔄 Scan Now", bootstyle="primary", 
                                command=self.start_client_scan, width=12)
        self.scan_btn.pack(side="left", padx=2)

        self.auto_refresh_btn = tb.Button(btn_frame, text="⏸️ Stop Auto", bootstyle="danger", 
                                        command=self.toggle_auto_refresh, width=12)
        self.auto_refresh_btn.pack(side="left", padx=2)

        self.export_btn = tb.Button(btn_frame, text="📊 Export", bootstyle="success", 
                                  command=self.export_clients, width=12)
        self.export_btn.pack(side="left", padx=2)

        # Main content area
        content_frame = tb.Frame(main_container)
        content_frame.pack(fill="both", expand=True)

        # Treeview with scrollbars
        tree_frame = tb.Frame(content_frame)
        tree_frame.pack(fill="both", expand=True)

        # Define columns
        cols = ("Status", "IP Address", "MAC Address", "Hostname", "Vendor", "Ping (ms)", "First Seen", "Last Seen")
        
        # Create Treeview
        self.client_tree = tb.Treeview(tree_frame, columns=cols, show="headings", 
                                     height=15, bootstyle="info")
        
        # Configure columns
        column_widths = [80, 120, 150, 200, 150, 80, 120, 120]
        for i, (col, width) in enumerate(zip(cols, column_widths)):
            self.client_tree.heading(col, text=col, command=lambda c=col: self.sort_clients_by_column(c))
            self.client_tree.column(col, width=width, anchor="center")

        # Scrollbars
        v_scrollbar = tb.Scrollbar(tree_frame, orient="vertical", command=self.client_tree.yview)
        h_scrollbar = tb.Scrollbar(tree_frame, orient="horizontal", command=self.client_tree.xview)
        self.client_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Pack treeview and scrollbars
        self.client_tree.pack(side="left", fill="both", expand=True)
        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")

        # Status bar
        status_frame = tb.Frame(main_container)
        status_frame.pack(fill="x", pady=(10, 0))

        self.client_status_label = tb.Label(status_frame, text="Ready to scan network...", 
                                          bootstyle="secondary", font=("Segoe UI", 9))
        self.client_status_label.pack(side="left")

        # Instructions label
        self.client_instructions = tb.Label(status_frame, text="💡 Click any row to view connection history | Double-click for details", 
                                          bootstyle="info", font=("Segoe UI", 8))
        self.client_instructions.pack(side="left", padx=(20, 0))

        self.client_last_update = tb.Label(status_frame, text="", 
                                         bootstyle="secondary", font=("Segoe UI", 9))
        self.client_last_update.pack(side="right")

        # Initialize variables
        self.client_data = []
        self.filtered_client_data = []
        self.auto_refresh_enabled = True
        self.auto_refresh_interval = 30000  # 30 seconds
        self.auto_refresh_job = None
        self.double_click_pending = False  # Flag to prevent single click on double click

        # Bind row click events
        self.client_tree.bind("<ButtonRelease-1>", self.on_client_row_click)
        self.client_tree.bind("<Double-Button-1>", self.on_client_row_double_click)

        # Context menu for right-click actions
        self.setup_client_context_menu()

        # Show modal immediately, then load data in background
        modal.update_idletasks()
        
        # Load existing clients from database first (lightweight)
        self.root.after(50, self.load_existing_clients)
        
        # Start initial scan and auto-refresh with slight delay for smooth opening
        self.root.after(200, self.start_client_scan)
        self.root.after(300, self.start_auto_refresh)

        # Handle window close with immediate response
        def close_immediately():
            # Set flag immediately
            self.client_modal_is_open = False
            self.auto_refresh_enabled = False
            # Cancel any pending jobs
            if hasattr(self, 'auto_refresh_job') and self.auto_refresh_job:
                try:
                    self.root.after_cancel(self.auto_refresh_job)
                except:
                    pass
            # Close modal
            self.close_client_modal(modal)
        
        modal.protocol("WM_DELETE_WINDOW", close_immediately)
        
        # Bind destroy event to reset flag as fallback
        def on_modal_destroy(event):
            if event.widget == modal:
                self.client_modal_is_open = False
                self.client_modal = None
                self.auto_refresh_enabled = False
                print("🗑️ Client modal destroyed, flag reset")
        modal.bind("<Destroy>", on_modal_destroy)
        
        # Bind ESC key for quick close
        modal.bind("<Escape>", lambda e: close_immediately())
        
        # Make modal responsive to focus
        modal.focus_force()

    def load_existing_clients(self):
        """Load existing clients from database - quick load for initial display."""
        # Check if modal is still open
        if not self.client_modal_is_open:
            return
        
        try:
            from db import get_network_clients, create_network_clients_table, create_connection_history_table
            
            # Create tables if they don't exist
            create_network_clients_table()
            create_connection_history_table()
            
            # Get existing clients (limited for faster load)
            existing_clients = get_network_clients(online_only=False, limit=500)
            
            self.client_data = []
            current_time = datetime.now()
            
            for client in existing_clients:
                first_seen = client.get('first_seen', current_time)
                last_seen = client.get('last_seen', current_time)
                
                # Convert to datetime if string
                if isinstance(first_seen, str):
                    first_seen = current_time
                if isinstance(last_seen, str):
                    last_seen = current_time
                
                client_info = {
                    "mac": client['mac_address'],
                    "ip": client.get('ip_address', 'Unknown'),
                    "hostname": client.get('hostname', 'Unknown'),
                    "vendor": client.get('vendor', 'Unknown'),
                    "ping": client.get('ping_latency_ms'),
                    "status": "🟢 Online" if client.get('is_online', False) else "🔴 Offline",
                    "first_seen": first_seen.strftime("%H:%M:%S") if hasattr(first_seen, 'strftime') else str(first_seen),
                    "last_seen": last_seen.strftime("%H:%M:%S") if hasattr(last_seen, 'strftime') else str(last_seen),
                    "is_online": client.get('is_online', False)
                }
                self.client_data.append(client_info)
            
            # Update display
            self.update_client_display()
            
        except Exception as e:
            safe_emoji_print(f"[ERROR] Error loading existing clients: {e}")

    def setup_client_context_menu(self):
        """Setup right-click context menu for client tree."""
        self.client_context_menu = tk.Menu(self.root, tearoff=0)
        self.client_context_menu.add_command(label="📊 Connection History (Click row)", command=self.show_connection_history)
        self.client_context_menu.add_command(label="🔍 View Details (Double-click)", command=self.view_client_details)
        self.client_context_menu.add_separator()
        self.client_context_menu.add_command(label="🏓 Ping Test", command=self.ping_client)
        self.client_context_menu.add_command(label="📝 Add Note", command=self.add_client_note)
        self.client_context_menu.add_separator()
        self.client_context_menu.add_command(label="🔄 Refresh Client", command=self.refresh_selected_client)
        self.client_context_menu.add_command(label="❌ Remove from List", command=self.remove_client)
        
        # Bind click events
        self.client_tree.bind("<Button-1>", self.on_client_row_click)  # Left click
        self.client_tree.bind("<Button-3>", self.show_client_context_menu)  # Right click
        self.client_tree.bind("<Double-1>", self.on_client_row_double_click)  # Double click

    def on_client_row_click(self, event):
        """Handle single click on client row - show connection history."""
        try:
            # Get the item that was clicked
            item = self.client_tree.identify_row(event.y)
            if item and not self.double_click_pending:
                # Select the item
                self.client_tree.selection_set(item)
                # Schedule connection history display with a small delay to prevent double-click conflicts
                self.root.after(150, self._delayed_show_connection_history)
        except Exception as e:
            print(f"Error handling client row click: {e}")

    def _delayed_show_connection_history(self):
        """Delayed connection history display to prevent double-click conflicts."""
        if not self.double_click_pending:
            # Check if modal is already open to prevent double-showing
            if hasattr(self, 'connection_history_modal') and self.connection_history_modal and self.connection_history_modal.winfo_exists():
                return
            self.show_connection_history()

    def on_client_row_double_click(self, event):
        """Handle double click on client row - show detailed client info."""
        try:
            # Set flag to prevent single click from executing
            self.double_click_pending = True
            # Reset flag after a short delay
            self.root.after(200, lambda: setattr(self, 'double_click_pending', False))
            
            # Get the item that was clicked
            item = self.client_tree.identify_row(event.y)
            if item:
                # Select the item
                self.client_tree.selection_set(item)
                # Show client details
                self.view_client_details()
        except Exception as e:
            print(f"Error handling client row double click: {e}")

    def show_client_context_menu(self, event):
        """Show context menu on right-click."""
        try:
            item = self.client_tree.selection()[0]
            self.client_context_menu.post(event.x_root, event.y_root)
        except IndexError:
            pass

    def start_client_scan(self):
        """Start scanning for network clients with cancellation support."""
        # Check if modal is still open
        if not self.client_modal_is_open:
            return
        
        try:
            if hasattr(self, 'scan_btn') and self.scan_btn.winfo_exists():
                self.scan_btn.config(state="disabled", text="🔄 Scanning...")
        except Exception:
            pass
        try:
            if hasattr(self, 'client_status_label') and self.client_status_label.winfo_exists():
                self.client_status_label.config(text="Scanning network for clients...", bootstyle="warning")
        except Exception:
            pass
        
        def scan_thread():
            try:
                # Check if modal is still open before starting heavy operations
                if not self.client_modal_is_open:
                    return
                from network_utils import scan_subnet, get_default_iface, ping_latency
                from db import (save_network_client, create_network_clients_table, create_connection_history_table, 
                              get_network_clients, update_client_offline_status, log_connection_event, get_connection_history)
                
                # Create tables if they don't exist
                create_network_clients_table()
                create_connection_history_table()
                
                # Get existing clients from database
                existing_clients = get_network_clients(online_only=False, limit=1000)
                existing_macs = {client['mac_address']: client for client in existing_clients}
                
                # Track previous online status
                previous_online_status = {mac: client.get('is_online', False) for mac, client in existing_macs.items()}
                
                # Mark all existing clients as offline first
                for client in existing_clients:
                    update_client_offline_status(client['mac_address'])
                
                iface = get_default_iface()
                
                # Check again before heavy scan operation
                if not self.client_modal_is_open:
                    return
                
                scanned_clients = scan_subnet(iface=iface, timeout=3)
                
                # Check if modal was closed during scan
                if not self.client_modal_is_open:
                    return
                
                # Process and save clients
                self.client_data = []
                current_time = datetime.now()
                
                for mac, info in scanned_clients.items():
                    # Check periodically if modal is still open
                    if not self.client_modal_is_open:
                        return
                    
                    # Get ping latency
                    ping_lat = None
                    if info.get("ip"):
                        ping_lat = ping_latency(info["ip"], timeout=1000)
                    
                    # Determine vendor (simplified)
                    vendor = self.get_vendor_from_mac(mac)
                    
                    # Determine if client is online
                    is_online = bool(info.get("ip"))
                    
                    # Check for connection state changes
                    was_online = previous_online_status.get(mac, False)
                    current_ip = info.get("ip")
                    previous_ip = existing_macs.get(mac, {}).get('ip_address')
                    
                    # Log connection events
                    if not was_online and is_online:
                        # Device connected
                        log_connection_event(
                            mac_address=mac,
                            event_type='CONNECT',
                            ip_address=current_ip,
                            ping_latency=ping_lat,
                            hostname=info.get("hostname", "Unknown"),
                            vendor=vendor
                        )
                    elif was_online and is_online and current_ip != previous_ip:
                        # IP address changed
                        log_connection_event(
                            mac_address=mac,
                            event_type='IP_CHANGE',
                            ip_address=current_ip,
                            previous_ip=previous_ip,
                            ping_latency=ping_lat,
                            hostname=info.get("hostname", "Unknown"),
                            vendor=vendor
                        )
                    
                    # Save to database
                    save_network_client(
                        mac_address=mac,
                        ip_address=info.get("ip"),
                        hostname=info.get("hostname", "Unknown"),
                        vendor=vendor,
                        ping_latency=ping_lat
                    )
                    
                    # Get first seen time from existing data or use current time
                    first_seen = existing_macs.get(mac, {}).get('first_seen', current_time)
                    if isinstance(first_seen, str):
                        first_seen = current_time
                    
                    # Add to display data
                    client_info = {
                        "mac": mac,
                        "ip": info.get("ip", "Unknown"),
                        "hostname": info.get("hostname", "Unknown"),
                        "vendor": vendor,
                        "ping": ping_lat,
                        "status": "🟢 Online" if is_online else "🔴 Offline",
                        "first_seen": first_seen.strftime("%H:%M:%S") if hasattr(first_seen, 'strftime') else first_seen,
                        "last_seen": current_time.strftime("%H:%M:%S"),
                        "is_online": is_online
                    }
                    self.client_data.append(client_info)
                
                # Add offline clients that weren't found in scan
                for mac, client in existing_macs.items():
                    if mac not in [c["mac"] for c in self.client_data]:
                        # Log disconnection event if device was previously online
                        if previous_online_status.get(mac, False):
                            # Calculate session duration
                            last_seen = client.get('last_seen', current_time)
                            if isinstance(last_seen, str):
                                last_seen = current_time
                            
                            session_duration = None
                            if hasattr(last_seen, 'timestamp') and hasattr(current_time, 'timestamp'):
                                session_duration = int((current_time.timestamp() - last_seen.timestamp()))
                            
                            log_connection_event(
                                mac_address=mac,
                                event_type='DISCONNECT',
                                ip_address=client.get('ip_address'),
                                ping_latency=None,
                                hostname=client.get('hostname', 'Unknown'),
                                vendor=client.get('vendor', 'Unknown'),
                                session_duration=session_duration
                            )
                        
                        first_seen = client.get('first_seen', current_time)
                        if isinstance(first_seen, str):
                            first_seen = current_time
                            
                        offline_client = {
                            "mac": mac,
                            "ip": client.get('ip_address', 'Unknown'),
                            "hostname": client.get('hostname', 'Unknown'),
                            "vendor": client.get('vendor', 'Unknown'),
                            "ping": None,
                            "status": "🔴 Offline",
                            "first_seen": first_seen.strftime("%H:%M:%S") if hasattr(first_seen, 'strftime') else first_seen,
                            "last_seen": client.get('last_seen', current_time).strftime("%H:%M:%S") if hasattr(client.get('last_seen', current_time), 'strftime') else str(client.get('last_seen', current_time)),
                            "is_online": False
                        }
                        self.client_data.append(offline_client)
                
                # Update UI in main thread
                self.root.after(0, self.update_client_display)
                
            except Exception as e:
                self.root.after(0, lambda e=e: self._safe_widget_config(
                    getattr(self, 'client_status_label', None),
                    text=f"Scan failed: {str(e)}", bootstyle="danger"))
            finally:
                self.root.after(0, lambda: self._safe_widget_config(
                    getattr(self, 'scan_btn', None), state="normal", text="🔄 Scan Now"))

        threading.Thread(target=scan_thread, daemon=True).start()

    def get_vendor_from_mac(self, mac):
        """Get vendor information from MAC address (simplified)."""
        # Common OUI prefixes
        oui_prefixes = {
            "00:50:56": "VMware",
            "08:00:27": "VirtualBox",
            "00:0c:29": "VMware",
            "00:1c:42": "Parallels",
            "00:15:5d": "Microsoft",
            "00:16:3e": "Xen",
            "52:54:00": "QEMU",
            "00:1b:21": "Intel",
            "00:1f:5b": "Apple",
            "00:23:12": "Apple",
            "00:25:00": "Apple",
            "00:26:bb": "Apple",
            "00:26:4a": "Apple",
            "00:26:b0": "Apple",
            "00:26:08": "Apple",
            "00:25:4b": "Apple",
            "00:25:bc": "Apple",
            "00:25:ca": "Apple",
            "00:25:00": "Apple",
            "00:23:12": "Apple",
            "00:1f:5b": "Apple",
            "00:1b:21": "Apple",
            "00:16:3e": "Xen",
            "52:54:00": "QEMU",
            "00:15:5d": "Microsoft",
            "00:1c:42": "Parallels",
            "00:0c:29": "VMware",
            "08:00:27": "VirtualBox",
            "00:50:56": "VMware"
        }
        
        mac_upper = mac.upper()
        for prefix, vendor in oui_prefixes.items():
            if mac_upper.startswith(prefix):
                return vendor
        return "Unknown"

    def _safe_widget_config(self, widget, **kwargs):
        """Safely configure a widget if it still exists."""
        try:
            if widget is not None and widget.winfo_exists():
                widget.config(**kwargs)
        except Exception:
            pass

    def update_client_display(self):
        """Update the client display with current data - optimized for speed."""
        # Quick exit if modal closed
        if not self.client_modal_is_open:
            return
        
        tree = getattr(self, 'client_tree', None)
        try:
            if not tree or not tree.winfo_exists():
                return
        except Exception:
            return
        
        # Clear existing items safely and quickly
        try:
            # Delete all items at once (faster than loop)
            children = self.client_tree.get_children()
            if children:
                self.client_tree.delete(*children)
        except Exception:
            return
        
        # Apply filters
        self.filtered_client_data = self.client_data.copy()
        
        # Apply search filter
        search_term = self.client_search_var.get().lower()
        if search_term:
            self.filtered_client_data = [
                client for client in self.filtered_client_data
                if (search_term in client["ip"].lower() or 
                    search_term in client["mac"].lower() or 
                    search_term in client["hostname"].lower() or
                    search_term in client["vendor"].lower())
            ]
        
        # Apply status filter
        filter_value = self.client_filter_var.get()
        if filter_value == "Online Only":
            self.filtered_client_data = [c for c in self.filtered_client_data if c.get("is_online", False)]
        elif filter_value == "Offline Only":
            self.filtered_client_data = [c for c in self.filtered_client_data if not c.get("is_online", True)]
        
        # Sort by online status first, then by last seen
        self.filtered_client_data.sort(key=lambda x: (not x.get("is_online", False), x.get("last_seen", "")), reverse=True)
        
        # Insert filtered data
        for client in self.filtered_client_data:
            ping_display = f"{client['ping']:.0f}" if client['ping'] else "N/A"
            self.client_tree.insert("", "end", values=(
                client["status"],
                client["ip"],
                client["mac"],
                client["hostname"],
                client["vendor"],
                ping_display,
                client["first_seen"],
                client["last_seen"]
            ))
        
        # Update statistics
        online_count = len([c for c in self.client_data if c.get("is_online", False)])
        offline_count = len([c for c in self.client_data if not c.get("is_online", True)])
        total_count = len(self.client_data)
        
        self._safe_widget_config(getattr(self, 'client_stats_online', None), text=f"Online: {online_count}")
        self._safe_widget_config(getattr(self, 'client_stats_total', None), text=f"Total: {total_count}")
        
        # Update status with more detailed information
        filtered_online = len([c for c in self.filtered_client_data if c.get("is_online", False)])
        filtered_offline = len([c for c in self.filtered_client_data if not c.get("is_online", True)])
        
        status_text = f"Showing {len(self.filtered_client_data)} clients"
        if filter_value == "Online Only":
            status_text += f" ({filtered_online} online)"
        elif filter_value == "Offline Only":
            status_text += f" ({filtered_offline} offline)"
        else:
            status_text += f" ({filtered_online} online, {filtered_offline} offline)"
        
        self._safe_widget_config(getattr(self, 'client_status_label', None), text=status_text, bootstyle="success")
        self._safe_widget_config(getattr(self, 'client_last_update', None), text=f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

    def filter_clients(self):
        """Filter clients based on search and filter criteria."""
        self.update_client_display()

    def sort_clients_by_column(self, col):
        """Sort clients by the specified column."""
        # Simple sorting implementation
        reverse = False
        if hasattr(self, '_last_sort_col') and self._last_sort_col == col:
            reverse = True
        self._last_sort_col = col
        
        # Sort the data
        if col == "Status":
            self.filtered_client_data.sort(key=lambda x: x["status"], reverse=reverse)
        elif col == "IP Address":
            self.filtered_client_data.sort(key=lambda x: x["ip"], reverse=reverse)
        elif col == "MAC Address":
            self.filtered_client_data.sort(key=lambda x: x["mac"], reverse=reverse)
        elif col == "Hostname":
            self.filtered_client_data.sort(key=lambda x: x["hostname"], reverse=reverse)
        elif col == "Vendor":
            self.filtered_client_data.sort(key=lambda x: x["vendor"], reverse=reverse)
        elif col == "Ping (ms)":
            self.filtered_client_data.sort(key=lambda x: x["ping"] or 0, reverse=reverse)
        
        # Refresh display
        self.update_client_display()

    def toggle_auto_refresh(self):
        """Toggle automatic refresh functionality."""
        if self.auto_refresh_enabled:
            self.stop_auto_refresh()
        else:
            self.start_auto_refresh()

    def start_auto_refresh(self):
        """Start automatic refresh."""
        self.auto_refresh_enabled = True
        self.auto_refresh_btn.config(text="⏸️ Stop Auto", bootstyle="danger")
        self.schedule_auto_refresh()

    def stop_auto_refresh(self):
        """Stop automatic refresh."""
        self.auto_refresh_enabled = False
        try:
            if hasattr(self, 'auto_refresh_btn') and self.auto_refresh_btn.winfo_exists():
                self.auto_refresh_btn.config(text="▶️ Auto Refresh", bootstyle="warning")
        except Exception:
            pass
        if self.auto_refresh_job:
            self.root.after_cancel(self.auto_refresh_job)
            self.auto_refresh_job = None

    def schedule_auto_refresh(self):
        """Schedule the next auto refresh."""
        # Only schedule if modal is still open and auto-refresh is enabled
        if self.auto_refresh_enabled and self.client_modal_is_open:
            self.auto_refresh_job = self.root.after(self.auto_refresh_interval, self.auto_refresh_clients)

    def auto_refresh_clients(self):
        """Perform automatic client refresh."""
        # Check if modal is still open
        if not self.client_modal_is_open or not hasattr(self, 'client_modal'):
            self.stop_auto_refresh()
            return
        
        if self.auto_refresh_enabled:
            self.start_client_scan()
            self.schedule_auto_refresh()

    def export_clients(self):
        """Export client data to CSV - uses current filter state from visible data."""
        try:
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Export Network Clients"
            )
            
            if filename:
                import csv
                
                # Use client_data (full dataset) or filtered_client_data based on current UI state
                # Reapply filters to ensure we export what's currently visible
                export_data = []
                search_term = self.client_search_var.get().lower() if hasattr(self, 'client_search_var') else ""
                filter_value = self.client_filter_var.get() if hasattr(self, 'client_filter_var') else "All Clients"
                
                # Start with full dataset
                data_to_export = self.client_data.copy() if hasattr(self, 'client_data') else []
                
                # Apply search filter
                if search_term:
                    data_to_export = [
                        client for client in data_to_export
                        if (search_term in client["ip"].lower() or 
                            search_term in client["mac"].lower() or 
                            search_term in client["hostname"].lower() or
                            search_term in client["vendor"].lower())
                    ]
                
                # Apply status filter
                if filter_value == "Online Only":
                    data_to_export = [c for c in data_to_export if c.get("is_online", False)]
                elif filter_value == "Offline Only":
                    data_to_export = [c for c in data_to_export if not c.get("is_online", True)]
                
                # Write to CSV
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(["Status", "IP Address", "MAC Address", "Hostname", "Vendor", "Ping (ms)", "First Seen", "Last Seen"])
                    
                    for client in data_to_export:
                        ping_display = f"{client['ping']:.0f}" if client['ping'] else "N/A"
                        writer.writerow([
                            client["status"],
                            client["ip"],
                            client["mac"],
                            client["hostname"],
                            client["vendor"],
                            ping_display,
                            client["first_seen"],
                            client["last_seen"]
                        ])
                
                messagebox.showinfo("Export Complete", f"Client data exported to {filename}\n{len(data_to_export)} clients exported.")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export data: {str(e)}")

    def view_client_details(self):
        """View detailed information about selected client - optimized for responsiveness."""
        try:
            selection = self.client_tree.selection()[0]
            item = self.client_tree.item(selection)
            values = item['values']
            
            # Create details window
            details_window = tb.Toplevel(self.root)
            details_window.title("Client Details")
            details_window.resizable(False, False)
            details_window.transient(self.root)
            
            # Set size and center BEFORE showing
            window_width = 500
            window_height = 400
            screen_width = details_window.winfo_screenwidth()
            screen_height = details_window.winfo_screenheight()
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            details_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
            
            # Flag for instant close response
            details_window.closing = False
            
            def close_details_modal():
                """Instantly close the details modal with immediate response."""
                if not hasattr(details_window, 'closing') or details_window.closing:
                    return
                
                # Set flag immediately for instant UI response
                details_window.closing = True
                
                # Destroy immediately - no complex cleanup needed
                try:
                    details_window.destroy()
                except:
                    pass
            
            # Bind ESC key for quick close
            details_window.bind('<Escape>', lambda e: close_details_modal())
            
            # Handle window close button (X)
            details_window.protocol("WM_DELETE_WINDOW", close_details_modal)
            
            # Details content
            frame = tb.Frame(details_window, padding=20)
            frame.pack(fill="both", expand=True)
            
            tb.Label(frame, text="Client Details", font=("Segoe UI", 16, "bold"), 
                    bootstyle="info").pack(pady=(0, 20))
            
            details = [
                ("Status:", values[0]),
                ("IP Address:", values[1]),
                ("MAC Address:", values[2]),
                ("Hostname:", values[3]),
                ("Vendor:", values[4]),
                ("Ping Latency:", values[5]),
                ("First Seen:", values[6]),
                ("Last Seen:", values[7])
            ]
            
            for label, value in details:
                row_frame = tb.Frame(frame)
                row_frame.pack(fill="x", pady=5)
                
                tb.Label(row_frame, text=label, font=("Segoe UI", 10, "bold"), 
                        width=15, anchor="w").pack(side="left")
                tb.Label(row_frame, text=value, font=("Segoe UI", 10)).pack(side="left", padx=(10, 0))
            
            # Close button with instant response
            close_btn = tb.Button(frame, text="Close", bootstyle="secondary", 
                     command=close_details_modal)
            close_btn.pack(pady=(20, 0))
            
            # Visual feedback on hover
            close_btn.bind('<Enter>', lambda e: close_btn.config(cursor='hand2'))
            close_btn.bind('<Leave>', lambda e: close_btn.config(cursor=''))
            
        except IndexError:
            messagebox.showwarning("No Selection", "Please select a client to view details.")

    def ping_client(self):
        """Ping the selected client."""
        try:
            selection = self.client_tree.selection()[0]
            item = self.client_tree.item(selection)
            values = item['values']
            ip = values[1]
            
            if ip == "Unknown":
                messagebox.showwarning("Cannot Ping", "IP address is unknown for this client.")
                return
            
            self.client_status_label.config(text=f"Pinging {ip}...", bootstyle="warning")
            
            def ping_thread():
                from network_utils import ping_latency
                latency = ping_latency(ip, timeout=2000)
                
                def update_result():
                    if latency:
                        messagebox.showinfo("Ping Result", f"Ping to {ip}: {latency:.2f} ms")
                        self.client_status_label.config(text=f"Ping to {ip}: {latency:.2f} ms", bootstyle="success")
                    else:
                        messagebox.showerror("Ping Failed", f"Could not ping {ip}")
                        self.client_status_label.config(text=f"Ping to {ip} failed", bootstyle="danger")
                
                self.root.after(0, update_result)
            
            threading.Thread(target=ping_thread, daemon=True).start()
            
        except IndexError:
            messagebox.showwarning("No Selection", "Please select a client to ping.")

    def add_client_note(self):
        """Add a note to the selected client."""
        try:
            selection = self.client_tree.selection()[0]
            item = self.client_tree.item(selection)
            values = item['values']
            mac = values[2]
            
            note = tk.simpledialog.askstring("Add Note", f"Enter note for {values[3]} ({mac}):")
            if note:
                # Here you would save the note to the database
                messagebox.showinfo("Note Added", f"Note added for {values[3]}")
                
        except IndexError:
            messagebox.showwarning("No Selection", "Please select a client to add a note.")

    def refresh_selected_client(self):
        """Refresh information for the selected client."""
        try:
            selection = self.client_tree.selection()[0]
            item = self.client_tree.item(selection)
            values = item['values']
            ip = values[1]
            
            if ip == "Unknown":
                messagebox.showwarning("Cannot Refresh", "IP address is unknown for this client.")
                return
            
            self.client_status_label.config(text=f"Refreshing {ip}...", bootstyle="warning")
            
            def refresh_thread():
                from network_utils import ping_latency
                import socket
                
                # Ping test
                latency = ping_latency(ip, timeout=1000)
                
                # Hostname lookup
                try:
                    hostname = socket.gethostbyaddr(ip)[0]
                except:
                    hostname = "Unknown"
                
                def update_result():
                    # Update the client data
                    for client in self.client_data:
                        if client["ip"] == ip:
                            client["ping"] = latency
                            client["hostname"] = hostname
                            client["last_seen"] = datetime.now().strftime("%H:%M:%S")
                            break
                    
                    self.update_client_display()
                    self.client_status_label.config(text=f"Refreshed {ip}", bootstyle="success")
                
                self.root.after(0, update_result)
            
            threading.Thread(target=refresh_thread, daemon=True).start()
            
        except IndexError:
            messagebox.showwarning("No Selection", "Please select a client to refresh.")

    def remove_client(self):
        """Remove the selected client from the list."""
        try:
            selection = self.client_tree.selection()[0]
            item = self.client_tree.item(selection)
            values = item['values']
            mac = values[2]
            
            if messagebox.askyesno("Remove Client", f"Remove {values[3]} ({mac}) from the list?"):
                # Remove from data
                self.client_data = [c for c in self.client_data if c["mac"] != mac]
                self.update_client_display()
                self.client_status_label.config(text=f"Removed {values[3]}", bootstyle="info")
                
        except IndexError:
            messagebox.showwarning("No Selection", "Please select a client to remove.")

    def show_connection_history(self):
        """Show connection history for the selected client."""
        try:
            # Get selected item
            selected_item = self.client_tree.selection()[0]
            values = self.client_tree.item(selected_item, "values")
            mac_address = values[2]  # MAC address is in column 2
            hostname = values[3]     # Hostname is in column 3
            
            from db import get_connection_history, get_client_connection_stats
            
            # Get connection history
            history = get_connection_history(mac_address=mac_address, limit=50)
            stats = get_client_connection_stats(mac_address)
            
            # Prevent double-showing if already open
            if hasattr(self, 'connection_history_modal') and self.connection_history_modal and self.connection_history_modal.winfo_exists():
                self.connection_history_modal.lift()
                self.connection_history_modal.focus_force()
                return
            
            # Create history modal - transient to client modal for proper interaction
            history_modal = tb.Toplevel(self.client_modal if hasattr(self, 'client_modal') else self.root)
            history_modal.title(f"📊 Connection History - {hostname}")
            history_modal.resizable(True, True)
            history_modal.configure(bg='#f8f9fa')
            
            # Make it transient to client modal so it works properly
            if hasattr(self, 'client_modal') and self.client_modal:
                history_modal.transient(self.client_modal)
            
            # Set size and center BEFORE showing
            window_width = 900
            window_height = 600
            screen_width = history_modal.winfo_screenwidth()
            screen_height = history_modal.winfo_screenheight()
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            history_modal.geometry(f"{window_width}x{window_height}+{x}+{y}")
            
            # Grab focus and bring to front immediately
            history_modal.grab_set()  # Take control from parent
            history_modal.lift()
            history_modal.focus_force()
            
            # Store reference to prevent double-showing
            self.connection_history_modal = history_modal
            
            # Flag for instant close response
            history_modal.closing = False
            history_modal.history_tree = None  # Will be set later
            
            def close_history_modal():
                """Instantly close the history modal with immediate response."""
                if not hasattr(history_modal, 'closing') or history_modal.closing:
                    return
                
                # Set flag immediately for instant UI response
                history_modal.closing = True
                
                # Release grab before closing
                try:
                    history_modal.grab_release()
                except:
                    pass
                
                # Return grab to client modal if it exists
                try:
                    if hasattr(self, 'client_modal') and self.client_modal and self.client_modal.winfo_exists():
                        self.client_modal.grab_set()
                except:
                    pass
                
                # Clear tree to prevent any lingering operations
                try:
                    if history_modal.history_tree and hasattr(history_modal.history_tree, 'get_children'):
                        for item in history_modal.history_tree.get_children():
                            history_modal.history_tree.delete(item)
                except:
                    pass
                
                # Clear reference
                if hasattr(self, 'connection_history_modal'):
                    self.connection_history_modal = None
                
                # Destroy immediately
                try:
                    history_modal.destroy()
                except:
                    pass
            
            # Bind ESC key for quick close
            history_modal.bind('<Escape>', lambda e: close_history_modal())
            
            # Handle window close button (X)
            history_modal.protocol("WM_DELETE_WINDOW", close_history_modal)
            
            # Main container
            main_container = tb.Frame(history_modal, bootstyle="light")
            main_container.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Header
            header_frame = tb.Frame(main_container, bootstyle="info")
            header_frame.pack(fill="x", pady=(0, 10))
            
            title_frame = tb.Frame(header_frame)
            title_frame.pack(fill="x", padx=15, pady=15)
            
            tb.Label(title_frame, text=f"📊 Connection History - {hostname}", 
                    font=("Segoe UI", 14, "bold"), bootstyle="inverse-info").pack(side="left")
            
            # Removed top-right X close icon per requirements
            
            # Stats frame
            stats_frame = tb.Frame(main_container)
            stats_frame.pack(fill="x", pady=(0, 10))
            
            # Connection statistics
            stats_info = [
                f"Total Connections: {stats.get('total_connections', 0)}",
                f"Recent Activity (24h): {stats.get('recent_activity_24h', 0)}",
                f"First Connection: {stats.get('first_connection', 'Unknown')}",
                f"Last Connection: {stats.get('last_connection', 'Unknown')}"
            ]
            
            for i, stat in enumerate(stats_info):
                tb.Label(stats_frame, text=stat, font=("Segoe UI", 10, "bold"), 
                        bootstyle="success").grid(row=0, column=i, padx=10, pady=5)
            
            # History table
            tree_frame = tb.Frame(main_container)
            tree_frame.pack(fill="both", expand=True)
            
            # Define columns
            cols = ("Event", "IP Address", "Previous IP", "Ping (ms)", "Timestamp", "Session Duration")
            
            # Create Treeview
            history_tree = tb.Treeview(tree_frame, columns=cols, show="headings", 
                                     height=15, bootstyle="info")
            
            # Store reference for cleanup
            history_modal.history_tree = history_tree
            
            # Configure columns
            column_widths = [100, 120, 120, 80, 150, 120]
            for i, (col, width) in enumerate(zip(cols, column_widths)):
                history_tree.heading(col, text=col)
                history_tree.column(col, width=width, anchor="center")
            
            # Scrollbars
            v_scrollbar = tb.Scrollbar(tree_frame, orient="vertical", command=history_tree.yview)
            h_scrollbar = tb.Scrollbar(tree_frame, orient="horizontal", command=history_tree.xview)
            history_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
            
            # Grid layout for proper scrollbar positioning
            history_tree.grid(row=0, column=0, sticky="nsew")
            v_scrollbar.grid(row=0, column=1, sticky="ns")
            h_scrollbar.grid(row=1, column=0, sticky="ew")
            
            # Configure grid weights
            tree_frame.grid_rowconfigure(0, weight=1)
            tree_frame.grid_columnconfigure(0, weight=1)
            
            # Bind mouse wheel scrolling for smooth scrolling
            def on_mousewheel_vertical(event):
                history_tree.yview_scroll(int(-1 * (event.delta / 120)), "units")
                return "break"
            
            def on_mousewheel_horizontal(event):
                history_tree.xview_scroll(int(-1 * (event.delta / 120)), "units")
                return "break"
            
            # Bind vertical scroll (normal mouse wheel)
            history_tree.bind("<MouseWheel>", on_mousewheel_vertical)
            # Bind horizontal scroll (Shift + mouse wheel)
            history_tree.bind("<Shift-MouseWheel>", on_mousewheel_horizontal)
            
            # Prevent modal from scrolling page behind
            history_modal.bind("<MouseWheel>", lambda e: "break")
            history_modal.bind("<Shift-MouseWheel>", lambda e: "break")
            
            # Insert history data
            for event in history:
                event_type = event['event_type']
                if event_type == 'CONNECT':
                    event_display = "🟢 Connected"
                elif event_type == 'DISCONNECT':
                    event_display = "🔴 Disconnected"
                elif event_type == 'IP_CHANGE':
                    event_display = "🔄 IP Changed"
                else:
                    event_display = event_type
                
                ping_display = f"{event['ping_latency_ms']}" if event['ping_latency_ms'] else "N/A"
                session_duration = event.get('session_duration_seconds')
                if session_duration:
                    hours = session_duration // 3600
                    minutes = (session_duration % 3600) // 60
                    duration_display = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                else:
                    duration_display = "N/A"
                
                history_tree.insert("", "end", values=(
                    event_display,
                    event['ip_address'] or "N/A",
                    event['previous_ip'] or "N/A",
                    ping_display,
                    event['event_timestamp'].strftime("%Y-%m-%d %H:%M:%S") if event['event_timestamp'] else "N/A",
                    duration_display
                ))
            
            # Status bar
            status_frame = tb.Frame(main_container)
            status_frame.pack(fill="x", pady=(10, 0))
            
            tb.Label(status_frame, text=f"Showing {len(history)} connection events", 
                    bootstyle="secondary", font=("Segoe UI", 9)).pack(side="left")
            
        except IndexError:
            messagebox.showwarning("No Selection", "Please select a client to view connection history.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load connection history: {str(e)}")

    def close_client_modal(self, modal=None):
        """Handle closing the client modal with immediate response and proper cleanup."""
        # Set flags immediately for instant response
        self.client_modal_is_open = False
        self.auto_refresh_enabled = False
        
        # Cancel auto-refresh job immediately
        if hasattr(self, 'auto_refresh_job') and self.auto_refresh_job:
            try:
                self.root.after_cancel(self.auto_refresh_job)
                self.auto_refresh_job = None
            except:
                pass
        
        # Use stored modal reference if no modal parameter provided
        if modal is None:
            modal = self.client_modal
        
        # Release grab and destroy modal immediately
        if modal:
            try:
                if modal.winfo_exists():
                    modal.grab_release()
                    modal.destroy()
            except:
                pass
        
        # Clear references
        self.client_modal = None
        
        # Clear data in background to not block UI
        self.root.after(100, self._cleanup_client_data)
        
        safe_print("[SUCCESS] Client modal closed instantly")
    
    def _cleanup_client_data(self):
        """Background cleanup of client data."""
        try:
            self.client_data = []
            self.filtered_client_data = []
        except:
            pass

    #auto update 
    def schedule_update(self):
        self.update_statistics()
        self.update_notification_count()  # Update notification count
        # Store the after() ID so we can cancel it later
        self.update_task = self.root.after(5000, self.schedule_update)  # 5 seconds



    def start_loop_detection(self):
        """Start automatic loop detection."""
        if not self.loop_detection_running and self.loop_detection_enabled:
            self.loop_detection_running = True
            self.loop_detection_thread = threading.Thread(target=self._run_loop_detection, daemon=True)
            self.loop_detection_thread.start()
            safe_print("[INFO] Automatic loop detection started")

    def stop_loop_detection(self):
        """Stop automatic loop detection."""
        self.loop_detection_running = False
        if self.loop_detection_thread:
            self.loop_detection_thread = None
        safe_print("⏹️ Automatic loop detection stopped")

    def _run_loop_detection(self):
        """Background loop detection thread using the same working method as manual detection."""
        while self.loop_detection_running and self.app_running:
            try:
                # FIX: Use the same working method as manual loop detection
                from network_utils import detect_loops, get_default_iface
                
                # Get the primary network interface (same as manual detection)
                iface = get_default_iface()
                safe_emoji_print(f"[INFO] Automatic loop detection scanning interface: {iface}")
                
                # Run detection on primary interface with advanced engine (same as manual)
                total_packets, offenders, stats, advanced_metrics = detect_loops(
                    timeout=5,  # 5 seconds for thorough scan
                    threshold=100,  # Threshold for severity
                    iface=iface,  # Use same interface as manual detection
                    enable_advanced=True  # Use advanced detection like manual
                )
                
                # Extract status from advanced detection (same logic as manual)
                max_severity = 0
                for mac, info in stats.items():
                    if isinstance(info.get("severity"), dict):
                        severity_value = info["severity"]["total"]
                    else:
                        severity_value = info.get("severity", 0)
                    max_severity = max(max_severity, severity_value)
                
                # Determine status (same logic as manual)
                if advanced_metrics.get("arp_storm_detected") or advanced_metrics.get("broadcast_flood_detected"):
                    status = "loop_detected"
                elif max_severity > 250:
                    status = "loop_detected"
                elif max_severity > 100:
                    status = "suspicious"
                else:
                    status = "clean"
                
                severity_score = max_severity
                
                # Build efficiency metrics compatible with dashboard
                efficiency_metrics = {
                    "detection_method": "ADVANCED",
                    "interfaces_scanned": [iface],
                    "total_interfaces": 1,
                    "detection_duration": advanced_metrics.get("duration", 5),
                    "packets_per_second": total_packets / max(1, advanced_metrics.get("duration", 5)),
                    "unique_macs": advanced_metrics.get("total_unique_macs", 0),
                    "arp_storm_detected": advanced_metrics.get("arp_storm_detected", False),
                    "broadcast_flood_detected": advanced_metrics.get("broadcast_flood_detected", False),
                    "storm_rate": advanced_metrics.get("storm_rate", 0),
                    "early_exit": advanced_metrics.get("early_exit", False),
                    "early_exit_reason": advanced_metrics.get("early_exit_reason", None),
                    "actual_duration": advanced_metrics.get("duration", 5),
                    "interface_results": [{
                        "interface": iface,
                        "packets": total_packets,
                        "offenders": offenders,
                        "status": status
                    }]
                }
                
                interface_str = iface
                
                # Enhanced logging
                safe_emoji_print(f"[STATS] Automatic Detection: packets={total_packets}, offenders={len(offenders)}, severity={severity_score:.1f}, status={status}")
                if offenders:
                    safe_emoji_print(f"   Offending MACs: {', '.join(offenders[:3])}")
                
                # Save to database with efficiency metrics
                from db import save_loop_detection
                detection_id = save_loop_detection(
                    total_packets=total_packets,
                    offenders=offenders,
                    stats=stats,
                    status=status,
                    severity_score=severity_score,
                    interface=interface_str,
                    duration=efficiency_metrics.get('detection_duration', 5),
                    efficiency_metrics=efficiency_metrics
                )
                
                # Send notification for loop detection
                if status in ["loop_detected", "suspicious"]:
                    notify_loop_detected(severity_score, offenders, interface_str)
                    # Update notification count in main thread
                    self.root.after(0, self.update_notification_count)
                    
                    # Show popup alert for loop detected (more visible than notification badge)
                    if status == "loop_detected":
                        self.root.after(0, lambda: messagebox.showwarning(
                            "⚠️ Network Loop Detected!",
                            f"A network loop has been detected!\n\n"
                            f"Severity Score: {severity_score:.1f}\n"
                            f"Offending Devices: {len(offenders)}\n"
                            f"Interface: {interface_str}\n\n"
                            f"Click 'Loop Test' button to view details."
                        ))
                    elif status == "suspicious":
                        # Less intrusive notification for suspicious activity
                        print(f"🟡 SUSPICIOUS ACTIVITY: Severity {severity_score:.1f}")
                
                # Reload stats and history from database
                from db import get_loop_detection_stats, get_loop_detections_history
                self.loop_detection_stats = get_loop_detection_stats()
                self.loop_detection_history = get_loop_detections_history(100)
                
                # Print status
                if status == "loop_detected":
                    safe_emoji_print(f"[WARNING] LOOP DETECTED! Severity: {severity_score:.2f}, Offenders: {len(offenders)}")
                elif status == "suspicious":
                    safe_emoji_print(f"[INFO] Suspicious activity detected. Severity: {severity_score:.2f}")
                else:
                    safe_emoji_print(f"[SUCCESS] Network clean. Severity: {severity_score:.2f}")
                
                # Create detection record for UI
                detection_record = {
                    "timestamp": datetime.now().isoformat(),
                    "total_packets": total_packets,
                    "offenders": offenders,
                    "stats": stats,
                    "status": status,
                    "severity_score": severity_score,
                    "duration": 5,
                    "efficiency_metrics": efficiency_metrics
                }
                
                # Update UI if loop detection tab is visible
                self.root.after(0, lambda: self._update_loop_detection_ui(detection_record))
                
                # Refresh history table if modal is open
                try:
                    if hasattr(self, 'loop_detection_tree') and self.loop_detection_tree.winfo_exists():
                        self.root.after(0, self._load_loop_detection_history_modal)
                except:
                    pass  # Modal might not be open
                
            except Exception as e:
                import traceback
                safe_emoji_print(f"[ERROR] Automatic loop detection error: {e}")
                traceback.print_exc()
            
            # Wait for next interval (ensure this always happens)
            if self.loop_detection_running and self.app_running:
                safe_emoji_print(f"[INFO] Waiting {self.loop_detection_interval // 60} minutes until next automatic scan...")
                time.sleep(self.loop_detection_interval)

    def _update_loop_detection_ui(self, detection_record):
        """Update loop detection UI with new detection record."""
        try:
            # Update loop detection history table if it exists
            if hasattr(self, 'loop_detection_tree'):
                # Add new record to tree
                timestamp = detection_record["timestamp"]
                status = detection_record["status"]
                packets = detection_record["total_packets"]
                offenders = len(detection_record["offenders"])
                severity = detection_record["severity_score"]
                
                # Format status with emoji
                status_emoji = {
                    'clean': '✅ Clean',
                    'suspicious': '🔍 Suspicious',
                    'loop_detected': '⚠️ Loop Detected'
                }.get(status, f'❓ {status}')
                
                # Insert at the beginning
                self.loop_detection_tree.insert("", 0, values=(
                    timestamp[:19],  # Format timestamp
                    status_emoji,
                    packets,
                    offenders,
                    f"{severity:.2f}",
                    "Wi-Fi"
                ))
                
                # Keep only last 50 records in UI
                children = self.loop_detection_tree.get_children()
                if len(children) > 50:
                    self.loop_detection_tree.delete(children[-1])
            
            # Update statistics labels if they exist
            if hasattr(self, 'total_detections_label'):
                self.total_detections_label.config(text=str(self.loop_detection_stats["total_detections"]))
            if hasattr(self, 'loops_detected_label'):
                self.loops_detected_label.config(text=str(self.loop_detection_stats["loops_detected"]))
            if hasattr(self, 'suspicious_label'):
                self.suspicious_label.config(text=str(self.loop_detection_stats["suspicious_activity"]))
            if hasattr(self, 'clean_label'):
                self.clean_label.config(text=str(self.loop_detection_stats["clean_detections"]))
                
        except Exception as e:
            print(f"Error updating loop detection UI: {e}")

    def toggle_loop_detection(self):
        """Toggle loop detection on/off."""
        if self.loop_detection_running:
            self.stop_loop_detection()
        else:
            self.start_loop_detection()

    def set_loop_detection_interval(self, interval_minutes):
        """Set loop detection interval in minutes."""
        self.loop_detection_interval = interval_minutes * 60
        safe_emoji_print(f"[INFO] Loop detection interval set to {interval_minutes} minutes")

    def get_loop_detection_history(self):
        """Get loop detection history."""
        return self.loop_detection_history.copy()

    def get_loop_detection_stats(self):
        """Get loop detection statistics."""
        return self.loop_detection_stats.copy()

    def export_loop_detection_history(self):
        """Export loop detection history to CSV."""
        try:
            import csv
            from datetime import datetime
            
            filename = f"loop_detection_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['timestamp', 'status', 'total_packets', 'offenders_count', 'severity_score', 'duration']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for record in self.loop_detection_history:
                    writer.writerow({
                        'timestamp': record['timestamp'],
                        'status': record['status'],
                        'total_packets': record['total_packets'],
                        'offenders_count': len(record['offenders']),
                        'severity_score': record['severity_score'],
                        'duration': record['duration']
                    })
            
            safe_emoji_print(f"[SUCCESS] Loop detection history exported to {filename}")
            return filename
            
        except Exception as e:
            safe_emoji_print(f"[ERROR] Error exporting history: {e}")
            return None

    def show_notifications_panel(self):
        """Show the notifications panel in a new window."""
        if not hasattr(self, 'notification_window') or not self.notification_window.winfo_exists():
            self.notification_window = tk.Toplevel(self.root)
            self.notification_window.title("Notifications")
            self.notification_window.geometry("600x500")
            self.notification_window.resizable(True, True)
            
            # Center the window
            self._center_window(self.notification_window, 600, 500)
            
            # Create notification panel
            self.notification_panel = self.notification_system.create_notification_panel(self.notification_window)
            self.notification_panel.refresh_callback = self.update_notification_count
            
            # Update notification count
            self.update_notification_count()
        else:
            self.notification_window.lift()
            self.notification_window.focus_force()
    
    def show_notification_settings(self):
        """Show the notification settings panel in a new window."""
        if not hasattr(self, 'settings_window') or not self.settings_window.winfo_exists():
            self.settings_window = tk.Toplevel(self.root)
            self.settings_window.title("Notification Settings")
            self.settings_window.geometry("500x600")
            self.settings_window.resizable(True, True)
            
            # Center the window
            self._center_window(self.settings_window, 500, 600)
            
            # Create settings panel
            self.settings_panel = self.notification_system.create_settings_panel(self.settings_window)
        else:
            self.settings_window.lift()
            self.settings_window.focus_force()
    
    def show_activity_log(self):
        """Show the Activity Log viewer window (admin only)."""
        # Ensure activity_logs table exists
        try:
            create_activity_logs_table()
        except Exception as e:
            print(f"Error creating activity_logs table: {e}")
        
        # Show the activity log viewer
        try:
            from activity_log_viewer import show_activity_log
            show_activity_log(self.root, self.current_user)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open Activity Log:\n{str(e)}")
            print(f"Error opening activity log: {e}")
    
    def show_service_manager(self):
        """Show the Service Manager window to control API services with real-time log monitoring."""
        # Create service manager window (wider to accommodate logs)
        service_window = Toplevel(self.root)
        service_window.title("⚙️ Service Manager with Live Logs")
        service_window.geometry("1400x800")
        service_window.resizable(True, True)
        service_window.minsize(1200, 600)
        
        # Center the window
        service_window.update_idletasks()
        x = (service_window.winfo_screenwidth() // 2) - (1400 // 2)
        y = (service_window.winfo_screenheight() // 2) - (800 // 2)
        service_window.geometry(f"1400x800+{x}+{y}")
        
        # Get service manager instance
        service_mgr = get_service_manager()
        
        # Header frame
        header_frame = tb.Frame(service_window, bootstyle="primary")
        header_frame.pack(fill='x', padx=0, pady=0)
        
        title_label = tb.Label(
            header_frame,
            text="⚙️ API Service Manager with Real-Time Logs",
            font=("Segoe UI", 16, "bold"),
            bootstyle="inverse-primary"
        )
        title_label.pack(pady=15)
        
        subtitle_label = tb.Label(
            header_frame,
            text="Control Flask API and UniFi API Services • Monitor Live Logs • Color-Coded Output",
            font=("Segoe UI", 10),
            bootstyle="inverse-primary"
        )
        subtitle_label.pack(pady=(0, 15))
        
        # Main content frame with canvas for scrolling
        main_container = tb.Frame(service_window)
        main_container.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Service status variables
        service_status_vars = {}
        service_health_labels = {}
        service_toggle_buttons = {}
        auto_start_vars = {}
        health_checks_running = {}
        log_widgets = {}  # Store log text widgets
        log_auto_scroll_vars = {}  # Store auto-scroll toggle vars
        log_update_jobs = {}  # Store after() job IDs
        
        # LogViewer class for color-coded log display
        class LogViewer:
            """Real-time log viewer with color coding and auto-scroll."""
            
            def __init__(self, parent, service_name, service_mgr):
                self.service_name = service_name
                self.service_mgr = service_mgr
                self.auto_scroll = True
                
                # Container frame
                self.frame = tb.Frame(parent)
                
                # Header with service name and controls
                header = tb.Frame(self.frame)
                header.pack(fill='x', padx=2, pady=(2, 0))
                
                tb.Label(
                    header,
                    text=f"📋 {service_mgr.services[service_name]['name']} Logs",
                    font=("Segoe UI", 9, "bold")
                ).pack(side='left', padx=5)
                
                # Auto-scroll toggle
                self.auto_scroll_var = tb.BooleanVar(value=True)
                auto_scroll_check = tb.Checkbutton(
                    header,
                    text="Auto-scroll",
                    variable=self.auto_scroll_var,
                    bootstyle="success-round-toggle",
                    command=self._toggle_auto_scroll
                )
                auto_scroll_check.pack(side='right', padx=5)
                
                # Clear button
                clear_btn = tb.Button(
                    header,
                    text="🗑️",
                    bootstyle="danger-outline",
                    command=self.clear_logs,
                    width=3
                )
                clear_btn.pack(side='right', padx=2)
                
                # Log text widget with scrollbar
                log_frame = tb.Frame(self.frame)
                log_frame.pack(fill='both', expand=True, padx=2, pady=2)
                
                # Create text widget with dark theme
                self.text = Text(
                    log_frame,
                    wrap='none',
                    font=("Consolas", 9),
                    bg="#1e1e1e",
                    fg="#d4d4d4",
                    insertbackground="#ffffff",
                    relief='flat',
                    padx=8,
                    pady=6
                )
                
                # Scrollbars
                v_scroll = tb.Scrollbar(log_frame, orient='vertical', command=self.text.yview)
                h_scroll = tb.Scrollbar(log_frame, orient='horizontal', command=self.text.xview)
                self.text.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
                
                # Grid layout
                self.text.grid(row=0, column=0, sticky='nsew')
                v_scroll.grid(row=0, column=1, sticky='ns')
                h_scroll.grid(row=1, column=0, sticky='ew')
                log_frame.grid_rowconfigure(0, weight=1)
                log_frame.grid_columnconfigure(0, weight=1)
                
                # Configure color tags
                self._configure_tags()
                
                # Initial placeholder
                self.text.insert('1.0', f"Waiting for {service_mgr.services[service_name]['name']} logs...\n")
                self.text.tag_add('secondary', '1.0', 'end')
                self.text.config(state='disabled')
                
                # Track if we've loaded initial logs
                self.initialized = False
            
            def _configure_tags(self):
                """Configure color tags for different log levels."""
                # INFO - white/light gray
                self.text.tag_config('INFO', foreground='#d4d4d4')
                # SUCCESS/STARTED - green
                self.text.tag_config('SUCCESS', foreground='#4ec9b0', font=("Consolas", 9, "bold"))
                # WARNING - yellow/orange
                self.text.tag_config('WARNING', foreground='#dcdcaa', font=("Consolas", 9, "bold"))
                # ERROR/CRITICAL - red
                self.text.tag_config('ERROR', foreground='#f48771', font=("Consolas", 9, "bold"))
                # STOPPED/EXIT - muted gray
                self.text.tag_config('STOPPED', foreground='#808080')
                # DEBUG - blue
                self.text.tag_config('DEBUG', foreground='#569cd6')
                # Timestamp - cyan
                self.text.tag_config('timestamp', foreground='#9cdcfe')
                # Secondary (placeholder text)
                self.text.tag_config('secondary', foreground='#6a6a6a')
            
            def _toggle_auto_scroll(self):
                """Toggle auto-scroll feature."""
                self.auto_scroll = self.auto_scroll_var.get()
            
            def clear_logs(self):
                """Clear all logs from display."""
                self.text.config(state='normal')
                self.text.delete('1.0', 'end')
                self.text.insert('1.0', f"{self.service_mgr.services[self.service_name]['name']} logs cleared.\n")
                self.text.tag_add('secondary', '1.0', 'end')
                self.text.config(state='disabled')
                self.initialized = False
            
            def update_logs(self):
                """Read and display new log lines with color coding."""
                try:
                    # Load initial buffered logs on first update
                    if not self.initialized:
                        lines = self.service_mgr.get_buffered_logs(self.service_name, max_lines=100)
                        if lines:
                            self.text.config(state='normal')
                            self.text.delete('1.0', 'end')
                            for timestamp, level, message in lines:
                                self._insert_log_line(timestamp, level, message)
                            self.text.config(state='disabled')
                            if self.auto_scroll:
                                self.text.see('end')
                        self.initialized = True
                    else:
                        # Read new logs
                        new_lines = self.service_mgr.read_new_logs(self.service_name, max_lines=50)
                        if new_lines:
                            self.text.config(state='normal')
                            for timestamp, level, message in new_lines:
                                self._insert_log_line(timestamp, level, message)
                            self.text.config(state='disabled')
                            
                            # Auto-scroll to bottom if enabled
                            if self.auto_scroll:
                                self.text.see('end')
                except Exception as e:
                    logger.debug(f"Error updating logs for {self.service_name}: {e}")
            
            def _insert_log_line(self, timestamp, level, message):
                """Insert a single log line with appropriate color coding."""
                # Insert timestamp
                self.text.insert('end', f"[{timestamp}] ", 'timestamp')
                
                # Insert level with appropriate tag
                tag = level if level in ['INFO', 'SUCCESS', 'WARNING', 'ERROR', 'STOPPED', 'DEBUG'] else 'INFO'
                self.text.insert('end', f"{level:8s} ", tag)
                
                # Insert message
                self.text.insert('end', f"{message}\n", tag)
        
        def update_service_status(service_name):
            """Update status label immediately; schedule async health check."""
            try:
                status = service_mgr.get_service_status(service_name)
                service_info = service_mgr.services[service_name]
                
                # Status indicator
                if status == 'running':
                    status_text = "🟢 Running"
                    status_color = "success"
                    button_text = "⏹️ Stop"
                elif status == 'stopped':
                    status_text = "⚫ Stopped"
                    status_color = "secondary"
                    button_text = "▶️ Start"
                else:  # crashed
                    status_text = "🔴 Crashed"
                    status_color = "danger"
                    button_text = "🔄 Restart"
                
                # Update status label
                service_status_vars[service_name].config(
                    text=status_text,
                    bootstyle=status_color
                )
                
                # Update button
                service_toggle_buttons[service_name].config(text=button_text)

                # Schedule async health check to avoid blocking UI
                def check_health_async():
                    try:
                        is_healthy = service_mgr.check_service_health(service_name)
                        def update_health_ui():
                            if not service_window.winfo_exists():
                                return
                            if status != 'running':
                                service_health_labels[service_name].config(text="➖ N/A", bootstyle="secondary")
                            elif is_healthy:
                                service_health_labels[service_name].config(text="✅ Healthy", bootstyle="success")
                            else:
                                service_health_labels[service_name].config(text="⚠️ Not Responding", bootstyle="warning")
                            health_checks_running.pop(service_name, None)
                        service_window.after(0, update_health_ui)
                    except Exception as e:
                        def update_health_error():
                            if service_window.winfo_exists():
                                service_health_labels[service_name].config(text="❌ Error", bootstyle="danger")
                                health_checks_running.pop(service_name, None)
                        service_window.after(0, update_health_error)
                
                if status == 'running' and not health_checks_running.get(service_name):
                    health_checks_running[service_name] = True
                    service_health_labels[service_name].config(text="🔍 Checking", bootstyle="secondary")
                    threading.Thread(target=check_health_async, daemon=True).start()
                elif status != 'running':
                    service_health_labels[service_name].config(text="➖ N/A", bootstyle="secondary")
                    
            except Exception as e:
                logger.error(f"Error updating status for {service_name}: {e}")
        
        def toggle_service(service_name):
            """Toggle service on/off"""
            status = service_mgr.get_service_status(service_name)
            service_info = service_mgr.services[service_name]
            
            btn = service_toggle_buttons.get(service_name)
            if btn:
                btn.config(state='disabled', text="⏳ Wait...")
            
            def _do_toggle():
                try:
                    if status == 'running':
                        success = service_mgr.stop_service(service_name)
                        msg = f"{service_info['name']} has been stopped."
                        # Force refresh the log viewer to show stop messages
                        if success and service_name in log_widgets:
                            # Reset the log viewer's initialized flag to force full re-read
                            log_widgets[service_name].initialized = False
                            # Immediately update logs to show stop messages
                            service_window.after(100, lambda: log_widgets[service_name].update_logs())
                    else:
                        success = service_mgr.start_service(service_name)
                        msg = f"{service_info['name']} has been started.\nPort: {service_info['port']}"
                    
                    if success:
                        messagebox.showinfo("Success", msg)
                    else:
                        messagebox.showerror("Error", f"Failed to {'stop' if status=='running' else 'start'} {service_info['name']}.")
                finally:
                    if btn and service_window.winfo_exists():
                        btn.config(state='normal')
                        update_service_status(service_name)
            
            # Run toggle in background
            threading.Thread(target=_do_toggle, daemon=True).start()
        
        def toggle_auto_start(service_name):
            """Toggle auto-start setting"""
            auto_start = auto_start_vars[service_name].get()
            service_mgr.set_auto_start(service_name, auto_start)
        
        # Create service cards with log viewers
        for service_name, service_info in service_mgr.services.items():
            # Main service container (horizontal split)
            service_container = tb.Frame(main_container)
            service_container.pack(fill='both', expand=True, pady=5)
            
            # Left side: Service controls (30% width)
            control_panel = tb.Labelframe(
                service_container,
                text=f"  {service_info['name']} Controls  ",
                bootstyle="primary",
                padding=12
            )
            control_panel.pack(side='left', fill='both', padx=(0, 5), expand=False)
            control_panel.config(width=350)
            
            # Service info
            info_frame = tb.Frame(control_panel)
            info_frame.pack(fill='x', pady=(0, 8))
            
            info_label = tb.Label(
                info_frame,
                text=f"📄 {service_info['script']}\n🔌 Port {service_info['port']}",
                font=("Segoe UI", 9),
                justify='left'
            )
            info_label.pack(side='left', anchor='w')
            
            # Status row
            status_frame = tb.Frame(control_panel)
            status_frame.pack(fill='x', pady=4)
            
            tb.Label(status_frame, text="Status:", font=("Segoe UI", 9, "bold")).pack(side='left', padx=(0, 10))
            
            status_label = tb.Label(
                status_frame,
                text="⚫ Stopped",
                font=("Segoe UI", 9, "bold"),
                bootstyle="secondary"
            )
            status_label.pack(side='left', padx=(0, 20))
            service_status_vars[service_name] = status_label
            
            # Health row
            health_frame = tb.Frame(control_panel)
            health_frame.pack(fill='x', pady=4)
            
            tb.Label(health_frame, text="Health:", font=("Segoe UI", 9, "bold")).pack(side='left', padx=(0, 10))
            
            health_label = tb.Label(
                health_frame,
                text="➖ N/A",
                font=("Segoe UI", 9),
                bootstyle="secondary"
            )
            health_label.pack(side='left')
            service_health_labels[service_name] = health_label
            
            # Control buttons
            control_frame = tb.Frame(control_panel)
            control_frame.pack(fill='x', pady=(12, 0))
            
            toggle_btn = tb.Button(
                control_frame,
                text="▶️ Start",
                bootstyle="success",
                command=lambda sn=service_name: toggle_service(sn),
                width=15
            )
            toggle_btn.pack(side='top', pady=(0, 8), fill='x')
            service_toggle_buttons[service_name] = toggle_btn
            
            # Auto-start checkbox
            auto_start_var = tb.BooleanVar(value=service_info['auto_start'])
            auto_start_vars[service_name] = auto_start_var
            
            auto_start_check = tb.Checkbutton(
                control_frame,
                text="🚀 Auto-start on login",
                variable=auto_start_var,
                bootstyle="success-round-toggle",
                command=lambda sn=service_name: toggle_auto_start(sn)
            )
            auto_start_check.pack(side='top', anchor='w')
            
            # Right side: Log viewer (70% width)
            log_viewer = LogViewer(service_container, service_name, service_mgr)
            log_viewer.frame.pack(side='right', fill='both', expand=True)
            log_widgets[service_name] = log_viewer
            
            # Initialize status
            update_service_status(service_name)
        
        # Start log update loop
        def update_all_logs():
            """Update all log viewers periodically."""
            if not service_window.winfo_exists():
                return
            
            for service_name, log_viewer in log_widgets.items():
                try:
                    log_viewer.update_logs()
                except Exception as e:
                    logger.debug(f"Error updating log viewer for {service_name}: {e}")
            
            # Schedule next update (500ms = 2 updates per second)
            job_id = service_window.after(500, update_all_logs)
            log_update_jobs['update_all'] = job_id
        
        # Start the update loop
        update_all_logs()
        
        # Cleanup on window close
        def on_close():
            """Cancel all pending after() jobs and close window."""
            for job_id in log_update_jobs.values():
                try:
                    service_window.after_cancel(job_id)
                except:
                    pass
            service_window.destroy()
        
        service_window.protocol("WM_DELETE_WINDOW", on_close)
        
        # Bottom button frame
        button_frame = tb.Frame(service_window)
        button_frame.pack(fill='x', padx=20, pady=(0, 15))
        
        def refresh_all():
            """Refresh all service statuses"""
            for service_name in list(service_mgr.services.keys()):
                update_service_status(service_name)
        
        refresh_btn = tb.Button(
            button_frame,
            text="🔄 Refresh Status",
            bootstyle="info-outline",
            command=refresh_all,
            width=15
        )
        refresh_btn.pack(side='left', padx=5)
        
        def view_logs():
            """Open logs directory in file explorer"""
            logs_dir = service_mgr.logs_dir
            if logs_dir.exists():
                try:
                    os.startfile(str(logs_dir))
                except:
                    messagebox.showinfo("Logs Location", f"Log files are located at:\n{logs_dir}")
            else:
                messagebox.showinfo("No Logs", "No service logs available yet.")
        
        logs_btn = tb.Button(
            button_frame,
            text="📂 Open Logs Folder",
            bootstyle="warning-outline",
            command=view_logs,
            width=15
        )
        logs_btn.pack(side='left', padx=5)
        
        close_btn = tb.Button(
            button_frame,
            text="❌ Close",
            bootstyle="secondary",
            command=on_close,
            width=12
        )
        close_btn.pack(side='right', padx=5)
    
    def _create_router_notification(self, router_name, router_ip, is_online):
        """Create a router status change notification in the main thread."""
        try:
            notification_id = notify_router_status_change(router_name, router_ip, is_online)
        except Exception as e:
            pass

    def update_notification_count(self, force_refresh=False):
        """
        Update the notification count badge with performance optimization.
        
        Args:
            force_refresh: Force database query (ignores cache)
        """
        try:
            # Use cached count to reduce database queries
            count = self._cached_notification_count.get_count(force_refresh=force_refresh)
            
            # Only update UI if count changed
            if count != self.notification_count:
                self.notification_count = count
                if count > 0:
                    self.notification_badge.config(text=str(count), background="#dc3545")
                    self.notification_badge.place(in_=self.notification_btn, x=180, y=5)
                else:
                    self.notification_badge.place_forget()
        except Exception as e:
            pass
    
    def on_close(self):
        """Confirm and exit the entire application cleanly from the Admin window."""
        import sys
        
        answer = messagebox.askyesno("Exit Confirmation", "Are you sure you want to exit WinyFi?")
        
        if not answer:
            return

        # Log logout activity before exiting
        try:
            from device_utils import get_device_info
            device_info = get_device_info()
            user_id = self.current_user.get('id')
            ip_addr = device_info.get('ip_address')
            
            log_activity(
                user_id=user_id,
                action='Logout',
                target='Application Exit',
                ip_address=ip_addr
            )
        except Exception as e:
            print(f"Error logging logout activity on exit: {e}")
        
        # Update login_sessions table
        try:
            user_id = self.current_user.get('id')
            log_user_logout(user_id)
        except Exception as e:
            print(f"Error updating login session on exit: {e}")

        # Give time for database operations to complete
        import time
        time.sleep(1.0)

        # Stop background activities
        self.app_running = False
        
        # Don't set _report_cancel_requested here to avoid "Cancelled" message
        # The app_running flag will stop background tasks gracefully
        
        # Cancel all scheduled after() jobs
        jobs_to_cancel = [
            'update_task',
            'unifi_refresh_job',
            'routers_refresh_job',
            'dashboard_refresh_job',
            'report_auto_update_job',
            'bandwidth_auto_update_job',
            '_unifi_bandwidth_job',
            '_bandwidth_hide_after_job',
            '_reports_hide_after_job',
        ]
        
        for job_name in jobs_to_cancel:
            try:
                job = getattr(self, job_name, None)
                if job:
                    self.root.after_cancel(job)
            except Exception:
                pass
        
        try:
            self.stop_loop_detection()
        except Exception:
            pass
        try:
            self.stop_routers_auto_refresh()
        except Exception:
            pass

        # Give a brief moment for tasks to cancel
        try:
            self.root.update()
        except Exception:
            pass

        # Destroy the admin window and terminate the entire application
        try:
            self.root.destroy()
        except Exception:
            pass

        # Also destroy the hidden login root (master) to terminate mainloop
        try:
            master = self.root.master
            if master and master.winfo_exists():
                master.destroy()
        except Exception:
            pass
        
        # Force exit the entire application
        import sys
        sys.exit(0)
    
    def show_user_profile(self):
        """Show user profile information with modern UI design"""
        # Safety check for current_user
        if not self.current_user:
            messagebox.showerror("Error", "User information not available.")
            return

        def backend_change_password(user_id, old_password, new_password):
            """Backend logic to change user password."""
            from db import change_user_password
            try:
                result = change_user_password(user_id, old_password, new_password)
                return result  # Should be True/False or error message
            except Exception as e:
                return str(e)

        def backend_edit_profile(user_id, new_profile_data):
            """Backend logic to edit user profile."""
            from db import update_user_profile
            try:
                result = update_user_profile(user_id, new_profile_data)
                return result  # Should be True/False or error message
            except Exception as e:
                return str(e)

        # --- Modal and backend functions ---
        def backend_change_password(user_id, old_password, new_password):
            from db import change_user_password
            try:
                success, message = change_user_password(user_id, old_password, new_password)
                if not success:
                    messagebox.showerror("Error", message)
                return success
            except Exception as e:
                messagebox.showerror("Error", f"Failed to change password: {e}")
                return False

        def backend_edit_profile(user_id, new_profile_data):
            from db import update_user_profile
            try:
                return update_user_profile(user_id, new_profile_data)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update profile: {e}")
                return False

        def open_change_password_modal():
            modal = tb.Toplevel(self.root)
            modal.title("Change Password")
            modal.geometry("400x380")
            modal.resizable(False, False)
            modal.transient(self.root)
            modal.grab_set()
            modal.lift()  # Bring to front
            modal.focus_force()  # Focus modal

            # Center modal on screen
            modal.update_idletasks()
            x = (modal.winfo_screenwidth() - 400) // 2
            y = (modal.winfo_screenheight() - 430) // 2
            modal.geometry(f"400x430+{x}+{y}")

            frame = tb.Frame(modal, padding=20)
            frame.pack(fill="both", expand=True)

            tb.Label(frame, text="Change Password", font=("Segoe UI", 16, "bold"), bootstyle="primary").pack(pady=(0, 20))

            old_pass_var = tk.StringVar()
            new_pass_var = tk.StringVar()
            confirm_pass_var = tk.StringVar()

            tb.Label(frame, text="Current Password:", font=("Segoe UI", 11)).pack(anchor="w")
            old_pass_entry = tb.Entry(frame, textvariable=old_pass_var, show="*")
            old_pass_entry.pack(fill="x", pady=(0, 10))

            tb.Label(frame, text="New Password:", font=("Segoe UI", 11)).pack(anchor="w")
            new_pass_entry = tb.Entry(frame, textvariable=new_pass_var, show="*")
            new_pass_entry.pack(fill="x", pady=(0, 5))
            
            # Password strength indicator
            strength_label = tb.Label(frame, text="", font=("Segoe UI", 9))
            strength_label.pack(anchor="w", pady=(0, 10))
            
            def check_password_strength(*args):
                password = new_pass_var.get()
                if len(password) == 0:
                    strength_label.config(text="", foreground="")
                elif len(password) < 6:
                    strength_label.config(text="⚠️ Too short (min 6 characters)", foreground="red")
                elif password.isdigit():
                    strength_label.config(text="⚠️ Weak (numbers only)", foreground="orange")
                elif password.isalpha():
                    strength_label.config(text="⚠️ Weak (letters only)", foreground="orange")
                elif len(password) < 8:
                    strength_label.config(text="🟡 Fair", foreground="orange")
                else:
                    has_upper = any(c.isupper() for c in password)
                    has_lower = any(c.islower() for c in password)
                    has_digit = any(c.isdigit() for c in password)
                    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
                    
                    score = sum([has_upper, has_lower, has_digit, has_special])
                    if score >= 3:
                        strength_label.config(text="✅ Strong", foreground="green")
                    else:
                        strength_label.config(text="🟡 Good", foreground="darkorange")
            
            new_pass_var.trace_add("write", check_password_strength)

            tb.Label(frame, text="Confirm New Password:", font=("Segoe UI", 11)).pack(anchor="w")
            confirm_pass_entry = tb.Entry(frame, textvariable=confirm_pass_var, show="*")
            confirm_pass_entry.pack(fill="x", pady=(0, 5))
            
            # Password match indicator
            match_label = tb.Label(frame, text="", font=("Segoe UI", 9))
            match_label.pack(anchor="w", pady=(0, 15))
            
            def check_password_match(*args):
                new_pass = new_pass_var.get()
                confirm_pass = confirm_pass_var.get()
                if len(confirm_pass) == 0:
                    match_label.config(text="", foreground="")
                elif new_pass != confirm_pass:
                    match_label.config(text="❌ Passwords do not match", foreground="red")
                else:
                    match_label.config(text="✅ Passwords match", foreground="green")
            
            confirm_pass_var.trace_add("write", check_password_match)
            new_pass_var.trace_add("write", check_password_match)

            status_label = tb.Label(frame, text="", font=("Segoe UI", 10))
            status_label.pack(pady=(0, 10))

            def submit_change():
                old_password = old_pass_var.get().strip()
                new_password = new_pass_var.get().strip()
                confirm_password = confirm_pass_var.get().strip()
                
                # Clear previous status
                status_label.config(text="", foreground="")
                
                # Validation
                if not old_password:
                    status_label.config(text="❌ Please enter current password", foreground="red")
                    return
                    
                if not new_password:
                    status_label.config(text="❌ Please enter new password", foreground="red")
                    return
                    
                if len(new_password) < 6:
                    status_label.config(text="❌ New password must be at least 6 characters", foreground="red")
                    return
                    
                if new_password != confirm_password:
                    status_label.config(text="❌ Passwords do not match", foreground="red")
                    return
                
                if old_password == new_password:
                    status_label.config(text="❌ New password must be different from current password", foreground="red")
                    return
                
                # Show processing
                status_label.config(text="⏳ Changing password...", foreground="blue")
                modal.update()
                
                # Call backend
                try:
                    user_id = self.current_user.get('id')
                    success = backend_change_password(user_id, old_password, new_password)
                    if success:
                        status_label.config(text="✅ Password changed successfully!", foreground="green")
                        self.root.after(1500, modal.destroy)  # Close after 1.5 seconds
                    else:
                        status_label.config(text="❌ Current password is incorrect", foreground="red")
                except Exception as e:
                    status_label.config(text=f"❌ Error: {str(e)}", foreground="red")

            # Buttons
            button_frame = tb.Frame(frame)
            button_frame.pack(fill="x", pady=(10, 0))
            
            tb.Button(button_frame, text="Cancel", command=modal.destroy, bootstyle="secondary").pack(side="right", padx=(10, 0))
            tb.Button(button_frame, text="Change Password", command=submit_change, bootstyle="primary").pack(side="right")

            # Focus on first entry
            old_pass_entry.focus_set()
            
            # Enter key binding
            def on_enter(event):
                submit_change()
            
            modal.bind('<Return>', on_enter)

        def open_edit_profile_modal():
            modal = tb.Toplevel(self.root)
            modal.title("Edit Profile")
            modal.geometry("400x400")
            modal.resizable(False, False)
            modal.transient(self.root)
            modal.grab_set()

            # Center modal on screen
            modal.update_idletasks()
            x = (modal.winfo_screenwidth() - 400) // 2
            y = (modal.winfo_screenheight() - 400) // 2
            modal.geometry(f"400x400+{x}+{y}")

            frame = tb.Frame(modal, padding=20)
            frame.pack(fill="both", expand=True)

            tb.Label(frame, text="Edit Profile", font=("Segoe UI", 16, "bold"), bootstyle="success").pack(pady=(0, 20))

            first_name_var = tk.StringVar(value=self.current_user.get('first_name', ''))
            last_name_var = tk.StringVar(value=self.current_user.get('last_name', ''))
            username_var = tk.StringVar(value=self.current_user.get('username', ''))

            tb.Label(frame, text="First Name:", font=("Segoe UI", 11)).pack(anchor="w")
            tb.Entry(frame, textvariable=first_name_var).pack(fill="x", pady=(0, 10))

            tb.Label(frame, text="Last Name:", font=("Segoe UI", 11)).pack(anchor="w")
            tb.Entry(frame, textvariable=last_name_var).pack(fill="x", pady=(0, 10))

            tb.Label(frame, text="Username:", font=("Segoe UI", 11)).pack(anchor="w")
            tb.Entry(frame, textvariable=username_var).pack(fill="x", pady=(0, 10))

            def submit_edit():
                new_profile = {
                    'first_name': first_name_var.get(),
                    'last_name': last_name_var.get(),
                    'username': username_var.get()
                }
                user_id = self.current_user.get('id')
                success = backend_edit_profile(user_id, new_profile)
                if success:
                    messagebox.showinfo("Success", "Profile updated successfully.")
                    modal.destroy()

            tb.Button(frame, text="Save Changes", bootstyle="success", command=submit_edit).pack(pady=(10, 0))
            tb.Button(frame, text="Cancel", bootstyle="secondary", command=modal.destroy).pack(pady=(5, 0))

        # ...existing code...
        """Show user profile information with modern UI design"""
        # Safety check for current_user
        if not self.current_user:
            messagebox.showerror("Error", "User information not available.")
            return
        
            
        profile_modal = tb.Toplevel(self.root)
        profile_modal.title("User Profile - Admin")
        profile_modal.geometry("950x655")
        profile_modal.resizable(True, True)
        profile_modal.configure(bg='#f8fafc')
        profile_modal.minsize(950, 655)
        
        # Center the window
        profile_modal.transient(self.root)
        profile_modal.grab_set()
        
        # Calculate center position
        profile_modal.update_idletasks()
        x = (profile_modal.winfo_screenwidth() - 950) // 2
        y = (profile_modal.winfo_screenheight() - 755) // 2
        profile_modal.geometry(f"950x655+{x}+{y}")
        
        # Main container with modern styling
        main_container = tb.Frame(profile_modal, bootstyle="light")
        main_container.pack(fill="both", expand=True, padx=12, pady=12)
        
        # Thin header line instead of thick banner
        header_line = tb.Frame(main_container, height=3, bootstyle="primary")
        header_line.pack(fill="x", pady=(0, 15))
        
        # Profile section with avatar and info
        profile_section = tb.Frame(main_container)
        profile_section.pack(fill="x", pady=(0, 20))
        
        # Modern circular avatar
        avatar_frame = tb.Frame(profile_section)
        avatar_frame.pack(side="left", padx=(0, 25))
        
        # Create a modern circular avatar with shadow effect
        avatar_canvas = tk.Canvas(avatar_frame, width=100, height=100, 
                                 highlightthickness=0, bg='#1976d2')
        avatar_canvas.pack()
        
        # Draw modern avatar with gradient effect
        avatar_canvas.create_oval(8, 8, 92, 92, fill='#1976d2', outline='#ffffff', width=4)
        avatar_canvas.create_text(50, 50, text="👤", font=("Segoe UI", 32), fill='white')
        
        # User information section
        user_info_section = tb.Frame(profile_section)
        user_info_section.pack(side="left", fill="both", expand=True)
        
        # Get user data
        first_name = self.current_user.get('first_name', '') or ''
        last_name = self.current_user.get('last_name', '') or ''
        username = self.current_user.get('username', 'User')
        
        # Handle name display logic
        first_name = first_name.strip() if first_name else ''
        last_name = last_name.strip() if last_name else ''
        
        if first_name and last_name:
            full_name = f"{first_name} {last_name}"
        elif first_name:
            full_name = first_name
        elif last_name:
            full_name = last_name
        elif username and username != 'User':
            full_name = username.title()
        else:
            full_name = "User"
        
        # User name with modern typography
        name_label = tb.Label(user_info_section, text=full_name, 
                             font=("Segoe UI", 24, "bold"), 
                             foreground="black")
        name_label.pack(anchor="w", pady=(0, 5))
        
        # Username with subtle styling
        username_label = tb.Label(user_info_section, text=f"@{username}", 
                                 font=("Segoe UI", 14), 
                                 foreground="#666666")
        username_label.pack(anchor="w", pady=(0, 10))
        
        # Role and status badges
        badges_frame = tb.Frame(user_info_section)
        badges_frame.pack(anchor="w")
        
        # Role badge with modern design
        role = self.current_user.get('role', 'user').title()
        role_badge = tb.Label(badges_frame, text=f"● {role}", 
                             font=("Segoe UI", 11, "bold"),
                             foreground="white",
                             background="#4caf50" if role == "Admin" else "#2196f3")
        role_badge.pack(side="left", padx=(0, 10))
        
        # Status indicator
        status_badge = tb.Label(badges_frame, text="🟢 Online", 
                               font=("Segoe UI", 11),
                               foreground="white",
                               background="#4caf50")
        status_badge.pack(side="left")

        # Main content area with side-by-side layout
        content_frame = tb.Frame(main_container)
        content_frame.pack(fill="both", expand=True)

        # Left column - Personal Information
        left_column = tb.Frame(content_frame)
        left_column.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        # Personal Information Card
        info_card = tb.LabelFrame(left_column, text="📋 Personal Information", 
                                 bootstyle="info", padding=15)
        info_card.pack(fill="both", expand=True)
        
        # User information in modern grid layout
        user_id = self.current_user.get('id', 'N/A')
        
        # Get last login information
        from db import get_user_last_login_info
        last_login_info = None
        try:
            if user_id != 'N/A':
                last_login_info = get_user_last_login_info(user_id)
        except Exception as e:
            print(f"Error getting last login info: {e}")
            last_login_info = None
        # Format last login information
        if last_login_info:
            last_login_display = last_login_info.get('login_timestamp', 'Unknown')
            device_hostname = last_login_info.get('device_hostname', 'Unknown')
            device_platform = last_login_info.get('device_platform', 'Unknown')
        else:
            last_login_display = 'Unknown'
            device_hostname = 'Not Available'
            device_platform = 'Not Available'

        user_info_data = [
            ("🆔", "User ID", str(user_id) if user_id != 'N/A' else 'Unknown'),
            ("✅", "Account Status", "Active"),
            ("🕒", "Last Login", last_login_display),
            ("💻", "Device Hostname", device_hostname),
            ("🖥️", "Device Platform", device_platform),
        ]
        for i, (icon, label, value) in enumerate(user_info_data):
            info_row = tb.Frame(info_card)
            info_row.pack(fill="x", pady=8)
            
            # Icon
            icon_label = tb.Label(info_row, text=icon, font=("Segoe UI", 14))
            icon_label.pack(side="left", padx=(0, 15))
            
            # Label and value container
            text_container = tb.Frame(info_row)
            text_container.pack(side="left", fill="x", expand=True)
            
            # Label
            label_widget = tb.Label(text_container, text=label, 
                                   font=("Segoe UI", 12, "bold"),
                                   foreground="#374151")
            label_widget.pack(anchor="w")
            
            # Value
            value_widget = tb.Label(text_container, text=value, 
                                   font=("Segoe UI", 12),
                                   foreground="#6b7280")
            value_widget.pack(anchor="w", pady=(1, 0))

        # Right column - Actions and Management
        right_column = tb.Frame(content_frame)
        right_column.pack(side="right", fill="both", expand=True, padx=(10, 0))
        
        # Quick Actions Card
        actions_card = tb.LabelFrame(right_column, text="⚡ Quick Actions", 
                                   bootstyle="success", padding=15)
        actions_card.pack(fill="x", pady=(0, 12))
        
        # Action buttons in modern vertical layout
        actions = [
            ("🔒", "Change Password", "primary", open_change_password_modal),
            ("✏️", "Edit Profile", "success", self.edit_user_profile),
        ]
        
        # Create action buttons vertically
        for icon, text, style, command in actions:
            action_btn = tb.Button(actions_card, text=f"{icon} {text}", 
                                 bootstyle=f"outline-{style}", 
                                 command=command,
                                 width=22)
            action_btn.pack(fill="x", pady=5)
        
        # Account Management Card
        account_card = tb.LabelFrame(right_column, text="🛡️ Account Management", 
                                   bootstyle="warning", padding=15)
        account_card.pack(fill="x", pady=(0, 12))
        
        # Account actions
        logout_btn = tb.Button(account_card, text="🚪 Logout", 
                              bootstyle="danger", 
                              command=self.logout,
                              width=22)
        logout_btn.pack(fill="x", pady=(0, 6))
        
        
        # Footer with modern styling
        footer_frame = tb.Frame(main_container)
        footer_frame.pack(fill="x", pady=(10, 0))
        footer_label = tb.Label(footer_frame, text="WinyFi © 2024. All rights reserved.",
                              font=("Segoe UI", 10), foreground="#9ca3af")

        # Store reference to modal
        self.profile_modal = profile_modal

    def handle_profile_option(self, option):
        """Handle profile option selection"""
        messagebox.showinfo("Feature Coming Soon", f"{option} functionality will be implemented soon.")

    def edit_user_profile(self):
        """Edit user profile information"""
        # Open the actual Edit Profile modal
        if hasattr(self, '_open_edit_profile_modal'):
            self._open_edit_profile_modal()
        else:
            messagebox.showerror("Error", "Edit Profile modal function not found.")

    def _open_edit_profile_modal(self):
        modal = tb.Toplevel(self.root)
        modal.title("Edit Profile")
        modal.geometry("440x420")
        modal.resizable(False, False)
        modal.transient(self.root)
        modal.grab_set()
        modal.lift()
        modal.focus_force()

        # Center modal on screen
        modal.update_idletasks()
        x = (modal.winfo_screenwidth() - 440) // 2
        y = (modal.winfo_screenheight() - 420) // 2
        modal.geometry(f"440x420+{x}+{y}")

        frame = tb.Frame(modal, padding=20)
        frame.pack(fill="both", expand=True)

        tb.Label(frame, text="Edit Profile", font=("Segoe UI", 16, "bold"), bootstyle="success").pack(pady=(0, 18))

        # Live-load current user from DB for freshness
        try:
            from db import get_user_by_id
            fresh = get_user_by_id(self.current_user.get('id')) or {}
        except Exception:
            fresh = {}

        first_name_var = tk.StringVar(value=fresh.get('first_name') or self.current_user.get('first_name', ''))
        last_name_var = tk.StringVar(value=fresh.get('last_name') or self.current_user.get('last_name', ''))
        username_var = tk.StringVar(value=fresh.get('username') or self.current_user.get('username', ''))

        def add_field(label, var, placeholder=""):
            row = tb.Frame(frame)
            row.pack(fill="x", pady=6)
            tb.Label(row, text=label, width=14, anchor="w").pack(side="left")
            entry = tb.Entry(row, textvariable=var)
            entry.pack(side="left", fill="x", expand=True)
            if placeholder and not var.get():
                entry.insert(0, placeholder)
                entry.configure(foreground="#9aa0a6")
                def _on_focus_in(event):
                    if entry.get() == placeholder and entry.cget('foreground') == '#9aa0a6':
                        entry.delete(0, 'end')
                        entry.configure(foreground='black')
                def _on_focus_out(event):
                    if not entry.get():
                        entry.insert(0, placeholder)
                        entry.configure(foreground="#9aa0a6")
                entry.bind('<FocusIn>', _on_focus_in)
                entry.bind('<FocusOut>', _on_focus_out)
            return entry

        add_field("First Name:", first_name_var, "Enter first name")
        add_field("Last Name:", last_name_var, "Enter last name")
        username_entry = add_field("Username:", username_var, "e.g. jdoe")

        # Status area
        status = tb.Label(frame, text="", font=("Segoe UI", 10))
        status.pack(fill="x", pady=(4,0))

        # Buttons
        btns = tb.Frame(frame)
        btns.pack(fill="x", pady=(12, 0))

        save_btn = tb.Button(btns, text="Save Changes", bootstyle="success")
        cancel_btn = tb.Button(btns, text="Cancel", bootstyle="secondary", command=modal.destroy)
        cancel_btn.pack(side="right")
        save_btn.pack(side="right", padx=(0,8))

        # Validation helpers
        import re
        def validate():
            fn = (first_name_var.get() or "").strip()
            ln = (last_name_var.get() or "").strip()
            un = (username_var.get() or "").strip()

            if not fn and not ln:
                return False, "Provide at least a first or last name"
            if un:
                if len(un) < 3:
                    return False, "Username must be at least 3 characters"
                if not re.fullmatch(r"[A-Za-z0-9_.-]+", un):
                    return False, "Username may contain letters, numbers, '.', '_' or '-' only"
            return True, ""

        def set_busy(busy: bool):
            save_btn.configure(state='disabled' if busy else 'normal')
            cancel_btn.configure(state='disabled' if busy else 'normal')

        def on_save():
            ok, msg = validate()
            if not ok:
                status.configure(text=f"❌ {msg}", foreground="red")
                return
            status.configure(text="⏳ Saving...", foreground="#0d6efd")
            set_busy(True)
            self.root.update_idletasks()

            new_profile = {
                'first_name': (first_name_var.get() or '').strip(),
                'last_name': (last_name_var.get() or '').strip(),
                'username': (username_var.get() or '').strip(),
            }

            try:
                from db import update_user_profile
                success, payload = update_user_profile(self.current_user.get('id'), new_profile)
                if success:
                    # Refresh current_user cache and UI labels
                    self.current_user.update(payload or {})
                    status.configure(text="✅ Profile updated successfully", foreground="green")
                    # Close shortly after success
                    self.root.after(900, modal.destroy)
                else:
                    status.configure(text=f"❌ {payload}", foreground="red")
            except Exception as e:
                status.configure(text=f"❌ Error: {e}", foreground="red")
            finally:
                set_busy(False)

        save_btn.configure(command=on_save)

    # =============================
    # Network Topology - Visual Wiring Map
    # =============================
    def open_topology_window(self):
        """Open simplified network topology for visualizing router positions and wiring."""
        try:
            from db import ensure_topology_schema
            ensure_topology_schema()
        except Exception:
            pass

        import tkinter as tk
        import ttkbootstrap as tb
        from router_utils import (
            get_routers,
            update_router_position,
            get_router_connections,
            add_router_connection,
            remove_router_connection,
            update_router_connection_bend,
        )

        if getattr(self, '_topology_window', None) and self._topology_window.winfo_exists():
            self._topology_window.lift()
            return

        win = tk.Toplevel(self.root)
        win.title("Network Topology - Wiring & Positions")
        win.geometry("1100x700")
        self._center_window(win, 1100, 700)
        self._topology_window = win

        outer = tb.Frame(win)
        outer.pack(fill='both', expand=True)

        # Simplified header with essential controls
        header = tb.Frame(outer, bootstyle='secondary')
        header.pack(fill='x', padx=0, pady=0)
        
        # Left side - Title
        title_frame = tb.Frame(header)
        title_frame.pack(side='left', padx=12, pady=8)
        tb.Label(title_frame, text="🗺️ Network Topology Map", 
                font=('Segoe UI', 14, 'bold')).pack(side='left')
        
        # Right side - Controls
        ctrl = tb.Frame(header)
        ctrl.pack(side='right', padx=12, pady=8)
        
        self._topology_edit_mode = tk.BooleanVar(value=False)
        edit_btn = tb.Checkbutton(ctrl, text="🎨 Edit Mode", variable=self._topology_edit_mode,
                                 bootstyle='warning-round-toggle')
        edit_btn.pack(side='left', padx=6)
        
        self._topology_auto_refresh = tk.BooleanVar(value=True)
        tb.Checkbutton(ctrl, text="Auto-Refresh", variable=self._topology_auto_refresh,
                       bootstyle='success-round-toggle').pack(side='left', padx=6)
        tb.Button(ctrl, text="🔄 Refresh", bootstyle='info-outline', 
                 command=self._topology_refresh_status, width=10).pack(side='left', padx=4)
        
        # Help button
        def _show_help():
            help_text = """🎨 TOPOLOGY DRAWING GUIDE
            
📍 BASIC CONTROLS:
• Drag routers to reposition them
• Click two routers to connect/disconnect
• Ctrl+Scroll or use zoom slider to zoom

✏️ EDIT MODE TOOLS:
• 👆 Select: Click shapes to select, drag to move, drag handles to resize
• ⬜ Box: Draw rectangles to group routers or mark areas
• 📝 Text: Add labels for buildings, floors, departments
• 📏 Line: Draw connection lines or annotations

🎨 STYLING:
• Choose from 8 colors for shapes and text
• Adjust line width (1-5px)
• Enable fill for rectangles with light colors
• Text: sizes 8-24px, bold toggle

⌨️ KEYBOARD SHORTCUTS:
• ESC: Cancel current drawing
• Right-click: Delete shape (with confirmation)
• Ctrl+Scroll: Zoom in/out

💡 TIPS:
• Use filled rectangles to highlight building floors
• Add text labels before drawing for context
• Select mode lets you modify existing shapes
• All changes are auto-saved"""
            messagebox.showinfo("Topology Guide", help_text, parent=win)
        
        tb.Button(ctrl, text="❓ Help", bootstyle='secondary-outline',
                 command=_show_help, width=8).pack(side='left', padx=4)
        
        # Instructions bar
        info_bar = tb.Frame(outer, bootstyle='light')
        info_bar.pack(fill='x', padx=0, pady=0)
        
        # Left side - instructions (dynamic based on edit mode)
        self._topology_instructions_var = tk.StringVar(value="💡 Drag routers to position | Click two routers to connect/disconnect | Ctrl+Scroll to zoom")
        tb.Label(info_bar, textvariable=self._topology_instructions_var, 
                bootstyle='secondary', font=('Segoe UI', 9)).pack(side='left', padx=12, pady=6)
        
        # Drawing tools panel (shown when edit mode is on)
        self._topology_tools_frame = tb.Frame(info_bar, bootstyle='light')
        
        self._topology_draw_mode = tk.StringVar(value='select')
        self._topology_draw_color = tk.StringVar(value='#f59e0b')  # Orange
        self._topology_line_width = tk.IntVar(value=2)
        self._topology_fill_enabled = tk.BooleanVar(value=False)
        self._topology_fill_color = tk.StringVar(value='#fef3c7')  # Light yellow
        self._topology_text_size = tk.IntVar(value=12)
        self._topology_text_bold = tk.BooleanVar(value=True)
        self._topology_tool_buttons = {}  # Store button references
        
        def _update_tool_buttons(*args):
            """Update tool button styling when mode changes."""
            current_mode = self._topology_draw_mode.get()
            for mode, btn in self._topology_tool_buttons.items():
                if mode == current_mode:
                    btn.configure(bootstyle='primary')
                else:
                    btn.configure(bootstyle='secondary-outline')
        
        def _create_tool_btn(text, mode, emoji):
            def select_tool():
                self._topology_draw_mode.set(mode)
                _update_tool_buttons()
            
            btn = tb.Button(self._topology_tools_frame, text=f"{emoji} {text}", 
                          bootstyle='primary' if mode == 'select' else 'secondary-outline',
                          width=9,
                          command=select_tool)
            btn.pack(side='left', padx=2)
            self._topology_tool_buttons[mode] = btn
            return btn
        
        # === DRAWING TOOLS SECTION ===
        tb.Label(self._topology_tools_frame, text="✏️ Draw:", font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(0, 6))
        _create_tool_btn('Select', 'select', '👆')
        _create_tool_btn('Box', 'rectangle', '⬜')
        _create_tool_btn('Text', 'text', '📝')
        _create_tool_btn('Line', 'line', '📏')
        
        # Separator
        tb.Separator(self._topology_tools_frame, orient='vertical').pack(side='left', fill='y', padx=10, pady=4)
        
        # === STYLE SECTION ===
        tb.Label(self._topology_tools_frame, text="🎨 Style:", font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(0, 6))
        
        # Color picker with names
        tb.Label(self._topology_tools_frame, text="Color:", font=('Segoe UI', 9)).pack(side='left', padx=(0, 3))
        
        color_map = {
            '🟠 Orange': '#f59e0b',
            '🔵 Blue': '#3b82f6', 
            '🔴 Red': '#ef4444',
            '🟢 Green': '#10b981',
            '🟡 Yellow': '#eab308',
            '🟣 Purple': '#8b5cf6',
            '⚫ Black': '#1f2937',
            '⚪ Gray': '#6b7280'
        }
        
        color_names = list(color_map.keys())
        color_combo = tb.Combobox(self._topology_tools_frame, 
                                 values=color_names,
                                 state='readonly', width=11, font=('Segoe UI', 9))
        color_combo.set('🟠 Orange')  # Default
        color_combo.pack(side='left', padx=(0, 4))
        
        def _on_color_change(event):
            selected_name = color_combo.get()
            self._topology_draw_color.set(color_map.get(selected_name, '#f59e0b'))
        
        color_combo.bind('<<ComboboxSelected>>', _on_color_change)
        
        # Line width
        tb.Label(self._topology_tools_frame, text="Width:", font=('Segoe UI', 9)).pack(side='left', padx=(10, 3))
        width_combo = tb.Combobox(self._topology_tools_frame, textvariable=self._topology_line_width,
                                 values=[1, 2, 3, 4, 5], state='readonly', width=3, font=('Segoe UI', 9))
        width_combo.set(2)  # Set default
        width_combo.pack(side='left', padx=(0, 4))
        
        # Separator
        tb.Separator(self._topology_tools_frame, orient='vertical').pack(side='left', fill='y', padx=10, pady=4)
        
        # === FILL SECTION (for rectangles) ===
        tb.Label(self._topology_tools_frame, text="🎯 Fill:", font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(0, 6))
        fill_check = tb.Checkbutton(self._topology_tools_frame, text="Enable", variable=self._topology_fill_enabled,
                                   bootstyle='success-round-toggle')
        fill_check.pack(side='left', padx=(0, 6))
        
        # Fill color with names
        tb.Label(self._topology_tools_frame, text="Color:", font=('Segoe UI', 9)).pack(side='left', padx=(0, 3))
        
        fill_color_map = {
            '🟡 Lt Yellow': '#fef3c7',
            '🔵 Lt Blue': '#dbeafe',
            '🔴 Lt Red': '#fee2e2',
            '🟢 Lt Green': '#d1fae5',
            '🟡 Cream': '#fef9c3',
            '🟣 Lt Purple': '#e9d5ff',
            '⚪ Lt Gray': '#f3f4f6'
        }
        
        fill_names = list(fill_color_map.keys())
        fill_combo = tb.Combobox(self._topology_tools_frame,
                                values=fill_names,
                                state='readonly', width=12)
        fill_combo.set('🟡 Lt Yellow')  # Default
        fill_combo.pack(side='left', padx=2)
        
        def _on_fill_color_change(event):
            selected_name = fill_combo.get()
            self._topology_fill_color.set(fill_color_map.get(selected_name, '#fef3c7'))
        
        fill_combo.bind('<<ComboboxSelected>>', _on_fill_color_change)
        
        # Separator
        tb.Separator(self._topology_tools_frame, orient='vertical').pack(side='left', fill='y', padx=10, pady=4)
        
        # === TEXT FORMATTING SECTION ===
        tb.Label(self._topology_tools_frame, text="📝 Text:", font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(0, 6))
        tb.Label(self._topology_tools_frame, text="Size:", font=('Segoe UI', 9)).pack(side='left', padx=(0, 3))
        size_combo = tb.Combobox(self._topology_tools_frame, textvariable=self._topology_text_size,
                                values=[8, 10, 12, 14, 16, 18, 20, 24], state='readonly', width=3, font=('Segoe UI', 9))
        size_combo.set(12)  # Set default
        size_combo.pack(side='left', padx=(0, 4))
        
        # Bold toggle
        tb.Checkbutton(self._topology_tools_frame, text="Bold", variable=self._topology_text_bold,
                      bootstyle='info-round-toggle').pack(side='left', padx=(8, 0))
        
        # Separator and help text
        tb.Separator(self._topology_tools_frame, orient='vertical').pack(side='left', fill='y', padx=10, pady=4)
        tb.Label(self._topology_tools_frame, text="💡 Right-click shapes to delete | ESC to cancel", 
                font=('Segoe UI', 8), bootstyle='secondary').pack(side='left', padx=(4, 0))
        
        def _update_instructions(*args):
            if self._topology_edit_mode.get():
                # Show contextual help based on selected tool
                mode = self._topology_draw_mode.get()
                if mode == 'select':
                    self._topology_instructions_var.set("👆 SELECT MODE: Click shapes to select • Drag to move • Drag handles to resize • Right-click to delete")
                elif mode == 'rectangle':
                    self._topology_instructions_var.set("⬜ RECTANGLE: Click and drag to draw • Use Fill toggle for background color • ESC to cancel")
                elif mode == 'text':
                    self._topology_instructions_var.set("📝 TEXT: Click anywhere to add label • Set size and color before clicking • Right-click to delete")
                elif mode == 'line':
                    self._topology_instructions_var.set("📏 LINE: Click and drag to draw connection • Adjust width and color as needed • ESC to cancel")
                self._topology_tools_frame.pack(side='left', padx=(20, 0), pady=6)
            else:
                self._topology_instructions_var.set("💡 Drag routers to position | Click two routers to connect/disconnect | Ctrl+Scroll to zoom")
                self._topology_tools_frame.pack_forget()
        
        def _update_ctrl_visibility(*args):
            """Show/hide connection control handles based on edit mode."""
            edit_enabled = self._topology_edit_mode.get()
            for conn_data in self._topology_connections.values():
                ctrl = conn_data.get('ctrl')
                if ctrl:
                    if edit_enabled:
                        topo_canvas.itemconfig(ctrl, state='normal')
                    else:
                        topo_canvas.itemconfig(ctrl, state='hidden')
        
        self._topology_edit_mode.trace_add('write', _update_instructions)
        self._topology_edit_mode.trace_add('write', _update_ctrl_visibility)
        self._topology_draw_mode.trace_add('write', _update_instructions)
        
        # Right side - zoom controls with slider
        zoom_frame = tb.Frame(info_bar)
        zoom_frame.pack(side='right', padx=12, pady=6)
        
        tb.Label(zoom_frame, text="🔍", font=('Segoe UI', 12)).pack(side='left', padx=(0, 8))
        tb.Button(zoom_frame, text="−", bootstyle='secondary-outline', width=3,
                 command=lambda: self._topology_set_zoom(self._topology_zoom_slider.get() - 10)).pack(side='left', padx=2)
        
        # Zoom slider (25% to 300%) - using ttkbootstrap Scale
        self._topology_zoom_slider = tb.Scale(zoom_frame, from_=25, to=300, orient='horizontal',
                                             length=150, bootstyle='info',
                                             command=lambda v: self._topology_apply_zoom(float(v)))
        self._topology_zoom_slider.set(100)
        self._topology_zoom_slider.pack(side='left', padx=6)
        
        self._topology_zoom_var = tk.StringVar(value="100%")
        zoom_label = tb.Label(zoom_frame, textvariable=self._topology_zoom_var, 
                             font=('Segoe UI', 10, 'bold'), width=5)
        zoom_label.pack(side='left', padx=6)
        
        tb.Button(zoom_frame, text="+", bootstyle='secondary-outline', width=3,
                 command=lambda: self._topology_set_zoom(self._topology_zoom_slider.get() + 10)).pack(side='left', padx=2)
        tb.Button(zoom_frame, text="Reset", bootstyle='info-outline', width=6,
                 command=lambda: self._topology_set_zoom(100)).pack(side='left', padx=4)

        # Main canvas area with grid background
        canvas_frame = tb.Frame(outer, bootstyle='light')
        canvas_frame.pack(fill='both', expand=True, padx=8, pady=8)
        
        hscroll = tb.Scrollbar(canvas_frame, orient='horizontal')
        vscroll = tb.Scrollbar(canvas_frame, orient='vertical')
        topo_canvas = tk.Canvas(canvas_frame, bg='#ffffff', 
                               xscrollcommand=hscroll.set, yscrollcommand=vscroll.set,
                               relief='sunken', borderwidth=1)
        hscroll.config(command=topo_canvas.xview)
        vscroll.config(command=topo_canvas.yview)
        topo_canvas.pack(side='left', fill='both', expand=True)
        vscroll.pack(side='right', fill='y')
        hscroll.pack(side='bottom', fill='x')

        # Draw subtle grid for easier positioning
        def _draw_grid():
            grid_size = 50
            for x in range(0, 2000, grid_size):
                topo_canvas.create_line(x, 0, x, 2000, fill='#e5e7eb', width=1, tags='grid')
            for y in range(0, 2000, grid_size):
                topo_canvas.create_line(0, y, 2000, y, fill='#e5e7eb', width=1, tags='grid')
            topo_canvas.tag_lower('grid')
        _draw_grid()

        # Zoom functionality
        self._topology_zoom_level = 1.0
        
        def _on_mousewheel(event):
            # Check for Ctrl key more reliably
            ctrl_pressed = (event.state & 0x0004) or (event.state & 0x20004)
            shift_pressed = event.state & 0x0001
            
            # Ctrl + Wheel = Zoom using slider
            if ctrl_pressed:
                if hasattr(self, '_topology_zoom_slider'):
                    current_zoom = self._topology_zoom_slider.get()
                    if event.delta > 0:
                        new_zoom = min(300, current_zoom + 10)
                    else:
                        new_zoom = max(25, current_zoom - 10)
                    self._topology_set_zoom(new_zoom)
                return "break"  # Prevent default scrolling
            # Shift + Wheel = Horizontal scroll
            elif shift_pressed:
                topo_canvas.xview_scroll(-1 if event.delta > 0 else 1, 'units')
            # Wheel alone = Vertical scroll
            else:
                topo_canvas.yview_scroll(-1 if event.delta > 0 else 1, 'units')
        
        # Bind mouse wheel events
        topo_canvas.bind('<MouseWheel>', _on_mousewheel)
        topo_canvas.bind('<Control-MouseWheel>', _on_mousewheel)

        # Data stores
        self._topology_canvas = topo_canvas
        self._topology_nodes = {}
        self._topology_connections = {}
        self._topology_ctrl_map = {}  # ctrl_id -> (a,b)
        self._topology_selected = None
        self._dragging_node = None
        self._drag_offset = (0, 0)
        self._dragging_ctrl_pair = None
        self._dragging_ctrl_off = (0, 0)
        self._topology_shapes = {}  # Store drawn shapes {id: {'type': 'rect'/'text'/'line', 'items': [canvas_ids], 'data': {}}}
        self._topology_shape_counter = 0
        self._topology_drawing = False
        self._topology_draw_start = None
        self._topology_temp_shape = None
        self._topology_selected_shape = None
        self._dragging_shape = None
        self._shape_drag_start = None
        self._shape_resize_handle = None
        self._shape_resize_handles = {}  # Store resize handles {shape_id: [handle_items]}

        routers = get_routers() or []
        connections_raw = get_router_connections() or []
        pairs = set(tuple(sorted((c['router_a_id'], c['router_b_id']))) for c in connections_raw)
        bend_lookup = {tuple(sorted((c['router_a_id'], c['router_b_id']))): (c.get('bend_x'), c.get('bend_y')) for c in connections_raw}

        # Smart initial layout - spread routers nicely
        cols = max(3, int((len(routers) ** 0.5)))
        base_x, base_y = 100, 100
        gap_x, gap_y = 250, 180

        # Draw routers with improved visual design
        for i, r in enumerate(routers):
            rid = r['id']
            name = r.get('name', f"Router {rid}")
            ip = r.get('ip_address', '0.0.0.0')
            
            # Check actual online status by pinging
            from router_utils import is_online
            status_bool = is_online(ip)
            status = 'online' if status_bool else 'offline'
            
            # Use saved position or calculate new position
            x = r.get('pos_x') if r.get('pos_x') is not None else base_x + (i % cols) * gap_x
            y = r.get('pos_y') if r.get('pos_y') is not None else base_y + (i // cols) * gap_y
            
            # Larger, cleaner router boxes
            w, h = 200, 90
            
            # Shadow effect
            shadow = topo_canvas.create_rectangle(x+4, y+4, x+w+4, y+h+4, 
                                                 fill='#d1d5db', outline='', tags='shadow')
            
            # Main router box with gradient-like effect
            rect = topo_canvas.create_rectangle(x, y, x + w, y + h, 
                                               fill='#ffffff', outline='#6b7280', width=2,
                                               tags='router')
            
            # Status indicator (larger and clearer)
            dot_color = '#10b981' if status == 'online' else '#ef4444'
            dot = topo_canvas.create_oval(x + 10, y + 10, x + 28, y + 28, 
                                         fill=dot_color, outline='', tags='status')
            
            # Router icon/label
            icon = topo_canvas.create_text(x + w/2, y + 30, text="📡", 
                                          font=('Segoe UI', 18), tags='icon')
            
            # Router name
            txt = topo_canvas.create_text(x + w/2, y + h/2 + 10, text=name, 
                                         font=('Segoe UI', 11, 'bold'), tags='label')
            
            # IP address
            ip_txt = topo_canvas.create_text(x + w/2, y + h/2 + 28, text=ip, 
                                            font=('Segoe UI', 9), fill='#6b7280', tags='ip')
            
            self._topology_nodes[rid] = {
                'rect': rect, 'shadow': shadow, 'dot': dot, 'icon': icon,
                'text': txt, 'ip_text': ip_txt, 'w': w, 'h': h
            }

        def _center(rid):
            """Get center point of router box."""
            nd = self._topology_nodes[rid]
            x1, y1, x2, y2 = topo_canvas.coords(nd['rect'])
            return (x1 + (x2 - x1)/2, y1 + (y2 - y1)/2)

        # Helper: make orthogonal polyline points between two nodes
        def _connection_points(a, b, bend):
            ax, ay = _center(a)
            bx, by = _center(b)
            bx_bend, by_bend = bend if bend else (None, None)
            if bx_bend is None:
                bx_bend = (ax + bx) / 2
            if by_bend is None:
                by_bend = (ay + by) / 2
            # Manhattan path with two elbows through bend point
            return [
                ax, ay,
                bx_bend, ay,
                bx_bend, by_bend,
                bx, by_bend,
                bx, by
            ], (bx_bend, by_bend)

        def _label_point(points):
            # Use middle segment between bend_y and dest for label
            if len(points) >= 8:
                x1, y1, x2, y2 = points[6], points[7], points[8], points[9]
                return ((x1 + x2) / 2, (y1 + y2) / 2)
            return ((points[0] + points[-2]) / 2, (points[1] + points[-1]) / 2)

        # Helper: create a straight/orthogonal connection
        def _create_straight_connection(a, b):
            bend = bend_lookup.get((a, b))
            pts, bend_point = _connection_points(a, b, bend)
            line = topo_canvas.create_line(*pts, fill='#3b82f6', width=3,
                                           arrow=tk.BOTH, arrowshape=(10, 12, 5),
                                           tags=('connection',))
            bx_bend, by_bend = bend_point
            ctrl = topo_canvas.create_rectangle(bx_bend-6, by_bend-6, bx_bend+6, by_bend+6,
                                                fill='#ffd966', outline='#3b82f6', width=2,
                                                tags=('connection_ctrl',), state='hidden')
            lx, ly = _label_point(pts)
            label_bg = topo_canvas.create_oval(lx-15, ly-15, lx+15, ly+15,
                                              fill='#dbeafe', outline='#3b82f6', width=2,
                                              tags=('connection_label',))
            label_text = topo_canvas.create_text(lx, ly, text='🔗',
                                                font=('Segoe UI', 10),
                                                tags=('connection_label',))

            topo_canvas.tag_lower('connection')
            topo_canvas.tag_raise('connection_ctrl')
            topo_canvas.tag_lower('connection_label')
            topo_canvas.tag_lower('grid')

            self._topology_connections[(a, b)] = {
                'line': line,
                'points': pts,
                'bend': bend_point,
                'ctrl': ctrl,
                'label_bg': label_bg,
                'label_text': label_text,
            }
            self._topology_ctrl_map[ctrl] = (a, b)

            # Bind drag on control to adjust bend
            def _on_ctrl_press(event, pair=(a, b)):
                conn = self._topology_connections.get(pair)
                if conn:
                    conn['drag_off'] = (event.x - conn['bend'][0], event.y - conn['bend'][1])

            def _on_ctrl_drag(event, pair=(a, b)):
                conn = self._topology_connections.get(pair)
                if not conn:
                    return
                offx, offy = conn.get('drag_off', (0, 0))
                new_bx = event.x - offx
                new_by = event.y - offy
                conn['bend'] = (new_bx, new_by)
                pts_new, _ = _connection_points(pair[0], pair[1], conn['bend'])
                conn['points'] = pts_new
                topo_canvas.coords(conn['line'], *pts_new)
                topo_canvas.coords(conn['ctrl'], new_bx-6, new_by-6, new_bx+6, new_by+6)
                lx2, ly2 = _label_point(pts_new)
                topo_canvas.coords(conn['label_bg'], lx2-15, ly2-15, lx2+15, ly2+15)
                topo_canvas.coords(conn['label_text'], lx2, ly2)
                # Persist bend
                update_router_connection_bend(pair[0], pair[1], int(new_bx), int(new_by))

            topo_canvas.tag_bind(ctrl, '<Button-1>', _on_ctrl_press)
            topo_canvas.tag_bind(ctrl, '<B1-Motion>', _on_ctrl_drag)

        # Draw connection wires (orthogonal) for existing pairs
        for a, b in pairs:
            if a in self._topology_nodes and b in self._topology_nodes:
                _create_straight_connection(a, b)
        
        # Load saved shapes from database
        def _load_saved_shapes():
            """Load all saved shapes from database and render them on canvas."""
            from db import get_topology_shapes
            import logging
            logger = logging.getLogger(__name__)
            saved_shapes = get_topology_shapes()
            
            for db_shape in saved_shapes:
                try:
                    shape_id = self._topology_shape_counter
                    self._topology_shape_counter += 1
                    
                    shape_type = db_shape['type']
                    color = db_shape.get('color', '#f59e0b')
                    width = db_shape.get('stroke_width', 2)
                    
                    # Skip shapes with invalid data
                    if db_shape.get('x') is None or db_shape.get('y') is None:
                        continue
                    
                    if shape_type == 'rect':
                        x, y = db_shape['x'], db_shape['y']
                        w, h = db_shape.get('w', 100), db_shape.get('h', 100)
                        
                        # Skip if width or height is None
                        if w is None or h is None:
                            continue
                            
                        x0, y0, x1, y1 = x, y, x + w, y + h
                        fill_color = db_shape.get('fill_color', '')
                        
                        rect = topo_canvas.create_rectangle(
                            x0, y0, x1, y1,
                            outline=color, width=width or 2, fill=fill_color if fill_color else '',
                            tags=('shape', f'shape_{shape_id}')
                        )
                        try:
                            topo_canvas.tag_lower('shape')
                            topo_canvas.tag_lower('grid')
                        except Exception:
                            pass  # Ignore layer reorder errors
                        
                        self._topology_shapes[shape_id] = {
                            'type': 'rectangle',
                            'items': [rect],
                            'data': {'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1, 'color': color, 'width': width or 2, 'fill': fill_color if fill_color else ''},
                            'db_id': db_shape['id']
                        }
                    
                    elif shape_type == 'line':
                        x0, y0 = db_shape['x'], db_shape['y']
                        x1, y1 = db_shape.get('x2'), db_shape.get('y2')
                        
                        # Skip if endpoint coordinates are None
                        if x1 is None or y1 is None:
                            continue
                        
                        line = topo_canvas.create_line(
                            x0, y0, x1, y1,
                            fill=color, width=width or 2,
                            tags=('shape', f'shape_{shape_id}')
                        )
                        try:
                            topo_canvas.tag_lower('shape')
                            topo_canvas.tag_lower('grid')
                        except Exception:
                            pass  # Ignore layer reorder errors
                        
                        self._topology_shapes[shape_id] = {
                            'type': 'line',
                            'items': [line],
                            'data': {'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1, 'color': color, 'width': width or 2},
                            'db_id': db_shape['id']
                        }
                    
                    elif shape_type == 'text':
                        x, y = db_shape['x'], db_shape['y']
                        text = db_shape.get('text', 'Label')
                        size = db_shape.get('stroke_width', 12)  # Using stroke_width for text size
                        
                        # Skip if text is None or empty
                        if not text:
                            text = 'Label'
                        
                        # Ensure size is valid
                        if size is None or size < 8:
                            size = 12
                        
                        text_item = topo_canvas.create_text(
                            x, y,
                            text=text,
                            font=('Segoe UI', int(size), 'bold'),
                            fill=color,
                            tags=('shape', f'shape_{shape_id}')
                        )
                        
                        self._topology_shapes[shape_id] = {
                            'type': 'text',
                            'items': [text_item],
                            'data': {'x': x, 'y': y, 'text': text, 'color': color, 'size': int(size), 'bold': True},
                            'db_id': db_shape['id']
                        }
                except Exception as e:
                    # Skip shapes that can't be loaded
                    logger.warning(f"Could not load shape {db_shape.get('id')}: {e}")
                    continue
        
        # Load shapes after grid and routers are drawn
        _load_saved_shapes()

        def _node_at(event):
            """Find which router node was clicked."""
            items = topo_canvas.find_overlapping(event.x, event.y, event.x, event.y)
            for item in items:
                for rid, nd in self._topology_nodes.items():
                    if item in (nd['rect'], nd['shadow'], nd['dot'], nd['icon'], nd['text'], nd['ip_text']):
                        return rid
            return None
        
        def _shape_at(event):
            """Find which shape was clicked."""
            items = topo_canvas.find_overlapping(event.x, event.y, event.x, event.y)
            for item in items:
                tags = topo_canvas.gettags(item)
                for tag in tags:
                    if tag.startswith('shape_'):
                        shape_id = int(tag.split('_')[1])
                        if shape_id in self._topology_shapes:
                            return shape_id
            return None
        
        def _add_resize_handles(shape_id):
            """Add resize handles to selected shape."""
            if shape_id not in self._topology_shapes:
                return
            
            shape = self._topology_shapes[shape_id]
            shape_type = shape['type']
            
            # Clear existing handles
            _clear_resize_handles()
            
            if shape_type == 'rectangle':
                data = shape['data']
                x0, y0, x1, y1 = data['x0'], data['y0'], data['x1'], data['y1']
                
                # Create 8 handles (corners and midpoints)
                handles = []
                positions = [
                    (x0, y0, 'nw'), (x1, y0, 'ne'), (x0, y1, 'sw'), (x1, y1, 'se'),  # Corners
                    ((x0+x1)/2, y0, 'n'), ((x0+x1)/2, y1, 's'),  # Top/bottom
                    (x0, (y0+y1)/2, 'w'), (x1, (y0+y1)/2, 'e')   # Left/right
                ]
                
                for x, y, cursor in positions:
                    handle = topo_canvas.create_rectangle(
                        x-4, y-4, x+4, y+4,
                        fill='#3b82f6', outline='white', width=2,
                        tags=('resize_handle', f'handle_{cursor}')
                    )
                    handles.append(handle)
                
                self._shape_resize_handles[shape_id] = handles
            
            elif shape_type == 'line':
                data = shape['data']
                x0, y0, x1, y1 = data['x0'], data['y0'], data['x1'], data['y1']
                
                # Create 2 handles (endpoints)
                handles = [
                    topo_canvas.create_oval(
                        x0-4, y0-4, x0+4, y0+4,
                        fill='#3b82f6', outline='white', width=2,
                        tags=('resize_handle', 'handle_start')
                    ),
                    topo_canvas.create_oval(
                        x1-4, y1-4, x1+4, y1+4,
                        fill='#3b82f6', outline='white', width=2,
                        tags=('resize_handle', 'handle_end')
                    )
                ]
                self._shape_resize_handles[shape_id] = handles
        
        def _clear_resize_handles():
            """Remove all resize handles."""
            for handles in self._shape_resize_handles.values():
                for handle in handles:
                    topo_canvas.delete(handle)
            self._shape_resize_handles.clear()
        
        def _handle_at(event):
            """Check if clicking on a resize handle."""
            items = topo_canvas.find_overlapping(event.x, event.y, event.x, event.y)
            for item in items:
                tags = topo_canvas.gettags(item)
                if 'resize_handle' in tags:
                    for tag in tags:
                        if tag.startswith('handle_'):
                            return tag.replace('handle_', '')
            return None

        def _on_press(event):
            """Handle mouse press for router dragging or shape drawing."""
            # 0) Connection bend handle drag (only when edit mode is on)
            if self._topology_edit_mode.get():
                items = topo_canvas.find_overlapping(event.x, event.y, event.x, event.y)
                for it in items:
                    if it in self._topology_ctrl_map:
                        pair = self._topology_ctrl_map[it]
                        conn = self._topology_connections.get(pair)
                        if conn:
                            bx, by = conn.get('bend', (event.x, event.y))
                            self._dragging_ctrl_pair = pair
                            self._dragging_ctrl_off = (event.x - bx, event.y - by)
                            return

            # Check if in edit mode with drawing tool selected
            if self._topology_edit_mode.get() and self._topology_draw_mode.get() != 'select':
                tool = self._topology_draw_mode.get()
                self._topology_drawing = True
                self._topology_draw_start = (event.x, event.y)
                
                # Create temporary preview shape
                if tool == 'rectangle':
                    self._topology_temp_shape = topo_canvas.create_rectangle(
                        event.x, event.y, event.x, event.y,
                        outline='#f59e0b', width=2, dash=(5, 5),
                        tags='temp_shape'
                    )
                elif tool == 'line':
                    self._topology_temp_shape = topo_canvas.create_line(
                        event.x, event.y, event.x, event.y,
                        fill='#f59e0b', width=2, dash=(5, 5),
                        tags='temp_shape'
                    )
                return
            
            # In select mode with edit enabled - check for shape selection/resize
            if self._topology_edit_mode.get() and self._topology_draw_mode.get() == 'select':
                # Check for resize handle first
                handle = _handle_at(event)
                if handle:
                    self._shape_resize_handle = handle
                    self._shape_drag_start = (event.x, event.y)
                    return
                
                # Check for shape selection
                shape_id = _shape_at(event)
                if shape_id is not None:
                    # Deselect previous shape
                    if self._topology_selected_shape is not None and self._topology_selected_shape != shape_id:
                        _clear_resize_handles()
                    
                    # Select this shape
                    self._topology_selected_shape = shape_id
                    self._dragging_shape = shape_id
                    self._shape_drag_start = (event.x, event.y)
                    _add_resize_handles(shape_id)
                    return
                else:
                    # Clicked empty space - deselect
                    self._topology_selected_shape = None
                    _clear_resize_handles()
            
            # Normal router dragging
            rid = _node_at(event)
            if rid is None:
                return
            self._dragging_node = rid
            x1, y1, x2, y2 = topo_canvas.coords(self._topology_nodes[rid]['rect'])
            self._drag_offset = (event.x - x1, event.y - y1)
        
        def _on_right_click(event):
            """Handle right-click for editing router name."""
            if not self._topology_edit_mode.get():
                return
            
            rid = _node_at(event)
            if rid is None:
                return
            
            # Get current router info
            router_info = None
            for r in routers:
                if r['id'] == rid:
                    router_info = r
                    break
            
            if not router_info:
                return
            
            # Create edit dialog
            current_name = router_info.get('name', f"Router {rid}")
            new_name = tk.simpledialog.askstring(
                "Edit Router Name",
                f"Enter new name for router:\nCurrent: {current_name}",
                initialvalue=current_name,
                parent=win
            )
            
            if new_name and new_name.strip() and new_name != current_name:
                # Update database
                try:
                    from router_utils import update_router_name
                    update_router_name(rid, new_name.strip())
                    
                    # Update canvas
                    nd = self._topology_nodes[rid]
                    topo_canvas.itemconfig(nd['text'], text=new_name.strip())
                    
                    messagebox.showinfo("Success", f"Router renamed to: {new_name.strip()}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to rename router: {e}")
        
        def _on_double_click(event):
            """Handle double-click for detailed router editing."""
            if not self._topology_edit_mode.get():
                return
            
            rid = _node_at(event)
            if rid is None:
                return
            
            # Get current router info
            router_info = None
            for r in routers:
                if r['id'] == rid:
                    router_info = r
                    break
            
            if not router_info:
                return
            
            # Create detailed edit dialog
            edit_window = tk.Toplevel(win)
            edit_window.title(f"Edit Router Details - {router_info.get('name', f'Router {rid}')}")
            edit_window.geometry("400x300")
            edit_window.resizable(False, False)
            edit_window.transient(win)
            edit_window.grab_set()
            
            # Center the window
            edit_window.update_idletasks()
            x = (edit_window.winfo_screenwidth() - 400) // 2
            y = (edit_window.winfo_screenheight() - 300) // 2
            edit_window.geometry(f"400x300+{x}+{y}")
            
            frame = tb.Frame(edit_window, padding=20)
            frame.pack(fill='both', expand=True)
            
            tb.Label(frame, text="Router Details", font=('Segoe UI', 14, 'bold')).pack(pady=(0, 15))
            
            # Name field
            tb.Label(frame, text="Router Name:", font=('Segoe UI', 10)).pack(anchor='w')
            name_var = tk.StringVar(value=router_info.get('name', f"Router {rid}"))
            name_entry = tb.Entry(frame, textvariable=name_var, font=('Segoe UI', 10))
            name_entry.pack(fill='x', pady=(0, 10))
            
            # IP field
            tb.Label(frame, text="IP Address:", font=('Segoe UI', 10)).pack(anchor='w')
            ip_var = tk.StringVar(value=router_info.get('ip_address', ''))
            ip_entry = tb.Entry(frame, textvariable=ip_var, font=('Segoe UI', 10))
            ip_entry.pack(fill='x', pady=(0, 10))
            
            # Location field
            tb.Label(frame, text="Location/Building:", font=('Segoe UI', 10)).pack(anchor='w')
            location_var = tk.StringVar(value=router_info.get('location', ''))
            location_entry = tb.Entry(frame, textvariable=location_var, font=('Segoe UI', 10))
            location_entry.pack(fill='x', pady=(0, 15))
            
            def save_changes():
                try:
                    from router_utils import update_router_details
                    
                    new_name = name_var.get().strip()
                    new_ip = ip_var.get().strip()
                    new_location = location_var.get().strip()
                    
                    if not new_name:
                        messagebox.showwarning("Validation", "Router name cannot be empty!")
                        return
                    
                    if not new_ip:
                        messagebox.showwarning("Validation", "IP address cannot be empty!")
                        return
                    
                    # Update database
                    update_router_details(rid, new_name, new_ip, new_location)
                    
                    # Update canvas
                    nd = self._topology_nodes[rid]
                    topo_canvas.itemconfig(nd['text'], text=new_name)
                    topo_canvas.itemconfig(nd['ip_text'], text=new_ip)
                    
                    messagebox.showinfo("Success", "Router details updated successfully!")
                    edit_window.destroy()
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update router: {e}")
            
            # Buttons
            btn_frame = tb.Frame(frame)
            btn_frame.pack(fill='x', pady=(10, 0))
            
            tb.Button(btn_frame, text="Cancel", bootstyle='secondary', 
                     command=edit_window.destroy).pack(side='right', padx=(10, 0))
            tb.Button(btn_frame, text="Save Changes", bootstyle='success', 
                     command=save_changes).pack(side='right')

        def _on_motion(event):
            """Handle mouse motion for router dragging or shape preview."""
            # Check if canvas still exists
            if not topo_canvas.winfo_exists():
                return

            # Dragging a connection bend handle
            if self._dragging_ctrl_pair is not None:
                pair = self._dragging_ctrl_pair
                conn = self._topology_connections.get(pair)
                if conn:
                    offx, offy = self._dragging_ctrl_off
                    new_bx = event.x - offx
                    new_by = event.y - offy
                    conn['bend'] = (new_bx, new_by)
                    pts_new, _ = _connection_points(pair[0], pair[1], conn['bend'])
                    conn['points'] = pts_new
                    topo_canvas.coords(conn['line'], *pts_new)
                    topo_canvas.coords(conn['ctrl'], new_bx-6, new_by-6, new_bx+6, new_by+6)
                    lx2, ly2 = _label_point(pts_new)
                    topo_canvas.coords(conn['label_bg'], lx2-15, ly2-15, lx2+15, ly2+15)
                    topo_canvas.coords(conn['label_text'], lx2, ly2)
                    update_router_connection_bend(pair[0], pair[1], int(new_bx), int(new_by))
                return
                
            # Drawing mode - update temporary shape preview
            if self._topology_drawing and self._topology_temp_shape:
                tool = self._topology_draw_mode.get()
                x0, y0 = self._topology_draw_start
                
                try:
                    if tool == 'rectangle':
                        topo_canvas.coords(self._topology_temp_shape, x0, y0, event.x, event.y)
                    elif tool == 'line':
                        topo_canvas.coords(self._topology_temp_shape, x0, y0, event.x, event.y)
                except Exception:
                    pass  # Ignore if canvas item doesn't exist
                return
            
            # Shape resizing mode
            if self._shape_resize_handle and self._topology_selected_shape is not None:
                shape_id = self._topology_selected_shape
                shape = self._topology_shapes.get(shape_id)
                if not shape:
                    return
                    
                dx = event.x - self._shape_drag_start[0]
                dy = event.y - self._shape_drag_start[1]
                
                if shape['type'] == 'rectangle':
                    data = shape['data']
                    x0, y0, x1, y1 = data['x0'], data['y0'], data['x1'], data['y1']
                    handle = self._shape_resize_handle
                    
                    # Update coordinates based on handle
                    if 'n' in handle:
                        y0 += dy
                    if 's' in handle:
                        y1 += dy
                    if 'w' in handle:
                        x0 += dx
                    if 'e' in handle:
                        x1 += dx
                    
                    # Update shape
                    try:
                        topo_canvas.coords(shape['items'][0], x0, y0, x1, y1)
                        data.update({'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1})
                    except Exception:
                        return  # Canvas item no longer exists
                    self._shape_drag_start = (event.x, event.y)
                    
                    # Update database
                    if 'db_id' in shape:
                        from db import update_topology_shape
                        update_topology_shape(
                            shape['db_id'],
                            x=int(min(x0, x1)), y=int(min(y0, y1)),
                            w=int(abs(x1-x0)), h=int(abs(y1-y0))
                        )
                    
                    # Update handles
                    _add_resize_handles(shape_id)
                
                elif shape['type'] == 'line':
                    data = shape['data']
                    if self._shape_resize_handle == 'start':
                        data['x0'] = event.x
                        data['y0'] = event.y
                    elif self._shape_resize_handle == 'end':
                        data['x1'] = event.x
                        data['y1'] = event.y
                    
                    topo_canvas.coords(shape['items'][0], data['x0'], data['y0'], data['x1'], data['y1'])
                    
                    # Update database
                    if 'db_id' in shape:
                        from db import update_topology_shape
                        update_topology_shape(
                            shape['db_id'],
                            x=int(data['x0']), y=int(data['y0']),
                            x2=int(data['x1']), y2=int(data['y1'])
                        )
                    
                    _add_resize_handles(shape_id)
                return
            
            # Shape dragging mode (move entire shape)
            if self._dragging_shape is not None and self._shape_drag_start:
                dx = event.x - self._shape_drag_start[0]
                dy = event.y - self._shape_drag_start[1]
                
                shape = self._topology_shapes[self._dragging_shape]
                
                # Move all shape items
                for item in shape['items']:
                    topo_canvas.move(item, dx, dy)
                
                # Update shape data
                data = shape['data']
                if shape['type'] == 'rectangle':
                    data['x0'] += dx
                    data['y0'] += dy
                    data['x1'] += dx
                    data['y1'] += dy
                    # Update database
                    if 'db_id' in shape:
                        from db import update_topology_shape
                        update_topology_shape(
                            shape['db_id'],
                            x=int(min(data['x0'], data['x1'])), y=int(min(data['y0'], data['y1']))
                        )
                elif shape['type'] == 'line':
                    data['x0'] += dx
                    data['y0'] += dy
                    data['x1'] += dx
                    data['y1'] += dy
                    # Update database
                    if 'db_id' in shape:
                        from db import update_topology_shape
                        update_topology_shape(
                            shape['db_id'],
                            x=int(data['x0']), y=int(data['y0']),
                            x2=int(data['x1']), y2=int(data['y1'])
                        )
                elif shape['type'] == 'text':
                    data['x'] += dx
                    data['y'] += dy
                    # Update database
                    if 'db_id' in shape:
                        from db import update_topology_shape
                        update_topology_shape(
                            shape['db_id'],
                            x=int(data['x']), y=int(data['y'])
                        )
                
                self._shape_drag_start = (event.x, event.y)
                
                # Update resize handles
                if self._topology_selected_shape == self._dragging_shape:
                    _add_resize_handles(self._dragging_shape)
                return
            
            # Normal router dragging
            if self._dragging_node is None:
                return
            
            # Check if canvas still exists
            if not topo_canvas.winfo_exists():
                return
                
            nd = self._topology_nodes[self._dragging_node]
            try:
                x1, y1, x2, y2 = topo_canvas.coords(nd['rect'])
            except Exception:
                return  # Canvas item no longer exists
                
            nx1 = event.x - self._drag_offset[0]
            ny1 = event.y - self._drag_offset[1]
            dx = nx1 - x1
            dy = ny1 - y1
            
            # Move all router elements together
            try:
                for key in ('rect', 'shadow', 'dot', 'icon', 'text', 'ip_text'):
                    topo_canvas.move(nd[key], dx, dy)
            except Exception:
                return  # Canvas items no longer exist
            
            # Update connected wires (orthogonal polyline)
            try:
                for (a, b), conn_items in self._topology_connections.items():
                    if a == self._dragging_node or b == self._dragging_node:
                        bend = conn_items.get('bend')
                        pts = None
                        if bend:
                            pts, _ = _connection_points(a, b, bend)
                        else:
                            pts, bend = _connection_points(a, b, None)
                        conn_items['points'] = pts
                        conn_items['bend'] = bend
                        topo_canvas.coords(conn_items['line'], *pts)
                        bx_b, by_b = bend
                        if 'ctrl' in conn_items:
                            topo_canvas.coords(conn_items['ctrl'], bx_b-6, by_b-6, bx_b+6, by_b+6)
                        lx, ly = _label_point(pts)
                        topo_canvas.coords(conn_items['label_bg'], lx - 15, ly - 15, lx + 15, ly + 15)
                        topo_canvas.coords(conn_items['label_text'], lx, ly)
            except Exception:
                pass  # Ignore connection update errors
            
            try:
                topo_canvas.configure(scrollregion=topo_canvas.bbox('all'))
            except Exception:
                pass  # Ignore scroll region update errors

        def _on_release(event):
            """Handle mouse release - save position, finalize shapes, or handle connections."""
            # Finish bend drag
            if self._dragging_ctrl_pair is not None:
                self._dragging_ctrl_pair = None
                self._dragging_ctrl_off = (0, 0)
                return
            # Drawing mode - finalize shape
            if self._topology_drawing:
                tool = self._topology_draw_mode.get()
                x0, y0 = self._topology_draw_start
                x1, y1 = event.x, event.y
                
                # Delete temporary preview
                if self._topology_temp_shape:
                    topo_canvas.delete(self._topology_temp_shape)
                    self._topology_temp_shape = None
                
                # Only create if dragged significantly (>10 pixels)
                if abs(x1 - x0) > 10 or abs(y1 - y0) > 10:
                    shape_id = self._topology_shape_counter
                    self._topology_shape_counter += 1
                    
                    color = self._topology_draw_color.get()
                    width = self._topology_line_width.get()
                    
                    if tool == 'rectangle':
                        # Create permanent rectangle with selected settings
                        fill_color = self._topology_fill_color.get() if self._topology_fill_enabled.get() else ''
                        rect = topo_canvas.create_rectangle(
                            x0, y0, x1, y1,
                            outline=color, width=width, fill=fill_color,
                            tags=('shape', f'shape_{shape_id}')
                        )
                        # Lower behind routers but above grid
                        try:
                            topo_canvas.tag_lower('shape')
                            topo_canvas.tag_lower('grid')
                        except Exception:
                            pass  # Ignore layer reorder errors
                        
                        # Save to database
                        from db import insert_topology_shape
                        db_id = insert_topology_shape(
                            shape_type='rect',
                            x=int(min(x0, x1)), y=int(min(y0, y1)),
                            w=int(abs(x1-x0)), h=int(abs(y1-y0)),
                            color=color, fill_color=fill_color if fill_color else None, stroke_width=width
                        )
                        
                        self._topology_shapes[shape_id] = {
                            'type': 'rectangle',
                            'items': [rect],
                            'data': {'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1, 'color': color, 'width': width, 'fill': fill_color},
                            'db_id': db_id
                        }
                    
                    elif tool == 'line':
                        # Create permanent line with selected settings
                        line = topo_canvas.create_line(
                            x0, y0, x1, y1,
                            fill=color, width=width,
                            tags=('shape', f'shape_{shape_id}')
                        )
                        try:
                            topo_canvas.tag_lower('shape')
                            topo_canvas.tag_lower('grid')
                        except Exception:
                            pass  # Ignore layer reorder errors
                        
                        # Save to database
                        from db import insert_topology_shape
                        db_id = insert_topology_shape(
                            shape_type='line',
                            x=int(x0), y=int(y0),
                            x2=int(x1), y2=int(y1),
                            color=color, stroke_width=width
                        )
                        
                        self._topology_shapes[shape_id] = {
                            'type': 'line',
                            'items': [line],
                            'data': {'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1, 'color': color, 'width': width},
                            'db_id': db_id
                        }
                
                self._topology_drawing = False
                self._topology_draw_start = None
                return
            
            # Reset shape dragging/resizing
            if self._dragging_shape is not None or self._shape_resize_handle is not None:
                self._dragging_shape = None
                self._shape_resize_handle = None
                self._shape_drag_start = None
                return
            
            # Text tool - prompt for text input
            if self._topology_edit_mode.get() and self._topology_draw_mode.get() == 'text':
                text_input = tk.simpledialog.askstring(
                    "Add Text Label",
                    "Enter label text:",
                    parent=win
                )
                
                if text_input and text_input.strip():
                    shape_id = self._topology_shape_counter
                    self._topology_shape_counter += 1
                    
                    color = self._topology_draw_color.get()
                    size = self._topology_text_size.get()
                    bold = self._topology_text_bold.get()
                    font_weight = 'bold' if bold else 'normal'
                    
                    # Create text label with selected settings
                    text_item = topo_canvas.create_text(
                        event.x, event.y,
                        text=text_input.strip(),
                        font=('Segoe UI', size, font_weight),
                        fill=color,
                        tags=('shape', f'shape_{shape_id}')
                    )
                    
                    # Save to database
                    from db import insert_topology_shape
                    db_id = insert_topology_shape(
                        shape_type='text',
                        x=int(event.x), y=int(event.y),
                        text=text_input.strip(),
                        color=color, stroke_width=size
                    )
                    
                    self._topology_shapes[shape_id] = {
                        'type': 'text',
                        'items': [text_item],
                        'data': {'x': event.x, 'y': event.y, 'text': text_input.strip(), 'color': color, 'size': size, 'bold': bold},
                        'db_id': db_id
                    }
                return
            
            # Normal router handling
            if self._dragging_node is not None:
                nd = self._topology_nodes[self._dragging_node]
                x1, y1, x2, y2 = topo_canvas.coords(nd['rect'])
                update_router_position(self._dragging_node, int(x1), int(y1))
            
            # Router connection logic - ONLY when edit mode is OFF
            if not self._topology_edit_mode.get():
                rid = _node_at(event)
                if rid is not None and self._dragging_node == rid:
                    # Handle selection and connection logic
                    if self._topology_selected is None:
                        # Select first router
                        self._topology_selected = rid
                        topo_canvas.itemconfig(self._topology_nodes[rid]['rect'], 
                                              outline='#3b82f6', width=3)
                        topo_canvas.itemconfig(self._topology_nodes[rid]['shadow'], fill='#93c5fd')
                    elif self._topology_selected == rid:
                        # Deselect if same router clicked again
                        topo_canvas.itemconfig(self._topology_nodes[rid]['rect'], 
                                              outline='#6b7280', width=2)
                        topo_canvas.itemconfig(self._topology_nodes[rid]['shadow'], fill='#d1d5db')
                        self._topology_selected = None
                    else:
                        # Connect/disconnect two routers
                        a, b = sorted([self._topology_selected, rid])
                        pair = (a, b)
                        
                        if pair in self._topology_connections:
                            # Remove existing connection
                            conn = self._topology_connections[pair]
                            topo_canvas.delete(conn['line'])
                            topo_canvas.delete(conn['label_bg'])
                            topo_canvas.delete(conn['label_text'])
                            remove_router_connection(a, b)
                            del self._topology_connections[pair]
                            messagebox.showinfo("Connection", 
                                              f"Removed connection between routers")
                        else:
                            # Add new connection
                            ax, ay = _center(a)
                            bx, by = _center(b)
                            mid_x, mid_y = (ax + bx) / 2, (ay + by) / 2
                            
                            # Create straight/orthogonal connection for new pair
                            _create_straight_connection(a, b)
                            # Default bend at midpoint; persist
                            mid_bx = (ax + bx) / 2
                            mid_by = (ay + by) / 2
                            add_router_connection(a, b, bend_x=int(mid_bx), bend_y=int(mid_by))
                            bend_lookup[(a, b)] = (mid_bx, mid_by)
                            messagebox.showinfo("Connection", 
                                              f"Created connection between routers")
                        
                        # Deselect first router
                        topo_canvas.itemconfig(self._topology_nodes[self._topology_selected]['rect'], 
                                              outline='#6b7280', width=2)
                        topo_canvas.itemconfig(self._topology_nodes[self._topology_selected]['shadow'], 
                                              fill='#d1d5db')
                        self._topology_selected = None
            
            self._dragging_node = None
        
        def _on_shape_right_click(event):
            """Handle right-click on shapes to delete them."""
            if not self._topology_edit_mode.get():
                return
            
            # Find which shape was clicked
            items = topo_canvas.find_overlapping(event.x, event.y, event.x, event.y)
            for item in items:
                # Check if this item belongs to a shape
                tags = topo_canvas.gettags(item)
                for tag in tags:
                    if tag.startswith('shape_'):
                        shape_id = int(tag.split('_')[1])
                        if shape_id in self._topology_shapes:
                            # Confirm deletion
                            if messagebox.askyesno("Delete Shape", 
                                                  "Delete this shape/label?",
                                                  parent=win):
                                # Delete from database
                                if 'db_id' in self._topology_shapes[shape_id]:
                                    from db import delete_topology_shape
                                    delete_topology_shape(self._topology_shapes[shape_id]['db_id'])
                                
                                # Delete all canvas items for this shape
                                for canvas_item in self._topology_shapes[shape_id]['items']:
                                    topo_canvas.delete(canvas_item)
                                # Remove from data store
                                del self._topology_shapes[shape_id]
                            return
        
        def _on_escape(event):
            """Handle ESC key to cancel drawing operation."""
            if self._topology_drawing:
                # Cancel drawing
                if self._topology_temp_shape:
                    topo_canvas.delete(self._topology_temp_shape)
                    self._topology_temp_shape = None
                self._topology_drawing = False
                self._topology_draw_start = None

        topo_canvas.bind('<ButtonPress-1>', _on_press)
        topo_canvas.bind('<B1-Motion>', _on_motion)
        topo_canvas.bind('<ButtonRelease-1>', _on_release)
        topo_canvas.bind('<Button-3>', _on_right_click)  # Right-click to rename router
        topo_canvas.bind('<Double-Button-1>', _on_double_click)  # Double-click to edit details
        win.bind('<Escape>', _on_escape)  # ESC to cancel drawing
        
        # Add right-click handler for shapes (must be after router right-click)
        def _on_canvas_right_click(event):
            """Route right-click to either shape or router handler."""
            # Check if clicking on a shape first
            items = topo_canvas.find_overlapping(event.x, event.y, event.x, event.y)
            for item in items:
                tags = topo_canvas.gettags(item)
                for tag in tags:
                    if tag.startswith('shape_'):
                        _on_shape_right_click(event)
                        return
            # Otherwise, handle as router right-click
            _on_right_click(event)
        
        topo_canvas.bind('<Button-3>', _on_canvas_right_click)
        topo_canvas.configure(scrollregion=topo_canvas.bbox('all'))

        def _auto_loop():
            if not win.winfo_exists():
                return
            if self._topology_auto_refresh.get():
                self._topology_refresh_status()
            win.after(5000, _auto_loop)
        _auto_loop()

    def _topology_refresh_status(self):
        """Update node status colors by actually pinging routers (non-blocking)."""
        if not hasattr(self, '_topology_canvas') or not self._topology_canvas:
            return
        
        def refresh_in_thread():
            """Background thread to ping routers and update colors."""
            try:
                from router_utils import get_routers, is_online
                routers = get_routers() or []
                
                # Check actual online status for each router
                status_updates = {}
                for r in routers:
                    rid = r['id']
                    ip = r.get('ip_address', '0.0.0.0')
                    is_up = is_online(ip)
                    status_updates[rid] = 'online' if is_up else 'offline'
                
                # Update UI in main thread
                def update_ui():
                    if not hasattr(self, '_topology_canvas') or not self._topology_canvas:
                        return
                    try:
                        for rid, status in status_updates.items():
                            if rid in self._topology_nodes:
                                nd = self._topology_nodes[rid]
                                color = '#10b981' if status == 'online' else '#ef4444'
                                self._topology_canvas.itemconfig(nd['dot'], fill=color)
                        # Ensure layering remains correct after refresh
                        self._topology_reorder_layers()
                    except Exception as e:
                        print(f"UI update error: {e}")
                
                self.root.after(0, update_ui)
                
            except Exception as e:
                print(f"Topology refresh error: {e}")
        
        # Run in background thread to avoid blocking UI
        import threading
        threading.Thread(target=refresh_in_thread, daemon=True).start()
    
    def _topology_set_zoom(self, zoom_percent):
        """Set zoom to specific percentage value."""
        if not hasattr(self, '_topology_zoom_slider'):
            return
        
        # Clamp between 25% and 300%
        zoom_percent = max(25, min(300, zoom_percent))
        
        # Update slider
        self._topology_zoom_slider.set(zoom_percent)
    
    def _topology_apply_zoom(self, zoom_percent):
        """Apply zoom transformation based on slider value."""
        if not hasattr(self, '_topology_canvas') or not self._topology_canvas:
            return
        
        canvas = self._topology_canvas
        
        # Check if canvas still exists (window not closed)
        try:
            if not canvas.winfo_exists():
                return
        except:
            return
        
        # Get current zoom level
        if not hasattr(self, '_topology_current_zoom'):
            self._topology_current_zoom = 100.0
        
        # Calculate scale factor
        factor = zoom_percent / self._topology_current_zoom
        
        # Update zoom label
        if hasattr(self, '_topology_zoom_var'):
            try:
                self._topology_zoom_var.set(f"{int(zoom_percent)}%")
            except:
                pass
        
        try:
            # Get canvas center for zoom origin
            canvas.update_idletasks()
            canvas_width = canvas.winfo_width()
            canvas_height = canvas.winfo_height()
            cx = canvas_width / 2
            cy = canvas_height / 2
            
            # Convert to canvas coordinates
            cx_canvas = canvas.canvasx(cx)
            cy_canvas = canvas.canvasy(cy)
            
            # Scale all items from center
            canvas.scale('all', cx_canvas, cy_canvas, factor, factor)
            
            # Update current zoom
            self._topology_current_zoom = zoom_percent
            
            # Update scroll region
            canvas.configure(scrollregion=canvas.bbox('all'))
        except:
            # Canvas destroyed or window closed
            pass
    
    def _topology_zoom_reset(self):
        """Reset zoom to 100%."""
        if not hasattr(self, '_topology_canvas') or not self._topology_canvas:
            return
        
        # Calculate reset factor
        if hasattr(self, '_topology_zoom_level') and self._topology_zoom_level != 0:
            reset_factor = 1.0 / self._topology_zoom_level
            self._topology_zoom_level = 1.0
            
            # Update label
            if hasattr(self, '_topology_zoom_var'):
                self._topology_zoom_var.set("100%")
            
            # Scale back to 100%
            canvas = self._topology_canvas
            canvas.update_idletasks()
            canvas_width = canvas.winfo_width()
            canvas_height = canvas.winfo_height()
            cx = canvas_width / 2
            cy = canvas_height / 2
            cx_canvas = canvas.canvasx(cx)
            cy_canvas = canvas.canvasy(cy)
            
            canvas.scale('all', cx_canvas, cy_canvas, reset_factor, reset_factor)
            canvas.configure(scrollregion=canvas.bbox('all'))
    
    def _topology_reorder_layers(self):
        """Enforce proper layering: lines -> shapes -> text labels -> routers."""
        if not hasattr(self, '_topology_canvas') or not self._topology_canvas:
            return
        try:
            c = self._topology_canvas
            # Lower connection lines first
            for line_id in self._topology_connections.values():
                c.tag_lower(line_id)
            # Lower shape lines
            for sid, data in self._topology_shapes.items():
                if data['type'] == 'line':
                    c.tag_lower(data['main'])
            # Raise shapes (rect, circle)
            for sid, data in self._topology_shapes.items():
                if data['type'] in ('rect', 'circle'):
                    c.tag_raise(data['main'])
            # Raise text labels
            for sid, data in self._topology_shapes.items():
                if data['type'] == 'text':
                    if 'hitbox' in data:
                        c.tag_raise(data['hitbox'])
                    c.tag_raise(data['main'])
            # Raise routers to top
            for rid, nd in self._topology_nodes.items():
                for key in ('rect', 'dot', 'text', 'ip_text'):
                    c.tag_raise(nd[key])
        except Exception as e:
            print(f"Layer reorder error: {e}")

    def logout(self):
        """Log out to the login screen without exiting the application."""
        if not messagebox.askyesno("Log Out", "Are you sure you want to log out?"):
            return

        # Log logout activity to activity_logs
        try:
            if self.current_user and self.current_user.get('id'):
                from device_utils import get_device_info
                device_info = get_device_info()
                log_activity(
                    user_id=self.current_user.get('id'),
                    action='Logout',
                    target=None,
                    ip_address=device_info.get('ip_address')
                )
        except Exception as e:
            print(f"Error logging logout activity: {e}")
        
        # Update login_sessions table
        try:
            if self.current_user and self.current_user.get('id'):
                log_user_logout(self.current_user.get('id'))
        except Exception as e:
            print(f"Error updating login session: {e}")

        # Stop background tasks BEFORE destroying window
        self.app_running = False
        
        # Don't set _report_cancel_requested here to avoid "Cancelled" message
        # The app_running flag will stop background tasks gracefully
        
        # Cancel all scheduled after() jobs
        jobs_to_cancel = [
            'update_task',
            'unifi_refresh_job',
            'routers_refresh_job',
            'dashboard_refresh_job',
            'report_auto_update_job',
            'bandwidth_auto_update_job',
            '_unifi_bandwidth_job',
            '_bandwidth_hide_after_job',
            '_reports_hide_after_job',
        ]
        
        for job_name in jobs_to_cancel:
            try:
                job = getattr(self, job_name, None)
                if job:
                    self.root.after_cancel(job)
                    setattr(self, job_name, None)
            except Exception:
                pass
        
        try:
            self.stop_loop_detection()
        except Exception:
            pass
        
        # Stop UniFi auto-refresh
        try:
            self._stop_unifi_auto_refresh()
        except Exception:
            pass
        
        # Stop routers auto-refresh
        try:
            self.stop_routers_auto_refresh()
        except Exception:
            pass

        # Give a brief moment for tasks to cancel
        try:
            self.root.update()
        except Exception:
            pass

        # Keep a handle to the hidden login root
        master = getattr(self.root, 'master', None)

        # Close the admin window
        try:
            self.root.destroy()
        except Exception:
            pass

        # Re-open login on the master root window
        try:
            if master and not master.winfo_exists():
                return  # Master already destroyed; nothing else to do
        except Exception:
            master = None

        try:
            if master:
                try:
                    master.deiconify()
                except Exception:
                    pass
                from login import show_login
                # Clear any previous children in the root and rebuild the login UI
                for child in master.winfo_children():
                    try:
                        child.destroy()
                    except Exception:
                        pass
                show_login(master)
        except Exception:
            pass


def show_dashboard(root, current_user, api_base_url="http://localhost:5000"):
    Dashboard(root, current_user, api_base_url)
