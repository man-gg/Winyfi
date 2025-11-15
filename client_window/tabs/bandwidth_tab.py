import ttkbootstrap as tb
import tkinter as tk
import requests
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime, timedelta
from tkinter import messagebox
import tkinter.ttk as ttk
from ttkbootstrap.widgets import DateEntry

class BandwidthTab:
    def __init__(self, parent_frame, api_base_url, root_window):
        self.parent_frame = parent_frame
        self.api_base_url = api_base_url
        self.root = root_window
        self.auto_update_interval = 30000  # 30 seconds in milliseconds
        self.auto_update_job = None
        self.last_update_time = None
        self.is_updating = False
        self.bandwidth_data = []
        self.routers = []
        self._build_bandwidth_page()

    def _build_bandwidth_page(self):
        # Header with title and auto-update controls
        header_frame = tb.Frame(self.parent_frame)
        header_frame.pack(fill="x", padx=20, pady=(20, 0))
        tb.Label(header_frame, text="📊 Bandwidth Monitoring", font=("Segoe UI", 16)).pack(side="left")

        # Auto-update controls
        auto_update_frame = tb.Frame(header_frame)
        auto_update_frame.pack(side="right")
        self.auto_update_var = tb.BooleanVar(value=True)
        auto_update_check = tb.Checkbutton(auto_update_frame, text="Auto Update", variable=self.auto_update_var, command=self.toggle_auto_update, bootstyle="success")
        auto_update_check.pack(side="right")

        # Update interval selector
        interval_frame = tb.Frame(auto_update_frame)
        interval_frame.pack(side="right", padx=(0, 10))
        tb.Label(interval_frame, text="Interval:", font=("Segoe UI", 8)).pack(side="left")
        self.interval_var = tb.StringVar(value="30s")
        interval_combo = tb.Combobox(interval_frame, textvariable=self.interval_var, values=["10s", "30s", "1m", "2m", "5m"], width=6, state="readonly")
        interval_combo.pack(side="left", padx=(2, 0))
        interval_combo.bind("<<ComboboxSelected>>", self.on_interval_changed)

        self.last_update_label = tb.Label(auto_update_frame, text="", font=("Segoe UI", 8), bootstyle="secondary")
        self.last_update_label.pack(side="right", padx=(0, 10))

        # Data points counter
        self.data_points_label = tb.Label(auto_update_frame, text="Data Points: 0", font=("Segoe UI", 8), bootstyle="info")
        self.data_points_label.pack(side="right", padx=(0, 10))

        # Controls section
        controls_frame = tb.LabelFrame(self.parent_frame, text="📋 Controls", bootstyle="info", padding=10)
        controls_frame.pack(fill="x", padx=20, pady=10)

        # Router selector
        router_frame = tb.Frame(controls_frame)
        router_frame.pack(fill="x", pady=(0, 10))
        tb.Label(router_frame, text="Select Router:", font=("Segoe UI", 10)).pack(side="left")
        self.router_var = tk.StringVar()
        self.router_combo = tb.Combobox(router_frame, textvariable=self.router_var, state="readonly", width=30)
        self.router_combo.pack(side="left", padx=(10, 0))
        self.router_combo.bind("<<ComboboxSelected>>", self.on_router_changed)

        # Date range filter
        date_frame = tb.Frame(controls_frame)
        date_frame.pack(fill="x", pady=(0, 10))
        tb.Label(date_frame, text="From:", font=("Segoe UI", 10)).pack(side="left")
        initial_start = datetime.now() - timedelta(days=7)
        self.start_date = DateEntry(date_frame, width=12, dateformat="%m/%d/%Y", bootstyle="primary")
        self.start_date.entry.delete(0, tk.END)
        self.start_date.entry.insert(0, initial_start.strftime("%m/%d/%Y"))
        self.start_date.pack(side="left", padx=(10, 5))
        tb.Label(date_frame, text="To:", font=("Segoe UI", 10)).pack(side="left", padx=(20, 0))
        initial_end = datetime.now()
        self.end_date = DateEntry(date_frame, width=12, dateformat="%m/%d/%Y", bootstyle="primary")
        self.end_date.entry.delete(0, tk.END)
        self.end_date.entry.insert(0, initial_end.strftime("%m/%d/%Y"))
        self.end_date.pack(side="left", padx=(10, 5))

        # Action buttons
        button_frame = tb.Frame(controls_frame)
        button_frame.pack(fill="x")
        self.apply_btn = tb.Button(button_frame, text="🔍 Apply Filter", bootstyle="primary", command=self.load_bandwidth_data)
        self.apply_btn.pack(side="left", padx=(0, 10))
        self.refresh_btn = tb.Button(button_frame, text="🔄 Refresh", bootstyle="info", command=self.refresh_bandwidth_data)
        self.refresh_btn.pack(side="left", padx=(0, 10))
        self.last7_btn = tb.Button(button_frame, text="📊 Last 7 Days", bootstyle="secondary", command=self.load_last_7_days)
        self.last7_btn.pack(side="left", padx=(0, 10))
        self.force_refresh_btn = tb.Button(button_frame, text="🔄 Force Chart Refresh", bootstyle="warning", command=self.force_chart_refresh)
        self.force_refresh_btn.pack(side="left")

        # Inline loader (hidden initially)
        self._bw_loader_container = tb.Frame(button_frame)
        self._bw_loader_container.pack(side='left', padx=(12,0))
        self._bw_loader_container.pack_forget()
        self._bw_pbar = tb.Progressbar(self._bw_loader_container, mode='indeterminate', length=110, bootstyle='info-striped')
        self._bw_phase_label = tb.Label(self._bw_loader_container, text='', font=("Segoe UI",9,'italic'), bootstyle='secondary')
        self._bw_cancel_btn = tb.Button(self._bw_loader_container, text='Cancel', bootstyle='danger-outline', width=7, command=self._cancel_bandwidth_load)
        self._bw_pbar.pack(side='left')
        self._bw_phase_label.pack(side='left', padx=(6,4))
        self._bw_cancel_btn.pack(side='left')
        self._bw_cancel_event = None

        # Statistics cards
        stats_frame = tb.Frame(self.parent_frame)
        stats_frame.pack(fill="x", padx=20, pady=10)
        
        # Create stats cards
        self.stats_cards = {}
        stats_data = [
            ("avg_download", "📥 Avg Download", "Mbps", "primary"),
            ("avg_upload", "📤 Avg Upload", "Mbps", "success"),
            ("avg_latency", "⏱️ Avg Latency", "ms", "warning"),
            ("max_download", "🚀 Max Download", "Mbps", "info")
        ]
        
        for i, (key, title, unit, style) in enumerate(stats_data):
            card = tb.LabelFrame(stats_frame, text=title, bootstyle=style, padding=10)
            card.grid(row=0, column=i, padx=5, pady=5, sticky="ew")
            stats_frame.grid_columnconfigure(i, weight=1)
            
            self.stats_cards[key] = tb.Label(card, text="—", font=("Segoe UI", 14, "bold"))
            self.stats_cards[key].pack()
            tb.Label(card, text=unit, font=("Segoe UI", 8), bootstyle="secondary").pack()

        # Chart frame - add chart above the table (like dashboard.py)
        self.bandwidth_chart_frame = tb.Frame(self.parent_frame)
        self.bandwidth_chart_frame.pack(fill="both", expand=True, padx=20, pady=(10, 10))
        
        # Initialize matplotlib figure and axes for bandwidth chart (side-by-side like dashboard.py)
        self.fig, (self.ax1, self.ax2) = plt.subplots(1, 2, figsize=(12, 4), dpi=100)
        self.fig.patch.set_facecolor('white')
        self.fig.tight_layout(pad=2.0)
        
        # Embed canvas in Tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.bandwidth_chart_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # Main content area - data table below the chart
        self.table_frame = tb.Frame(self.parent_frame)
        self.table_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Table with scrollbars
        table_container = tb.Frame(self.table_frame)
        table_container.pack(fill="both", expand=True, padx=10, pady=10)

        # Subtitle label describing current table context
        self.table_subtitle = tb.Label(table_container, text="", font=("Segoe UI", 10, "bold"), bootstyle="secondary")
        self.table_subtitle.grid(row=0, column=0, sticky="w", pady=(0, 6))

        # Define column configurations for different views
        self.table_columns_all = ("timestamp", "download", "upload", "latency")
        self.table_columns_router = ("timestamp", "download", "upload", "latency")

        # Create treeview frame for grid layout
        tree_container = tb.Frame(table_container)
        tree_container.grid(row=1, column=0, sticky="nsew")
        
        # Configure grid weights for table_container
        table_container.grid_rowconfigure(1, weight=1)
        table_container.grid_columnconfigure(0, weight=1)
        
        # Create treeview
        columns = ("timestamp", "router", "download", "upload", "latency")
        self.bandwidth_table = ttk.Treeview(tree_container, columns=columns, show="headings", height=20)
        
        # Configure columns
        self.bandwidth_table.column("timestamp", width=180, anchor="center")
        self.bandwidth_table.column("router", width=0, anchor="center", stretch=False)  # Hide router column by default
        self.bandwidth_table.column("download", width=120, anchor="center")
        self.bandwidth_table.column("upload", width=120, anchor="center")
        self.bandwidth_table.column("latency", width=100, anchor="center")

        # Configure headers
        self.bandwidth_table.heading("timestamp", text="Timestamp")
        self.bandwidth_table.heading("router", text="Router")
        self.bandwidth_table.heading("download", text="Download (Mbps)")
        self.bandwidth_table.heading("upload", text="Upload (Mbps)")
        self.bandwidth_table.heading("latency", text="Latency (ms)")

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.bandwidth_table.yview)
        h_scrollbar = ttk.Scrollbar(tree_container, orient="horizontal", command=self.bandwidth_table.xview)
        self.bandwidth_table.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Grid layout for proper scrollbar positioning
        self.bandwidth_table.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        # Configure grid weights
        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)
        
        # Bind mouse wheel scrolling for smooth scrolling
        def on_mousewheel_vertical(event):
            self.bandwidth_table.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"
        
        def on_mousewheel_horizontal(event):
            self.bandwidth_table.xview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"
        
        # Bind vertical scroll (normal mouse wheel)
        self.bandwidth_table.bind("<MouseWheel>", on_mousewheel_vertical)
        # Bind horizontal scroll (Shift + mouse wheel)
        self.bandwidth_table.bind("<Shift-MouseWheel>", on_mousewheel_horizontal)

        # Load initial data
        self.load_routers()
        self.load_bandwidth_data()
        self.start_auto_update()

    def load_routers(self):
        """Load routers from API and populate the dropdown"""
        try:
            response = requests.get(f"{self.api_base_url}/api/routers", timeout=5)
            if response.ok:
                self.routers = response.json()
                router_names = ["All Routers"] + [r["name"] for r in self.routers]
                self.router_combo['values'] = router_names
                if router_names:
                    self.router_combo.current(0)  # Select "All Routers" by default
        except Exception as e:
            print(f"Error loading routers: {e}")

    def on_router_changed(self, event=None):
        """Handle router selection change"""
        self.load_bandwidth_data()

    def load_last_7_days(self):
        """Load data for the last 7 days"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        self.start_date.entry.delete(0, tk.END)
        self.start_date.entry.insert(0, start_date.strftime("%m/%d/%Y"))
        self.end_date.entry.delete(0, tk.END)
        self.end_date.entry.insert(0, end_date.strftime("%m/%d/%Y"))
        self.load_bandwidth_data()

    def load_bandwidth_data(self):
        """Load bandwidth data with inline loader, phases, and cancellation."""
        import threading
        if self.is_updating:
            return
        self.is_updating = True
        self._show_bw_loader("Contacting server...")
        self._bw_cancel_event = threading.Event()

        def finish(success, msg):
            self._hide_bw_loader()
            self.is_updating = False
            self.last_update_time = datetime.now()
            self.update_last_update_display()
            if not success:
                messagebox.showerror("Bandwidth Data Error", msg)

        def worker():
            try:
                # Build params
                selected_router = self.router_var.get()
                router_id = None
                if selected_router and selected_router != "All Routers":
                    router = next((r for r in self.routers if r["name"] == selected_router), None)
                    if router:
                        router_id = router["id"]
                params = {"limit": 1000}
                if router_id:
                    params["router_id"] = router_id
                start_date = self.start_date.entry.get()
                end_date = self.end_date.entry.get()
                if start_date and end_date:
                    try:
                        start_dt = datetime.strptime(start_date, "%m/%d/%Y")
                        end_dt = datetime.strptime(end_date, "%m/%d/%Y")
                        params["start_date"] = start_dt.strftime("%Y-%m-%d")
                        params["end_date"] = end_dt.strftime("%Y-%m-%d")
                    except ValueError:
                        params["start_date"] = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
                        params["end_date"] = datetime.now().strftime("%Y-%m-%d")
                if self._bw_cancel_event.is_set():
                    self.root.after(0, lambda: finish(False, "Cancelled."))
                    return
                try:
                    resp = requests.get(f"{self.api_base_url}/api/bandwidth/logs", params=params, timeout=15)
                except requests.exceptions.Timeout:
                    self.root.after(0, lambda: finish(False, "Timeout (15s)."))
                    return
                except Exception as e:
                    self.root.after(0, lambda e=e: finish(False, f"Connection error: {e}"))
                    return
                if self._bw_cancel_event.is_set():
                    self.root.after(0, lambda: finish(False, "Cancelled."))
                    return
                if not resp.ok:
                    self.bandwidth_data = []
                    self.root.after(0, lambda: self._update_all_components())
                    self.root.after(0, lambda: finish(False, f"API Error: {resp.status_code}"))
                    return
                self.root.after(0, lambda: self._update_bw_phase("Parsing data..."))
                try:
                    self.bandwidth_data = resp.json()
                except Exception:
                    self.bandwidth_data = []
                    self.root.after(0, lambda: self._update_all_components())
                    self.root.after(0, lambda: finish(False, "Invalid JSON."))
                    return
                if self._bw_cancel_event.is_set():
                    self.root.after(0, lambda: finish(False, "Cancelled."))
                    return
                self.root.after(0, lambda: self._update_bw_phase("Updating UI..."))
                self.root.after(0, self._update_all_components)
                self.root.after(0, lambda: finish(True, "Loaded"))
            except Exception as e:
                self.bandwidth_data = []
                self.root.after(0, self._update_all_components)
                self.root.after(0, lambda e=e: finish(False, f"Unexpected: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    # Inline loader helpers
    def _show_bw_loader(self, phase="Loading..."):
        try:
            for btn in (self.apply_btn, self.refresh_btn, self.last7_btn, self.force_refresh_btn):
                btn.config(state='disabled')
        except Exception:
            pass
        self._bw_loader_container.pack(side='left')
        self._bw_phase_label.config(text=phase)
        try:
            self._bw_pbar.start(12)
        except Exception:
            pass

    def _update_bw_phase(self, text):
        if self._bw_loader_container.winfo_ismapped():
            self._bw_phase_label.config(text=text)

    def _hide_bw_loader(self):
        try:
            self._bw_pbar.stop()
        except Exception:
            pass
        try:
            self._bw_loader_container.pack_forget()
        except Exception:
            pass
        try:
            for btn in (self.apply_btn, self.refresh_btn, self.last7_btn, self.force_refresh_btn):
                btn.config(state='normal')
        except Exception:
            pass
        self._bw_phase_label.config(text='')
        self._bw_cancel_event = None

    def _cancel_bandwidth_load(self):
        if self._bw_cancel_event and not self._bw_cancel_event.is_set():
            self._bw_cancel_event.set()
            self._update_bw_phase("Cancelling...")
    
    def _prepare_chart_for_update(self):
        """No-op: No forced size locking needed for robust resizing."""
        pass
    
    def _lock_figure_size(self):
        """No-op: No forced size locking needed for robust resizing."""
        pass
    
    def _disable_resize_events(self):
        """No-op: No forced resize disabling needed for robust resizing."""
        pass
    
    def _enforce_canvas_size(self):
        """No-op: No forced canvas size enforcement needed for robust resizing."""
        pass
    
    def _update_all_components(self):
        """Update all chart components consistently"""
        try:
            # Build a unified filtered dataset so chart, table, and stats stay in sync
            # Limit to 100 rows to match table size and user expectations
            self._bw_filtered = list(self.bandwidth_data[:100]) if self.bandwidth_data else []
            self.update_charts()
            self.update_table()
            self.update_statistics()
        except Exception as e:
            print(f"Debug - Error updating components: {e}")

    def refresh_bandwidth_data(self):
        """Refresh bandwidth data"""
        self.load_bandwidth_data()
    
    def force_chart_refresh(self):
        """Force a complete chart refresh"""
        try:
            # Clear and redraw the entire figure with side-by-side layout
            self.fig.clear()
            self.ax1, self.ax2 = self.fig.subplots(1, 2, figsize=(12, 4), dpi=100)
            
            # Restore figure properties
            self.fig.patch.set_facecolor('white')
            self.fig.tight_layout(pad=2.0)
            
            # Update with current data
            self.update_charts()
        except Exception as e:
            print(f"Error in force_chart_refresh: {e}")

    def update_charts(self):
        """Update the bandwidth charts - side-by-side layout like dashboard.py"""
        import matplotlib.dates as mdates
        
        try:
            self.ax1.clear()
            self.ax2.clear()
            self.fig.patch.set_facecolor('white')

            # Use the unified filtered list to keep chart aligned with table
            source = getattr(self, "_bw_filtered", None)
            if source is None:
                source = list(self.bandwidth_data[:100]) if self.bandwidth_data else []

            if not source:
                # Clear charts if no data
                self.canvas.draw()
                return

            # Parse timestamps and prepare data
            timestamps = []
            downloads = []
            uploads = []
            latencies = []
            
            for d in source:
                try:
                    # Parse timestamp
                    ts_str = d['timestamp']
                    if 'GMT' in ts_str:
                        ts = datetime.strptime(ts_str, '%a, %d %b %Y %H:%M:%S GMT')
                    elif 'Z' in ts_str:
                        ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                    else:
                        ts = datetime.fromisoformat(ts_str)
                    
                    timestamps.append(ts)
                    
                    # Parse download
                    download_val = d.get('download_mbps')
                    if download_val is None or download_val == '':
                        downloads.append(0.0)
                    else:
                        try:
                            downloads.append(float(download_val))
                        except (ValueError, TypeError):
                            downloads.append(0.0)
                    
                    # Parse upload
                    upload_val = d.get('upload_mbps')
                    if upload_val is None or upload_val == '':
                        uploads.append(0.0)
                    else:
                        try:
                            uploads.append(float(upload_val))
                        except (ValueError, TypeError):
                            uploads.append(0.0)
                    
                    # Parse latency
                    latency_val = d.get('latency_ms')
                    if latency_val is None or latency_val == '':
                        latencies.append(0.0)
                    else:
                        try:
                            latencies.append(float(latency_val))
                        except (ValueError, TypeError):
                            latencies.append(0.0)
                except Exception as e:
                    print(f"Error parsing data point: {e}")
                    continue

            if not timestamps:
                self.canvas.draw()
                return

            # Plot 1: Download and Upload (Mbps) - side by side like dashboard.py
            self.ax1.plot(timestamps, downloads, label="Download (Mbps)", 
                         color="#dc3545", linewidth=2, marker='o', markersize=3)
            self.ax1.plot(timestamps, uploads, label="Upload (Mbps)", 
                         color="#28a745", linewidth=2, marker='s', markersize=3)
            self.ax1.set_title("Bandwidth Usage", fontsize=12, fontweight='bold')
            self.ax1.set_xlabel("Date", fontsize=10)
            self.ax1.set_ylabel("Mbps", fontsize=10)
            self.ax1.legend(loc='upper left', fontsize=9)
            self.ax1.grid(True, alpha=0.3)
            self.ax1.tick_params(axis="x", rotation=45, labelsize=8)
            
            # Format x-axis dates - always show date
            if len(timestamps) > 1:
                time_span = (timestamps[-1] - timestamps[0]).total_seconds()
                if time_span < 86400:  # Less than 1 day - show date and time
                    self.ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
                elif time_span < 604800:  # Less than 1 week - show date and time
                    self.ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
                else:  # More than 1 week - show date
                    self.ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d/%Y"))

            # Plot 2: Latency (ms) - side by side like dashboard.py
            self.ax2.plot(timestamps, latencies, label="Latency (ms)", 
                         color="#007bff", linewidth=2, marker='^', markersize=3)
            self.ax2.set_title("Latency", fontsize=12, fontweight='bold')
            self.ax2.set_xlabel("Date", fontsize=10)
            self.ax2.set_ylabel("ms", fontsize=10)
            self.ax2.legend(loc='upper left', fontsize=9)
            self.ax2.grid(True, alpha=0.3)
            self.ax2.tick_params(axis="x", rotation=45, labelsize=8)
            
            # Format x-axis dates for latency chart - always show date
            if len(timestamps) > 1:
                time_span = (timestamps[-1] - timestamps[0]).total_seconds()
                if time_span < 86400:  # Less than 1 day - show date and time
                    self.ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
                elif time_span < 604800:  # Less than 1 week - show date and time
                    self.ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
                else:  # More than 1 week - show date
                    self.ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d/%Y"))

            # Update data points counter
            total_points = len(self.bandwidth_data)
            displayed_points = len(timestamps)
            if total_points > displayed_points:
                self.data_points_label.config(text=f"Data Points: {displayed_points}/{total_points}")
            else:
                self.data_points_label.config(text=f"Data Points: {displayed_points}")

            # Adjust layout and redraw
            self.fig.tight_layout(pad=2.0)
            self.canvas.draw()

        except Exception as e:
            print(f"Error updating charts: {e}")

    def update_table(self):
        """Update the bandwidth data table to match admin logic"""
        try:
            # Clear existing data
            for item in self.bandwidth_table.get_children():
                self.bandwidth_table.delete(item)

            selected_router = self.router_var.get() if hasattr(self, 'router_var') else "All Routers"
            # If 'All Routers', hide router column and aggregate by hour if possible
            if selected_router == "All Routers":
                # Show router column for 'All Routers'
                self.bandwidth_table['displaycolumns'] = ("timestamp", "router", "download", "upload", "latency")
                self.bandwidth_table.column("router", width=150, anchor="center", stretch=True)
                self.table_subtitle.config(text="📊 Viewing: All Routers (Hourly Aggregated)")
            else:
                # Hide router column for specific router
                self.bandwidth_table['displaycolumns'] = ("timestamp", "download", "upload", "latency")
                self.bandwidth_table.column("router", width=0, stretch=False)
                self.table_subtitle.config(text=f"📊 Viewing: {selected_router}")

            # Add new data
            # Use the same unified filtered list as the chart
            source = getattr(self, "_bw_filtered", None)
            if source is None:
                source = list(self.bandwidth_data[:100]) if self.bandwidth_data else []
            for data in source:  # Already limited for performance
                try:
                    # Handle timestamp parsing
                    timestamp_str = data['timestamp']
                    if 'GMT' in timestamp_str:
                        timestamp = datetime.strptime(timestamp_str, '%a, %d %b %Y %H:%M:%S GMT')
                    elif 'Z' in timestamp_str:
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    else:
                        timestamp = datetime.fromisoformat(timestamp_str)
                    formatted_time = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                except Exception as e:
                    print(f"Error parsing timestamp in table: {e}")
                    formatted_time = "Invalid Date"

                router_name = data.get('router_name', 'Unknown')

                # Handle None values safely
                try:
                    download_val = data.get('download_mbps')
                    download = f"{float(download_val):.2f}" if download_val is not None else "0.00"
                except (ValueError, TypeError):
                    download = "0.00"

                try:
                    upload_val = data.get('upload_mbps')
                    upload = f"{float(upload_val):.2f}" if upload_val is not None else "0.00"
                except (ValueError, TypeError):
                    upload = "0.00"

                try:
                    latency_val = data.get('latency_ms')
                    latency = f"{float(latency_val):.1f}" if latency_val is not None else "0.0"
                except (ValueError, TypeError):
                    latency = "0.0"

                if selected_router == "All Routers":
                    self.bandwidth_table.insert('', 'end', values=(
                        formatted_time, router_name, download, upload, latency
                    ))
                else:
                    self.bandwidth_table.insert('', 'end', values=(
                        formatted_time, download, upload, latency
                    ))
        except Exception as e:
            print(f"Error updating table: {e}")

    def update_statistics(self):
        """Update the statistics cards"""
        try:
            # Use the same unified filtered list as table/chart for consistency
            source = getattr(self, "_bw_filtered", None)
            if source is None:
                source = list(self.bandwidth_data[:100]) if self.bandwidth_data else []
            if not source:
                for key in self.stats_cards:
                    self.stats_cards[key].config(text="—")
                return
            
            # Calculate statistics with proper None handling
            downloads = []
            uploads = []
            latencies = []
            
            for d in source:
                # Handle download_mbps
                download_val = d.get('download_mbps')
                if download_val is not None:
                    try:
                        downloads.append(float(download_val))
                    except (ValueError, TypeError):
                        downloads.append(0.0)
                else:
                    downloads.append(0.0)
                
                # Handle upload_mbps
                upload_val = d.get('upload_mbps')
                if upload_val is not None:
                    try:
                        uploads.append(float(upload_val))
                    except (ValueError, TypeError):
                        uploads.append(0.0)
                else:
                    uploads.append(0.0)
                
                # Handle latency_ms
                latency_val = d.get('latency_ms')
                if latency_val is not None:
                    try:
                        latencies.append(float(latency_val))
                    except (ValueError, TypeError):
                        latencies.append(0.0)
                else:
                    latencies.append(0.0)
            
            avg_download = sum(downloads) / len(downloads) if downloads else 0
            avg_upload = sum(uploads) / len(uploads) if uploads else 0
            avg_latency = sum(latencies) / len(latencies) if latencies else 0
            max_download = max(downloads) if downloads else 0
            
            # Update cards
            self.stats_cards['avg_download'].config(text=f"{avg_download:.2f}")
            self.stats_cards['avg_upload'].config(text=f"{avg_upload:.2f}")
            self.stats_cards['avg_latency'].config(text=f"{avg_latency:.1f}")
            self.stats_cards['max_download'].config(text=f"{max_download:.2f}")
            
        except Exception as e:
            print(f"Error updating statistics: {e}")

    # Auto-update methods
    def start_auto_update(self):
        """Start the automatic update timer"""
        if self.auto_update_var.get():
            self.auto_update_job = self.root.after(self.auto_update_interval, self.auto_update_bandwidth)

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

    def auto_update_bandwidth(self):
        """Automatically update bandwidth data and charts"""
        if self.auto_update_var.get():
            self.load_bandwidth_data()
            # Schedule next update
            self.auto_update_job = self.root.after(self.auto_update_interval, self.auto_update_bandwidth)

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

    def cleanup(self):
        """Clean up resources when tab is destroyed"""
        self.stop_auto_update()
