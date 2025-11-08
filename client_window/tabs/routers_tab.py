import os
import time
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
        self.metrics_refresh_interval_ms = 3000  # refresh latency/bandwidth every ~3s
        self.is_updating = False
        self.auto_update_job = None
        self.last_update_time = None
        # Initialize optional modals to avoid AttributeError on first use/cleanup
        self.client_modal = None
        self.loop_modal = None
        # Flags to prevent multiple modal openings
        self.client_modal_is_open = False
        self.loop_modal_is_open = False
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
        # Ensure filter is applied live for every letter typed
        def on_search_var_change(*_):
            self.apply_router_filter()
        self.router_search_var.trace_add("write", on_search_var_change)
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
        # Start lightweight metrics loop (after initial load)
        self._metrics_loop_job = None
        self._start_metrics_loop()

    def _is_router_online(self, router):
        """
        Check if router is online - simplified for fast, accurate results.
        Priority: bandwidth_timestamp > status API > last_seen
        """
        # 1. Fast path: recent bandwidth log means actively monitored and online
        ts = router.get('bandwidth_timestamp')
        if ts:
            try:
                parsed = None
                if isinstance(ts, str):
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
                        try:
                            parsed = datetime.strptime(ts.replace('Z',''), fmt)
                            break
                        except Exception:
                            pass
                elif isinstance(ts, datetime):
                    parsed = ts
                
                if parsed and (datetime.now() - parsed) <= timedelta(seconds=120):  # 2 min window
                    return True
            except Exception:
                pass

        # 2. Status API check (quick timeout)
        try:
            r = requests.get(f"{self.api_base_url}/api/routers/{router['id']}/status", timeout=1)
            if r.ok:
                status_data = r.json() or {}
                return status_data.get('is_online', False)
        except Exception:
            pass

        # 3. Legacy fallback: last_seen field
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
            
            # Use optimized endpoint that fetches routers with bandwidth data in single query
            r = requests.get(f"{self.api_base_url}/api/routers/with-bandwidth", timeout=8)
            if not r.ok:
                # Fallback to regular endpoint if new endpoint not available
                r = requests.get(f"{self.api_base_url}/api/routers", timeout=8)
                if not r.ok:
                    self.router_status_var.set(f"Failed to load routers: {r.status_code}")
                    return
                
            routers_raw = r.json() or []
            self.router_list = routers_raw
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
        raw = (self.router_search_var.get() or "").strip().lower()
        type_filter = self.router_type_var.get()
        flt = []
        for r in self.router_list:
            fields = [str(r.get(k, "") or "").lower() for k in ("name","ip_address","brand","location")]
            if raw and not any(raw in field for field in fields):
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
        # Diff-based rendering for smooth updates.
        self._ensure_router_sections()
        if not routers:
            # Empty state
            self._clear_router_section(self.online_section_frame)
            self._clear_router_section(self.offline_section_frame)
            if not hasattr(self, '_empty_label'):
                self._empty_label = tb.Label(self.online_section_frame, text="No routers to display", font=("Segoe UI", 11))
            self._empty_label.pack(pady=20)
            return
        else:
            if hasattr(self, '_empty_label') and self._empty_label.winfo_exists():
                self._empty_label.pack_forget()

        online_list, offline_list = [], []
        for r in routers:
            is_on = self._is_router_online(r)
            if (r.get('brand', '').lower() == 'unifi' or r.get('is_unifi')):
                try:
                    r_status = requests.get(f"{self.api_base_url}/api/routers/{r['id']}/status", timeout=2)
                    if r_status.ok:
                        status_data = r_status.json()
                        age = status_data.get('seconds_since_last_update')
                        if age is not None and age > 30:
                            is_on = False
                except Exception:
                    pass
            (online_list if is_on else offline_list).append(r)

        sort_mode = self.router_sort_var.get()
        # Determine which lists are used for layout
        if sort_mode == 'online':
            display_online = online_list
            display_offline = offline_list
        else:
            display_online = online_list + offline_list
            display_offline = []

        # Build desired id sets
        desired_ids = [r.get('id') for r in (display_online + display_offline) if r.get('id') is not None]
        existing_ids = set(self.router_widgets.keys()) if hasattr(self, 'router_widgets') else set()
        if not hasattr(self, 'router_widgets'):
            self.router_widgets = {}
        desired_set = set(desired_ids)

        # Remove obsolete cards
        for rid in list(existing_ids - desired_set):
            w = self.router_widgets.pop(rid, None)
            if w and w.get('card') and w['card'].winfo_exists():
                try: w['card'].destroy()
                except Exception: pass

        # Add or update cards
        for r in (display_online + display_offline):
            rid = r.get('id')
            if rid is None: 
                continue
            parent = self.online_section_frame if (sort_mode != 'online' or rid in [x.get('id') for x in online_list]) else self.offline_section_frame
            if rid not in self.router_widgets:
                self._create_router_card(parent, r, rid in [x.get('id') for x in online_list])
            else:
                self.router_widgets[rid]['data'] = r
                self._update_router_card(self.router_widgets[rid], r, rid in [x.get('id') for x in online_list])
                # Ensure card is in correct parent (recreate if needed)
                current_parent = self.router_widgets[rid].get('parent')
                if current_parent is not parent:
                    try:
                        old = self.router_widgets.pop(rid)
                        if old.get('card') and old['card'].winfo_exists():
                            old['card'].destroy()
                        self._create_router_card(parent, r, rid in [x.get('id') for x in online_list])
                    except Exception:
                        pass

        # Layout cards responsively (force one early layout pass to avoid initial 1-col)
        self._layout_router_cards(self.online_section_frame, [r.get('id') for r in display_online])
        # Force a second layout after idle so container width is settled
        self.root.after_idle(lambda: self._layout_router_cards(self.online_section_frame, [r.get('id') for r in display_online]))
        if sort_mode == 'online':
            self._layout_router_cards(self.offline_section_frame, [r.get('id') for r in display_offline])
            self.root.after_idle(lambda: self._layout_router_cards(self.offline_section_frame, [r.get('id') for r in display_offline]))
            self.offline_header_label.pack(anchor='w', padx=10, pady=(15,5))
            self.offline_section_frame.pack(fill='x', padx=10, pady=5)
        else:
            self.offline_header_label.pack_forget()
            self.offline_section_frame.pack_forget()

    # === Helper methods for diff rendering ===
    def _ensure_router_sections(self):
        if hasattr(self, 'online_section_frame') and hasattr(self, 'offline_section_frame'):
            return
        # Clean slate
        for c in list(self.scrollable_frame.winfo_children()):
            try: c.destroy()
            except Exception: pass
        self.online_header_label = tb.Label(self.scrollable_frame, text="🟢 Online Routers", font=("Segoe UI", 12, "bold"), bootstyle="secondary")
        self.online_header_label.pack(anchor='w', padx=10, pady=(15,5))
        self.online_section_frame = tb.Frame(self.scrollable_frame)
        self.online_section_frame.pack(fill='x', padx=10, pady=5)
        self.online_section_frame._resize_job = None
        self.offline_header_label = tb.Label(self.scrollable_frame, text="🔴 Offline Routers", font=("Segoe UI", 12, "bold"), bootstyle="secondary")
        self.offline_section_frame = tb.Frame(self.scrollable_frame)
        # Initially hidden until needed
        self.offline_section_frame._resize_job = None
        # Responsive relayout on resize with debounce
        def _debounced_relayout(container):
            try:
                if getattr(container, '_resize_job', None):
                    container.after_cancel(container._resize_job)
            except Exception:
                pass
            container._resize_job = container.after(200, lambda: self._layout_router_cards(container, None))
        self.online_section_frame.bind('<Configure>', lambda e: _debounced_relayout(self.online_section_frame))
        self.offline_section_frame.bind('<Configure>', lambda e: _debounced_relayout(self.offline_section_frame))

    def _clear_router_section(self, section):
        for w in list(section.winfo_children()):
            try: w.destroy()
            except Exception: pass

    def _compute_max_cols(self, container):
        width = container.winfo_width() or self.root.winfo_width() or 800
        if width <= 400: return 1
        if width <= 800: return 2
        if width <= 1200: return 3
        return 4

    def _create_router_card(self, parent, router, is_online):
        rid = router.get('id')
        is_unifi = router.get('brand', '').lower() == 'unifi' or router.get('is_unifi')
        card_style = ('primary' if is_unifi else 'success') if is_online else 'danger'
        card = tb.LabelFrame(parent, text=router.get('name','Unknown'), bootstyle=card_style, padding=0)
        card.grid_propagate(False)
        card.config(width=280, height=200)
        inner = tb.Frame(card, padding=10)
        inner.pack(fill='both', expand=True)
        if is_unifi:
            tb.Label(inner, text='📡', font=("Segoe UI Emoji", 30)).pack()
            tb.Label(inner, text='UniFi Device', font=("Segoe UI",8,'italic'), bootstyle='primary').pack()
        else:
            tb.Label(inner, text='⛀', font=("Segoe UI Emoji", 30)).pack()
        ip = router.get('ip_address') or router.get('ip') or '—'
        tb.Label(inner, text=ip, font=("Segoe UI",10)).pack(pady=(5,0))
        status_text, status_style = (('🟢 Online','success') if is_online else ('🔴 Offline','danger'))
        status_label = tb.Label(inner, text=status_text, bootstyle=status_style, cursor='hand2')
        status_label.pack(pady=5)
        bw_label = tb.Label(inner, text='… Loading bandwidth', bootstyle='secondary', font=("Segoe UI",8))
        bw_label.pack(pady=2)

        def bind_card_click(widget, router_obj):
            widget.bind('<Button-1>', lambda e: self.open_router_details(router_obj))
        bind_card_click(inner, router)
        for ch in inner.winfo_children():
            bind_card_click(ch, router)

        def on_enter(e, c=card, bs=card_style):
            c.configure(bootstyle=bs)

        def on_leave(e, c=card, bs=card_style):
            c.configure(bootstyle=bs)

        card.bind('<Enter>', on_enter)
        card.bind('<Leave>', on_leave)
        if not hasattr(self,'router_widgets'): self.router_widgets = {}
        self.router_widgets[rid] = {
            'card': card,
            'status_label': status_label,
            'bandwidth_label': bw_label,
            'data': router,
            'parent': parent,
        }
        # Async bandwidth fetch if online
        if is_online:
            threading.Thread(target=self._fetch_bandwidth_latency_safe, args=(rid,), daemon=True).start()
        return card

    def _update_router_card(self, w, router, is_online):
        # Title
        try:
            if w['card'].cget('text') != router.get('name','Unknown'):
                w['card'].configure(text=router.get('name','Unknown'))
        except Exception: pass
        # Status
        desired_status = '🟢 Online' if is_online else '🔴 Offline'
        desired_style = 'success' if is_online else 'danger'
        try:
            if w['status_label'].cget('text') != desired_status:
                w['status_label'].configure(text=desired_status, bootstyle=desired_style)
        except Exception:
            pass
        # Card style (force set; ttkbootstrap may not return bootstyle on cget reliably)
        try:
            is_unifi = router.get('brand', '').lower() == 'unifi' or router.get('is_unifi')
            card_style = ('primary' if is_unifi else 'success') if is_online else 'danger'
            w['card'].configure(bootstyle=card_style)
        except Exception:
            pass
        # If online, (re)fetch bandwidth/latency if placeholder or stale
        try:
            bw_text = w['bandwidth_label'].cget('text')
        except Exception:
            bw_text = ''
        stale = False
        last = w.get('metrics_last_fetch')
        if last is None:
            stale = True
        else:
            try:
                stale = (time.time() - last) > 3  # refresh every ~3s if online
            except Exception:
                stale = True
        # Combined label contains latency, so detect placeholder via '--' or 'Loading'
        needs_refresh = is_online and (("Loading" in bw_text) or ('--' in bw_text) or stale)
        if needs_refresh:
            w['metrics_last_fetch'] = time.time()
            threading.Thread(target=self._fetch_bandwidth_latency_safe, args=(router.get('id'),), daemon=True).start()
        else:
            if not is_online:
                # If offline, ensure latency shows unknown and neutral style
                try:
                    if w.get('bandwidth_label') and w['bandwidth_label'].winfo_exists():
                        # Combined line
                        w['bandwidth_label'].configure(text='📊 ↓0.0 Mbps ↑0.0 Mbps   ⚡ --', bootstyle='secondary')
                except Exception:
                    pass

    def _layout_router_cards(self, container, ids):
        # Responsive grid layout (ids optional). If ids None, infer from widgets in container.
        if ids is None:
            ids = [rid for rid, w in self.router_widgets.items() if w.get('parent') is container]
        max_cols = self._compute_max_cols(container)
        # Skip relayout if columns unchanged and children count same
        prev_cols = getattr(container, '_last_cols', None)
        prev_count = getattr(container, '_last_count', None)
        if prev_cols == max_cols and prev_count == len(ids):
            return
        container._last_cols = max_cols
        container._last_count = len(ids)
        # Clear previous grid placements only (keep widgets)
        for child in container.winfo_children():
            child.grid_forget()
        for idx, rid in enumerate(ids):
            w = self.router_widgets.get(rid)
            if not w: 
                continue
            row, col = divmod(idx, max_cols)
            w['card'].grid(row=row, column=col, padx=10, pady=10, sticky='nsew')
            container.grid_columnconfigure(col, weight=1, uniform='router_cards')
            container.grid_rowconfigure(row, weight=0)

    def _fetch_bandwidth_latency_safe(self, rid):
        w = self.router_widgets.get(rid)
        if not w: return
        try:
            # Single status endpoint first to get latency & online status quickly
            status_r = requests.get(f"{self.api_base_url}/api/routers/{rid}/status", timeout=3)
            lat = None
            is_online = False
            if status_r.ok:
                sdata = status_r.json() or {}
                lat = sdata.get('latency_ms') or sdata.get('avg_latency') or sdata.get('latency')
                is_online = sdata.get('is_online', False)

            br = requests.get(f"{self.api_base_url}/api/bandwidth/logs", params={"router_id": rid, "limit": 1}, timeout=4)
            dl=ul=0.0
            if br.ok:
                arr = br.json() or []
                if arr:
                    row = arr[0]
                    dl = float(row.get('download_mbps',0) or 0)
                    ul = float(row.get('upload_mbps',0) or 0)
                    if lat is None:
                        lat = row.get('latency_ms')
            # If still no latency and router considered online, attempt direct ping (non-blocking UI)
            if lat is None and is_online:
                # Spawn a quick ping thread to update latency once
                threading.Thread(target=self._ping_and_update_latency, args=(rid, w), daemon=True).start()
            # Compose combined line like admin (be tolerant to Decimal/str types)
            speed_text = f"📊 ↓{dl:.1f} Mbps ↑{ul:.1f} Mbps" if (dl>0 or ul>0) else "📊 ↓0.0 Mbps ↑0.0 Mbps"
            lat_val = None
            if lat is not None:
                try:
                    lat_val = float(lat)
                except Exception:
                    lat_val = None
            latency_text = f"   ⚡ {lat_val:.1f} ms" if isinstance(lat_val,(int,float)) else "   ⚡ --"
            new_text = speed_text + latency_text
            style = ("info" if (dl>0 or ul>0) else ("success" if is_online else "secondary")) if is_online else "secondary"
            self.root.after(0, lambda: (w['bandwidth_label'].config(text=new_text, bootstyle=style) if w['bandwidth_label'].winfo_exists() else None))
        except Exception:
            self.root.after(0, lambda: (w and w.get('bandwidth_label') and w['bandwidth_label'].winfo_exists() and w['bandwidth_label'].config(text='📊 ↓0.0 Mbps ↑0.0 Mbps   ⚡ --', bootstyle='secondary')))

    def _ping_and_update_latency(self, rid, widget_ref):
        # Direct ping fallback to populate latency if missing
        try:
            data = widget_ref.get('data') if widget_ref else None
            ip = None
            if data:
                ip = data.get('ip_address') or data.get('ip')
            if not ip:
                return
            # Lightweight ping using network_utils endpoint? If no API, local ping util
            try:
                from network_utils import ping_latency
                lat_val = ping_latency(ip, timeout=800, use_manager=False)
            except Exception:
                lat_val = None
            if lat_val is None:
                return
            # Merge into existing label text
            def apply():
                if widget_ref and widget_ref.get('bandwidth_label') and widget_ref['bandwidth_label'].winfo_exists():
                    current = widget_ref['bandwidth_label'].cget('text') or ''
                    parts = current.split('⚡')
                    if parts:
                        # Rebuild preserving bandwidth portion
                        bw_part = parts[0].strip()
                        new_text = f"{bw_part}   ⚡ {lat_val:.1f} ms"
                    else:
                        new_text = f"📊 ↓0.0 Mbps ↑0.0 Mbps   ⚡ {lat_val:.1f} ms"
                    widget_ref['bandwidth_label'].config(text=new_text)
            self.root.after(0, apply)
        except Exception:
            pass

    def _start_metrics_loop(self):
        # Periodically refresh metrics without full router list reload
        def loop():
            try:
                # Prefer batch refresh to avoid N requests per cycle
                ok = self._refresh_metrics_batch()
                if not ok:
                    # Fallback: per-router selective refresh
                    now = time.time()
                    for rid, w in list(getattr(self, 'router_widgets', {}).items()):
                        try:
                            is_online = 'Online' in (w.get('status_label').cget('text') if w.get('status_label') else '')
                        except Exception:
                            is_online = False
                        if not is_online:
                            continue
                        last = w.get('metrics_last_fetch') or 0
                        if now - last >= 3:
                            w['metrics_last_fetch'] = now
                            threading.Thread(target=self._fetch_bandwidth_latency_safe, args=(rid,), daemon=True).start()
            except Exception:
                pass
            finally:
                self._metrics_loop_job = self.root.after(self.metrics_refresh_interval_ms, loop)
        # Kick off
        loop()

    def _refresh_metrics_batch(self):
        """Fetch latest metrics for all routers in one call and update cards. Returns True if successful."""
        try:
            r = requests.get(f"{self.api_base_url}/api/routers/with-bandwidth", timeout=2)
            if not r.ok:
                return False
            arr = r.json() or []
            # Map by id for quick lookup
            by_id = {item.get('id') or item.get('router_id'): item for item in arr}
            now = time.time()
            
            for rid, w in list(getattr(self, 'router_widgets', {}).items()):
                data = by_id.get(rid)
                if not data:
                    continue
                # Only update if widget exists
                if not (w and w.get('bandwidth_label') and w['bandwidth_label'].winfo_exists()):
                    continue
                
                # Determine online status from fresh data
                is_online = self._is_router_online(data)
                
                # Update status label
                try:
                    if w.get('status_label') and w['status_label'].winfo_exists():
                        desired_status = '🟢 Online' if is_online else '🔴 Offline'
                        desired_style = 'success' if is_online else 'danger'
                        current_text = w['status_label'].cget('text')
                        if current_text != desired_status:
                            w['status_label'].configure(text=desired_status, bootstyle=desired_style)
                except Exception:
                    pass
                
                # Update card border style
                try:
                    is_unifi = data.get('brand', '').lower() == 'unifi' or data.get('is_unifi')
                    card_style = ('primary' if is_unifi else 'success') if is_online else 'danger'
                    if w.get('card') and w['card'].winfo_exists():
                        w['card'].configure(bootstyle=card_style)
                except Exception:
                    pass
                
                # Parse bandwidth values
                try:
                    dl = float(data.get('download_mbps') or 0)
                except Exception:
                    dl = 0.0
                try:
                    ul = float(data.get('upload_mbps') or 0)
                except Exception:
                    ul = 0.0
                lat_raw = data.get('latency_ms')
                try:
                    lat_val = float(lat_raw) if lat_raw is not None else None
                except Exception:
                    lat_val = None
                
                # Compose combined line
                speed_text = f"📊 ↓{dl:.1f} Mbps ↑{ul:.1f} Mbps" if (dl>0 or ul>0) else "📊 ↓0.0 Mbps ↑0.0 Mbps"
                latency_text = f"   ⚡ {lat_val:.1f} ms" if isinstance(lat_val,(int,float)) else "   ⚡ --"
                new_text = speed_text + latency_text
                
                # Style based on online state and traffic
                style = ("info" if (dl>0 or ul>0) else "success") if is_online else "secondary"
                
                def apply(widget=w['bandwidth_label'], txt=new_text, st=style, wid=w):
                    if widget and widget.winfo_exists():
                        widget.config(text=txt, bootstyle=st)
                        wid['metrics_last_fetch'] = now
                        wid['data'] = data  # Update cached data
                
                self.root.after(0, apply)
                
                # If latency missing but online, opportunistic ping
                if lat_val is None and is_online:
                    threading.Thread(target=self._ping_and_update_latency, args=(rid, w), daemon=True).start()
            
            return True
        except Exception as e:
            print(f"Batch refresh error: {e}")
            return False
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
    # Removed Last Seen label per request (was detail_last_seen_lbl)
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
        # Real-time status fetch
        try:
            r = requests.get(f"{self.api_base_url}/api/routers/{router['id']}/status", timeout=3)
            if r.ok:
                status_data = r.json()
                age = status_data.get('seconds_since_last_update')
                is_online = status_data.get('is_online', False)
                if age is not None and age > 30:
                    is_online = False
                if is_online:
                    detail_status_lbl = tb.Label(status_row, text="🟢 Online", font=("Segoe UI", 12, "bold"), bootstyle="success")
                else:
                    detail_status_lbl = tb.Label(status_row, text="🔴 Offline", font=("Segoe UI", 12, "bold"), bootstyle="danger")
            else:
                detail_status_lbl = tb.Label(status_row, text="🔴 Offline", font=("Segoe UI", 12, "bold"), bootstyle="danger")
        except Exception:
            detail_status_lbl = tb.Label(status_row, text="🔴 Offline", font=("Segoe UI", 12, "bold"), bootstyle="danger")
        detail_status_lbl.pack(side="left", padx=(10, 0))

    # Last Seen section removed

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
        tb.Button(actions_grid, text="👥 Connected Clients", bootstyle="success", command=lambda: self.show_connected_clients_for_router(router), width=20).grid(row=1, column=0, columnspan=2, padx=10, pady=5, sticky="ew")
        actions_grid.grid_columnconfigure(0, weight=1)
        actions_grid.grid_columnconfigure(1, weight=1)

        def refresh_details():
            if not d.winfo_exists():
                return
            rid = router.get('id')
            
            # Use batch endpoint for fresh data
            try:
                batch_r = requests.get(f"{self.api_base_url}/api/routers/with-bandwidth", timeout=2)
                if batch_r.ok:
                    routers_data = batch_r.json() or []
                    router_data = next((r for r in routers_data if r.get('id') == rid), None)
                    
                    if router_data:
                        # Determine online status from fresh data
                        is_online = self._is_router_online(router_data)
                        
                        # Update status
                        if is_online:
                            detail_status_lbl.config(text="🟢 Online", bootstyle="success")
                            status_circle.config(text="●", bootstyle="success")
                        else:
                            detail_status_lbl.config(text="🔴 Offline", bootstyle="danger")
                            status_circle.config(text="●", bootstyle="danger")
                        
                        # Update bandwidth & latency
                        try:
                            dl = float(router_data.get('download_mbps') or 0)
                        except:
                            dl = 0.0
                        try:
                            ul = float(router_data.get('upload_mbps') or 0)
                        except:
                            ul = 0.0
                        try:
                            lat = float(router_data.get('latency_ms') or 0)
                        except:
                            lat = 0.0
                        
                        detail_download_lbl.config(text=f"{dl:.2f} Mbps" if dl > 0 else "0.00 Mbps")
                        detail_upload_lbl.config(text=f"{ul:.2f} Mbps" if ul > 0 else "0.00 Mbps")
                        
                        if lat > 0:
                            detail_latency_lbl.config(text=f"{lat:.1f} ms", bootstyle="success")
                        else:
                            # Try quick ping if latency missing
                            detail_latency_lbl.config(text="Probing...", bootstyle="warning")
                            def _try_ping():
                                try:
                                    ip = router_data.get('ip_address') or router_data.get('ip')
                                    if ip:
                                        from network_utils import ping_latency
                                        ping_lat = ping_latency(ip, timeout=500, use_manager=False)
                                        if ping_lat:
                                            d.after(0, lambda: detail_latency_lbl.config(text=f"{ping_lat:.1f} ms", bootstyle="success") if d.winfo_exists() else None)
                                        else:
                                            d.after(0, lambda: detail_latency_lbl.config(text="—", bootstyle="secondary") if d.winfo_exists() else None)
                                except:
                                    d.after(0, lambda: detail_latency_lbl.config(text="—", bootstyle="secondary") if d.winfo_exists() else None)
                            threading.Thread(target=_try_ping, daemon=True).start()
                        
                        # Last Seen removed; skip timestamp processing
                    else:
                        # Router not found in batch
                        detail_status_lbl.config(text="❓ Unknown", bootstyle="secondary")
                        status_circle.config(text="●", bootstyle="secondary")
                else:
                    # Batch fetch failed
                    detail_status_lbl.config(text="⚠️ Server Error", bootstyle="warning")
            except Exception as e:
                # Network error
                detail_status_lbl.config(text="⚠️ Connection Error", bootstyle="danger")
                print(f"Router details refresh error: {e}")

            # Schedule next refresh
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

    def show_connected_clients_for_router(self, router):
        """Show connected clients for a specific router/AP via API (with DB fallback)."""
        try:
            router_id = router.get('id')
            if not router_id:
                messagebox.showerror("Error", "Router ID not found.")
                return

            # Create modal window
            modal = tk.Toplevel(self.root)
            modal.title(f"👥 Connected Clients - {router.get('name', 'Router')}")
            modal.geometry("900x600")
            modal.transient(self.root)
            modal.grab_set()

            # Center window
            self.root.update_idletasks()
            rx, ry = self.root.winfo_x(), self.root.winfo_y()
            rw, rh = self.root.winfo_width(), self.root.winfo_height()
            w, h = 900, 600
            x = rx + (rw // 2) - (w // 2)
            y = ry + (rh // 2) - (h // 2)
            modal.geometry(f"{w}x{h}+{x}+{y}")

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
                                    text="⏳ Loading clients...", 
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
            loading_label = tb.Label(content_frame, text="⏳ Fetching clients...", 
                                     font=("Segoe UI", 12), bootstyle="info")
            loading_label.pack(pady=50)

            # Footer with buttons
            footer_frame = tb.Frame(main_container)
            footer_frame.pack(fill="x", pady=(15, 0))

            refresh_btn = tb.Button(footer_frame, text="🔄 Refresh", bootstyle="info",
                                    command=lambda: [modal.destroy(), self.show_connected_clients_for_router(router)],
                                    width=15, state="disabled")
            refresh_btn.pack(side="left")

            tb.Button(footer_frame, text="Close", bootstyle="secondary",
                      command=modal.destroy, width=15).pack(side="right")

            # Fetch clients from DB via API (router_id filter) in background thread
            def fetch_clients():
                try:
                    db_resp = requests.get(f"{self.api_base_url}/api/clients", params={"router_id": router_id}, timeout=10)
                    clients = []
                    if db_resp.ok:
                        all_clients = (db_resp.json() or {}).get('clients', [])
                        clients = all_clients
                    else:
                        raise RuntimeError(f"Status {db_resp.status_code}")

                    self.root.after(0, lambda: update_ui_with_clients(clients))

                except requests.exceptions.ConnectionError:
                    self.root.after(0, lambda: update_ui_error(
                        "Cannot connect to server.\nPlease ensure the server is running."
                    ))
                except requests.exceptions.Timeout:
                    self.root.after(0, lambda: update_ui_error(
                        "Request timed out.\nPlease try again later."
                    ))
                except Exception as e:
                    self.root.after(0, lambda: update_ui_error(f"Unexpected error:\n{str(e)}"))

            def update_ui_error(error_msg):
                loading_label.config(text=f"❌ {error_msg}", bootstyle="danger")
                refresh_btn.config(state="normal")

            def update_ui_with_clients(clients):
                # Clear loading message
                loading_label.destroy()

                # Update status label
                status_label.config(
                    text=f"{len(clients)} Client{'s' if len(clients) != 1 else ''} Found",
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

                # Pack treeview and scrollbars
                tree.pack(side="left", fill="both", expand=True)
                v_scrollbar.pack(side="right", fill="y")
                h_scrollbar.pack(side="bottom", fill="x")

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

            # Start fetching clients in background thread
            import threading
            threading.Thread(target=fetch_clients, daemon=True).start()

        except Exception as e:
            messagebox.showerror("Error", 
                                 f"An unexpected error occurred:\n{str(e)}\n\n"
                                 f"Please check the console for more details.")
            print(f"⚠️ Error in show_connected_clients_for_router: {str(e)}")

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
        # Set flag FIRST before any other checks to prevent race condition
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
                    print("⚠️ Modal was destroyed, resetting flag")
            return
        
        # Set flag immediately to prevent multiple openings
        print("✅ Opening new client modal")
        self.client_modal_is_open = True
            
        self.client_modal = tb.Toplevel(self.root)
        self.client_modal.title("🌐 Network Clients Monitor")
        self.client_modal.geometry("1000x700")
        self.client_modal.resizable(True, True)
        self.client_modal.configure(bg='#f8f9fa')
        
        # Make it a proper modal window
        self.client_modal.transient(self.root)
        self.client_modal.grab_set()

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

        self.client_status_label = tb.Label(status_frame, text="Ready to load clients from database...", 
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
        
        # Bind destroy event to reset flag as fallback
        def on_modal_destroy(event):
            if event.widget == self.client_modal:
                self.client_modal_is_open = False
                print("🗑️ Client modal destroyed, flag reset")
        self.client_modal.bind("<Destroy>", on_modal_destroy)

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
        """Load clients from database via API (READ-ONLY) and map to display shape."""
        try:
            response = requests.get(f"{self.api_base_url}/api/clients", timeout=8)
            if response.ok:
                data = response.json() or {}
                raw_clients = data.get('clients', [])

                # Normalize to display structure expected by update_client_display
                mapped = []
                now = datetime.now()
                for client in raw_clients:
                    first_seen = client.get('first_seen') or now
                    last_seen = client.get('last_seen') or now
                    # Coerce to strings HH:MM:SS
                    if hasattr(first_seen, 'strftime'):
                        first_seen_str = first_seen.strftime('%H:%M:%S')
                    else:
                        first_seen_str = str(first_seen)
                    if hasattr(last_seen, 'strftime'):
                        last_seen_str = last_seen.strftime('%H:%M:%S')
                    else:
                        last_seen_str = str(last_seen)

                    is_online = bool(client.get('is_online', False))
                    ping_ms = client.get('ping_latency_ms')

                    mapped.append({
                        'status': '🟢 Online' if is_online else '🔴 Offline',
                        'ip': client.get('ip_address', 'Unknown') or 'Unknown',
                        'mac': client.get('mac_address', 'Unknown') or 'Unknown',
                        'hostname': client.get('hostname', 'Unknown') or 'Unknown',
                        'vendor': client.get('vendor', 'Unknown') or 'Unknown',
                        'ping': ping_ms,
                        'first_seen': first_seen_str,
                        'last_seen': last_seen_str,
                        'is_online': is_online,
                    })

                self.client_data = mapped
                self.update_client_display()
                self.client_status_label.config(text="Clients loaded from database", bootstyle="success")
            else:
                self.client_data = []
                self.client_status_label.config(text=f"Failed to load clients (HTTP {response.status_code})", bootstyle="danger")
        except Exception as e:
            print(f"❌ Error loading clients: {e}")
            self.client_data = []
            self.client_status_label.config(text="Error loading clients", bootstyle="danger")

        # Update last update time
        time_str = datetime.now().strftime('%H:%M:%S')
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
                if any(search_term in str(value).lower() for value in client.values())
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
        self.client_auto_refresh_enabled = False
        self.auto_refresh_btn.config(text="▶️ Auto Refresh", bootstyle="warning")
        if self.client_auto_refresh_job:
            self.root.after_cancel(self.client_auto_refresh_job)
            self.client_auto_refresh_job = None

    def schedule_auto_refresh(self):
        """Schedule the next auto refresh."""
        if self.client_auto_refresh_enabled:
            self.client_auto_refresh_job = self.root.after(self.client_auto_refresh_interval, self.auto_refresh_clients)

    def auto_refresh_clients(self):
        """Perform automatic client refresh by reloading from DB via API (no local scanning)."""
        if self.client_auto_refresh_enabled:
            self.load_clients_from_db()
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
        if self.client_modal and self.client_modal.winfo_exists():
            try:
                self.client_modal.grab_release()
            except:
                pass
            self.client_modal.destroy()
        self.client_modal = None
        self.client_modal_is_open = False  # Reset flag

    def show_loop_detection(self):
        """Show loop detection modal (client view only - data fetch from database)."""
        # Set flag FIRST before any other checks to prevent race condition
        if self.loop_modal_is_open:
            print("⚠️ Loop modal already open - bringing to front")
            if self.loop_modal and self.loop_modal.winfo_exists():
                try:
                    self.loop_modal.lift()
                    self.loop_modal.focus_force()
                    self.loop_modal.attributes('-topmost', True)
                    self.loop_modal.after(100, lambda: self.loop_modal.attributes('-topmost', False))
                except:
                    # Modal might have been destroyed, reset flag
                    self.loop_modal_is_open = False
                    print("⚠️ Loop modal was destroyed, resetting flag")
            return
        
        # Set flag immediately to prevent multiple openings
        print("✅ Opening new loop detection modal")
        self.loop_modal_is_open = True
            
        self.loop_modal = tb.Toplevel(self.root)
        self.loop_modal.title("🔄 Loop Detection Monitor")
        self.loop_modal.geometry("1000x700")
        self.loop_modal.resizable(True, True)
        self.loop_modal.configure(bg='#f8f9fa')
        
        # Make it a proper modal window
        self.loop_modal.transient(self.root)
        self.loop_modal.grab_set()

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
        
        # Bind destroy event to reset flag as fallback
        def on_modal_destroy(event):
            if event.widget == self.loop_modal:
                self.loop_modal_is_open = False
                print("🗑️ Loop modal destroyed, flag reset")
        self.loop_modal.bind("<Destroy>", on_modal_destroy)

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
        if self.loop_modal and self.loop_modal.winfo_exists():
            try:
                self.loop_modal.grab_release()
            except:
                pass
            self.loop_modal.destroy()
        self.loop_modal = None
        self.loop_modal_is_open = False  # Reset flag

    def cleanup(self):
        """Clean up resources when tab is destroyed"""
        self.stop_auto_update()
        self.close_client_modal()
        self.close_loop_modal()