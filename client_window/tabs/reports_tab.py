import ttkbootstrap as tb
import tkinter as tk
from tkinter import messagebox, filedialog
import requests
from datetime import datetime, timedelta
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import csv
import os
from ttkbootstrap.widgets import DateEntry


class ReportsTab:
    def __init__(self, parent_frame, api_base_url, root_window):
        self.parent_frame = parent_frame
        self.api_base_url = api_base_url
        self.root = root_window
        self.report_data = []
        self._build_reports_page()

    def _build_reports_page(self):
        # Header
        header = tb.Frame(self.parent_frame)
        header.pack(fill='x', padx=10, pady=(10, 0))
        tb.Label(header, text="📊 Network Reports", font=("Segoe UI", 16, "bold")).pack(side='left')
        
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
