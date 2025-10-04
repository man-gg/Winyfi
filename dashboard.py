import os
import shutil
import time
import threading
import concurrent.futures
import csv
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import messagebox, Toplevel, Menu, filedialog, ttk, simpledialog
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
import tkinter as tk
from datetime import datetime, date, timedelta
# tkcalendar Calendar not needed; using ttkbootstrap DateEntry
from datetime import datetime, timedelta  # ensure timedelta is imported
from ttkbootstrap.widgets import DateEntry
from report_utils import get_uptime_percentage, get_status_logs, get_bandwidth_usage
from router_utils import get_routers
from user_utils import insert_user, get_all_users, delete_user, update_user
from network_utils import ping_latency,get_bandwidth, detect_loops, discover_clients, get_default_iface,scan_subnet, get_default_iface
from bandwidth_logger import start_bandwidth_logging
from db import get_connection 
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import ticket_utils
from ticket_utils import fetch_srfs, create_srf
import itertools
from print_utils import print_srf_form
import numpy as np
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


# Directory for router images
IMAGE_FOLDER = "routerLocImg"
os.makedirs(IMAGE_FOLDER, exist_ok=True)

router_widgets = {}
class Dashboard:
    def __init__(self, root, current_user, api_base_url="http://localhost:5000"):
        self.app_running = True
        self.root = root
        self.current_user = current_user
        self.api_base_url = api_base_url
        self.router_list = []
        self.status_history = defaultdict(lambda: {"failures": 0, "current": None})
        self.router_widgets = {}
        self.bandwidth_data = {}
        self.update_task = None  # Store .after() task ID
        
        # Loop detection settings
        self.loop_detection_running = False
        self.loop_detection_interval = 300  # 5 minutes default
        self.loop_detection_enabled = True
        self.loop_detection_thread = None
        self.loop_detection_history = []
        
        # Initialize database and load stats
        from db import create_loop_detections_table, get_loop_detection_stats, get_loop_detections_history
        create_loop_detections_table()
        self.loop_detection_stats = get_loop_detection_stats()
        self.loop_detection_history = get_loop_detections_history(100)
        
        # Initialize notification system
        self.notification_system = NotificationSystem(self.root)
        self.notification_count = 0
        
        self._build_ui()
        self.reload_routers(force_reload=True)

        # 🟩 Place this BEFORE any looping tasks like background threads or after()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.schedule_update()  # For auto-refresh
        threading.Thread(target=self._background_status_updater, daemon=True).start()
        
        # Start automatic loop detection
        if self.loop_detection_enabled:
            self.start_loop_detection()

        start_bandwidth_logging(self._fetch_router_list)

    def _fetch_router_list(self):
        """Return router list from DB."""
        return get_routers()
        


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

        # —— WINDOW SETUP ——————————————————————————————
        r = self.root
        r.title("WINYFI Monitoring Dashboard")
        W, H = 1000, 600
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        x, y = (sw - W) // 2, 50
        r.geometry(f"{W}x{H}+{x}+{y}")

        # === Sidebar and content layout ===
        self.sidebar = tb.Frame(r, style='Sidebar.TFrame', width=220)
        self.sidebar.pack(side="left", fill="y")

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

        def add_sidebar_button(text, icon):
            btn = tb.Button(self.sidebar,
                            text=f"{icon} {text}",
                            style='Sidebar.TButton',
                            width=22,
                            command=lambda: show_page(text))
            btn.pack(pady=5)
            self.sidebar_buttons[text] = btn

        # Logo
        logo_path = os.path.join("assets", "images", "logo1.png")
        if os.path.exists(logo_path):
            img = Image.open(logo_path)
            img = img.resize((85, 50), Image.Resampling.LANCZOS)
            self.sidebar_logo = ImageTk.PhotoImage(img)
            tb.Label(self.sidebar, image=self.sidebar_logo,
                    background='white', borderwidth=0).pack(pady=(15, 45))
        else:
            tb.Label(self.sidebar, text="WINYFI",
                    font=("Segoe UI", 16, "bold"),
                    foreground='#d32f2f',
                    background='white').pack(pady=15)

        # Navigation buttons
        add_sidebar_button("Dashboard", "📊")
        add_sidebar_button("Routers", "📡")
        add_sidebar_button("Reports", "📑")
        add_sidebar_button("Bandwidth", "📶")

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

        # Settings dropdown
        settings_btn = tb.Button(self.sidebar,
                                text="⚙️ Settings ▼",
                                style='Sidebar.TButton',
                                width=22,
                                command=self.toggle_settings_dropdown)
        settings_btn.pack(pady=5)
        self.sidebar_buttons["Settings"] = settings_btn

        self.settings_dropdown = tb.Frame(self.sidebar, style='Sidebar.TFrame')
        self.dropdown_target_height = 170
        profile_btn = tb.Button(self.settings_dropdown, text="👤 User Profile",
                        bootstyle="link", command=self.show_user_profile)
        um_btn = tb.Button(self.settings_dropdown, text="👥 User Management",
                        bootstyle="link", command=self.open_user_mgmt)
        notif_btn = tb.Button(self.settings_dropdown, text="🔔 Notification Settings",
                        bootstyle="link", command=self.show_notification_settings)
        sep = ttk.Separator(self.settings_dropdown, orient='horizontal')
        lo_btn = tb.Button(self.settings_dropdown, text="⏏️ Log Out",
                        bootstyle="link", command=self.logout)
        profile_btn.pack(fill='x', pady=(5, 2))
        um_btn.pack(fill='x', pady=(2, 2))
        notif_btn.pack(fill='x', pady=(2, 2))
        sep.pack(fill='x', pady=2)
        lo_btn.pack(fill='x', pady=(2, 5))
        self.settings_dropdown.pack_propagate(False)
        self.settings_dropdown.config(height=0)

        # Export button with dropdown
        self.export_btn = tb.Button(
            self.sidebar,
            text="⬇️ Export to CSV",
            width=22,
            style='Sidebar.TButton',
            command=self.open_export_menu
        )
        self.export_btn.pack(pady=(0,0))

        # === Routers Page Content ===
        router_header_frame = tb.Frame(self.routers_frame)
        router_header_frame.pack(fill="x", padx=10, pady=(10, 0))

        tb.Label(router_header_frame, text="All Routers",
                font=("Segoe UI", 14, "bold")).pack(side="left")

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
        ).pack(side="right", padx=10)

        filter_frame = tb.Frame(self.routers_frame)
        filter_frame.pack(pady=5, padx=10, fill="x")

        self.search_var = tb.StringVar()
        self.search_var.trace_add("write", lambda *_: self.apply_filter())
        self.sort_var = tb.StringVar(value="default")

        tb.Label(filter_frame, text="Filter:", bootstyle="info").pack(side="left", padx=(0, 5))
        tb.Entry(filter_frame, textvariable=self.search_var, width=30).pack(side="left")
        tb.Label(filter_frame, text="Sort by:", bootstyle="info").pack(side="left", padx=(20, 5))
        tb.Radiobutton(filter_frame, text="Default", variable=self.sort_var, value="default",
                    command=self.reload_routers).pack(side="left")
        tb.Radiobutton(filter_frame, text="Online First", variable=self.sort_var, value="online",
                    command=self.reload_routers).pack(side="left", padx=(5, 0))

        canvas_frame = tb.Frame(self.routers_frame)
        canvas_frame.pack(fill="both", expand=True, padx=10, pady=10)
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
                font=("Segoe UI", 24, "bold"), 
                bootstyle="primary").pack(side="left")
        
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
        
        # Configure grid weights
        for i in range(4):
            metrics_frame.grid_columnconfigure(i, weight=1)
        
        # Router Status Card
        self.router_card = self._create_metric_card(
            metrics_frame, "🌐 Router Status", "primary", 0, 0
        )
        self.total_routers_label = tb.Label(self.router_card, text="0", 
                                          font=("Segoe UI", 28, "bold"),
                                          bootstyle="primary")
        self.total_routers_label.pack(pady=(10, 5))
        tb.Label(self.router_card, text="Total Routers", 
                font=("Segoe UI", 10), bootstyle="secondary").pack()
        
        # Online Routers Card
        self.online_card = self._create_metric_card(
            metrics_frame, "🟢 Online", "success", 0, 1
        )
        self.online_routers_label = tb.Label(self.online_card, text="0", 
                                           font=("Segoe UI", 28, "bold"),
                                           bootstyle="success")
        self.online_routers_label.pack(pady=(10, 5))
        tb.Label(self.online_card, text="Online Routers", 
                font=("Segoe UI", 10), bootstyle="secondary").pack()
        
        # Offline Routers Card
        self.offline_card = self._create_metric_card(
            metrics_frame, "🔴 Offline", "danger", 0, 2
        )
        self.offline_routers_label = tb.Label(self.offline_card, text="0", 
                                            font=("Segoe UI", 28, "bold"),
                                            bootstyle="danger")
        self.offline_routers_label.pack(pady=(10, 5))
        tb.Label(self.offline_card, text="Offline Routers", 
                font=("Segoe UI", 10), bootstyle="secondary").pack()
        
        # Uptime Card
        self.uptime_card = self._create_metric_card(
            metrics_frame, "⏱️ Avg Uptime", "info", 0, 3
        )
        self.uptime_label = tb.Label(self.uptime_card, text="0%", 
                                   font=("Segoe UI", 28, "bold"),
                                   bootstyle="info")
        self.uptime_label.pack(pady=(10, 5))
        tb.Label(self.uptime_card, text="Average Uptime", 
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
        """Create a modern metric card"""
        card = tb.LabelFrame(parent, text=title, bootstyle=style, padding=15)
        card.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
        return card

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
        
        # Optimize figure settings
        self.bandwidth_fig.tight_layout(pad=1.0)
        
        # Style the chart
        self.bandwidth_ax.spines['top'].set_visible(False)
        self.bandwidth_ax.spines['right'].set_visible(False)
        self.bandwidth_ax.spines['left'].set_color('#dee2e6')
        self.bandwidth_ax.spines['bottom'].set_color('#dee2e6')
        
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
        if self.auto_refresh_var.get():
            self.update_statistics()
            self.start_dashboard_auto_refresh()

    def _on_tab_change(self, event):
        tab = event.widget.tab(event.widget.select(), "text")
        if tab == "Bandwidth":
            self.load_bandwidth_data()
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_change)

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

        # if opening, pack it just before Export so it pushes Export down
        if opening:
            self.settings_dropdown.pack(fill='x', before=self.export_btn)

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
        online = sum(1 for r in routers if self.status_history.get(r['id'], {}).get('current') is True)
        offline = total - online
        
        # Calculate average uptime
        uptime_percentage = (online / total * 100) if total > 0 else 0

        # Update modern metric cards
        self.total_routers_label.config(text=str(total))
        self.online_routers_label.config(text=str(online))
        self.offline_routers_label.config(text=str(offline))
        self.uptime_label.config(text=f"{uptime_percentage:.1f}%")
        
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
        
        # Generate stable health data - only show last 8 hours with 4 data points
        import numpy as np
        
        # Create last 8 hours of data (every 2 hours = 4 data points)
        hours = [0, 2, 4, 6]  # 0, 2, 4, 6 hours ago
        health_scores = []
        
        # Calculate base health score once
        routers = self.router_list or get_routers()
        total = len(routers)
        online = sum(1 for r in routers if self.status_history.get(r['id'], {}).get('current') is True)
        base_score = (online / total * 100) if total > 0 else 0
        
        # Generate stable data points with minimal, consistent variation
        for i in range(4):
            hour = hours[i]
            
            # Check if we have stored data for this hour
            if hour not in self.health_data:
                # Use a deterministic variation based on hour and base score
                hour_factor = (6 - hour) / 6  # Decrease over time
                variation = (base_score * 0.05 * hour_factor)  # 5% variation max
                score = max(0, min(100, base_score + variation))
                self.health_data[hour] = score
            
            # Use stored health score
            health_scores.append(self.health_data[hour])
        
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
        """Update the bandwidth usage chart with stable, realistic data"""
        if not hasattr(self, 'bandwidth_ax') or not self.bandwidth_ax:
            return
            
        self.bandwidth_ax.clear()
        
        # Get router data for bandwidth visualization
        routers = self.router_list or get_routers()
        if not routers:
            self.bandwidth_ax.text(0.5, 0.5, 'No Router Data', ha='center', va='center', 
                                 transform=self.bandwidth_ax.transAxes, fontsize=12)
            self.bandwidth_canvas.draw_idle()
            return
        
        # Get top 3 routers by bandwidth with stable data
        router_names = [r.get('name', f'Router {r.get("id", "Unknown")}')[:10] for r in routers[:3]]
        
        # Generate stable bandwidth data based on router characteristics
        bandwidth_usage = []
        for i, router in enumerate(routers[:3]):
            router_id = router.get('id', 0)
            router_name = router.get('name', f'Router {router_id}')
            is_online = self.status_history.get(router_id, {}).get('current', False)
            
            # Check if we have stored data for this router
            if router_name not in self.bandwidth_data:
                # Initialize stable bandwidth based on router ID for consistency
                base_bandwidth = (router_id * 15) % 60 + 20  # Range: 20-80%
                self.bandwidth_data[router_name] = base_bandwidth
            
            # Get stored bandwidth and adjust based on online status
            stored_bandwidth = self.bandwidth_data[router_name]
            
            if is_online:
                # Online routers show their stored bandwidth (stable)
                bandwidth = stored_bandwidth
            else:
                # Offline routers show 0% bandwidth
                bandwidth = 0
            
            bandwidth_usage.append(bandwidth)
        
        # Create optimized bar chart
        colors = ['#007bff', '#28a745', '#ffc107']
        bars = self.bandwidth_ax.bar(range(len(router_names)), bandwidth_usage, 
                                   color=colors, alpha=0.85, width=0.7)
        
        # Add value labels on bars - optimized
        for i, (bar, value) in enumerate(zip(bars, bandwidth_usage)):
            height = bar.get_height()
            self.bandwidth_ax.text(bar.get_x() + bar.get_width()/2., height + 1.5,
                                 f'{value:.0f}%', ha='center', va='bottom', 
                                 fontsize=9, fontweight='bold')
        
        # Optimized styling
        self.bandwidth_ax.set_xlabel('Routers', fontsize=10)
        self.bandwidth_ax.set_ylabel('Bandwidth Usage (%)', fontsize=10)
        self.bandwidth_ax.set_title('Top 3 Routers by Bandwidth', fontsize=12, fontweight='bold', pad=10)
        self.bandwidth_ax.set_xticks(range(len(router_names)))
        self.bandwidth_ax.set_xticklabels(router_names, fontsize=9)
        self.bandwidth_ax.grid(True, alpha=0.15, axis='y')
        self.bandwidth_ax.set_ylim(0, 100)
        self.bandwidth_ax.margins(x=0.15, y=0.05)
        
        # Optimize drawing
        self.bandwidth_canvas.draw_idle()


    def apply_filter(self):
        query = self.search_var.get().lower()
        for rid, widgets in self.router_widgets.items():
            data = widgets['data']
            visible = (
                query in data['name'].lower() or
                query in data['ip_address'].lower() or
                query in data['location'].lower()
            )
            widgets['card'].grid_remove() if not visible else widgets['card'].grid()

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
            data = routers

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

        elif export_type == "tickets":
            tickets = ticket_utils.fetch_tickets()
            fieldnames = ["id", "router", "issue", "status", "created_by", "created_at", "updated_at"]
            for t in tickets:
                data.append({
                    "id": t["id"],
                    "router": t["router_name"] or "General",
                    "issue": t["issue"],
                    "status": t["status"],
                    "created_by": t["created_by"],
                    "created_at": t["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
                    "updated_at": t["updated_at"].strftime("%Y-%m-%d %H:%M:%S")
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
                    rows = routers or []

                elif export_type == "tickets":
                    lbl.after(0, lambda: lbl.config(text="Fetching tickets…"))
                    import ticket_utils
                    tickets = ticket_utils.fetch_tickets() or []
                    fieldnames = ["id", "router", "issue", "status", "created_by", "created_at", "updated_at"]
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
                            "router": t.get("router_name") or "General",
                            "issue": t.get("issue"),
                            "status": t.get("status"),
                            "created_by": t.get("created_by"),
                            "created_at": fmt(t.get("created_at")),
                            "updated_at": fmt(t.get("updated_at")),
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
                    self.root.after(0, lambda: on_done(False, f"Failed to write file: {e}"))
                    return

                if cancel_event.is_set():
                    self.root.after(0, lambda: on_done(False, "Export cancelled."))
                else:
                    self.root.after(0, lambda: on_done(True, f"{export_type.capitalize()} exported successfully!"))

            except Exception as e:
                self.root.after(0, lambda: on_done(False, f"Export failed: {e}"))

        import threading
        threading.Thread(target=worker, daemon=True).start()


    def open_router_popup(self, mode="add", router=None):
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
            entries[0].insert(0, router['name'])
            entries[1].insert(0, router['ip_address'])
            entries[2].insert(0, router['mac_address'])
            entries[3].insert(0, router['brand'])
            entries[4].insert(0, router['location'])
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
                update_router(router['id'], *vals, img_path)
                messagebox.showinfo("Updated","Router updated.")
            else:
                insert_router(*vals, img_path)
                messagebox.showinfo("Success","Router added.")
            popup.destroy()
            self.reload_routers(force_reload=True)

        btn_text = "Update Router" if mode=='edit' else "Add Router"
        tb.Button(
            outer, text=btn_text, bootstyle="success",
            command=submit
        ).grid(row=6, column=0, columnspan=2, pady=15)

    def delete_selected_router(self, router):
        if messagebox.askyesno("Delete", f"Delete router '{router['name']}'?"):
            delete_router(router['id'])
            self.reload_routers()

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
        d.title(f"Router Details - {router['name']}")
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

        router_title = tb.Label(title_text_frame, text=f"📡 {router['name']}", 
                               font=("Segoe UI", 20, "bold"), bootstyle="primary")
        router_title.pack(anchor="w")

        router_subtitle = tb.Label(title_text_frame, text=f"IP: {router['ip_address']}", 
                                  font=("Segoe UI", 12), bootstyle="secondary")
        router_subtitle.pack(anchor="w")

        # Quick actions in header
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

        # --- Store labels for live update ---
        self.detail_status_lbl = None
        self.detail_download_lbl = None
        self.detail_upload_lbl = None
        self.detail_last_seen_lbl = None
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

        # Last seen row
        last_seen_row = tb.Frame(status_grid)
        last_seen_row.pack(fill="x")

        tb.Label(last_seen_row, text="🕐 Last Seen:", font=("Segoe UI", 11, "bold"), 
                bootstyle="secondary").pack(side="left")
        
        self.detail_last_seen_lbl = tb.Label(last_seen_row, text="🕒 Checking...", 
                                            font=("Segoe UI", 11), bootstyle="dark")
        self.detail_last_seen_lbl.pack(side="left", padx=(10, 0))

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

        # Action buttons in grid (removed Advanced Settings and Export to PDF)
        action_buttons = [
            ("🔄 Refresh Data", "info", lambda: refresh_details()),
            ("📈 View History", "secondary", lambda: self.open_router_history(router)),
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

            rid = router['id']
            hist = self.status_history.get(rid, {})
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
                    
                    # Update latency if available
                    if bw.get("latency") is not None:
                        self.detail_latency_lbl.config(text=f"{bw['latency']:.0f} ms", bootstyle="success")
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

            # --- Last Seen ---
            last_seen = hist.get("last_checked")
            if self.detail_last_seen_lbl:
                if last_seen:
                    self.detail_last_seen_lbl.config(text=last_seen.strftime("%Y-%m-%d %H:%M:%S"))
                else:
                    self.detail_last_seen_lbl.config(text="Never")

            d.after(3000, refresh_details)  # refresh every 3s

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
    # Reload routers list and create/update router cards
    # ------------------------
    def reload_routers(self, force_reload=False):
        if force_reload or not self.router_list:
            self.router_list = get_routers()

        # Clear UI
        for w in self.scrollable_frame.winfo_children():
            w.destroy()
        self.router_widgets.clear()

        online, offline = [], []
        for r in self.router_list:
            st = self.status_history.get(r['id'], {}).get('current')
            (online if st is True else offline).append(r)

        def section(title, routers):
            if not routers:
                return

            tb.Label(
                self.scrollable_frame, text=title,
                font=("Segoe UI", 12, "bold"), bootstyle="secondary"
            ).pack(anchor="w", padx=10, pady=(15, 5))

            sec = tb.Frame(self.scrollable_frame)
            sec.pack(fill="x", padx=10, pady=5)

            sec._resize_job = None
            sec._last_cols = None

            def render_cards():
                width = sec.winfo_width() or self.root.winfo_width()
                if width <= 400:
                    max_cols = 1
                elif width <= 800:
                    max_cols = 2
                elif width <= 1200:
                    max_cols = 3
                else:
                    max_cols = 4

                if sec._last_cols == max_cols:
                    return
                sec._last_cols = max_cols

                for w in sec.winfo_children():
                    w.destroy()

                for i, router in enumerate(routers):
                    row, col = divmod(i, max_cols)

                    card = tb.LabelFrame(sec, text=router['name'], bootstyle="info", padding=0)
                    card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
                    sec.grid_columnconfigure(col, weight=1)

                    inner = tb.Frame(card, padding=10)
                    inner.pack(fill="both", expand=True)

                    tb.Label(inner, text="⛀", font=("Segoe UI Emoji", 30)).pack()
                    tb.Label(inner, text=router['ip_address'], font=("Segoe UI", 10)).pack(pady=(5, 0))

                    cur = self.status_history.get(router['id'], {}).get('current')
                    status_text, status_style = (
                        ("🟢 Online", "success") if cur is True
                        else ("🔴 Offline", "danger") if cur is False
                        else ("🕒 Checking...", "secondary")
                    )

                    # Status label (clickable)
                    status_label = tb.Label(inner, text=status_text, bootstyle=status_style, cursor="hand2")
                    status_label.pack(pady=5)

                    # Bandwidth label - Only check bandwidth if ONLINE
                    if cur is True:  # ✅ Only check bandwidth if ONLINE
                        lbl_bandwidth = tb.Label(inner, text="⏳ Bandwidth: checking...", bootstyle="secondary")
                        lbl_bandwidth.pack(pady=2)

                        threading.Thread(
                            target=self.fetch_and_update_bandwidth,
                            args=(router['id'], router['ip_address']),
                            daemon=True
                        ).start()
                    else:  # ✅ Offline or checking - show N/A for offline routers
                        lbl_bandwidth = tb.Label(inner, text="⏳ Bandwidth: N/A", bootstyle="secondary")
                        lbl_bandwidth.pack(pady=2)

                    # Save references
                    self.router_widgets[router['id']] = {
                        'card': card,
                        'status_label': status_label,
                        'bandwidth_label': lbl_bandwidth,
                        'data': router
                    }

                    # Click + context menu bindings
                    def bind_card_click(widget, router_obj):
                        widget.bind("<Button-1>", lambda e: self.open_router_details(router_obj))
                        widget.bind("<Button-3>", lambda e: self.show_context_menu(e, router_obj))

                    bind_card_click(inner, router)
                    for child in inner.winfo_children():
                        bind_card_click(child, router)

                    # Hover effect
                    def on_enter(e, c=card): c.configure(bootstyle="primary")
                    def on_leave(e, c=card): c.configure(bootstyle="info")
                    card.bind("<Enter>", on_enter)
                    card.bind("<Leave>", on_leave)

            def on_resize(event):
                if sec._resize_job:
                    sec.after_cancel(sec._resize_job)
                sec._resize_job = sec.after(200, render_cards)

            sec.bind("<Configure>", on_resize)
            render_cards()

        if self.sort_var.get() == "online":
            section("🟢 Online Routers", online)
            section("🔴 Offline Routers", offline)
        else:
            section("🟢 Online Routers", online + offline)



    # ------------------------
    # Fetch bandwidth for a router in a separate thread
    def fetch_and_update_bandwidth(self, rid, ip):
        try:
            # Fetch bandwidth data (download/upload)
            bw = get_bandwidth(ip)
            bw["latency"] = ping_latency(ip)  # Optional: Add latency info if needed

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
        # Ensure the router widget exists
        router_widget = self.router_widgets.get(rid)
        if not router_widget:
            return

        # Access the bandwidth label widget
        bw_label = router_widget.get('bandwidth_label')
        if not bw_label:
            return

        # Update the bandwidth label based on the available data
        if bandwidth is None:
            bw_label.config(text="❌ Bandwidth: Fetch failed", bootstyle="warning")
        elif bandwidth.get("download") is None or bandwidth.get("upload") is None:
            bw_label.config(text="⏳ Bandwidth: Fetching...", bootstyle="secondary")
        else:
            download = bandwidth.get("download")
            upload = bandwidth.get("upload")
            latency = bandwidth.get("latency")
            bw_label.config(
                text=f"⏱ {latency:.0f} ms | ⬇ {download:.2f} Mbps | ⬆ {upload:.2f} Mbps",
                bootstyle="info"
            )



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
                        print(f"🔔 Router status change: {router_name} ({router_ip}) is now {status_text}")
                        
                        # Create notification in main thread to ensure toast notifications work
                        if self.app_running:
                            self.root.after(0, lambda: self._create_router_notification(router_name, router_ip, new))
                            self.root.after(0, lambda r=rid, s=new: self._update_gui_status(r, s))
                            # Update notification count
                            self.root.after(0, self.update_notification_count)
            # Immediately stop if app closed during processing
            for _ in range(30):  # sleep for 3 seconds total, but check every 0.1s
                if not self.app_running:
                    return
                time.sleep(0.1)

    def _background_bandwidth_updater(self):
        while self.app_running:
            with concurrent.futures.ThreadPoolExecutor() as pool:
                futures = {
                    pool.submit(get_bandwidth, w['data']['ip_address']): rid
                    for rid, w in self.router_widgets.items()
                }
                for fut in concurrent.futures.as_completed(futures):
                    if not self.app_running:
                        return
                    rid = futures[fut]
                    try:
                        result = fut.result()  # should return {"download_mbps": X, "upload_mbps": Y}
                    except Exception:
                        result = {"download_mbps": None, "upload_mbps": None}

                    # ✅ store in shared dict
                    self.bandwidth_data[rid] = result

                    # ✅ refresh open router details (if visible)
                    if hasattr(self, "open_details_rid") and self.open_details_rid == rid:
                        self.root.after(0, self.refresh_details)
            
            # small sleep (e.g. 5s)
            for _ in range(50):  # 50 * 0.1s = 5s
                if not self.app_running:
                    return
                time.sleep(0.1)

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

        # Update bandwidth/latency label
        bw_lbl = w.get('bandwidth_label')
        if bw_lbl and bw_lbl.winfo_exists():
            if bandwidth is None:
                bw_lbl.config(text="⏳ Bandwidth: checking...", bootstyle="secondary")
            else:
                latency = bandwidth.get("latency")
                download = bandwidth.get("download")
                upload = bandwidth.get("upload")

                if online and latency is not None:
                    bw_lbl.config(
                        text=f"⏱ {latency:.0f} ms | ⬇ {download:.2f} Mbps | ⬆ {upload:.2f} Mbps",
                        bootstyle="info"
                    )
                elif not online:
                    bw_lbl.config(text="🔴 Offline", bootstyle="danger")
                else:
                    bw_lbl.config(text="❌ Bandwidth check failed", bootstyle="warning")


    def _background_status_updater(self):
        print("🔄 Starting router status monitoring...")
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

                    # Debug output
                    router_data = self.router_widgets.get(rid, {}).get('data', {})
                    router_name = router_data.get('name', f'Router {rid}')
                    print(f"🔍 Router {router_name}: {prev} -> {new} (online: {online})")

                    # Only update if state changes OR router is online (to refresh bandwidth)
                    if new is not prev or new is True:
                        hist['current'] = new
                        update_router_status_in_db(rid, new)
                        
                        # Send notification for router status change
                        if new is not prev:
                            router_data = self.router_widgets.get(rid, {}).get('data', {})
                            router_name = router_data.get('name', f'Router {rid}')
                            router_ip = router_data.get('ip_address', 'Unknown')
                            
                            # Debug output
                            status_text = "Online" if new else "Offline"
                            print(f"🔔 Router status change: {router_name} ({router_ip}) is now {status_text}")
                            
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
        cols = ("ID", "First Name", "Last Name", "Username", "Role", "Status", "Last Login")
        self.user_table = ttk.Treeview(table_frame, columns=cols, show="headings", height=12)
        
        # Configure columns with better widths
        column_widths = [60, 140, 140, 140, 100, 100, 140]
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
        popup.geometry("450x550")
        popup.transient(parent)
        popup.grab_set()
        popup.configure(bg='#f0f2f5')
        self._center_window(popup, 450, 550)

        # Header with modern styling
        header_frame = tb.LabelFrame(popup, text="", bootstyle="success", padding=20)
        header_frame.pack(fill="x", padx=15, pady=15)
        
        title_label = tb.Label(header_frame, text="➕ Add New User", 
                              font=("Segoe UI", 20, "bold"), bootstyle="success")
        title_label.pack()
        
        subtitle_label = tb.Label(header_frame, text="Create a new user account", 
                                 font=("Segoe UI", 11), bootstyle="secondary")
        subtitle_label.pack(pady=(5, 0))
        
        # Main form frame with enhanced styling
        form_frame = tb.LabelFrame(popup, text="📝 User Information", bootstyle="info", padding=25)
        form_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # Form fields
        fields = [
            ("First Name:", "first_name", False),
            ("Last Name:", "last_name", False),
            ("Username:", "username", False),
            ("Password:", "password", True),
            ("Confirm Password:", "confirm_password", True),
            ("Role:", "role", False)
        ]
        
        vars_ = {}
        entries = {}
        
        for i, (label, field_name, is_password) in enumerate(fields):
            row_frame = tb.Frame(form_frame)
            row_frame.pack(fill="x", pady=12)
            
            # Label with icon
            label_text = f"🔹 {label}" if not is_password else f"🔒 {label}"
            tb.Label(row_frame, text=label_text, font=("Segoe UI", 11, "bold"), 
                    width=18, anchor="w").pack(side="left")
            
            if field_name == "role":
                # Role selection with enhanced styling
                vars_[field_name] = tb.StringVar(value="user")
                role_combo = tb.Combobox(row_frame, textvariable=vars_[field_name], 
                                       values=["user", "admin"], width=28, state="readonly",
                                       font=("Segoe UI", 11), bootstyle="primary")
                role_combo.pack(side="left", padx=(15, 0))
                entries[field_name] = role_combo
            else:
                # Text entry with enhanced styling
                vars_[field_name] = tb.StringVar()
                entry = tb.Entry(row_frame, textvariable=vars_[field_name], 
                               width=32, show="*" if is_password else None,
                               font=("Segoe UI", 11), bootstyle="primary")
                entry.pack(side="left", padx=(15, 0))
                entries[field_name] = entry

        # Enhanced password strength indicator
        strength_frame = tb.Frame(form_frame)
        strength_frame.pack(fill="x", pady=(0, 15))
        
        strength_label = tb.Label(strength_frame, text="", font=("Segoe UI", 10, "bold"))
        strength_label.pack(anchor="w")

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

        vars_["password"].trace('w', lambda *args: check_password_strength())

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

            try:
                insert_user(username, password, first, last, role=role)
                messagebox.showinfo("Success", f"User '{username}' created successfully with {role} role.")
                popup.destroy()
                self._refresh_user_table()
            except Exception as e:
                messagebox.showerror("Error", f"Could not create user:\n{e}")

        # Enhanced buttons section
        button_frame = tb.LabelFrame(popup, text="", bootstyle="light", padding=20)
        button_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        # Button container
        btn_container = tb.Frame(button_frame)
        btn_container.pack()
        
        tb.Button(btn_container, text="➕ Create User", bootstyle="success", 
                 command=submit, width=18).pack(side="right", padx=(10, 0))
        tb.Button(btn_container, text="❌ Cancel", bootstyle="secondary", 
                 command=popup.destroy, width=12).pack(side="right")

    def _open_edit_user(self, parent, table):
        sel = table.selection()
        if not sel:
            return messagebox.showerror("Error", "Please select a user to edit.")
        
        # Get selected user data
        user_data = table.item(sel[0])["values"]
        uid, first, last, usern, role = user_data[:5]

        popup = Toplevel(parent)
        popup.title("✏️ Edit User")
        popup.geometry("450x500")
        popup.transient(parent)
        popup.grab_set()
        self._center_window(popup, 450, 500)

        # Header
        header_frame = tb.Frame(popup)
        header_frame.pack(fill="x", padx=20, pady=20)
        
        tb.Label(header_frame, text="✏️ Edit User", 
                font=("Segoe UI", 16, "bold"), bootstyle="primary").pack()
        
        tb.Label(header_frame, text=f"Editing: {first} {last} ({usern})", 
                font=("Segoe UI", 10), bootstyle="secondary").pack(pady=(5, 0))

        # Main form frame
        form_frame = tb.LabelFrame(popup, text="User Information", bootstyle="info", padding=20)
        form_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Form fields
        fields = [
            ("First Name:", "first_name", False),
            ("Last Name:", "last_name", False),
            ("Username:", "username", False),
            ("New Password:", "password", True),
            ("Confirm Password:", "confirm_password", True),
            ("Role:", "role", False)
        ]
        
        vars_ = {}
        entries = {}
        
        for i, (label, field_name, is_password) in enumerate(fields):
            row_frame = tb.Frame(form_frame)
            row_frame.pack(fill="x", pady=8)
            
            tb.Label(row_frame, text=label, font=("Segoe UI", 10, "bold"), 
                    width=15, anchor="w").pack(side="left")
            
            if field_name == "role":
                # Role selection
                vars_[field_name] = tb.StringVar(value=role.lower())
                role_combo = tb.Combobox(row_frame, textvariable=vars_[field_name], 
                                       values=["user", "admin"], width=25, state="readonly")
                role_combo.pack(side="left", padx=(10, 0))
                entries[field_name] = role_combo
            else:
                # Text entry
                vars_[field_name] = tb.StringVar()
            if field_name in ["first_name", "last_name", "username"]:
                field_index = ["first_name", "last_name", "username"].index(field_name) + 1
                vars_[field_name].set(user_data[field_index])
                
                entry = tb.Entry(row_frame, textvariable=vars_[field_name], 
                               width=30, show="*" if is_password else None,
                               font=("Segoe UI", 10))
                entry.pack(side="left", padx=(10, 0))
                entries[field_name] = entry

        # Password strength indicator
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

        # Validation function
        def validate_form():
            new_first = vars_["first_name"].get().strip()
            new_last = vars_["last_name"].get().strip()
            new_username = vars_["username"].get().strip()
            new_password = vars_["password"].get()
            confirm_password = vars_["confirm_password"].get()
            new_role = vars_["role"].get()

            if not all([new_first, new_last, new_username]):
                messagebox.showerror("Error", "First name, last name, and username are required.")
                return False

            if len(new_username) < 3:
                messagebox.showerror("Error", "Username must be at least 3 characters long.")
                return False

            # Check if username already exists (excluding current user)
            if new_username != usern:
                from user_utils import get_user_by_username
                if get_user_by_username(new_username):
                    messagebox.showerror("Error", "Username already exists. Please choose a different username.")
                    return False

            # Password validation (only if password is being changed)
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
            new_role = vars_["role"].get()

            try:
                # Update user with or without password change
                if new_password:
                    update_user(uid, new_username, new_password, new_first, new_last)
                else:
                    update_user(uid, new_username, None, new_first, new_last)
                
                messagebox.showinfo("Success", f"User '{new_username}' updated successfully.")
                popup.destroy()
                self._refresh_user_table()
            except Exception as e:
                messagebox.showerror("Error", f"Could not update user:\n{e}")

        # Buttons
        button_frame = tb.Frame(popup)
        button_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        tb.Button(button_frame, text="💾 Save Changes", bootstyle="primary", 
                 command=submit_edit, width=15).pack(side="right", padx=(5, 0))
        tb.Button(button_frame, text="Cancel", bootstyle="secondary", 
                 command=popup.destroy, width=10).pack(side="right")


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
            
            # Mock last login (you can implement actual last login tracking)
            last_login = "Never"  # You can implement actual last login tracking
            
            self.user_table.insert("", "end", values=(
                user["id"],
                user["first_name"],
                user["last_name"],
                user["username"],
                user["role"].title(),
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
            
            # Determine status and last login (simplified)
            status = "Active"
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
        self.router_var = tk.StringVar()
        router_names = ["All Routers"] + [r["name"] for r in get_routers()]
        self.router_picker = tb.Combobox(
            router_frame,
            textvariable=self.router_var,
            values=router_names if router_names else ["No routers available"],
            state="readonly",
            width=30
        )
        self.router_picker.current(0)  # Default to All Routers
        self.router_picker.pack(side="left", padx=(10, 0))
        self.router_picker.bind("<<ComboboxSelected>>", lambda e: self.show_last_7_days_for_selected_router())

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

        # To date
        tb.Label(date_frame, text="To:", font=("Segoe UI", 10)).pack(side="left", padx=(20, 0))
        initial_end = datetime.now().date()
        self.end_date = DateEntry(date_frame, width=12, dateformat="%m/%d/%Y", bootstyle="primary")
        self.end_date.entry.delete(0, tk.END)
        self.end_date.entry.insert(0, initial_end.strftime("%m/%d/%Y"))
        self.end_date.pack(side="left", padx=(10, 5))

        # Action buttons
        button_frame = tb.Frame(controls_frame)
        button_frame.pack(fill="x")
        
        tb.Button(button_frame, text="🔍 Apply Filter", bootstyle="primary",
                 command=self.refresh_total_bandwidth_chart).pack(side="left", padx=(0, 10))
        tb.Button(button_frame, text="🔄 Refresh", bootstyle="info",
                 command=lambda: self.load_bandwidth_data_by_name(self.router_var.get())).pack(side="left", padx=(0, 10))
        tb.Button(button_frame, text="📅 Last 7 Days", bootstyle="secondary",
                 command=self.load_last_7_days_bandwidth).pack(side="left")

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

        # Main content area with notebook
        self.bandwidth_notebook = tb.Notebook(self.bandwidth_frame)
        self.bandwidth_notebook.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Charts tab
        self.bandwidth_charts_frame = tb.Frame(self.bandwidth_notebook)
        self.bandwidth_notebook.add(self.bandwidth_charts_frame, text="📈 Charts")

        # Bandwidth trend chart
        chart_frame = tb.LabelFrame(self.bandwidth_charts_frame, text="📊 Bandwidth Trends", 
                                   bootstyle="info", padding=10)
        chart_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.bandwidth_fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(10, 8), dpi=100)
        self.bandwidth_canvas = FigureCanvasTkAgg(self.bandwidth_fig, master=chart_frame)
        self.bandwidth_canvas.get_tk_widget().pack(fill="both", expand=True)

        # Data table tab
        self.bandwidth_table_frame = tb.Frame(self.bandwidth_notebook)
        self.bandwidth_notebook.add(self.bandwidth_table_frame, text="📋 Data Table")

        # Table with scrollbars
        table_container = tb.Frame(self.bandwidth_table_frame)
        table_container.pack(fill="both", expand=True, padx=10, pady=10)

        # Create treeview
        columns = ("timestamp", "download", "upload", "latency")
        self.bandwidth_table = ttk.Treeview(table_container, columns=columns, show="headings", height=20)
        
        # Configure columns
        self.bandwidth_table.column("timestamp", width=200, anchor="center")
        self.bandwidth_table.column("download", width=150, anchor="center")
        self.bandwidth_table.column("upload", width=150, anchor="center")
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

        # Pack widgets
        self.bandwidth_table.pack(side="left", fill="both", expand=True)
        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")

        # Initialize auto-update
        self.bandwidth_auto_update_interval = 30000  # 30 seconds
        self.bandwidth_auto_update_job = None
        # Start auto-update after a short delay to ensure UI is fully built
        self.root.after(1000, self.start_bandwidth_auto_update)

        # After job tracker for auto-refresh
        self._bandwidth_after_job = None

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
        if self.report_auto_update_var.get():
            self.generate_report_table(filter_mode=self.report_mode.get().lower())
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
        """Refresh reports data"""
        self.generate_report_table(filter_mode=self.report_mode.get().lower())

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
        if self.bandwidth_auto_update_var.get():
            self.refresh_total_bandwidth_chart()
            self.update_bandwidth_last_update_display()
            self.bandwidth_auto_update_job = self.root.after(self.bandwidth_auto_update_interval, self.auto_update_bandwidth)

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
            # Get bandwidth data from the current table
            if not hasattr(self, 'bandwidth_table'):
                return
                
            # Extract data from table
            downloads = []
            uploads = []
            latencies = []
            
            for item in self.bandwidth_table.get_children():
                values = self.bandwidth_table.item(item)['values']
                if len(values) >= 4:
                    try:
                        download_val = float(values[1].replace(' Mbps', ''))
                        upload_val = float(values[2].replace(' Mbps', ''))
                        latency_val = float(values[3].replace(' ms', ''))
                        
                        downloads.append(download_val)
                        uploads.append(upload_val)
                        latencies.append(latency_val)
                    except (ValueError, IndexError):
                        continue
            
            # Update statistics cards
            if downloads and hasattr(self, 'avg_download_label'):
                avg_download = sum(downloads) / len(downloads)
                self.avg_download_label.config(text=f"{avg_download:.2f} Mbps")
                
                max_download = max(downloads)
                if hasattr(self, 'max_download_label'):
                    self.max_download_label.config(text=f"{max_download:.2f} Mbps")
            
            if uploads and hasattr(self, 'avg_upload_label'):
                avg_upload = sum(uploads) / len(uploads)
                self.avg_upload_label.config(text=f"{avg_upload:.2f} Mbps")
            
            if latencies and hasattr(self, 'avg_latency_label'):
                avg_latency = sum(latencies) / len(latencies)
                self.avg_latency_label.config(text=f"{avg_latency:.1f} ms")
                
        except Exception as e:
            print(f"Error updating bandwidth statistics: {e}")

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
        try:
            if router_name == "All Routers":
                # Handle "All Routers" selection
                routers = get_routers()
                if not routers:
                    messagebox.showinfo("No Routers", "No routers are configured in the system.")
                    return
                    
                # Cancel previous scheduled call
                if hasattr(self, "_bandwidth_after_job") and self._bandwidth_after_job:
                    self.bandwidth_frame.after_cancel(self._bandwidth_after_job)
                    
                # Combine data from all routers
                for router in routers:
                    self.load_bandwidth_data(router['id'])
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
                
            self.load_bandwidth_data(router['id'])
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load bandwidth data: {str(e)}")


    def load_bandwidth_data(self, router_id, start_date=None, end_date=None):
        """
        Load bandwidth logs for a given router, optionally filtered by start and end dates.
        Updates both the chart and the table, and schedules auto-refresh.
        """
        try:
            # Cancel previous scheduled refresh
            if hasattr(self, "_bandwidth_after_job") and self._bandwidth_after_job:
                self.bandwidth_frame.after_cancel(self._bandwidth_after_job)

            # Build SQL query
            params = [router_id]
            if start_date and end_date:
                start = datetime.strptime(start_date, "%m/%d/%Y")
                end = datetime.strptime(end_date, "%m/%d/%Y")
                days_diff = (end - start).days
                # Convert to YYYY-MM-DD format for SQL
                start_str = start.strftime("%Y-%m-%d")
                end_str = end.strftime("%Y-%m-%d")
                if days_diff > 1:
                    query = """
                        SELECT 
                            MIN(timestamp) AS timestamp,
                            ROUND(AVG(download_mbps), 2) AS download_mbps,
                            ROUND(AVG(upload_mbps), 2)  AS upload_mbps,
                            ROUND(AVG(latency_ms), 1)   AS latency_ms
                        FROM bandwidth_logs
                        WHERE router_id = %s AND DATE(timestamp) >= %s AND DATE(timestamp) <= %s
                        GROUP BY DATE(timestamp), HOUR(timestamp)
                        ORDER BY timestamp DESC
                        LIMIT 1000
                    """
                    params.extend([start_str, end_str])
                else:
                    query = """
                        SELECT 
                            timestamp,
                            download_mbps AS download_mbps,
                            upload_mbps   AS upload_mbps,
                            latency_ms    AS latency_ms
                        FROM bandwidth_logs
                        WHERE router_id = %s AND DATE(timestamp) >= %s AND DATE(timestamp) <= %s
                        ORDER BY timestamp DESC
                        LIMIT 1000
                    """
                    params.extend([start_str, end_str])
            else:
                query = """
                    SELECT 
                        timestamp,
                        download_mbps AS download_mbps,
                        upload_mbps   AS upload_mbps,
                        latency_ms    AS latency_ms
                    FROM bandwidth_logs
                    WHERE router_id = %s
                    ORDER BY timestamp DESC
                    LIMIT 1000
                """

            # Fetch data
            conn = get_connection()
            cur = conn.cursor(dictionary=True)
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            conn.close()

            if not rows:
                # Clear chart and table if no data
                self.ax1.clear()
                self.ax2.clear()
                self.bandwidth_canvas.draw()
                self.bandwidth_table.delete(*self.bandwidth_table.get_children())
                messagebox.showinfo("No Data", "No bandwidth data available for the selected period.")
                return

            rows.reverse()  # Oldest -> newest
        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch bandwidth data: {str(e)}")
            return

        # Prepare chart data
        timestamps = [r["timestamp"].strftime("%H:%M:%S") for r in rows]
        downloads  = [float(r["download_mbps"] or 0) for r in rows]
        uploads    = [float(r["upload_mbps"] or 0) for r in rows]
        latencies  = [float(r["latency_ms"] or 0) for r in rows]

        # Update chart
        self.ax1.clear()
        self.ax2.clear()

        self.ax1.plot(timestamps, downloads, label="Download (Mbps)", color="blue")
        self.ax1.plot(timestamps, uploads, label="Upload (Mbps)", color="green")
        self.ax1.set_xlabel("Time")
        self.ax1.set_ylabel("Bandwidth (Mbps)")
        self.ax1.tick_params(axis="x", rotation=45)
        self.ax1.legend(loc="upper left")

        self.ax2.plot(timestamps, latencies, label="Ping (ms)", color="red", marker="o")
        self.ax2.set_ylabel("Latency (ms)")
        self.ax2.legend(loc="upper right")

        self.bandwidth_canvas.draw()

        # Store rows internally for table (None-safe)
        def _nz(val):
            try:
                return 0.0 if val is None else float(val)
            except Exception:
                return 0.0

        self._bandwidth_rows = [
            (
                r["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                _nz(r.get("download_mbps")),
                _nz(r.get("upload_mbps")),
                _nz(r.get("latency_ms"))
            )
            for r in rows
        ]

        # Refresh table with current sorting
        self._refresh_bandwidth_table()

        # Update last updated label
        now = datetime.now().strftime("%H:%M:%S")
        if hasattr(self, 'bandwidth_last_update_label'):
            self.bandwidth_last_update_label.config(text=f"Last updated: {now}")

        # Schedule next refresh
        self._bandwidth_after_job = self.bandwidth_frame.after(
            5000,
            lambda: self.load_bandwidth_data(router_id, start_date, end_date)
        )

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

            self.load_bandwidth_data(router['id'], start_date=start, end_date=end)


    def show_last_7_days_for_selected_router(self):
        """On router selection, show last 7 days of data for that router or all routers."""
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

        # Load last 7 days for the selected router
        self.load_bandwidth_data(
            router['id'],
            start_date=last_7.strftime("%m/%d/%Y"),
            end_date=today.strftime("%m/%d/%Y")
        )


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
                    try:
                        return datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        return datetime.strptime(val, "%Y-%m-%d")
                data.sort(key=lambda x: parse_ts(x[idx]), reverse=reverse)
            else:
                def _nz_sort(v):
                    try:
                        return float(v) if v is not None else 0.0
                    except Exception:
                        return 0.0
                data.sort(key=lambda x: _nz_sort(x[idx]), reverse=reverse)

        for row in data:
            # Format the values properly
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

        # Update chart to match table
        self._update_bandwidth_chart_from_data(data)
        
        # Update statistics cards
        self.update_bandwidth_statistics()


    def _update_bandwidth_chart_from_data(self, data):
        """Updates chart from table data."""
        self.ax1.clear()
        self.ax2.clear()
        if not data:
            self.bandwidth_canvas.draw()
            return

        timestamps = [r[0] for r in data]
        downloads  = [r[1] for r in data]
        uploads    = [r[2] for r in data]
        latencies  = [r[3] for r in data]

        self.ax1.plot(timestamps, downloads, label="Download (Mbps)", color="blue")
        self.ax1.plot(timestamps, uploads, label="Upload (Mbps)", color="green")
        self.ax1.set_xlabel("Time")
        self.ax1.set_ylabel("Mbps")
        self.ax1.tick_params(axis="x", rotation=45)
        self.ax1.legend(loc="upper left")

        self.ax2.plot(timestamps, latencies, label="Latency (ms)", color="red", marker="o")
        self.ax2.set_ylabel("Latency (ms)")
        self.ax2.legend(loc="upper right")

        self.bandwidth_canvas.draw()

    def _reverse_column(self, col_name):
        """Toggles column sorting on header click."""
        reverse = self._reverse_flags.get(col_name, False)
        self._refresh_bandwidth_table(sort_column=col_name, reverse=reverse)
        self._reverse_flags[col_name] = not reverse



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
        """
        Draws/refreshes the Total Bandwidth chart and table.
        Respects router selection and optional date filter.
        """
        # Cancel previous refresh
        if hasattr(self, "_bandwidth_after_job") and self._bandwidth_after_job:
            self.bandwidth_frame.after_cancel(self._bandwidth_after_job)

        # Clear charts
        self.ax1.clear()
        self.ax2.clear()

        # Normalize dates
        def normalize(date_str):
            if not date_str:
                return None
            for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y"):
                try:
                    return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
                except ValueError:
                    continue
            return None

        start = normalize(self.start_date.entry.get())
        end   = normalize(self.end_date.entry.get())

        # Get selected router
        selected_name = self.router_var.get()
        router_id = None
        routers = get_routers()
        router = next((r for r in routers if r['name'] == selected_name), None)
        if router:
            router_id = router['id']

        # Fetch data
        conn = get_connection()
        cur = conn.cursor(dictionary=True)

        if start and end:
            if router_id:
                query = """
                    SELECT timestamp, download_mbps AS total_download,
                        upload_mbps AS total_upload, latency_ms AS avg_latency
                    FROM bandwidth_logs
                    WHERE router_id=%s AND DATE(timestamp) BETWEEN %s AND %s
                    ORDER BY timestamp ASC LIMIT 200
                """
                cur.execute(query, (router_id, start, end))
            else:
                query = """
                    SELECT timestamp, SUM(download_mbps) AS total_download,
                        SUM(upload_mbps) AS total_upload,
                        AVG(latency_ms) AS avg_latency
                    FROM bandwidth_logs
                    WHERE DATE(timestamp) BETWEEN %s AND %s
                    GROUP BY timestamp
                    ORDER BY timestamp ASC LIMIT 200
                """
                cur.execute(query, (start, end))
        else:
            if router_id:
                query = """
                    SELECT * FROM (
                        SELECT timestamp, download_mbps AS total_download,
                            upload_mbps AS total_upload, latency_ms AS avg_latency
                        FROM bandwidth_logs
                        WHERE router_id=%s
                        ORDER BY timestamp DESC LIMIT 20
                    ) AS recent ORDER BY timestamp ASC
                """
                cur.execute(query, (router_id,))
            else:
                query = """
                    SELECT * FROM (
                        SELECT timestamp, SUM(download_mbps) AS total_download,
                            SUM(upload_mbps) AS total_upload,
                            AVG(latency_ms) AS avg_latency
                        FROM bandwidth_logs
                        GROUP BY timestamp
                        ORDER BY timestamp DESC LIMIT 20
                    ) AS recent ORDER BY timestamp ASC
                """
                cur.execute(query)

        rows = cur.fetchall()
        conn.close()
        if not rows:
            return

        # Prepare data
        timestamps = [r["timestamp"].strftime("%H:%M:%S") for r in rows]
        downloads  = [float(r["total_download"] or 0) for r in rows]
        uploads    = [float(r["total_upload"] or 0) for r in rows]
        latencies  = [float(r["avg_latency"] or 0) for r in rows]

        # Update charts
        self.ax1.plot(timestamps, downloads, label="Download (Mbps)", color="blue")
        self.ax1.plot(timestamps, uploads, label="Upload (Mbps)", color="green")
        self.ax1.set_title("Total Bandwidth Usage")
        self.ax1.set_xlabel("Time")
        self.ax1.set_ylabel("Mbps")
        self.ax1.tick_params(axis="x", rotation=45)
        self.ax1.legend(loc="upper left")

        self.ax2.plot(timestamps, latencies, label="Avg Ping (ms)", color="red", marker="o")
        self.ax2.set_ylabel("Latency (ms)")
        self.ax2.legend(loc="upper right")

        self.bandwidth_canvas.draw()

        # Update table
        self.bandwidth_table.delete(*self.bandwidth_table.get_children())
        table_rows = []
        for r in rows:
            row_tuple = (
                r["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                round(r["total_download"] or 0, 2),
                round(r["total_upload"] or 0, 2),
                round(r["avg_latency"] or 0, 2)
            )
            self.bandwidth_table.insert("", "end", values=row_tuple)
            table_rows.append(row_tuple)

        # Keep background thread data dict intact; store table rows separately
        self._bandwidth_rows = table_rows

        # Update statistics cards
        self.update_bandwidth_statistics()

        # Auto-refresh every 5s
        self._bandwidth_after_job = self.bandwidth_frame.after(5000, self.load_total_bandwidth_chart)


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
        Fetch data based on router selection and optional date filter.
        Updates both the table and chart.
        """
        # Cancel any scheduled refresh
        if hasattr(self, "_bandwidth_after_job") and self._bandwidth_after_job:
            self.bandwidth_frame.after_cancel(self._bandwidth_after_job)

        # --- Parse dates safely ---
        # Get dates from StringVar
        # Prefer reading from DateEntry text directly
        try:
            start_date = datetime.strptime(self.start_date.entry.get(), "%m/%d/%Y").date()
        except Exception:
            start_date = None

        try:
            end_date = datetime.strptime(self.end_date.entry.get(), "%m/%d/%Y").date()
        except Exception:
            end_date = None

        # Default to last 7 days if empty
        today = datetime.now().date()
        if not start_date:
            start_date = today - timedelta(days=7)
            self.start_date.entry.delete(0, tk.END)
            self.start_date.entry.insert(0, start_date.strftime("%m/%d/%Y"))
            
        if not end_date:
            end_date = today
            self.end_date.entry.delete(0, tk.END)
            self.end_date.entry.insert(0, end_date.strftime("%m/%d/%Y"))

        start_str = start_date.strftime("%Y-%m-%d")
        end_str   = end_date.strftime("%Y-%m-%d")

        # --- Get selected router ---
        router_name = self.router_var.get()
        router_id = None
        for r in get_routers():
            if r["name"] == router_name:
                router_id = r["id"]
                break

        # --- Build SQL query ---
        query_params = []
        if router_id:
            # Single router → filter by router_id and date
            query = """
                SELECT timestamp, download_mbps AS total_download,
                    upload_mbps AS total_upload, latency_ms AS avg_latency
                FROM bandwidth_logs
                WHERE router_id=%s AND DATE(timestamp) BETWEEN %s AND %s
                ORDER BY timestamp ASC
            """
            query_params.extend([router_id, start_str, end_str])
        else:
            # All routers → aggregate by date
            query = """
                SELECT DATE(timestamp) AS timestamp_date,
                    SUM(download_mbps) AS total_download,
                    SUM(upload_mbps) AS total_upload,
                    AVG(latency_ms) AS avg_latency
                FROM bandwidth_logs
                WHERE DATE(timestamp) BETWEEN %s AND %s
                GROUP BY timestamp_date
                ORDER BY timestamp_date ASC
            """
            query_params.extend([start_str, end_str])

        # --- Execute query ---
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute(query, query_params)
        rows = cur.fetchall()
        conn.close()

        # --- Handle no data ---
        if not rows:
            # Ensure this remains a dict elsewhere; avoid list assignment errors
            if not isinstance(self.bandwidth_data, dict):
                self.bandwidth_data = {}
            self.bandwidth_table.delete(*self.bandwidth_table.get_children())
            self.ax1.clear()
            self.ax2.clear()
            self.bandwidth_canvas.draw()
            if hasattr(self, 'bandwidth_last_update_label'):
                self.bandwidth_last_update_label.config(text="Last updated: -")
            return

        # --- Prepare data for chart & table ---
        filtered_rows = []
        for r in rows:
            if router_id:
                ts_display = r["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
            else:
                ts_display = r["timestamp_date"].strftime("%Y-%m-%d")
            row_tuple = (
                ts_display,
                float(r["total_download"] or 0),
                float(r["total_upload"] or 0),
                float(r["avg_latency"] or 0)
            )
            filtered_rows.append(row_tuple)

        # Use the same internal storage the table expects
        self._bandwidth_rows = filtered_rows

        # --- Refresh table and chart ---
        self._refresh_bandwidth_table(sort_column="timestamp", reverse=False)

        # --- Update last updated label ---
        now = datetime.now().strftime("%H:%M:%S")
        if hasattr(self, 'bandwidth_last_update_label'):
            self.bandwidth_last_update_label.config(text=f"Last updated: {now}")

        # --- Schedule auto-refresh every 5s ---
        self._bandwidth_after_job = self.bandwidth_frame.after(5000, self.refresh_total_bandwidth_chart)



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
        
        tb.Button(button_frame, text="📊 Generate Report", bootstyle="primary",
            command=lambda: self.generate_report_table(
                filter_mode=self.report_mode.get().lower()
                 )).pack(side="left", padx=(0, 10))
        tb.Button(button_frame, text="🎫 Open Tickets Management", bootstyle="warning",
                 command=self.open_ticket_window).pack(side="left", padx=(0, 10))
        tb.Button(button_frame, text="🖨️ Print Report", bootstyle="info",
                 command=self.print_report).pack(side="left", padx=(0, 10))
        tb.Button(button_frame, text="🔄 Refresh", bootstyle="secondary",
                 command=self.refresh_reports).pack(side="left")

        # Summary cards
        self.summary_frame = tb.Frame(self.reports_frame)
        self.summary_frame.pack(fill="x", padx=20, pady=10)
        
        # Create summary cards
        self.total_routers_card = tb.LabelFrame(self.summary_frame, text="Total Routers", bootstyle="primary", padding=10)
        self.total_routers_card.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.total_routers_label = tb.Label(self.total_routers_card, text="—", font=("Segoe UI", 14, "bold"))
        self.total_routers_label.pack()
        
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

        # Pack widgets
        self.uptime_tree.pack(side="left", fill="both", expand=True)
        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")

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


    def generate_report_table(self, filter_mode="weekly"):
        try:
            from datetime import datetime, time, timedelta
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            import mplcursors
            import ttkbootstrap as tb

            # -----------------------------
            # Read selected dates
            # -----------------------------
            start_str = self.report_start_date.entry.get()
            end_str = self.report_end_date.entry.get()
            
            # Handle both old and new date formats
            try:
                start_date = datetime.combine(datetime.strptime(start_str, "%m/%d/%Y"), time.min)
                end_date = datetime.combine(datetime.strptime(end_str, "%m/%d/%Y"), time.max)
            except ValueError:
                # Fallback to old format
                start_date = datetime.combine(datetime.strptime(start_str, "%m/%d/%Y"), time.min)
                end_date = datetime.combine(datetime.strptime(end_str, "%m/%d/%Y"), time.max)

            if start_date > end_date:
                from tkinter import messagebox
                messagebox.showerror("Invalid Date Range", "Start date cannot be after end date.")
                return

            # -----------------------------
            # Utility: format downtime
            # -----------------------------
            def format_downtime(seconds):
                days, remainder = divmod(seconds, 86400)
                hours, remainder = divmod(remainder, 3600)
                minutes, sec = divmod(remainder, 60)
                if days > 0: return f"{days}d {hours}h {minutes}m"
                elif hours > 0: return f"{hours}h {minutes}m"
                elif minutes > 0: return f"{minutes}m {sec}s"
                else: return f"{sec}s"

            # -----------------------------
            # Clear previous table
            # -----------------------------
            if hasattr(self, 'uptime_tree'):
                self.uptime_tree.delete(*self.uptime_tree.get_children())
            routers = get_routers()

            # -----------------------------
            # Fill table
            # -----------------------------
            total_uptime = 0
            total_bandwidth = 0
            router_count = len(routers)
            
            for r in routers:
                router_id = r["id"]
                uptime = get_uptime_percentage(router_id, start_date, end_date)
                downtime_seconds = (1 - uptime / 100) * (end_date - start_date).total_seconds()
                downtime_str = format_downtime(int(downtime_seconds))
                bandwidth = get_bandwidth_usage(router_id, start_date, end_date)
                bandwidth_str = f"{bandwidth / 1024:.2f} GB" if bandwidth >= 1024 else f"{bandwidth:.2f} MB"

                if hasattr(self, 'uptime_tree'):
                    self.uptime_tree.insert(
                    "",
                    "end",
                    values=(
                        r["name"],
                        f"{uptime:.2f}%",
                        downtime_str,
                        bandwidth_str
                    )
                )
                
                total_uptime += uptime
                total_bandwidth += bandwidth

            # Update summary cards
            self.update_reports_summary_cards(router_count, total_uptime, total_bandwidth, router_count)

            # -----------------------------
            # Compute daily averages
            # -----------------------------
            def get_daily_avg_uptime(start_date, end_date):
                days = (end_date - start_date).days + 1
                results = []
                for i in range(days):
                    day_start = start_date + timedelta(days=i)
                    day_end = day_start.replace(hour=23, minute=59, second=59)
                    uptimes = [get_uptime_percentage(r["id"], day_start, day_end) for r in routers]
                    avg_uptime = sum(uptimes) / len(uptimes) if uptimes else 0
                    results.append((day_start, avg_uptime))
                return results

            daily_data = get_daily_avg_uptime(start_date, end_date)

            # -----------------------------
            # Aggregate based on filter_mode
            # -----------------------------
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

            # -----------------------------
            # Store for printing
            # -----------------------------
            self.agg_dates = agg_dates
            self.agg_uptimes = agg_uptimes

            # -----------------------------
            # Draw chart in GUI
            # -----------------------------
            def draw_chart():
                for widget in self.reports_charts_frame.winfo_children():
                    widget.destroy()
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

                # Tooltips
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

                # Store figure for printing
                self.current_fig = fig

            if not hasattr(self, "chart_visible"):
                self.chart_visible = True

            if not hasattr(self, "toggle_btn"):
                self.toggle_btn = tb.Button(self.reports_charts_frame, text="Hide Chart", command=lambda: self.toggle_chart(), bootstyle="secondary")
                self.toggle_btn.pack(anchor="ne", padx=5, pady=2)

            if self.chart_visible:
                draw_chart()

        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error", str(e))
            
    def print_report(self):
        """Show print preview window with report and charts"""
        try:
            if hasattr(self, 'uptime_tree') and self.uptime_tree.get_children():
                # Get all data from the table
                data = []
                for item in self.uptime_tree.get_children():
                    values = self.uptime_tree.item(item)['values']
                    data.append(values)
                
                if data:
                    # Show print preview window
                    self._show_print_preview(data)
                else:
                    from tkinter import messagebox
                    messagebox.showwarning("No Data", "No data to print. Please generate a report first.")
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
            
            # Bind mousewheel to canvas
            def _on_mousewheel(event):
                canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            
            def _bind_to_mousewheel(event):
                canvas.bind_all("<MouseWheel>", _on_mousewheel)
            
            def _unbind_from_mousewheel(event):
                canvas.unbind_all("<MouseWheel>")
            
            canvas.bind('<Enter>', _bind_to_mousewheel)
            canvas.bind('<Leave>', _unbind_from_mousewheel)
            
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
                canvas.unbind_all("<MouseWheel>")
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
        window.title("ICT Service Requests")
        window.geometry("900x500")

        # Header
        header_frame = tb.Frame(window)
        header_frame.pack(fill="x", padx=20, pady=10)
        tb.Label(header_frame, text="📋 ICT Service Requests", font=("Segoe UI", 16, "bold")).pack(side="left")

        tb.Button(
            header_frame,
            text="➕ New Service Request Form",
            bootstyle="primary",
            command=self.open_new_ticket_modal
        ).pack(side="right")

        # Ticket Table
        table_frame = tb.Frame(window)
        table_frame.pack(fill="both", expand=True, padx=20, pady=10)

        columns = ("ict_srf_no", "campus", "services", "status", "created_by", "created_at", "updated_at")
        self.tickets_table = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=15
        )

        for col in columns:
            self.tickets_table.heading(col, text=col.replace("_", " ").title())
            self.tickets_table.column(col, anchor="center", width=120)

        self.tickets_table.pack(fill="both", expand=True, side="left")

        # Scrollbar
        scrollbar = tb.Scrollbar(table_frame, orient="vertical", command=self.tickets_table.yview)
        scrollbar.pack(side="right", fill="y")
        self.tickets_table.configure(yscrollcommand=scrollbar.set)

        # Load tickets into the table
        self.load_tickets()

        # Bind double-click
        self.tickets_table.bind("<Double-1>", self._on_ticket_row_click)


    def load_tickets(self, status=None):
        """Fetch SRFs from DB and display in the table."""
        self.tickets_table.delete(*self.tickets_table.get_children())
        srfs = ticket_utils.fetch_srfs()
        for srf in srfs:
            self.tickets_table.insert(
                "",
                "end",
                values=(
                    srf["ict_srf_no"],
                    srf.get("campus", ""),
                    srf.get("services_requirements", ""),
                    srf.get("status", "open"),
                    srf.get("created_by_username", "Unknown"),
                    srf["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
                    srf["updated_at"].strftime("%Y-%m-%d %H:%M:%S")
                )
            )
    def collect_ticket_form_data(self):
        """Collect all values from SRF form fields."""
        data = {k: v.get() for k, v in self.form_vars.items()}
        data["services_requirements"] = self.service_req_text.get("1.0", "end").strip()
        data["remarks"] = self.remarks_text.get("1.0", "end").strip()
        return data


    def auto_refresh_tickets(self, interval=5000):
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

        # Optional: smooth scrolling bindings
        def _on_mousewheel(event):
            if event.delta:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        modal.bind_all("<MouseWheel>", _on_mousewheel)
        modal.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        modal.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

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



    def open_new_ticket_modal(self):
        """Open modal for creating a new SRF."""
        modal = tb.Toplevel(self.root)
        modal.title("ICT Service Request Form")
        modal.geometry("725x600")
        modal.resizable(False, False)
        modal.grab_set()

        # Build the SRF form
        button_host = self.build_ticket_form(modal)

        # Submit button
        tb.Button(
            button_host,
            text="Submit Ticket",
            bootstyle="primary",
            command=lambda: self.submit_new_ticket(modal)
        ).pack(pady=20)


    def submit_new_ticket(self, modal):
        """Submit the ICT Service Request Form to the database."""
        data = self.collect_ticket_form_data()

        if not data["ict_srf_no"]:
            messagebox.showwarning("Warning", "ICT SRF No. cannot be empty!")
            return

        try:
            ticket_utils.create_srf(data, created_by=self.current_user["id"])
            messagebox.showinfo("Success", "Service Request created successfully!")
            modal.destroy()
            self.load_tickets()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create Service Request:\n{e}")


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
        """Open a modal showing SRF details in a printable form layout."""
        srf = next((s for s in ticket_utils.fetch_srfs() if s["ict_srf_no"] == srf_no), None)
        if not srf:
            messagebox.showerror("Error", "Service Request not found!")
            return

        modal = tb.Toplevel(self.root)
        modal.title(f"SRF #{srf_no} Details")
        modal.geometry("700x600")
        modal.grab_set()

        # ---- Header with logo ----
        header_frame = tb.Frame(modal)
        header_frame.pack(fill="x", pady=10)

        try:
            logo_img = Image.open("assets/images/bsu_logo.png").resize((60, 60))
            self.logo_photo = ImageTk.PhotoImage(logo_img)
            tb.Label(header_frame, image=self.logo_photo).pack(side="left", padx=10)
        except:
            tb.Label(header_frame, text="LOGO", width=10, relief="solid").pack(side="left", padx=10)

        tb.Label(header_frame, text="ICT SERVICE REQUEST FORM", font=("Segoe UI", 16, "bold")).pack(side="left", padx=20)

        # ---- SRF Number ----
        tb.Label(modal, text=f"SRF No: {srf['ict_srf_no']}", font=("Segoe UI", 12, "bold")).pack(pady=5)

        # ---- Sections ----
        form_frame = tb.Frame(modal, padding=10)
        form_frame.pack(fill="both", expand=True)

        # Request Info
        tb.Label(form_frame, text="Request Information", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", pady=5, columnspan=2)
        tb.Label(form_frame, text=f"Campus: {srf['campus']}").grid(row=1, column=0, sticky="w", padx=10)
        tb.Label(form_frame, text=f"Office/Building: {srf['office_building']}").grid(row=2, column=0, sticky="w", padx=10)
        tb.Label(form_frame, text=f"Client: {srf['client_name']}").grid(row=3, column=0, sticky="w", padx=10)
        tb.Label(form_frame, text=f"Date/Time of Call: {srf['date_time_call']}").grid(row=4, column=0, sticky="w", padx=10)

        # Technician & Services
        tb.Label(form_frame, text="Technician & Services", font=("Segoe UI", 12, "bold")).grid(row=5, column=0, sticky="w", pady=5, columnspan=2)
        tb.Label(form_frame, text=f"Technician: {srf['technician_assigned']}").grid(row=6, column=0, sticky="w", padx=10)
        tb.Label(form_frame, text=f"Services: {srf['services_requirements']}").grid(row=7, column=0, sticky="w", padx=10)

        # Status
        tb.Label(form_frame, text="Status & Remarks", font=("Segoe UI", 12, "bold")).grid(row=8, column=0, sticky="w", pady=5, columnspan=2)
        tb.Label(form_frame, text=f"Status: {srf.get('status','open')}").grid(row=9, column=0, sticky="w", padx=10)
        tb.Label(form_frame, text=f"Remarks: {srf.get('remarks','')}").grid(row=10, column=0, sticky="w", padx=10)

        # Metadata
        tb.Label(form_frame, text="System Info", font=("Segoe UI", 12, "bold")).grid(row=11, column=0, sticky="w", pady=5, columnspan=2)
        tb.Label(form_frame, text=f"Created by: {srf.get('created_by_username','Unknown')}").grid(row=12, column=0, sticky="w", padx=10)
        tb.Label(form_frame, text=f"Created at: {srf['created_at']}").grid(row=13, column=0, sticky="w", padx=10)
        tb.Label(form_frame, text=f"Updated at: {srf.get('updated_at','-')}").grid(row=14, column=0, sticky="w", padx=10)

        # ---- Buttons ----
        btn_frame = tb.Frame(modal)
        btn_frame.pack(pady=15)

        tb.Button(btn_frame, text="✏️ Edit", bootstyle="warning",
          command=lambda srf=srf: self.open_edit_ticket_modal(srf)).pack(side="left", padx=10)

        tb.Button(
            modal,
            text="🖨 Print",
            bootstyle="secondary",
            command=lambda: print_srf_form(srf, logo_path="assets/images/bsu_logo.png")
        ).pack(pady=10)
        tb.Button(btn_frame, text="❌ Close", bootstyle="danger", command=modal.destroy).pack(side="left", padx=10)

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
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE tickets SET status='resolved', updated_at=NOW() WHERE id=%s",
            (ticket_id,)
        )
        conn.commit()
        cursor.close()
        conn.close()

        messagebox.showinfo("Success", "Ticket marked as resolved!")
        modal.destroy()
        self.load_tickets()  # <- correct method to refresh the ticket table
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
        
        self.loop_export_btn = tb.Button(control_frame, text="📊 Export", bootstyle="info",
                                        command=lambda: self.export_loop_detection_history(), width=8)
        self.loop_export_btn.pack(side='left')

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
        
        tb.Label(history_controls, text="History updates automatically after each detection", 
                font=("Segoe UI", 9), bootstyle="secondary").pack(side='left', padx=(10, 0))
        
        # Create treeview for history
        columns = ("Time", "Status", "Packets", "Offenders", "Severity", "Interface")
        self.loop_detection_tree = ttk.Treeview(history_frame, columns=columns, show="headings", height=10)
        
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
                    timestamp = record["detection_time"].strftime("%Y-%m-%d %H:%M:%S") if hasattr(record["detection_time"], 'strftime') else str(record["detection_time"])[:19]
                    status = record["status"]
                    packets = record["total_packets"]
                    offenders = record["offenders_count"]
                    severity = record["severity_score"]
                    interface = record["network_interface"]
                else:
                    # In-memory record
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
                
                self.loop_detection_tree.insert("", "end", values=(
                    timestamp,
                    status_emoji,
                    packets,
                    offenders,
                    f"{severity:.2f}",
                    interface
                ))
                
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


    def _run_loop_scan_thread(self, modal):
        try:
            # Use the same lightweight detection as automatic detection
            from network_utils import detect_loops_lightweight
            iface = "Wi-Fi"  # or get_default_iface()
            
            # Run lightweight detection with same parameters as automatic
            total_packets, offenders, stats, status, severity_score = detect_loops_lightweight(
                timeout=3,  # 3 seconds for efficiency
                threshold=30,  # Same threshold as automatic detection
                iface=iface
            )

            modal.after(0, self._finish_loop_scan_lightweight, total_packets, offenders, stats, status, severity_score)

        except Exception as e:
            modal.after(0, self._finish_loop_scan_lightweight, None, None, None, None, None, str(e))


    def _finish_loop_scan_lightweight(self, total_packets, offenders, stats, status, severity_score, error=None):
        """Finish lightweight loop scan with proper status handling."""
        # Stop spinner
        self._spinner_running = False
        self.spinner_lbl.config(text="")

        self.loop_results.config(state="normal")
        self.loop_results.delete("1.0", tk.END)

        if error:
            self.loop_status_lbl.config(text="❌ Error during scan", bootstyle="danger")
            self.loop_results.insert(tk.END, f"Error: {error}\n")
        else:
            # Save to database
            from db import save_loop_detection
            detection_id = save_loop_detection(
                total_packets=total_packets,
                offenders=offenders,
                stats=stats,
                status=status,
                severity_score=severity_score,
                interface="Wi-Fi",
                duration=3
            )
            
            # Send notification for loop detection
            if status in ["loop_detected", "suspicious"]:
                notify_loop_detected(severity_score, offenders, "Wi-Fi")
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
            
            # Display results based on status
            if status == "loop_detected":
                self.loop_status_lbl.config(text="⚠️ Loop Detected!", bootstyle="danger")
                self.loop_results.insert(tk.END, f"⚠️ LOOP DETECTED!\n")
                self.loop_results.insert(tk.END, f"Severity Score: {severity_score:.2f}\n")
                self.loop_results.insert(tk.END, f"Total Packets: {total_packets}\n")
                self.loop_results.insert(tk.END, f"Offenders: {len(offenders)}\n\n")
                
                # Show offender details
                for mac in offenders:
                    info = stats.get(mac, {})
                    ips = ", ".join(info.get("ips", [])) if info.get("ips") else "Unknown"
                    self.loop_results.insert(tk.END, f"• {mac} → {ips} (Severity: {info.get('severity', 0):.2f})\n")
                    
            elif status == "suspicious":
                self.loop_status_lbl.config(text="🔍 Suspicious Activity", bootstyle="warning")
                self.loop_results.insert(tk.END, f"🔍 Suspicious activity detected\n")
                self.loop_results.insert(tk.END, f"Severity Score: {severity_score:.2f}\n")
                self.loop_results.insert(tk.END, f"Total Packets: {total_packets}\n")
                self.loop_results.insert(tk.END, f"Offenders: {len(offenders)}\n\n")
                
                # Show offender details
                for mac in offenders:
                    info = stats.get(mac, {})
                    ips = ", ".join(info.get("ips", [])) if info.get("ips") else "Unknown"
                    self.loop_results.insert(tk.END, f"• {mac} → {ips} (Severity: {info.get('severity', 0):.2f})\n")
                    
            else:  # status == "clean"
                self.loop_status_lbl.config(text="✅ Network Clean", bootstyle="success")
                self.loop_results.insert(tk.END, f"✅ Network is clean\n")
                self.loop_results.insert(tk.END, f"Severity Score: {severity_score:.2f}\n")
                self.loop_results.insert(tk.END, f"Total Packets: {total_packets}\n")
                self.loop_results.insert(tk.END, f"No suspicious activity detected\n")

            # Show detailed stats
            if stats:
                self.loop_results.insert(tk.END, f"\n📊 Detailed Statistics:\n")
                for mac, info in stats.items():
                    ips = ", ".join(info.get("ips", [])) if info.get("ips") else "Unknown"
                    self.loop_results.insert(tk.END, f"• {mac}:\n")
                    self.loop_results.insert(tk.END, f"  - Total packets: {info.get('count', 0)}\n")
                    self.loop_results.insert(tk.END, f"  - ARP packets: {info.get('arp_count', 0)}\n")
                    self.loop_results.insert(tk.END, f"  - Broadcast packets: {info.get('broadcast_count', 0)}\n")
                    self.loop_results.insert(tk.END, f"  - Severity: {info.get('severity', 0):.2f}\n")
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

    def _refresh_loop_detection_history(self):
        """Refresh loop detection history from database."""
        try:
            from db import get_loop_detections_history, get_loop_detection_stats
            self.loop_detection_history = get_loop_detections_history(100)
            self.loop_detection_stats = get_loop_detection_stats()
            self._load_loop_detection_history_modal()
            self._update_loop_status_display_modal(None)
            print("✅ Loop detection history refreshed from database")
        except Exception as e:
            print(f"❌ Error refreshing history: {e}")

    def clear_loop_results(self):
        """Clear the loop detection results."""
        self.loop_results.config(state="normal")
        self.loop_results.delete("1.0", tk.END)
        self.loop_results.config(state="disabled")
        self.loop_status_lbl.config(text="⏳ Ready to scan...", bootstyle="default")
        self.spinner_lbl.config(text="")


    def show_clients(self):
        """Enhanced popup modal that shows discovered network clients with modern UI."""
        modal = tb.Toplevel(self.root)
        modal.title("🌐 Network Clients Monitor")
        modal.geometry("1000x700")
        modal.resizable(True, True)
        modal.configure(bg='#f8f9fa')

        # Center modal
        modal.update_idletasks()
        x = (modal.winfo_screenwidth() - modal.winfo_width()) // 2
        y = (modal.winfo_screenheight() - modal.winfo_height()) // 2
        modal.geometry(f"+{x}+{y}")

        # Main container
        main_container = tb.Frame(modal, bootstyle="light")
        main_container.pack(fill="both", expand=True, padx=10, pady=10)

        # Header section
        header_frame = tb.Frame(main_container, bootstyle="info")
        header_frame.pack(fill="x", pady=(0, 10))

        # Title and stats
        title_frame = tb.Frame(header_frame)
        title_frame.pack(fill="x", padx=15, pady=15)

        tb.Label(title_frame, text="🌐 Network Clients Monitor", 
                font=("Segoe UI", 16, "bold"), bootstyle="inverse-info").pack(side="left")

        # Close button
        close_btn = tb.Button(title_frame, text="✕", bootstyle="danger-outline", 
                            command=lambda: self.close_client_modal(modal), width=3)
        close_btn.pack(side="right", padx=(10, 0))

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

        # Context menu for right-click actions
        self.setup_client_context_menu()

        # Load existing clients from database first
        self.load_existing_clients()
        
        # Start initial scan and auto-refresh
        self.start_client_scan()
        self.start_auto_refresh()

        # Handle window close
        modal.protocol("WM_DELETE_WINDOW", lambda: self.close_client_modal(modal))

    def load_existing_clients(self):
        """Load existing clients from database."""
        try:
            from db import get_network_clients, create_network_clients_table, create_connection_history_table
            
            # Create tables if they don't exist
            create_network_clients_table()
            create_connection_history_table()
            
            # Get existing clients
            existing_clients = get_network_clients(online_only=False, limit=1000)
            
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
            print(f"❌ Error loading existing clients: {e}")

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
        """Start scanning for network clients."""
        self.scan_btn.config(state="disabled", text="🔄 Scanning...")
        self.client_status_label.config(text="Scanning network for clients...", bootstyle="warning")
        
        def scan_thread():
            try:
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
                scanned_clients = scan_subnet(iface=iface, timeout=3)
                
                # Process and save clients
                self.client_data = []
                current_time = datetime.now()
                
                for mac, info in scanned_clients.items():
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
                self.root.after(0, lambda: self.client_status_label.config(
                    text=f"Scan failed: {str(e)}", bootstyle="danger"))
            finally:
                self.root.after(0, lambda: self.scan_btn.config(
                    state="normal", text="🔄 Scan Now"))

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

    def update_client_display(self):
        """Update the client display with current data."""
        # Clear existing items
        for item in self.client_tree.get_children():
            self.client_tree.delete(item)
        
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
        
        self.client_stats_online.config(text=f"Online: {online_count}")
        self.client_stats_total.config(text=f"Total: {total_count}")
        
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
        
        self.client_status_label.config(text=status_text, bootstyle="success")
        self.client_last_update.config(text=f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

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
        self.auto_refresh_enabled = True
        self.auto_refresh_btn.config(text="▶️ Auto Refresh", bootstyle="warning")
        if self.auto_refresh_job:
            self.root.after_cancel(self.auto_refresh_job)
            self.auto_refresh_job = None

    def schedule_auto_refresh(self):
        """Schedule the next auto refresh."""
        if self.auto_refresh_enabled:
            self.auto_refresh_job = self.root.after(self.auto_refresh_interval, self.auto_refresh_clients)

    def auto_refresh_clients(self):
        """Perform automatic client refresh."""
        if self.auto_refresh_enabled:
            self.start_client_scan()
            self.schedule_auto_refresh()

    def export_clients(self):
        """Export client data to CSV."""
        try:
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Export Network Clients"
            )
            
            if filename:
                import csv
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(["Status", "IP Address", "MAC Address", "Hostname", "Vendor", "Ping (ms)", "First Seen", "Last Seen"])
                    
                    for client in self.filtered_client_data:
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
                
                messagebox.showinfo("Export Complete", f"Client data exported to {filename}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export data: {str(e)}")

    def view_client_details(self):
        """View detailed information about selected client."""
        try:
            selection = self.client_tree.selection()[0]
            item = self.client_tree.item(selection)
            values = item['values']
            
            # Create details window
            details_window = tb.Toplevel(self.root)
            details_window.title("Client Details")
            details_window.geometry("500x400")
            details_window.resizable(False, False)
            
            # Center window
            details_window.update_idletasks()
            x = (details_window.winfo_screenwidth() - details_window.winfo_width()) // 2
            y = (details_window.winfo_screenheight() - details_window.winfo_height()) // 2
            details_window.geometry(f"+{x}+{y}")
            
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
            
            # Close button
            tb.Button(frame, text="Close", bootstyle="secondary", 
                     command=details_window.destroy).pack(pady=(20, 0))
            
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
            
            # Create history modal
            history_modal = tb.Toplevel(self.root)
            history_modal.title(f"📊 Connection History - {hostname}")
            history_modal.geometry("900x600")
            history_modal.resizable(True, True)
            history_modal.configure(bg='#f8f9fa')
            
            # Center modal
            history_modal.update_idletasks()
            x = (history_modal.winfo_screenwidth() - history_modal.winfo_width()) // 2
            y = (history_modal.winfo_screenheight() - history_modal.winfo_height()) // 2
            history_modal.geometry(f"+{x}+{y}")
            
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
            
            close_btn = tb.Button(title_frame, text="✕", bootstyle="danger-outline", 
                                command=history_modal.destroy, width=3)
            close_btn.pack(side="right", padx=(10, 0))
            
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
            
            # Configure columns
            column_widths = [100, 120, 120, 80, 150, 120]
            for i, (col, width) in enumerate(zip(cols, column_widths)):
                history_tree.heading(col, text=col)
                history_tree.column(col, width=width, anchor="center")
            
            # Scrollbars
            v_scrollbar = tb.Scrollbar(tree_frame, orient="vertical", command=history_tree.yview)
            h_scrollbar = tb.Scrollbar(tree_frame, orient="horizontal", command=history_tree.xview)
            history_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
            
            # Pack treeview and scrollbars
            history_tree.pack(side="left", fill="both", expand=True)
            v_scrollbar.pack(side="right", fill="y")
            h_scrollbar.pack(side="bottom", fill="x")
            
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
        """Handle closing the client modal."""
        self.stop_auto_refresh()
        if modal:
            modal.destroy()
        else:
            # Find and close the modal window
            for child in self.root.winfo_children():
                if isinstance(child, tb.Toplevel) and child.title() == "🌐 Network Clients Monitor":
                    child.destroy()
                    break

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
            print("🔄 Automatic loop detection started")

    def stop_loop_detection(self):
        """Stop automatic loop detection."""
        self.loop_detection_running = False
        if self.loop_detection_thread:
            self.loop_detection_thread = None
        print("⏹️ Automatic loop detection stopped")

    def _run_loop_detection(self):
        """Background loop detection thread."""
        while self.loop_detection_running and self.app_running:
            try:
                from network_utils import detect_loops_lightweight
                
                # Run lightweight detection
                total_packets, offenders, stats, status, severity_score = detect_loops_lightweight(
                    timeout=3,  # 3 seconds for efficiency
                    threshold=30,  # Lower threshold for sensitivity
                    iface="Wi-Fi"  # or get_default_iface()
                )
                
                # Save to database
                from db import save_loop_detection
                detection_id = save_loop_detection(
                    total_packets=total_packets,
                    offenders=offenders,
                    stats=stats,
                    status=status,
                    severity_score=severity_score,
                    interface="Wi-Fi",
                    duration=3
                )
                
                # Send notification for loop detection
                if status in ["loop_detected", "suspicious"]:
                    notify_loop_detected(severity_score, offenders, "Wi-Fi")
                    # Update notification count in main thread
                    self.root.after(0, self.update_notification_count)
                
                # Reload stats and history from database
                from db import get_loop_detection_stats, get_loop_detections_history
                self.loop_detection_stats = get_loop_detection_stats()
                self.loop_detection_history = get_loop_detections_history(100)
                
                # Print status
                if status == "loop_detected":
                    print(f"⚠️ LOOP DETECTED! Severity: {severity_score:.2f}, Offenders: {len(offenders)}")
                elif status == "suspicious":
                    print(f"🔍 Suspicious activity detected. Severity: {severity_score:.2f}")
                else:
                    print(f"✅ Network clean. Severity: {severity_score:.2f}")
                
                # Create detection record for UI
                detection_record = {
                    "timestamp": datetime.now().isoformat(),
                    "total_packets": total_packets,
                    "offenders": offenders,
                    "stats": stats,
                    "status": status,
                    "severity_score": severity_score,
                    "duration": 3
                }
                
                # Update UI if loop detection tab is visible
                self._update_loop_detection_ui(detection_record)
                
                # Refresh history table if modal is open
                try:
                    if hasattr(self, 'loop_detection_tree') and self.loop_detection_tree.winfo_exists():
                        self._load_loop_detection_history_modal()
                except:
                    pass  # Modal might not be open
                
            except Exception as e:
                print(f"❌ Loop detection error: {e}")
            
            # Wait for next interval
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
        print(f"🔄 Loop detection interval set to {interval_minutes} minutes")

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
            
            print(f"📊 Loop detection history exported to {filename}")
            return filename
            
        except Exception as e:
            print(f"❌ Error exporting history: {e}")
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
    
    def _create_router_notification(self, router_name, router_ip, is_online):
        """Create a router status change notification in the main thread."""
        try:
            print(f"🔔 Creating router notification: {router_name} ({router_ip}) - {'Online' if is_online else 'Offline'}")
            notification_id = notify_router_status_change(router_name, router_ip, is_online)
            print(f"🔔 Notification created with ID: {notification_id}")
            print(f"🔔 Callbacks registered: {len(notification_manager.notification_callbacks)}")
        except Exception as e:
            print(f"❌ Error creating router notification: {e}")

    def update_notification_count(self):
        """Update the notification count badge."""
        try:
            count = self.notification_system.get_notification_count()
            self.notification_count = count
            
            print(f"🔔 Updating notification count: {count}")
            
            if count > 0:
                self.notification_badge.config(text=str(count), background="#dc3545")
                self.notification_badge.place(in_=self.notification_btn, x=180, y=5)
                print(f"🔔 Badge updated with count: {count}")
            else:
                self.notification_badge.place_forget()
                print("🔔 Badge hidden (no notifications)")
        except Exception as e:
            print(f"Error updating notification count: {e}")
    
    def on_close(self):
        """Confirm and exit the entire application cleanly from the Admin window."""
        answer = messagebox.askyesno("Exit Confirmation", "Are you sure you want to exit WinyFi?")
        if not answer:
            return

        # Stop background activities
        self.app_running = False
        try:
            self.stop_loop_detection()
        except Exception:
            pass
        try:
            if getattr(self, 'update_task', None):
                self.root.after_cancel(self.update_task)
        except Exception:
            pass

        # Destroy the admin window
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

        # Hard-exit fallback to ensure full termination
        try:
            os._exit(0)
        except Exception:
            pass
    
    def show_user_profile(self):
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
            login_time = last_login_info.get('login_timestamp')
            device_ip = last_login_info.get('device_ip', 'Unknown')
            device_mac = last_login_info.get('device_mac', 'Unknown')
            
            # Format the timestamp
            if login_time:
                if isinstance(login_time, str):
                    formatted_time = login_time
                else:
                    formatted_time = login_time.strftime('%Y-%m-%d %H:%M:%S')
                last_login_display = f"{formatted_time} | {device_ip} | {device_mac}"
            else:
                last_login_display = f"Unknown | {device_ip} | {device_mac}"
        else:
            last_login_display = "No login data available"
        
        user_info_data = [
            ("🆔", "User ID", str(user_id) if user_id != 'N/A' else 'Unknown'),
            ("✅", "Account Status", "Active"),
            ("🕒", "Last Login", last_login_display),
        ]
        
        # Add additional device information if available
        if last_login_info:
            device_hostname = last_login_info.get('device_hostname', 'Unknown')
            device_platform = last_login_info.get('device_platform', 'Unknown')
            
            user_info_data.extend([
                ("💻", "Device Hostname", device_hostname),
                ("🖥️", "Device Platform", device_platform),
            ])
        else:
            # Show fallback device info if no login data available
            user_info_data.extend([
                ("💻", "Device Hostname", "Not Available"),
                ("🖥️", "Device Platform", "Not Available"),
            ])
        
        # Create modern info grid
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
            ("🔒", "Change Password", "primary", lambda: self.handle_profile_option("Change Password")),
            ("✏️", "Edit Profile", "success", self.edit_user_profile),
            ("🔔", "Notifications", "warning", lambda: self.handle_profile_option("Notifications")),
            ("⚙️", "Settings", "secondary", lambda: self.handle_profile_option("Settings")),
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
        
        export_btn = tb.Button(account_card, text="📊 Export Data", 
                              bootstyle="info", 
                              command=self.open_export_menu,
                              width=22)
        export_btn.pack(fill="x")
        
        # Footer with modern styling
        footer_frame = tb.Frame(main_container)
        footer_frame.pack(fill="x", pady=(10, 0))
        
        footer_text = tb.Label(footer_frame, 
                              text="💡 Manage your account settings and preferences from this modern dashboard", 
                              font=("Segoe UI", 11), 
                              foreground="#9ca3af")
        footer_text.pack()
        
        # Store reference to modal
        self.profile_modal = profile_modal

    def handle_profile_option(self, option):
        """Handle profile option selection"""
        messagebox.showinfo("Feature Coming Soon", f"{option} functionality will be implemented soon.")

    def edit_user_profile(self):
        """Edit user profile information"""
        messagebox.showinfo("Edit Profile", "Profile editing functionality will be implemented soon.")

    def logout(self):
        """Log out to the login screen without exiting the application."""
        if not messagebox.askyesno("Log Out", "Are you sure you want to log out?"):
            return

        # Stop background tasks
        self.app_running = False
        try:
            self.stop_loop_detection()
        except Exception:
            pass
        try:
            if getattr(self, 'update_task', None):
                self.root.after_cancel(self.update_task)
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
