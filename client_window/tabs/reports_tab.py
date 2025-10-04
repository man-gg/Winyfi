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
    def __init__(self, parent_frame, root):
        self.parent_frame = parent_frame
        self.root = root
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
        
        tb.Button(button_frame, text="📊 Generate Report", 
                 bootstyle="primary", command=self.generate_report).pack(side='left', padx=(0, 10))
        tb.Button(button_frame, text="📁 Export CSV", 
                 bootstyle="success", command=self.export_csv).pack(side='left', padx=(0, 10))
        tb.Button(button_frame, text="🖨️ Print PDF", 
                 bootstyle="warning", command=self.print_pdf).pack(side='left', padx=(0, 10))
        tb.Button(button_frame, text="📈 PDF with Charts", 
                 bootstyle="danger", command=self.print_pdf_with_charts).pack(side='left', padx=(0, 10))
        tb.Button(button_frame, text="🔄 Refresh", 
                 bootstyle="info", command=self.refresh_report).pack(side='left')
        
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
        
        # Treeview for data
        columns = ("Router Name", "Start Date", "Uptime %", "Downtime", "Bandwidth Usage")
        self.report_tree = tb.Treeview(table_container, columns=columns, show="headings", height=15)
        
        # Configure columns
        for col in columns:
            self.report_tree.heading(col, text=col)
            self.report_tree.column(col, width=120, anchor='center')
        
        # Scrollbars
        v_scrollbar = tb.Scrollbar(table_container, orient="vertical", command=self.report_tree.yview)
        h_scrollbar = tb.Scrollbar(table_container, orient="horizontal", command=self.report_tree.xview)
        self.report_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack widgets
        self.report_tree.pack(side="left", fill="both", expand=True)
        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")
        
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
        self.fig, self.ax = plt.subplots(figsize=(8, 4), dpi=100)
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
        """Generate report data from API"""
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
            
            # Make API request
            params = {
                "start_date": start_date,
                "end_date": end_date,
                "mode": mode
            }
            
            response = requests.get(f"{self.api_base_url}/api/reports/uptime", params=params, timeout=10)
            
            if response.ok:
                data = response.json()
                self.report_data = data.get("report_data", [])
                chart_data = data.get("chart_data", {})
                summary = data.get("summary", {})
                
                # Update summary cards
                self.total_routers_label.config(text=str(summary.get("total_routers", 0)))
                self.avg_uptime_label.config(text=f"{summary.get('avg_uptime', 0):.1f}%")
                self.total_bandwidth_label.config(text=f"{summary.get('total_bandwidth', 0):.1f} MB")
                
                # Update table
                self.update_table()
                
                # Update chart
                self.update_chart(chart_data)
                
            else:
                error_msg = response.json().get("error", "Unknown error")
                messagebox.showerror("API Error", f"Failed to generate report: {error_msg}")
                
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Connection Error", f"Failed to connect to server: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")

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
        """Update the uptime trend chart"""
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
            
            # Rotate x-axis labels for better readability
            plt.setp(self.ax.get_xticklabels(), rotation=45, ha='right')
        else:
            self.ax.set_title("No Data Available")
            self.ax.text(0.5, 0.5, "No data to display", ha='center', va='center', transform=self.ax.transAxes)
        
        self.canvas.draw()

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
                
                messagebox.showinfo("Export Successful", f"Report exported to {filename}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export CSV: {str(e)}")

    def refresh_report(self):
        """Refresh the current report"""
        self.generate_report()

    def print_pdf(self):
        """Generate and download PDF report"""
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
            messagebox.showinfo("Generating PDF", "Generating PDF report... Please wait.")
            
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
            messagebox.showinfo("Generating PDF", "Generating PDF report with charts... Please wait.")
            
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
        """Open a window for ICT Service Request viewing and creation (client scope)."""
        window = tb.Toplevel(self.root)
        window.title("ICT Service Requests")
        window.geometry("900x500")
        window.resizable(True, True)
        self._center_window(window, 900, 500)

        # Header
        header_frame = tb.Frame(window)
        header_frame.pack(fill="x", padx=20, pady=10)
        tb.Label(header_frame, text="📋 ICT Service Requests", font=("Segoe UI", 16, "bold")).pack(side="left")

        tb.Button(
            header_frame,
            text="➕ New Service Request Form",
            bootstyle="primary",
            command=lambda: self._open_new_ticket_modal(window)
        ).pack(side="right")

        # Table
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

        scrollbar = tb.Scrollbar(table_frame, orient="vertical", command=self.tickets_table.yview)
        scrollbar.pack(side="right", fill="y")
        self.tickets_table.configure(yscrollcommand=scrollbar.set)

        # Load + bind
        self._load_tickets()
        self.tickets_table.bind("<Double-1>", self._on_ticket_row_click)

    def _center_window(self, window, width, height):
        """Center a window on the screen."""
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        window.geometry(f"{width}x{height}+{x}+{y}")

    def _load_tickets(self):
        """Fetch SRFs from API and display in the table."""
        if not hasattr(self, 'tickets_table'):
            return
        self.tickets_table.delete(*self.tickets_table.get_children())
        try:
            resp = requests.get(f"{self.api_base_url}/api/srfs", timeout=8)
            resp.raise_for_status()
            srfs = resp.json() or []
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load tickets from API: {e}")
            return

        for srf in srfs:
            created_at = srf.get("created_at")
            updated_at = srf.get("updated_at")
            def fmt(dt):
                try:
                    return dt.strftime("%Y-%m-%d %H:%M:%S") if hasattr(dt, 'strftime') else str(dt)
                except Exception:
                    return str(dt)

            self.tickets_table.insert(
                "",
                "end",
                values=(
                    srf.get("ict_srf_no"),
                    srf.get("campus", ""),
                    (srf.get("services_requirements", "") or "")[:40] + ("…" if srf.get("services_requirements") and len(srf.get("services_requirements")) > 40 else ""),
                    srf.get("status", "open"),
                    srf.get("created_by_username", "Unknown"),
                    fmt(created_at),
                    fmt(updated_at)
                )
            )

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
        """Build SRF form UI."""
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
            "technician_assigned": tb.StringVar(value=initial_data.get("technician_assigned", "")),
            "required_response_time": tb.StringVar(value=initial_data.get("required_response_time", "")),
        }

        self.service_req_text = tb.Text(form_frame, height=4, wrap="word")
        self.remarks_text = tb.Text(form_frame, height=4, wrap="word")

        # Form fields
        def add_row(label1, key1, label2=None, key2=None, row_idx=0):
            tb.Label(form_frame, text=label1, anchor="w").grid(row=row_idx, column=0, sticky="w", padx=5, pady=5)
            tb.Entry(form_frame, textvariable=self.form_vars[key1]).grid(row=row_idx, column=1, sticky="ew", padx=5, pady=5)
            if label2 and key2:
                tb.Label(form_frame, text=label2, anchor="w").grid(row=row_idx, column=2, sticky="w", padx=5, pady=5)
                tb.Entry(form_frame, textvariable=self.form_vars[key2]).grid(row=row_idx, column=3, sticky="ew", padx=5, pady=5)

        add_row("Campus:", "campus", "ICT SRF NO.:", "ict_srf_no", row_idx=0)
        add_row("Office/Building:", "office_building", "Technician Assigned:", "technician_assigned", row_idx=1)
        add_row("Client's Name:", "client_name", row_idx=2)
        add_row("Date/Time of Call:", "date_time_call", "Required Response Time:", "required_response_time", row_idx=3)

        tb.Label(form_frame, text="Services Requirements:").grid(row=4, column=0, sticky="w", padx=5, pady=5)
        self.service_req_text.grid(row=5, column=0, columnspan=4, sticky="ew", padx=5, pady=(0, 10))

        tb.Label(form_frame, text="Remarks:").grid(row=6, column=0, sticky="w", padx=5, pady=5)
        self.remarks_text.grid(row=7, column=0, columnspan=4, sticky="ew", padx=5, pady=(0, 10))

        return scrollable_frame

    def _collect_ticket_form_data(self):
        """Collect form data."""
        data = {k: v.get() for k, v in getattr(self, 'form_vars', {}).items()}
        if hasattr(self, 'service_req_text'):
            data["services_requirements"] = self.service_req_text.get("1.0", "end").strip()
        if hasattr(self, 'remarks_text'):
            data["remarks"] = self.remarks_text.get("1.0", "end").strip()
        return data

    def _submit_new_ticket(self, modal):
        """Submit the SRF via API server."""
        data = self._collect_ticket_form_data()
        if not data.get("ict_srf_no"):
            messagebox.showerror("Validation", "ICT SRF No. is required and must be numeric.")
            return
        try:
            payload = {"created_by": 1, "data": data}  # Default created_by for client
            resp = requests.post(f"{self.api_base_url}/api/srfs", json=payload, timeout=8)
            if resp.ok:
                messagebox.showinfo("Success", "Service Request submitted successfully!")
                modal.destroy()
                self._load_tickets()
            else:
                messagebox.showerror("Error", f"Ticket submission failed: {resp.text}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to submit ticket: {e}")

    def _open_ticket_detail_modal(self, srf_no):
        """Open a modal showing SRF details."""
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
        modal.title(f"SRF #{srf_no} Details")
        modal.geometry("700x600")
        modal.grab_set()

        # Header
        header_frame = tb.Frame(modal)
        header_frame.pack(fill="x", pady=10)
        tb.Label(header_frame, text="ICT SERVICE REQUEST FORM", font=("Segoe UI", 16, "bold")).pack(side="left", padx=20)

        # SRF number
        tb.Label(modal, text=f"SRF No: {srf.get('ict_srf_no')}", font=("Segoe UI", 12, "bold")).pack(pady=5)

        # Details
        form_frame = tb.Frame(modal, padding=10)
        form_frame.pack(fill="both", expand=True)

        details = [
            ("Campus", srf.get('campus', '')),
            ("Office/Building", srf.get('office_building', '')),
            ("Client", srf.get('client_name', '')),
            ("Services", srf.get('services_requirements', '')),
            ("Status", srf.get('status', 'open')),
            ("Created by", srf.get('created_by_username', 'Unknown')),
        ]

        for i, (label, value) in enumerate(details):
            tb.Label(form_frame, text=f"{label}: {value}").grid(row=i, column=0, sticky="w", padx=10, pady=2)

        # Print button
        tb.Button(
            modal,
            text="🖨 Print",
            bootstyle="secondary",
            command=lambda: print_srf_form(srf, logo_path="assets/images/bsu_logo.png")
        ).pack(pady=10)
