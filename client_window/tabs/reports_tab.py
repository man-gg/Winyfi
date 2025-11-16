import ttkbootstrap as tb
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import requests
from datetime import datetime, timedelta
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import csv
import os
import sys
from ttkbootstrap.widgets import DateEntry
from PIL import Image, ImageTk

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from print_utils import print_srf_form


class ReportsTab:
    def __init__(self, parent_frame, root, app=None):
        self.parent_frame = parent_frame
        self.root = root
        self.app = app  # Reference to parent ClientApp
        self.api_base_url = os.getenv("WINYFI_API", "http://127.0.0.1:5000")
        self._build_reports_page()

    def _build_reports_page(self):
        # Header
        header = tb.Frame(self.parent_frame)
        header.pack(fill='x', padx=10, pady=(10, 0))
        tb.Label(header, text="📊 Network Reports", font=("Segoe UI", 16, "bold")).pack(side='left')
        
        # Add ICT Service Requests button to header
        tb.Button(header, text="📝 ICT Service Requests", 
                 bootstyle="primary", command=self._open_tickets_window).pack(side='right')
        
        # Filter controls
        filter_frame = tb.LabelFrame(self.parent_frame, text="Report Filters", padding=15)
        filter_frame.pack(fill='x', padx=10, pady=10)
        
        # Date range selection
        date_frame = tb.Frame(filter_frame)
        date_frame.pack(fill='x', pady=(0, 10))
        
        # Start Date
        tb.Label(date_frame, text="Start Date:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, padx=(0, 5), pady=5, sticky='w')
        initial_start = datetime.now() - timedelta(days=7)
        self.start_date = DateEntry(date_frame, width=12, dateformat="%m/%d/%Y", bootstyle="primary")
        self.start_date.entry.delete(0, tk.END)
        self.start_date.entry.insert(0, initial_start.strftime("%m/%d/%Y"))
        self.start_date.grid(row=0, column=1, padx=(0, 20), pady=5)
        
        # End Date
        tb.Label(date_frame, text="End Date:", font=("Segoe UI", 10, "bold")).grid(row=0, column=2, padx=(0, 5), pady=5, sticky='w')
        initial_end = datetime.now()
        self.end_date = DateEntry(date_frame, width=12, dateformat="%m/%d/%Y", bootstyle="primary")
        self.end_date.entry.delete(0, tk.END)
        self.end_date.entry.insert(0, initial_end.strftime("%m/%d/%Y"))
        self.end_date.grid(row=0, column=3, padx=(0, 20), pady=5)
        
        # View Mode
        tb.Label(date_frame, text="View Mode:", font=("Segoe UI", 10, "bold")).grid(row=0, column=4, padx=(0, 5), pady=5, sticky='w')
        self.view_mode_var = tk.StringVar(value="weekly")
        view_mode_combo = tb.Combobox(date_frame, textvariable=self.view_mode_var, 
                                     values=["daily", "weekly", "monthly"], 
                                     state="readonly", width=10)
        view_mode_combo.grid(row=0, column=5, padx=(0, 20), pady=5)
        
        # Action buttons
        button_frame = tb.Frame(filter_frame)
        button_frame.pack(fill='x', pady=(10, 0))
        # Store button references for selective disabling
        self.generate_btn = tb.Button(button_frame, text="📊 Generate Report", 
            bootstyle="primary", command=self.generate_report)
        self.generate_btn.pack(side='left', padx=(0, 10))
        self.export_csv_btn = tb.Button(button_frame, text="📁 Export CSV", 
            bootstyle="success", command=self.export_csv)
        self.export_csv_btn.pack(side='left', padx=(0, 10))
        self.print_pdf_btn = tb.Button(button_frame, text="🖨️ Print PDF", 
            bootstyle="warning", command=self.print_pdf)
        self.print_pdf_btn.pack(side='left', padx=(0, 10))
        self.print_pdf_charts_btn = tb.Button(button_frame, text="📈 PDF with Charts", 
            bootstyle="danger", command=self.print_pdf_with_charts)
        self.print_pdf_charts_btn.pack(side='left', padx=(0, 10))
        self.refresh_btn = tb.Button(button_frame, text="🔄 Refresh", 
            bootstyle="info", command=self.refresh_report)
        self.refresh_btn.pack(side='left')

        # Inline loader container (initially hidden)
        self._report_loader_container = tb.Frame(button_frame)
        self._report_loader_container.pack(side='left', padx=(10,0))
        self._report_loader_container.pack_forget()
        self._report_pbar = tb.Progressbar(self._report_loader_container, mode='indeterminate', length=110, bootstyle='info-striped')
        self._report_phase_label = tb.Label(self._report_loader_container, text='', font=("Segoe UI", 9, 'italic'), bootstyle='secondary')
        self._report_cancel_btn = tb.Button(self._report_loader_container, text='Cancel', bootstyle='danger-outline', width=7, command=self._cancel_report_generation)
        # Layout inside container
        self._report_pbar.pack(side='left')
        self._report_phase_label.pack(side='left', padx=(6,4))
        self._report_cancel_btn.pack(side='left')
        self._report_generating = False
        self._report_cancel_event = None
        
        # Summary cards
        self.summary_frame = tb.Frame(self.parent_frame)
        self.summary_frame.pack(fill='x', padx=10, pady=(0, 10))
        
        # Create summary cards
        self.total_routers_card = tb.LabelFrame(self.summary_frame, text="Total Routers", bootstyle="primary", padding=10)
        self.total_routers_card.grid(row=0, column=0, padx=5, pady=5, sticky='ew')
        self.total_routers_label = tb.Label(self.total_routers_card, text="—", font=("Segoe UI", 14, "bold"))
        self.total_routers_label.pack()
        
        self.avg_uptime_card = tb.LabelFrame(self.summary_frame, text="Avg Uptime", bootstyle="success", padding=10)
        self.avg_uptime_card.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        self.avg_uptime_label = tb.Label(self.avg_uptime_card, text="—", font=("Segoe UI", 14, "bold"))
        self.avg_uptime_label.pack()
        
        self.total_bandwidth_card = tb.LabelFrame(self.summary_frame, text="Total Bandwidth", bootstyle="info", padding=10)
        self.total_bandwidth_card.grid(row=0, column=2, padx=5, pady=5, sticky='ew')
        self.total_bandwidth_label = tb.Label(self.total_bandwidth_card, text="—", font=("Segoe UI", 14, "bold"))
        self.total_bandwidth_label.pack()
        
        # Configure grid weights
        for i in range(3):
            self.summary_frame.grid_columnconfigure(i, weight=1)
        
        # Main content area with notebook for tabs
        self.notebook = tb.Notebook(self.parent_frame)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        
        # Data table tab
        self.table_frame = tb.Frame(self.notebook)
        self.notebook.add(self.table_frame, text="📋 Data Table")
        
        # Create table
        table_container = tb.Frame(self.table_frame)
        table_container.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create tree container for grid layout
        tree_container = tb.Frame(table_container)
        tree_container.pack(fill='both', expand=True)
        
        # Treeview for data
        columns = ("Router Name", "Start Date", "Uptime %", "Downtime", "Bandwidth Usage")
        self.report_tree = tb.Treeview(tree_container, columns=columns, show="headings", height=15)
        
        # Configure columns
        for col in columns:
            self.report_tree.heading(col, text=col)
            self.report_tree.column(col, width=120, anchor='center')
        
        # Scrollbars
        v_scrollbar = tb.Scrollbar(tree_container, orient="vertical", command=self.report_tree.yview)
        h_scrollbar = tb.Scrollbar(tree_container, orient="horizontal", command=self.report_tree.xview)
        self.report_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Grid layout for proper scrollbar positioning
        self.report_tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        # Configure grid weights
        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)
        
        # Bind mouse wheel scrolling for smooth scrolling
        def on_mousewheel_vertical(event):
            self.report_tree.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"
        
        def on_mousewheel_horizontal(event):
            self.report_tree.xview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"
        
        # Bind vertical scroll (normal mouse wheel)
        self.report_tree.bind("<MouseWheel>", on_mousewheel_vertical)
        # Bind horizontal scroll (Shift + mouse wheel)
        self.report_tree.bind("<Shift-MouseWheel>", on_mousewheel_horizontal)
        
        # Charts tab
        self.charts_frame = tb.Frame(self.notebook)
        self.notebook.add(self.charts_frame, text="📈 Charts")
        
        # Create charts container
        charts_container = tb.Frame(self.charts_frame)
        charts_container.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Uptime chart
        self.uptime_chart_frame = tb.LabelFrame(charts_container, text="Uptime Trend", padding=10)
        self.uptime_chart_frame.pack(fill='both', expand=True, pady=(0, 10))
        # Initialize empty chart
        self.fig, self.ax = plt.subplots(figsize=(8, 4), dpi=100, constrained_layout=True)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.uptime_chart_frame)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)
        
        # Initial empty chart
        self.ax.set_title("Uptime Trend - Generate a report to view data")
        self.ax.set_xlabel("Date")
        self.ax.set_ylabel("Uptime %")
        self.ax.grid(True, alpha=0.3)
        self.canvas.draw()
        
        # Load initial data
        self.generate_report()

    def generate_report(self):
        """Generate report using inline loader with phases and cancel."""
        import threading
        if self._report_generating:
            return
        start_date_raw = self.start_date.entry.get()
        end_date_raw = self.end_date.entry.get()
        mode = self.view_mode_var.get()
        # Validate dates
        try:
            start_dt = datetime.strptime(start_date_raw, "%m/%d/%Y")
            end_dt = datetime.strptime(end_date_raw, "%m/%d/%Y")
            if start_dt > end_dt:
                messagebox.showerror("Invalid Date Range", "Start date cannot be after end date.")
                return
        except ValueError:
            messagebox.showerror("Invalid Date Format", "Use MM/DD/YYYY.")
            return
        params = {
            'start_date': start_dt.strftime('%Y-%m-%d'),
            'end_date': end_dt.strftime('%Y-%m-%d'),
            'mode': mode
        }
        # Show loader
        self._show_report_loader(initial_phase="Contacting server...")
        self._report_cancel_event = threading.Event()

        def finish(success, msg, payload=None):
            try:
                self._hide_report_loader()
            except Exception:
                # Widget may have been destroyed
                return
            
            if success:
                try:
                    data = (payload or {}).get('report_data', [])
                    chart_data = (payload or {}).get('chart_data', {})
                    summary = (payload or {}).get('summary', {})
                    self.report_data = data
                    self.total_routers_label.config(text=str(summary.get('total_routers', 0)))
                    self.avg_uptime_label.config(text=f"{summary.get('avg_uptime', 0):.1f}%")
                    self.total_bandwidth_label.config(text=f"{summary.get('total_bandwidth', 0):.1f} MB")
                    self.update_table()
                    self.update_chart(chart_data)
                except Exception:
                    # Widget may have been destroyed during logout
                    pass
            else:
                try:
                    messagebox.showerror("Report Error", msg)
                except Exception:
                    # Window may have been destroyed
                    pass

        def worker():
            try:
                # Phase: Request
                try:
                    resp = requests.get(f"{self.api_base_url}/api/reports/uptime", params=params, timeout=60)
                except requests.exceptions.Timeout:
                    self.root.after(0, lambda: finish(False, "Server timeout (60s). Try narrower date range."))
                    return
                except Exception as e:
                    self.root.after(0, lambda e=e: finish(False, f"Connection error: {e}"))
                    return
                # Check if app is closing (silent exit) or report cancelled (show message)
                if self._report_cancel_event.is_set():
                    app_closing = self.app and not getattr(self.app, 'status_monitoring_running', True)
                    if app_closing:
                        # App is closing, exit silently without message
                        return
                    # User explicitly cancelled, show message
                    self.root.after(0, lambda: finish(False, "Report cancelled."))
                    return
                if not resp.ok:
                    try:
                        err = resp.json().get('error', resp.text)
                    except Exception:
                        err = resp.text or 'Unknown error'
                    self.root.after(0, lambda: finish(False, f"Failed: {err}"))
                    return
                # Phase: parsing
                self.root.after(0, lambda: self._update_report_phase("Parsing data..."))
                try:
                    payload = resp.json()
                except Exception:
                    self.root.after(0, lambda: finish(False, "Invalid JSON response."))
                    return
                # Check if app is closing (silent exit) or report cancelled (show message)
                if self._report_cancel_event.is_set():
                    app_closing = self.app and not getattr(self.app, 'status_monitoring_running', True)
                    if app_closing:
                        # App is closing, exit silently without message
                        return
                    # User explicitly cancelled, show message
                    self.root.after(0, lambda: finish(False, "Report cancelled."))
                    return
                # Simulate small processing steps for user feedback (optional quick phases)
                self.root.after(0, lambda: self._update_report_phase("Updating UI..."))
                self.root.after(0, lambda: finish(True, "Done", payload))
            except Exception as e:
                self.root.after(0, lambda e=e: finish(False, f"Unexpected: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    # ---------------- Inline Loader Helpers -----------------
    def _show_report_loader(self, initial_phase="Loading..."):
        self._report_generating = True
        # Disable buttons except maybe refresh
        for btn in (self.generate_btn, self.export_csv_btn, self.print_pdf_btn, self.print_pdf_charts_btn):
            try: btn.config(state='disabled')
            except Exception: pass
        self._report_loader_container.pack(side='left')
        self._report_phase_label.config(text=initial_phase)
        try: self._report_pbar.start(12)
        except Exception: pass

    def _update_report_phase(self, text):
        if self._report_generating and self._report_phase_label.winfo_exists():
            self._report_phase_label.config(text=text)

    def _hide_report_loader(self):
        if not self._report_generating:
            return
        try: self._report_pbar.stop()
        except Exception: pass
        try: self._report_loader_container.pack_forget()
        except Exception: pass
        for btn in (self.generate_btn, self.export_csv_btn, self.print_pdf_btn, self.print_pdf_charts_btn):
            try: btn.config(state='normal')
            except Exception: pass
        try:
            if self._report_phase_label.winfo_exists():
                self._report_phase_label.config(text='')
        except Exception:
            pass
        self._report_generating = False
        self._report_cancel_event = None

    def _cancel_report_generation(self):
        if self._report_cancel_event and not self._report_cancel_event.is_set():
            self._report_cancel_event.set()
            self._update_report_phase("Cancelling...")

    def update_table(self):
        """Update the data table with report data"""
        # Clear existing data
        for item in self.report_tree.get_children():
            self.report_tree.delete(item)
        
        # Add new data
        for row in self.report_data:
            self.report_tree.insert("", "end", values=(
                row["router_name"],
                row["start_date"],
                f"{row['uptime_percentage']:.2f}%",
                row["downtime"],
                row["bandwidth_usage"]
            ))

    def update_chart(self, chart_data):
        """Update the uptime trend chart with robust layout and label handling, prevent shrinking."""
        self.ax.clear()
        dates = chart_data.get("dates", [])
        uptimes = chart_data.get("uptimes", [])

        if dates and uptimes:
            self.ax.plot(dates, uptimes, marker='o', linewidth=2, markersize=6)
            self.ax.set_title("Average Uptime Trend")
            self.ax.set_xlabel("Date")
            self.ax.set_ylabel("Uptime %")
            self.ax.grid(True, alpha=0.3)
            self.ax.set_ylim(0, 100)
            # Limit number of x-axis labels for readability
            max_labels = 10
            step = max(1, len(dates) // max_labels)
            shown_ticks = list(range(0, len(dates), step))
            self.ax.set_xticks(shown_ticks)
            self.ax.set_xticklabels([dates[i] for i in shown_ticks], rotation=45, ha='right')
        else:
            self.ax.set_title("No Data Available")
            self.ax.text(0.5, 0.5, "No data to display", ha='center', va='center', transform=self.ax.transAxes)

        self.canvas.draw_idle()

    def export_csv(self):
        """Export report data to CSV file"""
        if not self.report_data:
            messagebox.showwarning("No Data", "No report data to export. Please generate a report first.")
            return
        
        # Ask user for file location
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save Report as CSV"
        )
        
        if filename:
            try:
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ["router_name", "start_date", "uptime_percentage", "downtime", "bandwidth_usage", "bandwidth_mb"]
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    
                    writer.writeheader()
                    for row in self.report_data:
                        writer.writerow(row)
                
                # Log activity
                try:
                    import requests
                    api_base_url = self.parent.api_base_url
                    # Try to determine local IP for logging (optional)
                    local_ip = None
                    try:
                        from device_utils import get_device_info
                        info = get_device_info()
                        local_ip = info.get('ip_address')
                    except Exception:
                        try:
                            import socket
                            local_ip = socket.gethostbyname(socket.gethostname())
                        except Exception:
                            pass
                    payload = {
                        "user_id": self.parent.current_user.get('id'),
                        "action": "Export Report",
                        "target": f"CSV Report ({len(self.report_data)} records)"
                    }
                    if local_ip and local_ip not in ("127.0.0.1", "::1"):
                        payload["device_ip"] = local_ip
                    requests.post(f"{api_base_url}/api/log-activity", json=payload, timeout=2)
                except Exception:
                    pass
                
                messagebox.showinfo("Export Successful", f"Report exported to {filename}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export CSV: {str(e)}")

    def refresh_report(self):
        """Refresh the current report"""
        self.generate_report()

    def print_pdf(self):
        """Generate and download PDF report with fresh data from database"""
        try:
            start_date_raw = self.start_date.entry.get()
            end_date_raw = self.end_date.entry.get()
            mode = self.view_mode_var.get()
            
            # Convert MM/DD/YYYY to YYYY-MM-DD for API
            try:
                start_dt = datetime.strptime(start_date_raw, "%m/%d/%Y")
                end_dt = datetime.strptime(end_date_raw, "%m/%d/%Y")
                start_date = start_dt.strftime('%Y-%m-%d')
                end_date = end_dt.strftime('%Y-%m-%d')
            except ValueError:
                messagebox.showerror("Invalid Date", "Please enter valid dates in MM/DD/YYYY format.")
                return
            
            # Show progress message
            messagebox.showinfo("Generating PDF", "Generating PDF report with actual data... Please wait.")
            
            # Make API request for PDF
            params = {
                "start_date": start_date,
                "end_date": end_date,
                "mode": mode
            }
            
            response = requests.get(f"{self.api_base_url}/api/reports/pdf", params=params, timeout=30)
            
            if response.ok:
                # Save PDF file
                filename = filedialog.asksaveasfilename(
                    defaultextension=".pdf",
                    filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                    initialfile=f"network_report_{start_date}_to_{end_date}.pdf"
                )
                
                if filename:
                    with open(filename, 'wb') as f:
                        f.write(response.content)
                    messagebox.showinfo("Success", f"PDF report saved to:\n{filename}")
                        
            else:
                error_msg = response.json().get('error', 'Unknown error') if response.headers.get('content-type') == 'application/json' else response.text
                messagebox.showerror("Error", f"Failed to generate PDF:\n{error_msg}")
                
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Connection Error", f"Failed to connect to server: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while generating PDF: {str(e)}")

    def print_pdf_with_charts(self):
        """Generate and download PDF report with charts and fresh data"""
        try:
            start_date_raw = self.start_date.entry.get()
            end_date_raw = self.end_date.entry.get()
            mode = self.view_mode_var.get()
            
            # Convert MM/DD/YYYY to YYYY-MM-DD for API
            try:
                start_dt = datetime.strptime(start_date, "%m/%d/%Y")
                end_dt = datetime.strptime(end_date, "%m/%d/%Y")
                if start_dt > end_dt:
                    messagebox.showerror("Invalid Date Range", "Start date cannot be after end date.")
                    return
                # Convert to API format
                start_date = start_dt.strftime("%Y-%m-%d")
                end_date = end_dt.strftime("%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Invalid Date Format", "Please use MM/DD/YYYY format for dates.")
                return
            
            # Show progress message
            messagebox.showinfo("Generating PDF", "Generating PDF report with actual database data... Please wait.")
            
            # Make API request for PDF
            params = {
                "start_date": start_date,
                "end_date": end_date,
                "mode": mode
            }
            
            response = requests.get(f"{self.api_base_url}/api/reports/pdf", params=params, timeout=30)
            
            if response.ok:
                # Ask user where to save the file
                filename = filedialog.asksaveasfilename(
                    defaultextension=".pdf",
                    filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                    title="Save PDF Report As",
                    initialfile=f"network_report_{start_date}_to_{end_date}.pdf"
                )
                
                if filename:
                    # Save PDF content to file
                    with open(filename, 'wb') as pdf_file:
                        pdf_file.write(response.content)
                    
                    messagebox.showinfo("PDF Generated", f"PDF report saved successfully!\nLocation: {filename}")
                    
                    # Optionally open the PDF
                    try:
                        import os
                        os.startfile(filename)
                    except:
                        pass  # If we can't open the file, that's okay
                        
            else:
                error_msg = response.json().get("error", "Unknown error")
                messagebox.showerror("PDF Generation Error", f"Failed to generate PDF: {error_msg}")
                
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Connection Error", f"Failed to connect to server: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while generating PDF: {str(e)}")

    def print_pdf_with_charts(self):
        """Generate and download PDF report with charts"""
        try:
            start_date = self.start_date.entry.get()
            end_date = self.end_date.entry.get()
            mode = self.view_mode_var.get()
            
            # Convert MM/DD/YYYY to YYYY-MM-DD for API
            try:
                start_dt = datetime.strptime(start_date, "%m/%d/%Y")
                end_dt = datetime.strptime(end_date, "%m/%d/%Y")
                if start_dt > end_dt:
                    messagebox.showerror("Invalid Date Range", "Start date cannot be after end date.")
                    return
                # Convert to API format
                start_date = start_dt.strftime("%Y-%m-%d")
                end_date = end_dt.strftime("%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Invalid Date Format", "Please use MM/DD/YYYY format for dates.")
                return
            
            # Show progress message
            messagebox.showinfo("Generating PDF", "Generating PDF report with charts and actual database data... Please wait.")
            
            # Make API request for PDF with charts
            params = {
                "start_date": start_date,
                "end_date": end_date,
                "mode": mode
            }
            
            response = requests.get(f"{self.api_base_url}/api/reports/pdf-with-charts", params=params, timeout=30)
            
            if response.ok:
                # Ask user where to save the file
                filename = filedialog.asksaveasfilename(
                    defaultextension=".pdf",
                    filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                    title="Save PDF Report with Charts As",
                    initialfile=f"network_report_with_charts_{start_date}_to_{end_date}.pdf"
                )
                
                if filename:
                    # Save PDF content to file
                    with open(filename, 'wb') as pdf_file:
                        pdf_file.write(response.content)
                    
                    messagebox.showinfo("PDF Generated", f"PDF report with charts saved successfully!\nLocation: {filename}")
                    
                    # Optionally open the PDF
                    try:
                        import os
                        os.startfile(filename)
                    except:
                        pass  # If we can't open the file, that's okay
                        
            else:
                error_msg = response.json().get("error", "Unknown error")
                messagebox.showerror("PDF Generation Error", f"Failed to generate PDF with charts: {error_msg}")
                
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Connection Error", f"Failed to connect to server: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while generating PDF with charts: {str(e)}")

    def _open_tickets_window(self):
        """Open an enhanced window for ICT Service Request viewing and creation (client scope)."""
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
        
        tb.Label(title_frame, text="🎫 My Assigned Tickets", 
                font=("Segoe UI", 18, "bold"), bootstyle="inverse-primary").pack(anchor="w")
        tb.Label(title_frame, text="View tickets assigned to you and submit new requests", 
                font=("Segoe UI", 10), bootstyle="inverse-secondary").pack(anchor="w", pady=(2, 0))

        # Action buttons container
        action_frame = tb.Frame(header_content)
        action_frame.pack(side="right")

        tb.Button(
            action_frame,
            text="➕ New Request",
            bootstyle="success",
            command=lambda: self._open_new_ticket_modal(window),
            width=12
        ).pack(side="right", padx=(5, 0))

        tb.Button(
            action_frame,
            text="🔄 Refresh",
            bootstyle="info",
            command=self._load_tickets,
            width=10
        ).pack(side="right", padx=(5, 0))

        # Statistics and filter section
        stats_filter_frame = tb.Frame(main_container)
        stats_filter_frame.pack(fill="x", pady=(0, 15))

        # Statistics cards
        stats_frame = tb.LabelFrame(stats_filter_frame, text="📊 My Assigned Tickets", 
                                   bootstyle="info", padding=10)
        stats_frame.pack(side="left", fill="y")

        # Create statistics display
        self._create_client_ticket_stats(stats_frame)

        # Filter and search section
        filter_frame = tb.LabelFrame(stats_filter_frame, text="🔍 Filter & Search", 
                                   bootstyle="secondary", padding=10)
        filter_frame.pack(side="right", fill="both", expand=True, padx=(15, 0))

        # Filter controls
        filter_row1 = tb.Frame(filter_frame)
        filter_row1.pack(fill="x", pady=(0, 10))

        tb.Label(filter_row1, text="Status:", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.client_status_filter = tb.Combobox(filter_row1, values=["All", "Open", "Resolved"], 
                                        state="readonly", width=12)
        self.client_status_filter.set("All")
        self.client_status_filter.pack(side="left", padx=(5, 15))
        self.client_status_filter.bind("<<ComboboxSelected>>", lambda e: self._apply_client_filters())

        # Search row
        filter_row2 = tb.Frame(filter_frame)
        filter_row2.pack(fill="x")

        tb.Label(filter_row2, text="Search:", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.client_search_var = tb.StringVar()
        search_entry = tb.Entry(filter_row2, textvariable=self.client_search_var, width=25)
        search_entry.pack(side="left", padx=(5, 10))
        search_entry.bind("<KeyRelease>", lambda e: self._apply_client_filters())

        tb.Button(filter_row2, text="Clear", bootstyle="secondary-outline",
                 command=self._clear_client_filters, width=8).pack(side="left")

        # Enhanced Table Section
        table_container = tb.LabelFrame(main_container, text="📋 My Assigned Service Requests", 
                                       bootstyle="success", padding=10)
        table_container.pack(fill="both", expand=True)

        # Table frame with improved styling
        table_frame = tb.Frame(table_container)
        table_frame.pack(fill="both", expand=True)

        # Column configuration with better widths and headers
        columns = ("ict_srf_no", "campus", "services", "status", "created_at", "updated_at")
        column_config = {
            "ict_srf_no": {"text": "SRF No.", "width": 80, "anchor": "center"},
            "campus": {"text": "Campus", "width": 100, "anchor": "center"},
            "services": {"text": "Service Description", "width": 300, "anchor": "w"},
            "status": {"text": "Status", "width": 100, "anchor": "center"},
            "created_at": {"text": "Submitted", "width": 150, "anchor": "center"},
            "updated_at": {"text": "Last Updated", "width": 150, "anchor": "center"}
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
            self.tickets_table.heading(col, command=lambda c=col: self._sort_client_tickets_by_column(c))

        self.tickets_table.pack(fill="both", expand=True, side="left")

        # Enhanced scrollbars
        v_scrollbar = tb.Scrollbar(table_frame, orient="vertical", command=self.tickets_table.yview)
        h_scrollbar = tb.Scrollbar(table_frame, orient="horizontal", command=self.tickets_table.xview)
        
        self.tickets_table.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Convert to grid layout
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

        tb.Label(context_frame, text="💡 Tip: Double-click a row to view details", 
                font=("Segoe UI", 9), bootstyle="secondary").pack()

        # Auto-refresh controls
        refresh_frame = tb.Frame(footer_frame)
        refresh_frame.pack(side="right")

        self.client_auto_refresh_var = tb.BooleanVar(value=True)
        tb.Checkbutton(refresh_frame, text="Auto-refresh", variable=self.client_auto_refresh_var,
                      command=self._toggle_client_auto_refresh).pack(side="right", padx=(0, 10))

        self.client_last_refresh_label = tb.Label(refresh_frame, text="", font=("Segoe UI", 8), bootstyle="secondary")
        self.client_last_refresh_label.pack(side="right", padx=(0, 10))

        # Load tickets and start auto-refresh
        self._load_tickets()
        self._update_client_last_refresh_time()

        # Enhanced event bindings
        self.tickets_table.bind("<Double-1>", self._on_ticket_row_click)
        
        # Initialize auto-refresh
        if self.client_auto_refresh_var.get():
            self._start_client_ticket_auto_refresh()

    def _center_window(self, window, width, height):
        """Center a window on the screen."""
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        window.geometry(f"{width}x{height}+{x}+{y}")

    def _load_tickets(self):
        """Fetch SRFs assigned to current user from API and display in the table with enhanced formatting."""
        if not hasattr(self, 'tickets_table'):
            return
            
        try:
            self.tickets_table.delete(*self.tickets_table.get_children())
            
            # Get current user's assigned tickets instead of all tickets
            user_id = self._get_current_user_id()
            if user_id:
                resp = requests.get(f"{self.api_base_url}/api/technician/{user_id}/tickets", timeout=8)
            else:
                # Fallback to all tickets if user ID not available
                resp = requests.get(f"{self.api_base_url}/api/srfs", timeout=8)
            
            resp.raise_for_status()
            srfs = resp.json() or []
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load tickets from API: {e}")
            return

        row_count = 0
        for srf in srfs:
            # Determine row styling
            tag = "even" if row_count % 2 == 0 else "odd"
            
            # Special styling for status
            status = srf.get("status", "open")
            if status is None:
                status = "open"
            status = status.lower()
            
            if status == "resolved":
                tag = "resolved"
            elif srf.get("priority", "").lower() == "urgent":
                tag = "urgent"
            
            # Format dates nicely
            created_at = srf.get("created_at")
            updated_at = srf.get("updated_at")
            
            def fmt_date(dt):
                try:
                    if isinstance(dt, str):
                        # Try to parse the string date
                        dt_obj = datetime.fromisoformat(dt.replace('Z', '+00:00'))
                        return dt_obj.strftime("%m/%d/%Y %H:%M")
                    elif hasattr(dt, 'strftime'):
                        return dt.strftime("%m/%d/%Y %H:%M")
                    else:
                        return str(dt) if dt else "N/A"
                except Exception:
                    return str(dt) if dt else "N/A"

            # Truncate long service descriptions
            services = srf.get("services_requirements", "") or ""
            if len(services) > 40:
                services = services[:37] + "..."

            self.tickets_table.insert(
                "",
                "end",
                values=(
                    srf.get("ict_srf_no"),
                    srf.get("campus", ""),
                    services,
                    status.title(),
                    fmt_date(created_at),
                    fmt_date(updated_at)
                ),
                tags=(tag,)
            )
            row_count += 1
            
        # Update statistics
        self._update_client_ticket_statistics()
        self._update_client_last_refresh_time()

    def _create_client_ticket_stats(self, parent):
        """Create statistics cards for client tickets."""
        stats_container = tb.Frame(parent)
        stats_container.pack(fill="both", expand=True)
        
        # Total tickets
        total_frame = tb.Frame(stats_container)
        total_frame.pack(fill="x", pady=(0, 5))
        tb.Label(total_frame, text="Total:", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.client_total_tickets_label = tb.Label(total_frame, text="0", font=("Segoe UI", 12, "bold"), bootstyle="info")
        self.client_total_tickets_label.pack(side="right")
        
        # Open tickets
        open_frame = tb.Frame(stats_container)
        open_frame.pack(fill="x", pady=(0, 5))
        tb.Label(open_frame, text="Open:", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.client_open_tickets_label = tb.Label(open_frame, text="0", font=("Segoe UI", 12, "bold"), bootstyle="warning")
        self.client_open_tickets_label.pack(side="right")
        
        # Resolved tickets
        resolved_frame = tb.Frame(stats_container)
        resolved_frame.pack(fill="x")
        tb.Label(resolved_frame, text="Resolved:", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.client_resolved_tickets_label = tb.Label(resolved_frame, text="0", font=("Segoe UI", 12, "bold"), bootstyle="success")
        self.client_resolved_tickets_label.pack(side="right")

    def _update_client_ticket_statistics(self):
        """Update the statistics display for client tickets."""
        try:
            # Get current table items for statistics
            all_items = self.tickets_table.get_children()
            total_count = len(all_items)
            
            open_count = 0
            resolved_count = 0
            
            for item in all_items:
                status = self.tickets_table.item(item)['values'][3].lower()
                if status == 'open':
                    open_count += 1
                elif status == 'resolved':
                    resolved_count += 1
            
            # Update labels
            self.client_total_tickets_label.config(text=str(total_count))
            self.client_open_tickets_label.config(text=str(open_count))
            self.client_resolved_tickets_label.config(text=str(resolved_count))
            
        except Exception as e:
            print(f"Error updating client ticket statistics: {e}")

    def _apply_client_filters(self):
        """Apply filters to the client ticket table, only showing tickets assigned to the current user."""
        try:
            # Get filter values
            status_filter = self.client_status_filter.get()
            search_text = self.client_search_var.get().lower()

            # Get only tickets assigned to the current user
            user_id = self._get_current_user_id()
            if user_id:
                resp = requests.get(f"{self.api_base_url}/api/technician/{user_id}/tickets", timeout=8)
            else:
                resp = requests.get(f"{self.api_base_url}/api/srfs", timeout=8)
            resp.raise_for_status()
            srfs = resp.json() or []

            # Clear current display
            for item in self.tickets_table.get_children():
                self.tickets_table.delete(item)

            row_count = 0
            for srf in srfs:
                # Apply status filter
                status = srf.get("status", "open").lower()
                if status_filter != "All" and status != status_filter.lower():
                    continue

                # Apply search filter
                if search_text:
                    searchable_text = f"{srf.get('ict_srf_no', '')} {srf.get('campus', '')} {srf.get('services_requirements', '')}".lower()
                    if search_text not in searchable_text:
                        continue

                # Add filtered item
                tag = "even" if row_count % 2 == 0 else "odd"
                if status == "resolved":
                    tag = "resolved"
                elif srf.get("priority", "").lower() == "urgent":
                    tag = "urgent"

                # Format dates
                def fmt_date(dt):
                    try:
                        if isinstance(dt, str):
                            dt_obj = datetime.fromisoformat(dt.replace('Z', '+00:00'))
                            return dt_obj.strftime("%m/%d/%Y %H:%M")
                        elif hasattr(dt, 'strftime'):
                            return dt.strftime("%m/%d/%Y %H:%M")
                        else:
                            return str(dt) if dt else "N/A"
                    except Exception:
                        return str(dt) if dt else "N/A"

                services = srf.get("services_requirements", "") or ""
                if len(services) > 40:
                    services = services[:37] + "..."

                self.tickets_table.insert(
                    "",
                    "end",
                    values=(
                        srf.get("ict_srf_no"),
                        srf.get("campus", ""),
                        services,
                        status.title(),
                        fmt_date(srf.get("created_at")),
                        fmt_date(srf.get("updated_at"))
                    ),
                    tags=(tag,)
                )
                row_count += 1

            self._update_client_ticket_statistics()

        except Exception as e:
            print(f"Error applying client filters: {e}")

    def _clear_client_filters(self):
        """Clear all client filters and reload data."""
        self.client_status_filter.set("All")
        self.client_search_var.set("")
        self._load_tickets()

    def _sort_client_tickets_by_column(self, col):
        """Sort client tickets by the selected column."""
        try:
            # Get current data
            data = []
            for item in self.tickets_table.get_children():
                values = self.tickets_table.item(item)['values']
                data.append(values)
            
            # Sort data
            if hasattr(self, f'_client_sort_{col}_reverse'):
                reverse = getattr(self, f'_client_sort_{col}_reverse')
                setattr(self, f'_client_sort_{col}_reverse', not reverse)
            else:
                reverse = False
                setattr(self, f'_client_sort_{col}_reverse', True)
            
            col_index = list(self.tickets_table['columns']).index(col)
            
            # Custom sorting for different column types
            if col in ['created_at', 'updated_at']:
                data.sort(key=lambda x: x[col_index], reverse=reverse)
            elif col == 'ict_srf_no':
                data.sort(key=lambda x: int(x[col_index]) if str(x[col_index]).isdigit() else 0, reverse=reverse)
            else:
                data.sort(key=lambda x: str(x[col_index]).lower(), reverse=reverse)
            
            # Clear and repopulate table
            for item in self.tickets_table.get_children():
                self.tickets_table.delete(item)
            
            for i, values in enumerate(data):
                tag = "even" if i % 2 == 0 else "odd"
                if values[3].lower() == "resolved":
                    tag = "resolved"
                    
                self.tickets_table.insert("", "end", values=values, tags=(tag,))
                
        except Exception as e:
            print(f"Error sorting client tickets: {e}")

    def _update_client_last_refresh_time(self):
        """Update the last refresh time display for client portal."""
        current_time = datetime.now().strftime("%H:%M:%S")
        if hasattr(self, 'client_last_refresh_label'):
            self.client_last_refresh_label.config(text=f"Last updated: {current_time}")

    def _toggle_client_auto_refresh(self):
        """Toggle auto-refresh functionality for client portal."""
        if self.client_auto_refresh_var.get():
            self._start_client_ticket_auto_refresh()
        else:
            self._stop_client_ticket_auto_refresh()

    def _start_client_ticket_auto_refresh(self):
        """Start auto-refresh for client tickets."""
        if hasattr(self, '_client_ticket_refresh_job'):
            self.root.after_cancel(self._client_ticket_refresh_job)
        self._client_ticket_refresh_job = self.root.after(30000, self._auto_refresh_client_tickets)  # 30 seconds

    def _stop_client_ticket_auto_refresh(self):
        """Stop auto-refresh for client tickets."""
        if hasattr(self, '_client_ticket_refresh_job'):
            self.root.after_cancel(self._client_ticket_refresh_job)
            delattr(self, '_client_ticket_refresh_job')

    def _auto_refresh_client_tickets(self):
        """Internal method for auto-refreshing client tickets."""
        if hasattr(self, 'client_auto_refresh_var') and self.client_auto_refresh_var.get():
            self._apply_client_filters()  # Reapply current filters
            self._start_client_ticket_auto_refresh()  # Schedule next refresh

    def _on_ticket_row_click(self, event):
        selected_item = self.tickets_table.selection()
        if not selected_item:
            return
        ticket_id = self.tickets_table.item(selected_item[0])["values"][0]
        self._open_ticket_detail_modal(ticket_id)

    def _open_new_ticket_modal(self, parent_window):
        """Open modal for creating a new SRF."""
        modal = tb.Toplevel(parent_window)
        modal.title("ICT Service Request Form")
        modal.geometry("725x600")
        modal.resizable(False, False)
        modal.grab_set()

        button_host = self._build_ticket_form(modal)
        tb.Button(
            button_host,
            text="Submit Ticket",
            bootstyle="primary",
            command=lambda: self._submit_new_ticket(modal)
        ).pack(pady=20)

    def _build_ticket_form(self, modal, initial_data=None):
        """Build SRF form UI with technician dropdown."""
        if initial_data is None:
            initial_data = {}

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

        # Header
        header_frame = tb.Frame(scrollable_frame)
        header_frame.pack(fill="x", padx=20, pady=10)

        tb.Label(scrollable_frame, text="ICT SERVICE REQUEST FORM", font=("Segoe UI", 14, "bold")).pack(fill="x", pady=(10, 20), padx=20)

        form_frame = tb.Frame(scrollable_frame)
        form_frame.pack(fill="both", expand=True, padx=20)
        for col in range(4):
            form_frame.columnconfigure(col, weight=1)

        # Form variables
        self.form_vars = {
            "campus": tb.StringVar(value=initial_data.get("campus", "")),
            "office_building": tb.StringVar(value=initial_data.get("office_building", "")),
            "client_name": tb.StringVar(value=initial_data.get("client_name", "")),
            "date_time_call": tb.StringVar(value=initial_data.get("date_time_call", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))),
            "ict_srf_no": tb.StringVar(value=initial_data.get("ict_srf_no", "")),
            "required_response_time": tb.StringVar(value=initial_data.get("required_response_time", "")),
        }

        # Load technicians for dropdown
        self.technicians = []
        self.technician_var = tb.StringVar()
        try:
            resp = requests.get(f"{self.api_base_url}/api/technicians", timeout=5)
            if resp.ok:
                self.technicians = resp.json()
        except Exception as e:
            print(f"Failed to load technicians: {e}")

        self.service_req_text = tb.Text(form_frame, height=4, wrap="word")
        self.remarks_text = tb.Text(form_frame, height=4, wrap="word")

        # Form fields
        def add_row(label1, key1, label2=None, key2=None, row_idx=0):
            tb.Label(form_frame, text=label1, anchor="w").grid(row=row_idx, column=0, sticky="w", padx=5, pady=5)
            tb.Entry(form_frame, textvariable=self.form_vars[key1]).grid(row=row_idx, column=1, sticky="ew", padx=5, pady=5)
            if label2 and key2:
                tb.Label(form_frame, text=label2, anchor="w").grid(row=row_idx, column=2, sticky="w", padx=5, pady=5)
                if key2 == "technician_dropdown":
                    # Special handling for technician dropdown: use first and last name only
                    technician_names = [f"{tech.get('first_name', '').strip()} {tech.get('last_name', '').strip()}".strip() for tech in self.technicians]
                    technician_combo = tb.Combobox(form_frame, textvariable=self.technician_var, 
                                                 values=technician_names, state="readonly", width=25)
                    technician_combo.grid(row=row_idx, column=3, sticky="ew", padx=5, pady=5)
                else:
                    tb.Entry(form_frame, textvariable=self.form_vars[key2]).grid(row=row_idx, column=3, sticky="ew", padx=5, pady=5)

        add_row("Campus:", "campus", "ICT SRF NO.:", "ict_srf_no", row_idx=0)
        add_row("Office/Building:", "office_building", "Assign Technician:", "technician_dropdown", row_idx=1)
        add_row("Client's Name:", "client_name", row_idx=2)
        add_row("Date/Time of Call:", "date_time_call", "Required Response Time:", "required_response_time", row_idx=3)

        tb.Label(form_frame, text="Services Requirements:").grid(row=4, column=0, sticky="w", padx=5, pady=5)
        self.service_req_text.grid(row=5, column=0, columnspan=4, sticky="ew", padx=5, pady=(0, 10))

        tb.Label(form_frame, text="Remarks:").grid(row=6, column=0, sticky="w", padx=5, pady=5)
        self.remarks_text.grid(row=7, column=0, columnspan=4, sticky="ew", padx=5, pady=(0, 10))

        return scrollable_frame

    def _collect_ticket_form_data(self):
        """Collect form data including technician assignment."""
        data = {k: v.get() for k, v in getattr(self, 'form_vars', {}).items()}
        if hasattr(self, 'service_req_text'):
            data["services_requirements"] = self.service_req_text.get("1.0", "end").strip()
        if hasattr(self, 'remarks_text'):
            data["remarks"] = self.remarks_text.get("1.0", "end").strip()
        
        # Handle technician assignment
        if hasattr(self, 'technician_var') and self.technician_var.get():
            selected_tech = self.technician_var.get()
            # Find the selected technician ID by first and last name only
            for tech in getattr(self, 'technicians', []):
                tech_display = f"{tech.get('first_name', '').strip()} {tech.get('last_name', '').strip()}".strip()
                if tech_display == selected_tech:
                    data["technician_assigned_id"] = tech['id']
                    data["technician_assigned"] = tech_display
                    break
        
        return data

    def _submit_new_ticket(self, modal):
        """Submit the SRF via API server with improved user handling."""
        data = self._collect_ticket_form_data()
        
        # Basic validation
        if not data.get("ict_srf_no"):
            messagebox.showerror("Validation", "ICT SRF No. is required and must be numeric.")
            return
            
        if not data.get("client_name", "").strip():
            messagebox.showerror("Validation", "Client name is required.")
            return
            
        if not data.get("campus", "").strip():
            messagebox.showerror("Validation", "Campus is required.")
            return
            
        try:
            # Step 1: Get valid user ID for ticket submission
            created_by_id = self._get_or_create_client_user()
            
            if not created_by_id:
                messagebox.showerror("User Error", 
                                   "Unable to authenticate user for ticket submission.\n\n"
                                   "Please try again or contact system administrator.")
                return
            
            # Step 2: Prepare ticket data
            payload = {
                "created_by": created_by_id, 
                "data": data
            }
            
            # Step 3: Submit ticket
            resp = requests.post(f"{self.api_base_url}/api/srfs", json=payload, timeout=10)
            
            if resp.ok:
                # If technician was assigned, assign the ticket
                if data.get("technician_assigned_id"):
                    try:
                        assign_payload = {
                            "technician_id": data["technician_assigned_id"],
                            "assigned_by": created_by_id
                        }
                        assign_resp = requests.post(
                            f"{self.api_base_url}/api/tickets/{data['ict_srf_no']}/assign", 
                            json=assign_payload, 
                            timeout=5
                        )
                        if not assign_resp.ok:
                            print(f"Warning: Failed to assign technician: {assign_resp.text}")
                    except Exception as e:
                        print(f"Warning: Failed to assign technician: {e}")
                
                messagebox.showinfo("Success", "✅ Service Request submitted successfully!")
                modal.destroy()
                self._load_tickets()
            else:
                # Handle specific error cases
                error_details = ""
                try:
                    error_json = resp.json()
                    error_details = error_json.get('error', resp.text)
                except:
                    error_details = resp.text
                
                if "foreign key constraint" in error_details.lower():
                    messagebox.showerror("Database Error", 
                                       "❌ Unable to submit ticket: Database user reference error.\n\n"
                                       "The system cannot link this ticket to a valid user account.\n"
                                       "Please contact your system administrator.")
                elif "duplicate" in error_details.lower():
                    messagebox.showerror("Duplicate Ticket", 
                                       "❌ A ticket with this SRF number already exists.\n"
                                       "Please use a different SRF number.")
                else:
                    messagebox.showerror("Submission Error", 
                                       f"❌ Ticket submission failed:\n\n{error_details}")
                    
        except requests.exceptions.Timeout:
            messagebox.showerror("Timeout Error", 
                               "⏱️ The server took too long to respond.\n"
                               "Please try again in a moment.")
        except requests.exceptions.ConnectionError:
            messagebox.showerror("Connection Error", 
                               "🔌 Cannot connect to the server.\n"
                               "Please check your network connection and try again.")
        except Exception as e:
            messagebox.showerror("Unexpected Error", 
                               f"❌ An unexpected error occurred:\n\n{str(e)}")

    def _get_current_user_id(self):
        """Get current user ID for filtering assigned tickets."""
        try:
            # Try to get technician user (for assigned tickets view)
            users_resp = requests.get(f"{self.api_base_url}/api/users", timeout=5)
            if users_resp.ok:
                users = users_resp.json()
                
                # Look for technician user first
                for user in users:
                    username = user.get('username', '').lower()
                    role = user.get('role', '').lower()
                    if 'technician' in username or 'tech' in username or role == 'technician':
                        return user['id']
                
                # If no technician found, return None to show all tickets
                return None
            
            return None
            
        except Exception as e:
            print(f"Error getting current user: {e}")
            return None

    def _get_current_user_id(self):
        """Get current user ID for filtering assigned tickets."""
        try:
            # Try to get technician user (for assigned tickets view)
            users_resp = requests.get(f"{self.api_base_url}/api/users", timeout=5)
            if users_resp.ok:
                users = users_resp.json()
                
                # Look for technician user first
                for user in users:
                    username = user.get('username', '').lower()
                    role = user.get('role', '').lower()
                    if 'technician' in username or 'tech' in username or role == 'technician':
                        return user['id']
                
                # If no technician found, return None to show all tickets
                return None
            
            return None
            
        except Exception as e:
            print(f"Error getting current user: {e}")
            return None

    def _get_or_create_client_user(self):
        """Get or create a valid client user ID for ticket submission."""
        try:
            # Method 1: Try to get existing users
            users_resp = requests.get(f"{self.api_base_url}/api/users", timeout=5)
            if users_resp.ok:
                users = users_resp.json()
                
                # Look for client user first
                for user in users:
                    username = user.get('username', '').lower()
                    role = user.get('role', '').lower()
                    if username == 'client' or role == 'client':
                        return user['id']
                
                # Look for any active user
                if users:
                    return users[0]['id']
            
            # Method 2: Try to create a client session (fallback)
            session_resp = requests.post(f"{self.api_base_url}/api/create-client-session", 
                                       json={"client_name": "Client Portal User"}, 
                                       timeout=5)
            if session_resp.ok:
                session_data = session_resp.json()
                return session_data.get('user_id')
            
            # Method 3: Use a known default (last resort)
            # This assumes user ID 2 exists (created by our setup script)
            return 2
            
        except Exception as e:
            print(f"Error getting client user: {e}")
            return None

    def _open_ticket_detail_modal(self, srf_no):
        """Open an enhanced modal showing SRF details with modern styling."""
        try:
            resp = requests.get(f"{self.api_base_url}/api/srfs", timeout=8)
            resp.raise_for_status()
            srfs = resp.json() or []
            srf = next((s for s in srfs if s.get("ict_srf_no") == srf_no), None)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load SRF details from API: {e}")
            return
        
        if not srf:
            messagebox.showerror("Not found", f"No SRF found with id {srf_no}")
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
            # Try to load logo
            logo_placeholder = tb.Label(logo_title_frame, text="🏛️", font=("Segoe UI", 40))
            logo_placeholder.pack(side="left", padx=(0, 15))
        except:
            logo_placeholder = tb.Label(logo_title_frame, text="🏛️", font=("Segoe UI", 40))
            logo_placeholder.pack(side="left", padx=(0, 15))

        # Title and SRF info
        title_info_frame = tb.Frame(logo_title_frame)
        title_info_frame.pack(side="left", fill="x", expand=True)

        tb.Label(title_info_frame, text="ICT Service Request Details", 
                font=("Segoe UI", 18, "bold"), bootstyle="inverse-primary").pack(anchor="w")
        
        # SRF number with status badge
        srf_status_frame = tb.Frame(title_info_frame)
        srf_status_frame.pack(anchor="w", pady=(5, 0))
        
        tb.Label(srf_status_frame, text=f"SRF #{srf.get('ict_srf_no')}", 
                font=("Segoe UI", 14, "bold")).pack(side="left")
        
        # Status badge
        status = srf.get('status', 'open').lower()
        status_style = "success" if status == "resolved" else "warning" if status == "in progress" else "info"
        tb.Label(srf_status_frame, text=status.title(), 
                font=("Segoe UI", 10, "bold"), bootstyle=f"inverse-{status_style}").pack(side="left", padx=(10, 0))

        # Quick info bar
        info_bar = tb.Frame(header_content)
        info_bar.pack(fill="x", pady=(10, 0))
        
        def fmt_date(dt):
            try:
                if isinstance(dt, str):
                    dt_obj = datetime.fromisoformat(dt.replace('Z', '+00:00'))
                    return dt_obj.strftime('%m/%d/%Y %H:%M')
                elif hasattr(dt, 'strftime'):
                    return dt.strftime('%m/%d/%Y %H:%M')
                else:
                    return str(dt) if dt else "N/A"
            except Exception:
                return str(dt) if dt else "N/A"
        
        created_date = fmt_date(srf.get('created_at'))
        quick_info = f"📅 Submitted: {created_date} | 🏢 Campus: {srf.get('campus', 'N/A')}"
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

        # Request Information Section
        self._create_client_detail_section(details_scrollable, "🏢 Request Information", [
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

        # Technician Information Section (if available)
        if srf.get('technician_assigned'):
            self._create_client_detail_section(details_scrollable, "👨‍💻 Technician Information", [
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
        
        self._create_client_status_card(status_grid, "Status", current_status, 0, 0, status_style)
        self._create_client_status_card(status_grid, "Priority", priority, 0, 1, "warning" if priority == "High" else "info")

        # Timeline section
        timeline_frame = tb.LabelFrame(status_tab, text="⏰ Timeline", 
                                     bootstyle="secondary", padding=15)
        timeline_frame.pack(fill="both", expand=True, padx=10, pady=10)

        timeline_items = [
            ("📝 Submitted", fmt_date(srf.get('created_at')), "Request submitted"),
            ("🔄 Last Updated", fmt_date(srf.get('updated_at')) if srf.get('updated_at') else "N/A", "Last modification")
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

        # Center the buttons
        button_container = tb.Frame(action_frame)
        button_container.pack(expand=True)

        tb.Button(button_container, text="🖨️ Print", bootstyle="info",
                 command=lambda: print_srf_form(srf, logo_path="assets/images/bsu_logo.png"), 
                 width=12).pack(side="left", padx=(0, 10))

        # Add accomplishment button (only if ticket is not completed)
        if srf.get('status', '').lower() not in ['completed', 'resolved']:
            tb.Button(button_container, text="✅ Add Accomplishment", bootstyle="success",
                     command=lambda: self._open_accomplishment_modal(srf, modal), 
                     width=18).pack(side="left", padx=(0, 10))

        tb.Button(button_container, text="❌ Close", bootstyle="secondary",
                 command=modal.destroy, width=10).pack(side="left")

    def _create_client_detail_section(self, parent, title, fields):
        """Create a detail section with fields for client portal."""
        section = tb.LabelFrame(parent, text=title, bootstyle="primary", padding=15)
        section.pack(fill="x", padx=10, pady=10)

        for i, (label, value) in enumerate(fields):
            field_frame = tb.Frame(section)
            field_frame.pack(fill="x", pady=2)
            field_frame.columnconfigure(1, weight=1)

            tb.Label(field_frame, text=f"{label}:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", padx=(0, 10))
            tb.Label(field_frame, text=str(value), font=("Segoe UI", 10)).grid(row=0, column=1, sticky="w")

    def _create_client_status_card(self, parent, title, value, row, col, style="info"):
        """Create a status card widget for client portal."""
        card = tb.LabelFrame(parent, text=title, bootstyle=style, padding=10)
        card.grid(row=row, column=col, padx=5, pady=5, sticky="ew")
        parent.columnconfigure(col, weight=1)

        tb.Label(card, text=str(value), font=("Segoe UI", 14, "bold"), 
                bootstyle=f"inverse-{style}").pack()

    def _open_accomplishment_modal(self, srf, parent_modal):
        """Open modal for adding accomplishment to a ticket."""
        modal = tb.Toplevel(parent_modal)
        modal.title(f"Add Accomplishment - SRF #{srf.get('ict_srf_no')}")
        modal.geometry("600x500")
        modal.resizable(False, False)
        modal.transient(parent_modal)
        modal.grab_set()

        # Center the modal
        modal.update_idletasks()
        x = parent_modal.winfo_x() + (parent_modal.winfo_width() // 2) - (600 // 2)
        y = parent_modal.winfo_y() + (parent_modal.winfo_height() // 2) - (500 // 2)
        modal.geometry(f"+{x}+{y}")

        # Main container
        main_container = tb.Frame(modal)
        main_container.pack(fill="both", expand=True, padx=20, pady=20)

        # Header
        header_frame = tb.LabelFrame(main_container, text="", bootstyle="success", padding=15)
        header_frame.pack(fill="x", pady=(0, 15))

        tb.Label(header_frame, text="✅ Add Service Accomplishment", 
                font=("Segoe UI", 16, "bold"), bootstyle="inverse-success").pack()
        tb.Label(header_frame, text=f"SRF #{srf.get('ict_srf_no')} - {srf.get('client_name', 'N/A')}", 
                font=("Segoe UI", 11), bootstyle="inverse-secondary").pack(pady=(5, 0))

        # Ticket info summary
        info_frame = tb.LabelFrame(main_container, text="📋 Ticket Summary", bootstyle="info", padding=10)
        info_frame.pack(fill="x", pady=(0, 15))

        info_text = f"Campus: {srf.get('campus', 'N/A')} | Service: {srf.get('services_requirements', 'N/A')[:50]}..."
        tb.Label(info_frame, text=info_text, font=("Segoe UI", 9)).pack()

        # Accomplishment details (only response time and service time)
        acc_frame = tb.LabelFrame(main_container, text="📝 Accomplishment Details", bootstyle="warning", padding=10)
        acc_frame.pack(fill="both", expand=True, pady=(0, 15))

        details_frame = tb.Frame(acc_frame)
        details_frame.pack(fill="x", pady=10)

        tb.Label(details_frame, text="Response Time (minutes):", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.response_time_var = tb.StringVar()
        response_time_entry = tb.Entry(details_frame, textvariable=self.response_time_var, width=10)
        response_time_entry.pack(side="left", padx=(5, 20))

        tb.Label(details_frame, text="Service Time (minutes):", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.service_time_var = tb.StringVar()
        service_time_entry = tb.Entry(details_frame, textvariable=self.service_time_var, width=10)
        service_time_entry.pack(side="left", padx=(5, 0))

        # Action buttons
        button_frame = tb.Frame(main_container)
        button_frame.pack(fill="x")

        button_container = tb.Frame(button_frame)
        button_container.pack(expand=True)

        def save_accomplishment():
            response_time = self.response_time_var.get().strip()
            service_time = self.service_time_var.get().strip()
            if not response_time or not service_time:
                messagebox.showerror("Validation", "Both response time and service time are required.")
                return
            try:
                payload = {
                    "response_time": response_time,
                    "service_time": service_time
                }
                resp = requests.post(f"{self.api_base_url}/api/tickets/{srf['ict_srf_no']}/accomplish", json=payload, timeout=8)
                if resp.ok:
                    messagebox.showinfo("Success", "Accomplishment saved successfully!")
                    modal.destroy()
                    parent_modal.destroy()
                    self._load_tickets()
                else:
                    try:
                        error_msg = resp.json().get("error", resp.text)
                    except Exception:
                        error_msg = resp.text
                    messagebox.showerror("Error", f"Failed to save accomplishment: {error_msg}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save accomplishment: {e}")

        tb.Button(button_container, text="Save", bootstyle="success", command=save_accomplishment, width=20).pack(side="left", padx=(0, 10))
        tb.Button(button_container, text="Cancel", bootstyle="secondary", command=modal.destroy, width=10).pack(side="left")

    def _clear_placeholder(self):
        """Clear placeholder text when user focuses on the text area."""
        if hasattr(self, 'accomplishment_text'):
            current_text = self.accomplishment_text.get("1.0", "end-1c")
            if "Example:" in current_text:
                self.accomplishment_text.delete("1.0", "end")

    def _submit_accomplishment(self, srf, modal, parent_modal):
        """Submit the accomplishment details."""
        try:
            # Validation
            accomplishment = self.accomplishment_text.get("1.0", "end-1c").strip()
            if not accomplishment or "Example:" in accomplishment:
                messagebox.showerror("Validation Error", "Please provide accomplishment details.")
                return

            technician_selection = self.accomplishment_tech_var.get()
            if not technician_selection:
                messagebox.showerror("Validation Error", "Please select a technician.")
                return

            # Find selected technician
            selected_technician = None
            for tech in self.accomplishment_technicians:
                tech_display = f"{tech['name']} - {tech['specialization']}"
                if tech_display == technician_selection:
                    selected_technician = tech
                    break

            if not selected_technician:
                messagebox.showerror("Error", "Selected technician not found.")
                return

            # Prepare accomplishment data
            payload = {
                "accomplishment": accomplishment,
                "accomplished_by": selected_technician['user_id'],
                "service_time": self.service_time_var.get(),
                "response_time": self.response_time_var.get()
            }

            # Submit accomplishment
            resp = requests.post(
                f"{self.api_base_url}/api/tickets/{srf['ict_srf_no']}/accomplish", 
                json=payload, 
                timeout=10
            )

            if resp.ok:
                messagebox.showinfo("Success", "✅ Accomplishment submitted successfully!\n\nThe ticket has been marked as completed.")
                modal.destroy()
                parent_modal.destroy()  # Close the detail modal too
                self._load_tickets()  # Refresh the ticket list
            else:
                error_details = ""
                try:
                    error_json = resp.json()
                    error_details = error_json.get('error', resp.text)
                except:
                    error_details = resp.text
                messagebox.showerror("Submission Error", f"❌ Failed to submit accomplishment:\n\n{error_details}")

        except requests.exceptions.Timeout:
            messagebox.showerror("Timeout Error", "⏱️ The server took too long to respond.")
        except requests.exceptions.ConnectionError:
            messagebox.showerror("Connection Error", "🔌 Cannot connect to the server.")
        except Exception as e:
            messagebox.showerror("Unexpected Error", f"❌ An unexpected error occurred:\n\n{str(e)}")
