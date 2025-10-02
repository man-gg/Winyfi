#!/usr/bin/env python3
"""
Admin Loop Detection Dashboard
Provides comprehensive monitoring and control for loop detection system.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import requests
import json
import threading
import time
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd

class AdminLoopDashboard:
    def __init__(self, root, api_base_url="http://localhost:5000"):
        self.root = root
        self.api_base_url = api_base_url
        self.auto_refresh_running = False
        self.refresh_interval = 5000  # 5 seconds
        
        # Configure root window
        self.root.title("Admin Loop Detection Dashboard")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 600)
        
        # Set theme
        self.style = tb.Style(theme="superhero")
        
        self._build_ui()
        self._start_auto_refresh()
        
    def _build_ui(self):
        """Build the admin dashboard UI."""
        # Main container
        main_frame = tb.Frame(self.root)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Header
        self._build_header(main_frame)
        
        # Content area with notebook
        self.notebook = tb.Notebook(main_frame)
        self.notebook.pack(fill='both', expand=True, pady=(10, 0))
        
        # Dashboard tab
        self._build_dashboard_tab()
        
        # History tab
        self._build_history_tab()
        
        # Configuration tab
        self._build_config_tab()
        
        # Statistics tab
        self._build_stats_tab()
        
    def _build_header(self, parent):
        """Build the header with status and controls."""
        header_frame = tb.Frame(parent)
        header_frame.pack(fill='x', pady=(0, 10))
        
        # Title
        title_frame = tb.Frame(header_frame)
        title_frame.pack(side='left')
        
        tb.Label(title_frame, text="🔄 Loop Detection Admin Dashboard", 
                font=("Segoe UI", 16, "bold")).pack(side='left')
        
        # Status indicators
        status_frame = tb.Frame(header_frame)
        status_frame.pack(side='right')
        
        self.status_label = tb.Label(status_frame, text="●", font=("Segoe UI", 12))
        self.status_label.pack(side='left', padx=(0, 10))
        
        self.status_text = tb.Label(status_frame, text="Checking...", font=("Segoe UI", 11))
        self.status_text.pack(side='left', padx=(0, 20))
        
        # Control buttons
        self.start_btn = tb.Button(status_frame, text="▶ Start", bootstyle="success",
                                  command=self.start_detection, width=8)
        self.start_btn.pack(side='left', padx=(0, 5))
        
        self.stop_btn = tb.Button(status_frame, text="⏹ Stop", bootstyle="danger",
                                 command=self.stop_detection, width=8)
        self.stop_btn.pack(side='left', padx=(0, 5))
        
        self.refresh_btn = tb.Button(status_frame, text="🔄 Refresh", bootstyle="info",
                                    command=self.refresh_data, width=8)
        self.refresh_btn.pack(side='left')
        
    def _build_dashboard_tab(self):
        """Build the main dashboard tab."""
        dashboard_frame = tb.Frame(self.notebook)
        self.notebook.add(dashboard_frame, text="📊 Dashboard")
        
        # Stats cards
        self._build_stats_cards(dashboard_frame)
        
        # Current status
        self._build_current_status(dashboard_frame)
        
        # Recent detections
        self._build_recent_detections(dashboard_frame)
        
    def _build_stats_cards(self, parent):
        """Build statistics cards."""
        cards_frame = tb.Frame(parent)
        cards_frame.pack(fill='x', pady=(10, 20))
        
        # Total detections card
        self.total_card = tb.LabelFrame(cards_frame, text="📈 Total Detections", 
                                       bootstyle="info", padding=15)
        self.total_card.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        self.total_label = tb.Label(self.total_card, text="0", font=("Segoe UI", 24, "bold"))
        self.total_label.pack()
        
        # Recent detections card
        self.recent_card = tb.LabelFrame(cards_frame, text="🕐 Recent (24h)", 
                                        bootstyle="warning", padding=15)
        self.recent_card.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        self.recent_label = tb.Label(self.recent_card, text="0", font=("Segoe UI", 24, "bold"))
        self.recent_label.pack()
        
        # Loop detections card
        self.loops_card = tb.LabelFrame(cards_frame, text="⚠️ Loops Detected", 
                                      bootstyle="danger", padding=15)
        self.loops_card.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        self.loops_label = tb.Label(self.loops_card, text="0", font=("Segoe UI", 24, "bold"))
        self.loops_label.pack()
        
        # Suspicious activity card
        self.suspicious_card = tb.LabelFrame(cards_frame, text="🔍 Suspicious", 
                                           bootstyle="secondary", padding=15)
        self.suspicious_card.pack(side='left', fill='x', expand=True)
        
        self.suspicious_label = tb.Label(self.suspicious_card, text="0", font=("Segoe UI", 24, "bold"))
        self.suspicious_label.pack()
        
    def _build_current_status(self, parent):
        """Build current detection status."""
        status_frame = tb.LabelFrame(parent, text="🔍 Current Detection Status", 
                                   bootstyle="primary", padding=15)
        status_frame.pack(fill='x', pady=(0, 20))
        
        # Status info
        info_frame = tb.Frame(status_frame)
        info_frame.pack(fill='x')
        
        self.status_info = tb.Text(info_frame, height=6, width=80, state="disabled")
        self.status_info.pack(fill='both', expand=True)
        
    def _build_recent_detections(self, parent):
        """Build recent detections table."""
        recent_frame = tb.LabelFrame(parent, text="📋 Recent Detections", 
                                   bootstyle="success", padding=15)
        recent_frame.pack(fill='both', expand=True)
        
        # Create treeview
        columns = ("Time", "Status", "Packets", "Offenders", "Severity", "Interface")
        self.recent_tree = ttk.Treeview(recent_frame, columns=columns, show="headings", height=8)
        
        # Configure columns
        for col in columns:
            self.recent_tree.heading(col, text=col)
            self.recent_tree.column(col, width=120, anchor="center")
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(recent_frame, orient="vertical", command=self.recent_tree.yview)
        self.recent_tree.configure(yscrollcommand=scrollbar.set)
        
        self.recent_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
    def _build_history_tab(self):
        """Build the history tab."""
        history_frame = tb.Frame(self.notebook)
        self.notebook.add(history_frame, text="📜 History")
        
        # Controls
        controls_frame = tb.Frame(history_frame)
        controls_frame.pack(fill='x', pady=(10, 0))
        
        tb.Label(controls_frame, text="Show last:", font=("Segoe UI", 11)).pack(side='left')
        
        self.limit_var = tk.StringVar(value="100")
        limit_combo = tb.Combobox(controls_frame, textvariable=self.limit_var, 
                                 values=["50", "100", "200", "500"], width=10, state="readonly")
        limit_combo.pack(side='left', padx=(5, 10))
        
        tb.Button(controls_frame, text="🔄 Refresh", bootstyle="info",
                 command=self.refresh_history).pack(side='left', padx=(0, 10))
        
        tb.Button(controls_frame, text="📊 Export CSV", bootstyle="success",
                 command=self.export_history).pack(side='left')
        
        # History table
        table_frame = tb.Frame(history_frame)
        table_frame.pack(fill='both', expand=True, pady=(10, 0))
        
        columns = ("Time", "Status", "Packets", "Offenders", "Severity", "Interface", "Duration")
        self.history_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=20)
        
        # Configure columns
        for col in columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=120, anchor="center")
        
        # Scrollbar
        history_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=history_scrollbar.set)
        
        self.history_tree.pack(side="left", fill="both", expand=True)
        history_scrollbar.pack(side="right", fill="y")
        
    def _build_config_tab(self):
        """Build the configuration tab."""
        config_frame = tb.Frame(self.notebook)
        self.notebook.add(config_frame, text="⚙️ Configuration")
        
        # Configuration form
        form_frame = tb.LabelFrame(config_frame, text="Loop Detection Settings", 
                                 bootstyle="primary", padding=20)
        form_frame.pack(fill='x', pady=(20, 10))
        
        # Enable/disable
        self.enabled_var = tk.BooleanVar(value=True)
        enabled_check = tb.Checkbutton(form_frame, text="Enable Automatic Loop Detection", 
                                      variable=self.enabled_var, bootstyle="success")
        enabled_check.pack(anchor='w', pady=(0, 15))
        
        # Interval setting
        interval_frame = tb.Frame(form_frame)
        interval_frame.pack(fill='x', pady=(0, 15))
        
        tb.Label(interval_frame, text="Detection Interval (minutes):", 
                font=("Segoe UI", 11)).pack(anchor='w')
        
        self.interval_var = tk.StringVar(value="5")
        interval_entry = tb.Entry(interval_frame, textvariable=self.interval_var, width=10)
        interval_entry.pack(anchor='w', pady=(5, 0))
        
        # Threshold setting
        threshold_frame = tb.Frame(form_frame)
        threshold_frame.pack(fill='x', pady=(0, 20))
        
        tb.Label(threshold_frame, text="Detection Threshold:", 
                font=("Segoe UI", 11)).pack(anchor='w')
        
        self.threshold_var = tk.StringVar(value="30")
        threshold_entry = tb.Entry(threshold_frame, textvariable=self.threshold_var, width=10)
        threshold_entry.pack(anchor='w', pady=(5, 0))
        
        # Save button
        tb.Button(form_frame, text="💾 Save Configuration", bootstyle="success",
                 command=self.save_configuration).pack(anchor='w')
        
        # Current configuration display
        self._build_config_display(config_frame)
        
    def _build_config_display(self, parent):
        """Build current configuration display."""
        display_frame = tb.LabelFrame(parent, text="Current Configuration", 
                                    bootstyle="info", padding=15)
        display_frame.pack(fill='x', pady=(10, 0))
        
        self.config_text = tb.Text(display_frame, height=8, state="disabled")
        self.config_text.pack(fill='both', expand=True)
        
    def _build_stats_tab(self):
        """Build the statistics tab with charts."""
        stats_frame = tb.Frame(self.notebook)
        self.notebook.add(stats_frame, text="📊 Statistics")
        
        # Chart controls
        controls_frame = tb.Frame(stats_frame)
        controls_frame.pack(fill='x', pady=(10, 0))
        
        tb.Label(controls_frame, text="Time Range:", font=("Segoe UI", 11)).pack(side='left')
        
        self.time_range_var = tk.StringVar(value="7")
        time_combo = tb.Combobox(controls_frame, textvariable=self.time_range_var,
                                values=["1", "3", "7", "30"], width=10, state="readonly")
        time_combo.pack(side='left', padx=(5, 10))
        
        tb.Button(controls_frame, text="📊 Update Charts", bootstyle="info",
                 command=self.update_charts).pack(side='left')
        
        # Charts frame
        charts_frame = tb.Frame(stats_frame)
        charts_frame.pack(fill='both', expand=True, pady=(10, 0))
        
        # Create matplotlib figure
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(12, 8))
        self.canvas = FigureCanvasTkAgg(self.fig, charts_frame)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)
        
    def _start_auto_refresh(self):
        """Start automatic data refresh."""
        self.auto_refresh_running = True
        self._refresh_loop()
        
    def _refresh_loop(self):
        """Background refresh loop."""
        if self.auto_refresh_running:
            self.refresh_data()
            self.root.after(self.refresh_interval, self._refresh_loop)
            
    def refresh_data(self):
        """Refresh all data from server."""
        try:
            # Get status
            status_response = requests.get(f"{self.api_base_url}/api/loop-detection/status", timeout=5)
            if status_response.status_code == 200:
                status_data = status_response.json()
                self._update_status_display(status_data)
            
            # Get stats
            stats_response = requests.get(f"{self.api_base_url}/api/loop-detection/stats", timeout=5)
            if stats_response.status_code == 200:
                stats_data = stats_response.json()
                self._update_stats_display(stats_data)
            
            # Get recent history
            history_response = requests.get(f"{self.api_base_url}/api/loop-detection/history?limit=10", timeout=5)
            if history_response.status_code == 200:
                history_data = history_response.json()
                self._update_recent_detections(history_data)
                
        except Exception as e:
            self.status_text.config(text=f"Error: {str(e)}", bootstyle="danger")
            
    def _update_status_display(self, data):
        """Update status display."""
        running = data.get("running", False)
        enabled = data.get("enabled", False)
        interval = data.get("interval_minutes", 0)
        
        if running and enabled:
            self.status_label.config(text="🟢", bootstyle="success")
            self.status_text.config(text=f"Running (every {interval} min)", bootstyle="success")
        elif enabled:
            self.status_label.config(text="🟡", bootstyle="warning")
            self.status_text.config(text="Enabled but not running", bootstyle="warning")
        else:
            self.status_label.config(text="🔴", bootstyle="danger")
            self.status_text.config(text="Disabled", bootstyle="danger")
            
    def _update_stats_display(self, data):
        """Update statistics display."""
        self.total_label.config(text=str(data.get("total_detections", 0)))
        self.recent_label.config(text=str(data.get("recent_detections", 0)))
        
        # Update status breakdown
        status_breakdown = data.get("status_breakdown", [])
        loops_count = 0
        suspicious_count = 0
        
        for status in status_breakdown:
            if status["status"] == "loop_detected":
                loops_count = status["count"]
            elif status["status"] == "suspicious":
                suspicious_count = status["count"]
                
        self.loops_label.config(text=str(loops_count))
        self.suspicious_label.config(text=str(suspicious_count))
        
        # Update current status info
        latest = data.get("latest_detection")
        if latest:
            self._update_current_status(latest)
            
    def _update_current_status(self, latest):
        """Update current status information."""
        self.status_info.config(state="normal")
        self.status_info.delete("1.0", tk.END)
        
        info_text = f"""Latest Detection: {latest.get('detection_time', 'Unknown')}
Status: {latest.get('status', 'Unknown')}
Total Packets: {latest.get('total_packets', 0)}
Offenders: {latest.get('offenders_count', 0)}
Severity Score: {latest.get('severity_score', 0):.2f}
Interface: {latest.get('network_interface', 'Unknown')}
Duration: {latest.get('detection_duration', 0)} seconds"""
        
        self.status_info.insert(tk.END, info_text)
        self.status_info.config(state="disabled")
        
    def _update_recent_detections(self, data):
        """Update recent detections table."""
        # Clear existing items
        for item in self.recent_tree.get_children():
            self.recent_tree.delete(item)
            
        # Add new data
        for record in data:
            timestamp = record.get('detection_time', '')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    formatted_time = dt.strftime('%H:%M:%S')
                except:
                    formatted_time = timestamp
            else:
                formatted_time = 'Unknown'
                
            status = record.get('status', 'clean')
            status_emoji = {
                'clean': '✅ Clean',
                'suspicious': '🔍 Suspicious',
                'loop_detected': '⚠️ Loop'
            }.get(status, f'❓ {status}')
            
            self.recent_tree.insert("", "end", values=(
                formatted_time,
                status_emoji,
                record.get('total_packets', 0),
                record.get('offenders_count', 0),
                f"{record.get('severity_score', 0):.2f}",
                record.get('network_interface', 'Unknown')
            ))
            
    def start_detection(self):
        """Start loop detection."""
        try:
            response = requests.post(f"{self.api_base_url}/api/loop-detection/start", timeout=5)
            if response.status_code == 200:
                messagebox.showinfo("Success", "Loop detection started successfully!")
                self.refresh_data()
            else:
                messagebox.showerror("Error", f"Failed to start detection: {response.text}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start detection: {str(e)}")
            
    def stop_detection(self):
        """Stop loop detection."""
        try:
            response = requests.post(f"{self.api_base_url}/api/loop-detection/stop", timeout=5)
            if response.status_code == 200:
                messagebox.showinfo("Success", "Loop detection stopped successfully!")
                self.refresh_data()
            else:
                messagebox.showerror("Error", f"Failed to stop detection: {response.text}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to stop detection: {str(e)}")
            
    def save_configuration(self):
        """Save configuration settings."""
        try:
            interval = int(self.interval_var.get())
            threshold = int(self.threshold_var.get())
            enabled = self.enabled_var.get()
            
            if interval < 1 or interval > 60:
                messagebox.showerror("Error", "Interval must be between 1 and 60 minutes")
                return
                
            if threshold < 10 or threshold > 100:
                messagebox.showerror("Error", "Threshold must be between 10 and 100")
                return
                
            config_data = {
                "interval_minutes": interval,
                "threshold": threshold,
                "enabled": enabled
            }
            
            response = requests.post(f"{self.api_base_url}/api/loop-detection/configure", 
                                   json=config_data, timeout=5)
            
            if response.status_code == 200:
                messagebox.showinfo("Success", "Configuration saved successfully!")
                self.refresh_data()
            else:
                messagebox.showerror("Error", f"Failed to save configuration: {response.text}")
                
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numbers for interval and threshold")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {str(e)}")
            
    def refresh_history(self):
        """Refresh history data."""
        try:
            limit = int(self.limit_var.get())
            response = requests.get(f"{self.api_base_url}/api/loop-detection/history?limit={limit}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Clear existing items
                for item in self.history_tree.get_children():
                    self.history_tree.delete(item)
                    
                # Add new data
                for record in data:
                    timestamp = record.get('detection_time', '')
                    if timestamp:
                        try:
                            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            formatted_time = timestamp
                    else:
                        formatted_time = 'Unknown'
                        
                    status = record.get('status', 'clean')
                    status_emoji = {
                        'clean': '✅ Clean',
                        'suspicious': '🔍 Suspicious',
                        'loop_detected': '⚠️ Loop'
                    }.get(status, f'❓ {status}')
                    
                    self.history_tree.insert("", "end", values=(
                        formatted_time,
                        status_emoji,
                        record.get('total_packets', 0),
                        record.get('offenders_count', 0),
                        f"{record.get('severity_score', 0):.2f}",
                        record.get('network_interface', 'Unknown'),
                        f"{record.get('detection_duration', 0)}s"
                    ))
                    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh history: {str(e)}")
            
    def export_history(self):
        """Export history to CSV."""
        try:
            response = requests.get(f"{self.api_base_url}/api/loop-detection/history?limit=1000", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Convert to DataFrame and save
                df = pd.DataFrame(data)
                filename = f"loop_detection_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                df.to_csv(filename, index=False)
                
                messagebox.showinfo("Success", f"History exported to {filename}")
            else:
                messagebox.showerror("Error", f"Failed to export history: {response.text}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export history: {str(e)}")
            
    def update_charts(self):
        """Update statistics charts."""
        try:
            days = int(self.time_range_var.get())
            response = requests.get(f"{self.api_base_url}/api/loop-detection/history?limit=1000", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Process data for charts
                df = pd.DataFrame(data)
                df['detection_time'] = pd.to_datetime(df['detection_time'])
                df = df[df['detection_time'] >= datetime.now() - timedelta(days=days)]
                
                # Clear previous plots
                self.ax1.clear()
                self.ax2.clear()
                
                # Plot 1: Detection frequency over time
                df['date'] = df['detection_time'].dt.date
                daily_counts = df.groupby('date').size()
                self.ax1.plot(daily_counts.index, daily_counts.values, marker='o')
                self.ax1.set_title('Detection Frequency Over Time')
                self.ax1.set_xlabel('Date')
                self.ax1.set_ylabel('Number of Detections')
                self.ax1.tick_params(axis='x', rotation=45)
                
                # Plot 2: Status distribution
                status_counts = df['status'].value_counts()
                self.ax2.pie(status_counts.values, labels=status_counts.index, autopct='%1.1f%%')
                self.ax2.set_title('Detection Status Distribution')
                
                # Refresh canvas
                self.canvas.draw()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update charts: {str(e)}")
            
    def on_closing(self):
        """Handle window closing."""
        self.auto_refresh_running = False
        self.root.destroy()

def show_admin_dashboard(api_base_url="http://localhost:5000"):
    """Show the admin loop detection dashboard."""
    root = tb.Window(themename="superhero")
    app = AdminLoopDashboard(root, api_base_url)
    
    # Handle window closing
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    root.mainloop()

if __name__ == "__main__":
    show_admin_dashboard()
