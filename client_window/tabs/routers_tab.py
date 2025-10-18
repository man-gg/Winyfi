import os
import ttkbootstrap as tb
import tkinter as tk
import requests
import threading
from datetime import datetime, timedelta
from tkinter import messagebox
from PIL import Image, ImageTk


class RoutersTab:
    def __init__(self, parent_frame, api_base_url, root_window):
        self.parent_frame = parent_frame
        self.api_base_url = api_base_url
        self.root = root_window
        self.auto_update_interval = 30000  # 30 seconds in milliseconds
        self.is_updating = False
        self.auto_update_job = None
        self.last_update_time = None
        router_header_frame = tb.Frame(self.parent_frame)
        router_header_frame.pack(fill="x", padx=10, pady=(10, 0))
        tb.Label(router_header_frame, text="Routers",
                 font=("Segoe UI", 14, "bold")).pack(side="left")

        # Auto-update controls (more compact)
        auto_update_frame = tb.Frame(router_header_frame)
        auto_update_frame.pack(side="right", padx=5)
        self.auto_update_var = tb.BooleanVar(value=True)
        auto_update_check = tb.Checkbutton(auto_update_frame, text="Auto", 
                                          variable=self.auto_update_var,
                                          command=self.toggle_auto_update,
                                          bootstyle="success")
        auto_update_check.pack(side="right", padx=(0, 5))

        # Update interval selector (more compact)
        self.interval_var = tb.StringVar(value="30s")
        interval_combo = tb.Combobox(auto_update_frame, textvariable=self.interval_var, 
                                     values=["10s", "30s", "1m", "2m", "5m"], 
                                     width=5, state="readonly")
        interval_combo.pack(side="right", padx=(0, 5))
        interval_combo.bind("<<ComboboxSelected>>", self.on_interval_changed)

        self.last_update_label = tb.Label(auto_update_frame, text="", 
                                         font=("Segoe UI", 7), bootstyle="secondary")
        self.last_update_label.pack(side="right", padx=(0, 5))

        # Button container for better organization
        button_frame = tb.Frame(router_header_frame)
        button_frame.pack(side="right", padx=5)
        tb.Button(button_frame, text="🔄 Refresh",
                  bootstyle="info", command=self.load_routers, width=8).pack(side="right", padx=2)
        tb.Button(button_frame, text="👥 Clients",
                  bootstyle="info", command=self.show_network_clients, width=8).pack(side="right", padx=2)
        tb.Button(button_frame, text="🔄 Loops",
                  bootstyle="warning", command=self.show_loop_detection, width=8).pack(side="right", padx=2)
        tb.Button(button_frame, text="➕ Add",
                  bootstyle="success", state='disabled', width=6).pack(side="right", padx=2)

        filter_frame = tb.Frame(self.parent_frame)
        filter_frame.pack(pady=5, padx=10, fill="x")
        tb.Label(filter_frame, text="Filter:", bootstyle="info").pack(side="left", padx=(0, 5))
        self.router_search_var = tb.StringVar()
        search_entry = tb.Entry(filter_frame, textvariable=self.router_search_var, width=30)
        search_entry.pack(side="left")
        self.router_search_var.trace_add("write", lambda *_: self.apply_router_filter())
        tb.Label(filter_frame, text="Type:", bootstyle="info").pack(side="left", padx=(20, 5))
        self.router_type_var = tb.StringVar(value="All")
        type_combo = tb.Combobox(filter_frame, textvariable=self.router_type_var,
                                 values=["All", "UniFi", "Non-UniFi"], state="readonly", width=10)
        type_combo.pack(side="left")
        type_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_router_filter())
        tb.Label(filter_frame, text="Sort by:", bootstyle="info").pack(side="left", padx=(20, 5))
        self.router_sort_var = tb.StringVar(value="default")
        tb.Radiobutton(filter_frame, text="Default", variable=self.router_sort_var, value="default",
                       command=self.apply_router_filter).pack(side="left")
        tb.Radiobutton(filter_frame, text="Online First", variable=self.router_sort_var, value="online",
                       command=self.apply_router_filter).pack(side="left", padx=(5, 0))
        # Loading animation frame
        self.loading_frame = tb.Frame(self.parent_frame)
        self.loading_label = tb.Label(self.loading_frame, text="Loading...", font=("Segoe UI", 12), bootstyle="info")
        self.loading_label.pack(padx=10, pady=10)

        canvas_frame = tb.Frame(self.parent_frame)
        canvas_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.canvas = tb.Canvas(canvas_frame)
        scrollbar = tb.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tb.Frame(self.canvas)
        self._canvas_window_id = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self._canvas_window_id, width=e.width))
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.router_status_var = tb.StringVar(value="Loading routers…")
        tb.Label(self.parent_frame, textvariable=self.router_status_var, bootstyle='secondary').pack(padx=10, pady=(0,10), anchor='w')

        # Data state
        self.router_list = []
        self.filtered_router_list = []
        # Load initial
        self.load_routers()
        # Start auto-update
        self.start_auto_update()

        self.router_status_var = tb.StringVar(value="Loading routers…")
        tb.Label(self.parent_frame, textvariable=self.router_status_var, bootstyle='secondary').pack(padx=10, pady=(0,10), anchor='w')

        # Data state
        self.router_list = []
        self.filtered_router_list = []
        # Load initial
        self.load_routers()
        # Start auto-update
        self.start_auto_update()

    def _is_router_online(self, router):
        """
        Check if router is online based on router_status_log table.
        Router is considered online if there's an 'online' status entry 
        within the last 5 seconds.
        """
        try:
            # Use the API endpoint to get status-based online detection
            r = requests.get(f"{self.api_base_url}/api/routers/{router['id']}/status", timeout=3)
            if r.ok:
                status_data = r.json()
                return status_data.get('is_online', False)
            else:
                # Fallback to old method if API fails
                return self._is_router_online_fallback(router)
        except Exception:
            # Fallback to old method if API fails
            return self._is_router_online_fallback(router)
    
    def _is_router_online_fallback(self, router):
        """Fallback method using last_seen field"""
        try:
            last_seen = router.get('last_seen')
            if not last_seen:
                return False
            dt = None
            if isinstance(last_seen, str):
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
                    try:
                        dt = datetime.strptime(last_seen, fmt)
                        break
                    except Exception:
                        dt = None
            else:
                dt = last_seen
            if not dt:
                return False
            return dt >= datetime.now() - timedelta(minutes=5)
        except Exception:
            return False

    def load_routers(self):
        self._show_routers_loading()
        if self.is_updating:
            return  # Prevent multiple simultaneous updates
        self.is_updating = True
        try:
            # Show updating indicator
            self.router_status_var.set("Updating routers...")
            self.root.update_idletasks()
            r = requests.get(f"{self.api_base_url}/api/routers", timeout=8)
            if not r.ok:
                self.router_status_var.set(f"Failed to load routers: {r.status_code}")
                return
            self.router_list = r.json() or []
            self.router_status_var.set(f"Loaded {len(self.router_list)} routers")
            self.last_update_time = datetime.now()
            self.update_last_update_display()
            self.apply_router_filter()
        except Exception as exc:
            self.router_status_var.set(f"Error loading routers: {exc}")
        finally:
            self.is_updating = False
            self._hide_routers_loading()

    def apply_router_filter(self):
        self._show_routers_loading()
        text = (self.router_search_var.get() or "").strip().lower()
        type_filter = self.router_type_var.get()
        flt = []
        for r in self.router_list:
            blob = " ".join(str(r.get(k, "")) for k in ("name","ip_address","brand","location")).lower()
            if text and text not in blob:
                continue
            if type_filter == "UniFi" and not (r.get("brand", "").lower() == "unifi" or r.get("is_unifi")):
                continue
            if type_filter == "Non-UniFi" and (r.get("brand", "").lower() == "unifi" or r.get("is_unifi")):
                continue
            flt.append(r)
        sort_mode = self.router_sort_var.get()
        if sort_mode == "online":
            flt.sort(key=lambda r: (not self._is_router_online(r), str(r.get('name','')).lower()))
        else:
            flt.sort(key=lambda r: str(r.get('name','')).lower())
        self.filtered_router_list = flt
        self.render_router_cards(flt)
        self._hide_routers_loading()

    def render_router_cards(self, routers):
        # Clear previous cards
        for child in list(self.scrollable_frame.winfo_children()):
            child.destroy()

        if not routers:
            tb.Label(self.scrollable_frame, text="No routers to display", font=("Segoe UI", 11)).pack(pady=20)
            return

        online_list = [r for r in routers if self._is_router_online(r)]
        offline_list = [r for r in routers if not self._is_router_online(r)]

        self.router_widgets = {}  # Store widgets for later updates

        def section(title, items):
            if not items:
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
                for i, router in enumerate(items):
                    row, col = divmod(i, max_cols)
                    is_unifi = router.get('brand', '').lower() == 'unifi' or router.get('is_unifi')
                    card_style = "primary" if is_unifi else "info"
                    card = tb.LabelFrame(sec, text=router.get('name', 'Unknown'), bootstyle=card_style, padding=0)
                    card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
                    sec.grid_columnconfigure(col, weight=1)
                    inner = tb.Frame(card, padding=10)
                    inner.pack(fill="both", expand=True)
                    # UniFi badge and icon
                    if is_unifi:
                        tb.Label(inner, text="📡", font=("Segoe UI Emoji", 30)).pack()
                        tb.Label(inner, text="UniFi Device", font=("Segoe UI", 8, "italic"), bootstyle="primary").pack()
                    else:
                        tb.Label(inner, text="⛀", font=("Segoe UI Emoji", 30)).pack()
                    ip = router.get('ip_address') or router.get('ip') or '—'
                    tb.Label(inner, text=ip, font=("Segoe UI", 10)).pack(pady=(5, 0))
                    # Status
                    online = self._is_router_online(router)
                    if is_unifi:
                        status_text, status_style = ("🟢 Online", "success")
                    else:
                        status_text, status_style = ("🟢 Online", "success") if online else ("🔴 Offline", "danger")
                    status_label = tb.Label(inner, text=status_text, bootstyle=status_style, cursor="hand2")
                    status_label.pack(pady=5)
                    # Bandwidth/latency
                    if is_unifi:
                        down = router.get('download_speed', 0)
                        up = router.get('upload_speed', 0)
                        latency = router.get('latency')
                        if latency is not None:
                            lbl_bandwidth = tb.Label(inner, text=f"📶 ↓{down:.1f} Mbps ↑{up:.1f} Mbps   ⚡ {latency:.1f} ms", bootstyle="success")
                        else:
                            lbl_bandwidth = tb.Label(inner, text=f"📶 ↓{down:.1f} Mbps ↑{up:.1f} Mbps   ⚡ N/A", bootstyle="success")
                        lbl_bandwidth.pack(pady=2)
                    else:
                        lbl_bandwidth = tb.Label(inner, text="⏳ Bandwidth: N/A", bootstyle="secondary")
                        lbl_bandwidth.pack(pady=2)
                    # Store widgets for later update
                    rid = router.get('id')
                    if rid:
                        self.router_widgets[rid] = {
                            'card': card,
                            'status_label': status_label,
                            'bandwidth_label': lbl_bandwidth,
                            'data': router
                        }
                    # Bind click to open details
                    def bind_card_click(widget, router_obj):
                        widget.bind("<Button-1>", lambda e: self.open_router_details(router_obj))
                    bind_card_click(inner, router)
                    for child in inner.winfo_children():
                        bind_card_click(child, router)
                    # Hover effect
                    if is_unifi:
                        def on_enter(e, c=card): c.configure(bootstyle="success")
                        def on_leave(e, c=card): c.configure(bootstyle="primary")
                    else:
                        def on_enter(e, c=card): c.configure(bootstyle="primary")
                        def on_leave(e, c=card): c.configure(bootstyle="info")
                    card.bind("<Enter>", on_enter)
                    card.bind("<Leave>", on_leave)
            def on_resize(event):
                if hasattr(sec, '_resize_job') and sec._resize_job is not None:
                    try:
                        sec.after_cancel(sec._resize_job)
                    except Exception:
                        pass
                sec._resize_job = sec.after(300, render_cards)
            sec.bind("<Configure>", on_resize)
            render_cards()
        # Respect sort toggle: online first vs default
        if self.router_sort_var.get() == "online":
            section("🟢 Online Routers", online_list)
            section("🔴 Offline Routers", offline_list)
        else:
            section("🟢 Online Routers", online_list + offline_list)
    def _show_routers_loading(self):
        self.loading_frame.pack(fill="x", padx=10, pady=10)
        self.root.update_idletasks()

    def _hide_routers_loading(self):
        self.loading_frame.pack_forget()
        self.root.update_idletasks()

    def open_router_details(self, router):
        # Modernized client-side router details aligned with admin UI
        d = tk.Toplevel(self.root)
        d.title(f"Router Details - {router.get('name','')}")
        d.geometry("700x600")
        d.transient(self.root)
        d.grab_set()
        d.configure(bg='#f8f9fa')
        d.resizable(True, True)

        # Center window
        self.root.update_idletasks()
        rx, ry = self.root.winfo_x(), self.root.winfo_y()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        w, h = 700, 600
        x = rx + (rw // 2) - (w // 2)
        y = ry + (rh // 2) - (h // 2)
        d.geometry(f"{w}x{h}+{x}+{y}")

        # Main container
        main_container = tb.Frame(d, bootstyle="light")
        main_container.pack(fill="both", expand=True, padx=20, pady=20)

        # Header
        header_frame = tb.LabelFrame(main_container, text="", bootstyle="primary", padding=20)
        header_frame.pack(fill="x", pady=(0, 20))

        title_frame = tb.Frame(header_frame)
        title_frame.pack(fill="x")

        status_indicator = tb.Frame(title_frame, width=20, height=20)
        status_indicator.pack(side="left", padx=(0, 15))
        status_circle = tb.Label(status_indicator, text="●", font=("Segoe UI", 24), bootstyle="secondary")
        status_circle.pack()

        title_text_frame = tb.Frame(title_frame)
        title_text_frame.pack(side="left", fill="x", expand=True)
        tb.Label(title_text_frame, text=f"📡 {router.get('name','')}", font=("Segoe UI", 20, "bold"), bootstyle="primary").pack(anchor="w")
        ip_text = router.get('ip_address') or router.get('ip') or '—'
        tb.Label(title_text_frame, text=f"IP: {ip_text}", font=("Segoe UI", 12), bootstyle="secondary").pack(anchor="w")

        quick_actions = tb.Frame(header_frame)
        quick_actions.pack(fill="x", pady=(15, 0))

        img_path = router.get('image_path')
        if img_path:
            tb.Button(quick_actions, text="📷 View Image", bootstyle="info",
                      command=lambda: self.show_router_image(img_path), width=15).pack(side="left")

        # Scrollable content area
        canvas = tk.Canvas(main_container, highlightthickness=0, bg='#f8f9fa')
        scrollbar = tb.Scrollbar(main_container, orient="vertical", command=canvas.yview, bootstyle="secondary")
        scroll_frame = tb.Frame(canvas, bootstyle="light")
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Store labels for updates
        detail_status_lbl = None
        detail_download_lbl = None
        detail_upload_lbl = None
        detail_last_seen_lbl = None
        detail_latency_lbl = None

        # Basic Information Card
        basic_info_card = tb.LabelFrame(scroll_frame, text="🔧 Basic Information", bootstyle="info", padding=20)
        basic_info_card.pack(fill="x", pady=(0, 15))
        basic_grid = tb.Frame(basic_info_card)
        basic_grid.pack(fill="x")
        basic_grid.grid_columnconfigure(1, weight=1)
        basic_grid.grid_columnconfigure(3, weight=1)

        name = router.get('name','—')
        mac = router.get('mac_address','—')
        brand = router.get('brand','—')
        location = router.get('location','—')
        basic_fields = [
            ("🏷️ Name:", name),
            ("📍 Location:", location),
            ("🏭 Brand:", brand),
            ("📱 MAC Address:", mac),
        ]
        for i, (label, value) in enumerate(basic_fields):
            row, col = i // 2, (i % 2) * 2
            tb.Label(basic_grid, text=label, font=("Segoe UI", 11, "bold"), bootstyle="secondary").grid(row=row, column=col, sticky="w", padx=(0, 10), pady=8)
            tb.Label(basic_grid, text=value, font=("Segoe UI", 11), bootstyle="dark").grid(row=row, column=col+1, sticky="w", padx=(0, 30), pady=8)

        # Connection Status Card
        status_card = tb.LabelFrame(scroll_frame, text="🌐 Connection Status", bootstyle="success", padding=20)
        status_card.pack(fill="x", pady=(0, 15))
        status_row = tb.Frame(status_card)
        status_row.pack(fill="x", pady=(0, 15))
        tb.Label(status_row, text="📶 Current Status:", font=("Segoe UI", 12, "bold"), bootstyle="secondary").pack(side="left")
        detail_status_lbl = tb.Label(status_row, text="🕒 Checking...", font=("Segoe UI", 12, "bold"), bootstyle="warning")
        detail_status_lbl.pack(side="left", padx=(10, 0))

        last_seen_row = tb.Frame(status_card)
        last_seen_row.pack(fill="x")
        tb.Label(last_seen_row, text="🕐 Last Seen:", font=("Segoe UI", 11, "bold"), bootstyle="secondary").pack(side="left")
        last_seen = router.get('last_seen')
        ls_text = last_seen if isinstance(last_seen, str) else (last_seen.strftime('%Y-%m-%d %H:%M:%S') if last_seen else 'Never')
        detail_last_seen_lbl = tb.Label(last_seen_row, text=ls_text or 'Never', font=("Segoe UI", 11), bootstyle="dark")
        detail_last_seen_lbl.pack(side="left", padx=(10, 0))

        # Performance Metrics Card
        performance_card = tb.LabelFrame(scroll_frame, text="📊 Performance Metrics", bootstyle="warning", padding=20)
        performance_card.pack(fill="x", pady=(0, 15))

        latency_frame = tb.Frame(performance_card)
        latency_frame.pack(fill="x", pady=(0, 15))
        tb.Label(latency_frame, text="⚡ Latency:", font=("Segoe UI", 12, "bold"), bootstyle="secondary").pack(side="left")
        detail_latency_lbl = tb.Label(latency_frame, text="📡 Measuring...", font=("Segoe UI", 12), bootstyle="info")
        detail_latency_lbl.pack(side="left", padx=(10, 0))

        bandwidth_frame = tb.LabelFrame(performance_card, text="🚀 Bandwidth Usage", bootstyle="info", padding=15)
        bandwidth_frame.pack(fill="x")
        download_frame = tb.Frame(bandwidth_frame)
        download_frame.pack(fill="x", pady=(0, 10))
        tb.Label(download_frame, text="⬇️", font=("Segoe UI", 16)).pack(side="left", padx=(0, 10))
        download_text_frame = tb.Frame(download_frame)
        download_text_frame.pack(side="left", fill="x", expand=True)
        tb.Label(download_text_frame, text="Download Speed", font=("Segoe UI", 10, "bold"), bootstyle="secondary").pack(anchor="w")
        detail_download_lbl = tb.Label(download_text_frame, text="📶 Fetching...", font=("Segoe UI", 14, "bold"), bootstyle="success")
        detail_download_lbl.pack(anchor="w")

        upload_frame = tb.Frame(bandwidth_frame)
        upload_frame.pack(fill="x")
        tb.Label(upload_frame, text="⬆️", font=("Segoe UI", 16)).pack(side="left", padx=(0, 10))
        upload_text_frame = tb.Frame(upload_frame)
        upload_text_frame.pack(side="left", fill="x", expand=True)
        tb.Label(upload_text_frame, text="Upload Speed", font=("Segoe UI", 10, "bold"), bootstyle="secondary").pack(anchor="w")
        detail_upload_lbl = tb.Label(upload_text_frame, text="📶 Fetching...", font=("Segoe UI", 14, "bold"), bootstyle="primary")
        detail_upload_lbl.pack(anchor="w")

        # Additional Actions Card
        actions_card = tb.LabelFrame(scroll_frame, text="⚙️ Additional Actions", bootstyle="dark", padding=20)
        actions_card.pack(fill="x", pady=(0, 15))
        actions_grid = tb.Frame(actions_card)
        actions_grid.pack(fill="x")
        tb.Button(actions_grid, text="🔄 Refresh Data", bootstyle="info", command=lambda: refresh_details(), width=20).grid(row=0, column=0, padx=10, pady=5, sticky="ew")
        tb.Button(actions_grid, text="📈 View History", bootstyle="secondary", command=lambda: self.open_router_history(router), width=20).grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        actions_grid.grid_columnconfigure(0, weight=1)
        actions_grid.grid_columnconfigure(1, weight=1)

        def refresh_details():
            if not d.winfo_exists():
                return
            rid = router.get('id')
            # Status via API
            try:
                rs = requests.get(f"{self.api_base_url}/api/routers/{rid}/status", timeout=5)
                if rs.ok:
                    info = rs.json() or {}
                    is_online = info.get('is_online', False)
                    if is_online:
                        detail_status_lbl.config(text="🟢 Online", bootstyle="success")
                        status_circle.config(text="●", bootstyle="success")
                    else:
                        detail_status_lbl.config(text="🔴 Offline", bootstyle="danger")
                        status_circle.config(text="●", bootstyle="danger")
                else:
                    detail_status_lbl.config(text="🔄 Checking...", bootstyle="warning")
                    status_circle.config(text="●", bootstyle="warning")
            except Exception:
                detail_status_lbl.config(text="🔄 Checking...", bootstyle="warning")
                status_circle.config(text="●", bootstyle="warning")

            # Latest bandwidth log
            try:
                br = requests.get(f"{self.api_base_url}/api/bandwidth/logs", params={"router_id": rid, "limit": 1}, timeout=5)
                if br.ok:
                    arr = br.json() or []
                    if arr:
                        row = arr[0]
                        dl = row.get('download_mbps') or 0
                        ul = row.get('upload_mbps') or 0
                        lat = row.get('latency_ms') or 0
                        detail_download_lbl.config(text=f"{dl:.2f} Mbps")
                        detail_upload_lbl.config(text=f"{ul:.2f} Mbps")
                        detail_latency_lbl.config(text=f"{lat:.0f} ms", bootstyle="success")
                    else:
                        detail_download_lbl.config(text="No data")
                        detail_upload_lbl.config(text="No data")
                        detail_latency_lbl.config(text="—")
                else:
                    detail_download_lbl.config(text="📶 Fetching...")
                    detail_upload_lbl.config(text="📶 Fetching...")
                    detail_latency_lbl.config(text="📡 Measuring...")
            except Exception:
                detail_download_lbl.config(text="📶 Fetching...")
                detail_upload_lbl.config(text="📶 Fetching...")
                detail_latency_lbl.config(text="📡 Measuring...")

            d.after(3000, refresh_details)

        refresh_details()

    def show_router_image(self, image_path):
        if not image_path or not os.path.exists(image_path):
            return messagebox.showerror("Image Not Found", "No image file found for this router.")
        img_win = tk.Toplevel(self.root)
        img_win.title("Router Image")
        img_win.geometry("850x650")
        img_win.transient(self.root)
        img_win.grab_set()
        try:
            img = Image.open(image_path)
            img = img.resize((800, 600), Image.Resampling.LANCZOS)
            ph = ImageTk.PhotoImage(img)
            lbl = tb.Label(img_win, image=ph)
            lbl.image = ph
            lbl.pack(padx=10, pady=10)
        except Exception:
            messagebox.showerror("Error", "Could not display image.")

    def open_router_history(self, router):
        # History modal for client side using API; falls back to report_utils if available
        win = tk.Toplevel(self.root)
        win.title(f"📈 History - {router.get('name','Router')}")
        win.geometry("800x600")
        win.transient(self.root)
        win.grab_set()

        # Center
        self.root.update_idletasks()
        rx, ry = self.root.winfo_x(), self.root.winfo_y()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        w, h = 800, 600
        x = rx + (rw // 2) - (w // 2)
        y = ry + (rh // 2) - (h // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")

        outer = tb.Frame(win, padding=15)
        outer.pack(fill="both", expand=True)

        # Date range controls
        controls = tb.Frame(outer)
        controls.pack(fill="x", pady=(0, 10))
        tb.Label(controls, text="Start:").pack(side="left")
        start_var = tb.StringVar()
        end_var = tb.StringVar()
        now = datetime.now()
        start_default = now - timedelta(days=7)
        start_var.set(start_default.strftime("%Y-%m-%d"))
        end_var.set(now.strftime("%Y-%m-%d"))
        tb.Entry(controls, textvariable=start_var, width=12).pack(side="left", padx=5)
        tb.Label(controls, text="End:").pack(side="left")
        tb.Entry(controls, textvariable=end_var, width=12).pack(side="left", padx=5)
        tb.Button(controls, text="🔄 Refresh", bootstyle="info", command=lambda: load_data()).pack(side="left", padx=10)

        # Summary cards
        cards = tb.Frame(outer)
        cards.pack(fill="x")
        for i in range(3):
            cards.grid_columnconfigure(i, weight=1)
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
        tree = tk.ttk.Treeview(logs_frame, columns=cols, show="headings") if hasattr(tk, 'ttk') else ttk.Treeview(logs_frame, columns=cols, show="headings")
        # Fallback to ttk import
        try:
            from tkinter import ttk as _ttk
            tree = _ttk.Treeview(logs_frame, columns=cols, show="headings")
            vsb = _ttk.Scrollbar(logs_frame, orient="vertical", command=tree.yview)
        except Exception:
            from tkinter import ttk
            tree = ttk.Treeview(logs_frame, columns=cols, show="headings")
            vsb = ttk.Scrollbar(logs_frame, orient="vertical", command=tree.yview)
        tree.heading("timestamp", text="Timestamp")
        tree.heading("status", text="Status")
        tree.column("timestamp", width=200, anchor="w")
        tree.column("status", width=120, anchor="center")
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        def load_data():
            try:
                s = datetime.strptime(start_var.get(), "%Y-%m-%d")
                e = datetime.strptime(end_var.get(), "%Y-%m-%d")
                e = datetime.combine(e.date(), datetime.max.time())
            except Exception:
                messagebox.showerror("Date Error", "Use YYYY-MM-DD format.")
                return
            rid = router.get('id')
            # Uptime + Bandwidth via server-side report_utils through direct import if available
            uptime = None
            bw_total = None
            try:
                from report_utils import get_uptime_percentage, get_bandwidth_usage, get_status_logs
                uptime = get_uptime_percentage(rid, s, e)
                bw_total = get_bandwidth_usage(rid, s, e)
                logs = get_status_logs(rid, s, e)
            except Exception:
                # Fallback: approximate uptime from status endpoint and leave logs empty
                logs = []
                try:
                    # We could add an API endpoint for logs; not available yet
                    pass
                except Exception:
                    pass

            if uptime is None:
                # If uptime not computable locally, leave as '-'
                uptime_lbl.config(text="-")
                downtime_lbl.config(text="-")
            else:
                uptime_lbl.config(text=f"{uptime:.2f}%")
                total_secs = (e - s).total_seconds()
                downtime_hours = round(((100 - uptime) / 100.0) * total_secs / 3600.0, 2)
                downtime_lbl.config(text=f"{downtime_hours:.2f}")

            if bw_total is None:
                # Try API bandwidth stats as fallback
                try:
                    params = {"router_id": rid, "start_date": s.strftime("%Y-%m-%d"), "end_date": e.strftime("%Y-%m-%d")}
                    br = requests.get(f"{self.api_base_url}/api/bandwidth/stats", params=params, timeout=6)
                    if br.ok:
                        data = br.json() or {}
                        # approximate MB from averages * count; not perfect
                        bw_total = round((data.get('avg_download', 0) + data.get('avg_upload', 0)) * max(data.get('total_measurements', 0), 1), 2)
                except Exception:
                    bw_total = None
            bw_lbl.config(text=f"{bw_total:.2f}" if bw_total is not None else "-")

            # Populate logs if available
            try:
                for iid in tree.get_children():
                    tree.delete(iid)
                for ts, status in logs:
                    ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if hasattr(ts, 'strftime') else str(ts)
                    tree.insert('', 'end', values=(ts_str, str(status).title()))
            except Exception:
                # Ignore if logs not available
                pass

        load_data()

    def start_auto_update(self):
        """Start the automatic update timer"""
        if self.auto_update_var.get():
            self.auto_update_job = self.root.after(self.auto_update_interval, self.auto_update_routers)

    def stop_auto_update(self):
        """Stop the automatic update timer"""
        if self.auto_update_job:
            self.root.after_cancel(self.auto_update_job)
            self.auto_update_job = None

    def toggle_auto_update(self):
        """Toggle auto-update on/off"""
        if self.auto_update_var.get():
            self.start_auto_update()
        else:
            self.stop_auto_update()

    def auto_update_routers(self):
        """Automatically update routers data"""
        if self.auto_update_var.get():
            self.load_routers()
            # Schedule next update
            self.auto_update_job = self.root.after(self.auto_update_interval, self.auto_update_routers)

    def update_last_update_display(self):
        """Update the last update time display"""
        if self.last_update_time:
            time_str = self.last_update_time.strftime("%H:%M:%S")
            self.last_update_label.config(text=f"Last update: {time_str}")

    def on_interval_changed(self, event=None):
        """Handle interval selection change"""
        interval_str = self.interval_var.get()
        if interval_str == "10s":
            self.auto_update_interval = 10000
        elif interval_str == "30s":
            self.auto_update_interval = 30000
        elif interval_str == "1m":
            self.auto_update_interval = 60000
        elif interval_str == "2m":
            self.auto_update_interval = 120000
        elif interval_str == "5m":
            self.auto_update_interval = 300000
        
        # Restart auto-update with new interval if it's currently running
        if self.auto_update_var.get():
            self.stop_auto_update()
            self.start_auto_update()

    def show_network_clients(self):
        """Show network clients modal."""
        if self.client_modal and self.client_modal.winfo_exists():
            self.client_modal.lift()
            return
            
        self.client_modal = tb.Toplevel(self.root)
        self.client_modal.title("🌐 Network Clients Monitor")
        self.client_modal.geometry("1000x700")
        self.client_modal.resizable(True, True)
        self.client_modal.configure(bg='#f8f9fa')

        # Center modal
        self.client_modal.update_idletasks()
        x = (self.client_modal.winfo_screenwidth() - self.client_modal.winfo_width()) // 2
        y = (self.client_modal.winfo_screenheight() - self.client_modal.winfo_height()) // 2
        self.client_modal.geometry(f"+{x}+{y}")

        # Main container
        main_container = tb.Frame(self.client_modal, bootstyle="light")
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
                            command=self.close_client_modal, width=3)
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

        self.refresh_btn = tb.Button(btn_frame, text="🔄 Refresh", bootstyle="primary", 
                                command=self.load_clients_from_db, width=12)
        self.refresh_btn.pack(side="left", padx=2)

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
        self.client_auto_refresh_enabled = True
        self.client_auto_refresh_interval = 30000  # 30 seconds
        self.client_auto_refresh_job = None
        self.double_click_pending = False  # Flag to prevent single click on double click

        # Context menu for right-click actions
        self.setup_client_context_menu()

        # Load existing clients from database first
        self.load_existing_clients()
        
        # Load clients from database (read-only)
        self.load_clients_from_db()

        # Handle window close
        self.client_modal.protocol("WM_DELETE_WINDOW", self.close_client_modal)

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

    def load_existing_clients(self):
        """Load existing clients from database."""
        try:
            # Import database functions
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
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

    def load_clients_from_db(self):
        """Load clients from database via API (READ-ONLY)"""
        try:
            response = requests.get(f"{self.api_base_url}/api/clients", timeout=5)
            if response.ok:
                data = response.json()
                self.client_data = data.get('clients', [])
                self.update_client_display()
                self.client_status_label.config(text="Clients loaded successfully", bootstyle="success")
            else:
                self.client_data = []
                self.client_status_label.config(text="Failed to load clients", bootstyle="danger")
        except Exception as e:
            print(f"❌ Error loading clients: {e}")
            self.client_data = []
            self.client_status_label.config(text="Error loading clients", bootstyle="danger")
        
        # Update last update time
        from datetime import datetime
        time_str = datetime.now().strftime("%H:%M:%S")
        self.client_last_update.config(text=f"Last update: {time_str}")

    def start_client_scan(self):
        """Start scanning for network clients."""
        self.scan_btn.config(state="disabled", text="🔄 Scanning...")
        self.client_status_label.config(text="Scanning network for clients...", bootstyle="warning")
        
        def scan_thread():
            try:
                # Import required modules
                import sys
                import os
                sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
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
        if self.client_auto_refresh_enabled:
            self.stop_auto_refresh()
        else:
            self.start_auto_refresh()

    def start_auto_refresh(self):
        """Start automatic refresh."""
        self.client_auto_refresh_enabled = True
        self.auto_refresh_btn.config(text="⏸️ Stop Auto", bootstyle="danger")
        self.schedule_auto_refresh()

    def stop_auto_refresh(self):
        """Stop automatic refresh."""
        self.client_auto_refresh_enabled = True
        self.auto_refresh_btn.config(text="▶️ Auto Refresh", bootstyle="warning")
        if self.client_auto_refresh_job:
            self.root.after_cancel(self.client_auto_refresh_job)
            self.client_auto_refresh_job = None

    def schedule_auto_refresh(self):
        """Schedule the next auto refresh."""
        if self.client_auto_refresh_enabled:
            self.client_auto_refresh_job = self.root.after(self.client_auto_refresh_interval, self.auto_refresh_clients)

    def auto_refresh_clients(self):
        """Perform automatic client refresh."""
        if self.client_auto_refresh_enabled:
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

    def show_connection_history(self):
        """Show connection history for the selected client."""
        try:
            # Get selected item
            selected_item = self.client_tree.selection()[0]
            values = self.client_tree.item(selected_item, "values")
            mac_address = values[2]  # MAC address is in column 2
            hostname = values[3]     # Hostname is in column 3
            
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
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

    def view_client_details(self):
        """View detailed client information."""
        try:
            selected_item = self.client_tree.selection()[0]
            values = self.client_tree.item(selected_item, "values")
            
            # Create details modal
            details_modal = tb.Toplevel(self.root)
            details_modal.title(f"Client Details - {values[3]}")
            details_modal.geometry("500x400")
            details_modal.resizable(True, True)
            details_modal.configure(bg='#f8f9fa')
            
            # Center modal
            details_modal.update_idletasks()
            x = (details_modal.winfo_screenwidth() - details_modal.winfo_width()) // 2
            y = (details_modal.winfo_screenheight() - details_modal.winfo_height()) // 2
            details_modal.geometry(f"+{x}+{y}")
            
            # Main container
            main_container = tb.Frame(details_modal, bootstyle="light")
            main_container.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Header
            header_frame = tb.Frame(main_container, bootstyle="info")
            header_frame.pack(fill="x", pady=(0, 10))
            
            title_frame = tb.Frame(header_frame)
            title_frame.pack(fill="x", padx=15, pady=15)
            
            tb.Label(title_frame, text=f"🔍 Client Details - {values[3]}", 
                    font=("Segoe UI", 14, "bold"), bootstyle="inverse-info").pack(side="left")
            
            close_btn = tb.Button(title_frame, text="✕", bootstyle="danger-outline", 
                                command=details_modal.destroy, width=3)
            close_btn.pack(side="right", padx=(10, 0))
            
            # Details frame
            details_frame = tb.Frame(main_container)
            details_frame.pack(fill="both", expand=True)
            
            # Client information
            info_fields = [
                ("Status", values[0]),
                ("IP Address", values[1]),
                ("MAC Address", values[2]),
                ("Hostname", values[3]),
                ("Vendor", values[4]),
                ("Ping Latency", values[5]),
                ("First Seen", values[6]),
                ("Last Seen", values[7])
            ]
            
            for i, (label, value) in enumerate(info_fields):
                field_frame = tb.LabelFrame(details_frame, text=label, padding=10, bootstyle="secondary")
                field_frame.pack(fill="x", padx=5, pady=5)
                
                tb.Label(field_frame, text=value, font=("Segoe UI", 10)).pack(anchor="w")
            
        except IndexError:
            messagebox.showwarning("No Selection", "Please select a client to view details.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load client details: {str(e)}")

    def ping_client(self):
        """Ping the selected client."""
        try:
            selected_item = self.client_tree.selection()[0]
            values = self.client_tree.item(selected_item, "values")
            ip = values[1]  # IP address is in column 1
            
            if ip == "Unknown":
                messagebox.showwarning("Invalid IP", "Cannot ping client with unknown IP address.")
                return
            
            def ping_thread():
                import sys
                import os
                sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                from network_utils import ping_latency
                latency = ping_latency(ip, timeout=2000)
                
                def update_result():
                    if latency is not None:
                        messagebox.showinfo("Ping Result", f"Ping to {ip}: {latency:.2f}ms")
                    else:
                        messagebox.showwarning("Ping Failed", f"Could not ping {ip}")
                
                self.root.after(0, update_result)
            
            threading.Thread(target=ping_thread, daemon=True).start()
            
        except IndexError:
            messagebox.showwarning("No Selection", "Please select a client to ping.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to ping client: {str(e)}")

    def add_client_note(self):
        """Add a note to the selected client."""
        messagebox.showinfo("Feature Coming Soon", "Client notes feature will be available in a future update.")

    def refresh_selected_client(self):
        """Refresh the selected client."""
        try:
            selected_item = self.client_tree.selection()[0]
            values = self.client_tree.item(selected_item, "values")
            ip = values[1]  # IP address is in column 1
            
            if ip == "Unknown":
                messagebox.showwarning("Invalid IP", "Cannot refresh client with unknown IP address.")
                return
            
            def refresh_thread():
                import sys
                import os
                sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                from network_utils import ping_latency
                latency = ping_latency(ip, timeout=1000)
                
                def update_result():
                    # Update the client data
                    for client in self.client_data:
                        if client["ip"] == ip:
                            client["ping"] = latency
                            client["last_seen"] = datetime.now().strftime("%H:%M:%S")
                            client["is_online"] = latency is not None
                            client["status"] = "🟢 Online" if latency is not None else "🔴 Offline"
                            break
                    
                    # Refresh display
                    self.update_client_display()
                    
                    if latency is not None:
                        messagebox.showinfo("Refresh Complete", f"Client {values[3]} refreshed successfully. Ping: {latency:.2f}ms")
                    else:
                        messagebox.showwarning("Refresh Failed", f"Client {values[3]} is not responding")
                
                self.root.after(0, update_result)
            
            threading.Thread(target=refresh_thread, daemon=True).start()
            
        except IndexError:
            messagebox.showwarning("No Selection", "Please select a client to refresh.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh client: {str(e)}")

    def remove_client(self):
        """Remove the selected client from the list."""
        try:
            selected_item = self.client_tree.selection()[0]
            values = self.client_tree.item(selected_item, "values")
            
            if messagebox.askyesno("Confirm Removal", f"Are you sure you want to remove {values[3]} from the client list?"):
                # Remove from data
                mac_to_remove = values[2]  # MAC address
                self.client_data = [c for c in self.client_data if c["mac"] != mac_to_remove]
                
                # Refresh display
                self.update_client_display()
                
                messagebox.showinfo("Client Removed", f"Removed {values[3]} from the client list")
                
        except IndexError:
            messagebox.showwarning("No Selection", "Please select a client to remove.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to remove client: {str(e)}")

    def close_client_modal(self):
        """Handle closing the client modal."""
        self.stop_auto_refresh()
        if self.client_modal:
            self.client_modal.destroy()
            self.client_modal = None

    def show_loop_detection(self):
        """Show loop detection modal (client view only - data fetch from database)."""
        if hasattr(self, 'loop_modal') and self.loop_modal and self.loop_modal.winfo_exists():
            self.loop_modal.lift()
            return
            
        self.loop_modal = tb.Toplevel(self.root)
        self.loop_modal.title("🔄 Loop Detection Monitor")
        self.loop_modal.geometry("1000x700")
        self.loop_modal.resizable(True, True)
        self.loop_modal.configure(bg='#f8f9fa')

        # Center modal
        self.loop_modal.update_idletasks()
        x = (self.loop_modal.winfo_screenwidth() - self.loop_modal.winfo_width()) // 2
        y = (self.loop_modal.winfo_screenheight() - self.loop_modal.winfo_height()) // 2
        self.loop_modal.geometry(f"+{x}+{y}")

        # Main container
        main_container = tb.Frame(self.loop_modal, bootstyle="light")
        main_container.pack(fill="both", expand=True, padx=10, pady=10)

        # Header section
        header_frame = tb.Frame(main_container, bootstyle="warning")
        header_frame.pack(fill="x", pady=(0, 10))

        # Title and stats
        title_frame = tb.Frame(header_frame)
        title_frame.pack(fill="x", padx=15, pady=15)

        tb.Label(title_frame, text="🔄 Loop Detection Monitor", 
                font=("Segoe UI", 16, "bold"), bootstyle="inverse-warning").pack(side="left")

        # Close button
        close_btn = tb.Button(title_frame, text="✕", bootstyle="danger-outline", 
                            command=self.close_loop_modal, width=3)
        close_btn.pack(side="right", padx=(10, 0))

        # Stats frame
        stats_frame = tb.Frame(title_frame)
        stats_frame.pack(side="right", padx=(0, 10))

        self.loop_stats_total = tb.Label(stats_frame, text="Total: 0", 
                                        font=("Segoe UI", 10, "bold"), bootstyle="info")
        self.loop_stats_total.pack(side="left", padx=(0, 15))

        self.loop_stats_loops = tb.Label(stats_frame, text="Loops: 0", 
                                        font=("Segoe UI", 10, "bold"), bootstyle="danger")
        self.loop_stats_loops.pack(side="left", padx=(0, 15))

        self.loop_stats_suspicious = tb.Label(stats_frame, text="Suspicious: 0", 
                                            font=("Segoe UI", 10, "bold"), bootstyle="warning")
        self.loop_stats_suspicious.pack(side="left", padx=(0, 15))

        # Control panel
        control_frame = tb.Frame(main_container)
        control_frame.pack(fill="x", pady=(0, 10))

        # Refresh button
        refresh_btn = tb.Button(control_frame, text="🔄 Refresh Data", bootstyle="primary", 
                              command=self.load_loop_detection_data, width=15)
        refresh_btn.pack(side="left", padx=(0, 10))

        # Auto refresh toggle
        self.loop_auto_refresh_var = tb.BooleanVar(value=False)
        auto_refresh_check = tb.Checkbutton(control_frame, text="Auto Refresh (30s)", 
                                          variable=self.loop_auto_refresh_var,
                                          command=self.toggle_loop_auto_refresh,
                                          bootstyle="success")
        auto_refresh_check.pack(side="left", padx=(0, 10))

        # Export button
        export_btn = tb.Button(control_frame, text="📊 Export CSV", bootstyle="success", 
                             command=self.export_loop_detection_data, width=12)
        export_btn.pack(side="right")

        # Main content area
        content_frame = tb.Frame(main_container)
        content_frame.pack(fill="both", expand=True)

        # Treeview with scrollbars
        tree_frame = tb.Frame(content_frame)
        tree_frame.pack(fill="both", expand=True)

        # Define columns
        cols = ("Time", "Status", "Total Packets", "Offenders", "Severity", "Interface", "Duration")
        
        # Create Treeview
        self.loop_tree = tb.Treeview(tree_frame, columns=cols, show="headings", 
                                   height=15, bootstyle="info")
        
        # Configure columns
        column_widths = [150, 100, 100, 80, 80, 100, 80]
        for i, (col, width) in enumerate(zip(cols, column_widths)):
            self.loop_tree.heading(col, text=col, command=lambda c=col: self.sort_loop_data_by_column(c))
            self.loop_tree.column(col, width=width, anchor="center")

        # Scrollbars
        v_scrollbar = tb.Scrollbar(tree_frame, orient="vertical", command=self.loop_tree.yview)
        h_scrollbar = tb.Scrollbar(tree_frame, orient="horizontal", command=self.loop_tree.xview)
        self.loop_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Pack treeview and scrollbars
        self.loop_tree.pack(side="left", fill="both", expand=True)
        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")

        # Status bar
        status_frame = tb.Frame(main_container)
        status_frame.pack(fill="x", pady=(10, 0))

        self.loop_status_label = tb.Label(status_frame, text="Loading loop detection data...", 
                                        bootstyle="secondary", font=("Segoe UI", 9))
        self.loop_status_label.pack(side="left")

        self.loop_last_update = tb.Label(status_frame, text="", 
                                       bootstyle="secondary", font=("Segoe UI", 9))
        self.loop_last_update.pack(side="right")

        # Initialize variables
        self.loop_data = []
        self.loop_auto_refresh_job = None

        # Load initial data
        self.load_loop_detection_data()

        # Handle window close
        self.loop_modal.protocol("WM_DELETE_WINDOW", self.close_loop_modal)

    def load_loop_detection_data(self):
        """Load loop detection data from database via API."""
        try:
            # Try to get data from API first
            response = requests.get(f"{self.api_base_url}/api/loop-detection", timeout=5)
            if response.ok:
                data = response.json()
                self.loop_data = data.get('detections', [])
            else:
                # Fallback to direct database access
                self.load_loop_detection_from_db()
        except Exception as e:
            print(f"❌ Error loading loop detection data from API: {e}")
            # Fallback to direct database access
            self.load_loop_detection_from_db()
        
        self.update_loop_display()
        
        # Update last update time
        from datetime import datetime
        time_str = datetime.now().strftime("%H:%M:%S")
        self.loop_last_update.config(text=f"Last update: {time_str}")

    def load_loop_detection_from_db(self):
        """Load loop detection data directly from database."""
        try:
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            from db import get_loop_detections_history, get_loop_detection_stats
            
            # Get detection history
            detections = get_loop_detections_history(limit=100)
            self.loop_data = []
            
            for detection in detections:
                detection_info = {
                    "id": detection['id'],
                    "detection_time": detection['detection_time'],
                    "total_packets": detection['total_packets'],
                    "offenders_count": detection['offenders_count'],
                    "offenders_data": detection['offenders_data'],
                    "severity_score": detection['severity_score'],
                    "network_interface": detection['network_interface'],
                    "detection_duration": detection['detection_duration'],
                    "status": detection['status']
                }
                self.loop_data.append(detection_info)
            
            self.loop_status_label.config(text="Data loaded from database", bootstyle="success")
            
        except Exception as e:
            print(f"❌ Error loading loop detection data from database: {e}")
            self.loop_data = []
            self.loop_status_label.config(text="Error loading data", bootstyle="danger")

    def update_loop_display(self):
        """Update the loop detection display with current data."""
        # Clear existing items
        for item in self.loop_tree.get_children():
            self.loop_tree.delete(item)
        
        # Insert data
        for detection in self.loop_data:
            # Format status with emoji
            status = detection['status']
            if status == 'loop_detected':
                status_display = "🔴 Loop Detected"
            elif status == 'suspicious':
                status_display = "⚠️ Suspicious"
            elif status == 'clean':
                status_display = "✅ Clean"
            else:
                status_display = status
            
            # Format time
            detection_time = detection['detection_time']
            if isinstance(detection_time, str):
                time_display = detection_time
            else:
                time_display = detection_time.strftime("%Y-%m-%d %H:%M:%S")
            
            # Format severity score
            severity = f"{detection['severity_score']:.1f}" if detection['severity_score'] else "0.0"
            
            self.loop_tree.insert("", "end", values=(
                time_display,
                status_display,
                detection['total_packets'],
                detection['offenders_count'],
                severity,
                detection['network_interface'],
                f"{detection['detection_duration']}s"
            ))
        
        # Update statistics
        total_detections = len(self.loop_data)
        loops_detected = len([d for d in self.loop_data if d['status'] == 'loop_detected'])
        suspicious = len([d for d in self.loop_data if d['status'] == 'suspicious'])
        
        self.loop_stats_total.config(text=f"Total: {total_detections}")
        self.loop_stats_loops.config(text=f"Loops: {loops_detected}")
        self.loop_stats_suspicious.config(text=f"Suspicious: {suspicious}")
        
        # Update status
        if total_detections > 0:
            latest = self.loop_data[0] if self.loop_data else None
            if latest:
                latest_status = latest['status']
                if latest_status == 'loop_detected':
                    self.loop_status_label.config(text="⚠️ Latest detection: Loop detected!", bootstyle="danger")
                elif latest_status == 'suspicious':
                    self.loop_status_label.config(text="🔍 Latest detection: Suspicious activity", bootstyle="warning")
                else:
                    self.loop_status_label.config(text="✅ Latest detection: Network clean", bootstyle="success")
        else:
            self.loop_status_label.config(text="No detection data available", bootstyle="secondary")

    def sort_loop_data_by_column(self, col):
        """Sort loop detection data by the specified column."""
        # Simple sorting implementation
        reverse = False
        if hasattr(self, '_last_loop_sort_col') and self._last_loop_sort_col == col:
            reverse = True
        self._last_loop_sort_col = col
        
        # Sort the data
        if col == "Time":
            self.loop_data.sort(key=lambda x: x['detection_time'], reverse=reverse)
        elif col == "Status":
            self.loop_data.sort(key=lambda x: x['status'], reverse=reverse)
        elif col == "Total Packets":
            self.loop_data.sort(key=lambda x: x['total_packets'], reverse=reverse)
        elif col == "Offenders":
            self.loop_data.sort(key=lambda x: x['offenders_count'], reverse=reverse)
        elif col == "Severity":
            self.loop_data.sort(key=lambda x: x['severity_score'] or 0, reverse=reverse)
        
        # Refresh display
        self.update_loop_display()

    def toggle_loop_auto_refresh(self):
        """Toggle automatic refresh for loop detection data."""
        if self.loop_auto_refresh_var.get():
            self.start_loop_auto_refresh()
        else:
            self.stop_loop_auto_refresh()

    def start_loop_auto_refresh(self):
        """Start automatic refresh for loop detection data."""
        self.loop_auto_refresh_job = self.root.after(30000, self.auto_refresh_loop_data)  # 30 seconds

    def stop_loop_auto_refresh(self):
        """Stop automatic refresh for loop detection data."""
        if self.loop_auto_refresh_job:
            self.root.after_cancel(self.loop_auto_refresh_job)
            self.loop_auto_refresh_job = None

    def auto_refresh_loop_data(self):
        """Perform automatic refresh of loop detection data."""
        if self.loop_auto_refresh_var.get():
            self.load_loop_detection_data()
            self.loop_auto_refresh_job = self.root.after(30000, self.auto_refresh_loop_data)

    def export_loop_detection_data(self):
        """Export loop detection data to CSV."""
        try:
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Export Loop Detection Data"
            )
            
            if filename:
                import csv
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(["Time", "Status", "Total Packets", "Offenders", "Severity", "Interface", "Duration"])
                    for detection in self.loop_data:
                        # Format status
                        status = detection['status']
                        if status == 'loop_detected':
                            status_display = "Loop Detected"
                        elif status == 'suspicious':
                            status_display = "Suspicious"
                        elif status == 'clean':
                            status_display = "Clean"
                        else:
                            status_display = status
                        
                        # Format time
                        detection_time = detection['detection_time']
                        if isinstance(detection_time, str):
                            time_display = detection_time
                        else:
                            time_display = detection_time.strftime("%Y-%m-%d %H:%M:%S")
                        
                        writer.writerow([
                            time_display,
                            status_display,
                            detection['total_packets'],
                            detection['offenders_count'],
                            f"{detection['severity_score']:.1f}" if detection['severity_score'] else "0.0",
                            detection['network_interface'],
                            f"{detection['detection_duration']}s"
                        ])
                messagebox.showinfo("Export Complete", f"Loop detection data exported to {filename}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export data: {str(e)}")

    def close_loop_modal(self):
        """Handle closing the loop detection modal."""
        self.stop_loop_auto_refresh()
        if self.loop_modal:
            self.loop_modal.destroy()
            self.loop_modal = None

    def cleanup(self):
        """Clean up resources when tab is destroyed"""
        self.stop_auto_update()
        self.close_client_modal()
        self.close_loop_modal()