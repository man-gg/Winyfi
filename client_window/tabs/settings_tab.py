import tkinter as tk
import ttkbootstrap as tb
from tkinter import messagebox
from datetime import datetime


class SettingsTab:
    def __init__(self, parent_frame, api_base_url, root_window, app=None):
        self.parent_frame = parent_frame
        self.api_base_url = api_base_url
        self.root = root_window
        self.app = app  # Reference to parent ClientApp/Dashboard
        self._build_settings_page()

    def _build_settings_page(self):
        """Build the settings page UI"""
        header = tb.Frame(self.parent_frame)
        header.pack(fill='x', padx=10, pady=(10, 0))
        tb.Label(header, text="Settings", font=("Segoe UI", 14, "bold")).pack(side='left')
        
        # Settings content
        settings_container = tb.Frame(self.parent_frame)
        settings_container.pack(fill='both', expand=True, padx=20, pady=20)
        
        # User Profile Section
        user_profile_card = tb.LabelFrame(settings_container, text="👤 User Profile", 
                                         bootstyle="primary", padding=15)
        user_profile_card.pack(fill='x', pady=(0, 15))
        
        tb.Label(user_profile_card, text="View and manage your personal information", 
                font=("Segoe UI", 11)).pack(anchor='w')
        tb.Button(user_profile_card, text="Open User Profile", 
                 bootstyle="primary", command=self.open_user_mgmt).pack(pady=(10, 0))
        
        # Export Settings Section
        export_card = tb.LabelFrame(settings_container, text="📊 Export Settings", 
                                   bootstyle="info", padding=15)
        export_card.pack(fill='x', pady=(0, 15))
        
        tb.Label(export_card, text="Configure data export options", 
                font=("Segoe UI", 11)).pack(anchor='w')
        tb.Button(export_card, text="Open Export Menu", 
                 bootstyle="info", command=self.open_export_menu).pack(pady=(10, 0))
        
        # Loop Detection Section
        loop_detection_card = tb.LabelFrame(settings_container, text="🔄 Loop Detection", 
                                           bootstyle="warning", padding=15)
        loop_detection_card.pack(fill='x', pady=(0, 15))
        
        tb.Label(loop_detection_card, text="Monitor and manage automatic loop detection", 
                font=("Segoe UI", 11)).pack(anchor='w')
        
        loop_buttons_frame = tb.Frame(loop_detection_card)
        loop_buttons_frame.pack(fill='x', pady=(10, 0))
        
        tb.Button(loop_buttons_frame, text="View Detection History", 
                 bootstyle="warning", command=self.open_loop_history).pack(side='left', padx=(0, 10))
        tb.Button(loop_buttons_frame, text="Configure Detection", 
                 bootstyle="warning-outline", command=self.configure_loop_detection).pack(side='left')
        
        # System Settings Section
        system_card = tb.LabelFrame(settings_container, text="⚙️ System Settings", 
                                   bootstyle="secondary", padding=15)
        system_card.pack(fill='x', pady=(0, 15))
        
        tb.Label(system_card, text="Configure system preferences and notifications", 
                font=("Segoe UI", 11)).pack(anchor='w')
        tb.Button(system_card, text="Configure System", 
                 bootstyle="secondary", state='disabled').pack(pady=(10, 0))
        
        # Logout Section
        logout_card = tb.LabelFrame(settings_container, text="🚪 Account", 
                                   bootstyle="danger", padding=15)
        logout_card.pack(fill='x', pady=(0, 15))
        
        tb.Label(logout_card, text="Sign out of your account", 
                font=("Segoe UI", 11)).pack(anchor='w')
        logout_btn = tb.Button(logout_card, text="🚪 Logout", 
                              bootstyle="danger", 
                              command=self.handle_logout,
                              width=22)
        logout_btn.pack(pady=(10, 0))

    def open_user_mgmt(self):
        """Open user profile window"""
        messagebox.showinfo("User Profile", "User profile functionality will be implemented here.")

    def open_export_menu(self):
        """Open export menu"""
        messagebox.showinfo("Export", "Export functionality will be implemented here.")

    def open_loop_history(self):
        """Open loop detection history window (client view only)"""
        import tkinter as tk
        from tkinter import ttk
        import requests
        import json
        from datetime import datetime
        
        # Create history window
        history_window = tk.Toplevel(self.root)
        history_window.title("Loop Detection History (Read-Only)")
        history_window.geometry("800x600")
        history_window.resizable(True, True)
        
        # Center the window
        history_window.transient(self.root)
        history_window.grab_set()
        
        # Header
        header_frame = tb.Frame(history_window)
        header_frame.pack(fill='x', padx=10, pady=10)
        
        tb.Label(header_frame, text="🔄 Loop Detection History (Read-Only)", 
                font=("Segoe UI", 14, "bold")).pack(side='left')
        
        # Info label
        info_label = tb.Label(header_frame, text="ℹ️ Loop detection is managed by the server", 
                             font=("Segoe UI", 10), bootstyle="info")
        info_label.pack(side='left', padx=(20, 0))
        
        # Refresh button
        tb.Button(header_frame, text="🔄 Refresh", 
                 bootstyle="primary", command=lambda: self._load_loop_history(history_window)).pack(side='right')
        
        # Create treeview for history
        tree_frame = tb.Frame(history_window)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        
        columns = ("Time", "Status", "Packets", "Offenders", "Severity", "Interface")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)
        
        # Configure columns
        tree.heading("Time", text="Detection Time")
        tree.heading("Status", text="Status")
        tree.heading("Packets", text="Total Packets")
        tree.heading("Offenders", text="Offenders Count")
        tree.heading("Severity", text="Severity Score")
        tree.heading("Interface", text="Interface")
        
        tree.column("Time", width=150)
        tree.column("Status", width=100)
        tree.column("Packets", width=100)
        tree.column("Offenders", width=100)
        tree.column("Severity", width=100)
        tree.column("Interface", width=120)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Bind mouse wheel scrolling
        def on_mousewheel(event):
            tree.yview_scroll(int(-1*(event.delta/120)), "units")
            return "break"
        
        tree.bind("<MouseWheel>", on_mousewheel)
        
        # Status label
        status_label = tb.Label(history_window, text="Loading...", bootstyle="info")
        status_label.pack(pady=(0, 10))
        
        # Load initial data
        self._load_loop_history(history_window, tree, status_label)

    def _load_loop_history(self, window, tree=None, status_label=None):
        """Load loop detection history from API"""
        try:
            import requests
            
            response = requests.get(f"{self.api_base_url}/api/loop-detection/history?limit=100", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if tree:
                    # Clear existing items
                    for item in tree.get_children():
                        tree.delete(item)
                    
                    # Add data to tree
                    for record in data:
                        # Format timestamp
                        timestamp = record.get('detection_time', '')
                        if timestamp:
                            try:
                                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                                formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                            except:
                                formatted_time = timestamp
                        else:
                            formatted_time = 'Unknown'
                        
                        # Format status with emoji
                        status = record.get('status', 'clean')
                        status_emoji = {
                            'clean': '✅ Clean',
                            'suspicious': '🔍 Suspicious', 
                            'loop_detected': '⚠️ Loop Detected'
                        }.get(status, f'❓ {status}')
                        
                        tree.insert("", "end", values=(
                            formatted_time,
                            status_emoji,
                            record.get('total_packets', 0),
                            record.get('offenders_count', 0),
                            f"{record.get('severity_score', 0):.2f}",
                            record.get('network_interface', 'Unknown')
                        ))
                
                if status_label:
                    status_label.config(text=f"Loaded {len(data)} records", bootstyle="success")
            else:
                if status_label:
                    status_label.config(text=f"Error loading data: {response.status_code}", bootstyle="danger")
                    
        except Exception as e:
            if status_label:
                status_label.config(text=f"Error: {str(e)}", bootstyle="danger")

    def configure_loop_detection(self):
        """Open loop detection configuration window (read-only for clients)"""
        import tkinter as tk
        from tkinter import messagebox
        import requests
        
        config_window = tk.Toplevel(self.root)
        config_window.title("Loop Detection Status (Read-Only)")
        config_window.geometry("500x400")
        config_window.resizable(False, False)
        
        # Center the window
        config_window.transient(self.root)
        config_window.grab_set()
        
        # Header
        tb.Label(config_window, text="🔄 Loop Detection Status", 
                font=("Segoe UI", 14, "bold")).pack(pady=20)
        
        # Info message
        info_frame = tb.Frame(config_window)
        info_frame.pack(fill='x', padx=20, pady=(0, 20))
        
        tb.Label(info_frame, text="ℹ️ Loop detection is managed by the server administrator", 
                font=("Segoe UI", 10), bootstyle="info").pack()
        
        # Current status display
        status_frame = tb.LabelFrame(config_window, text="Current Status", 
                                   bootstyle="primary", padding=15)
        status_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))
        
        # Status text
        self.status_text = tb.Text(status_frame, height=10, state="disabled")
        self.status_text.pack(fill='both', expand=True)
        
        # Buttons
        button_frame = tb.Frame(config_window)
        button_frame.pack(fill='x', padx=20, pady=(0, 20))
        
        tb.Button(button_frame, text="🔄 Refresh Status", 
                 bootstyle="info", command=lambda: self._load_loop_status()).pack(side='left', padx=(0, 10))
        tb.Button(button_frame, text="Close", 
                 bootstyle="secondary", command=config_window.destroy).pack(side='left')
        
        # Load initial status
        self._load_loop_status()
        
    def _load_loop_status(self):
        """Load current loop detection status from server."""
        try:
            import requests
            
            # Get status
            status_response = requests.get(f"{self.api_base_url}/api/loop-detection/status", timeout=5)
            stats_response = requests.get(f"{self.api_base_url}/api/loop-detection/stats", timeout=5)
            
            self.status_text.config(state="normal")
            self.status_text.delete("1.0", tk.END)
            
            if status_response.status_code == 200:
                status_data = status_response.json()
                status_text = f"""Server Status:
Running: {'Yes' if status_data.get('running') else 'No'}
Enabled: {'Yes' if status_data.get('enabled') else 'No'}
Interval: {status_data.get('interval_minutes', 0)} minutes

"""
            else:
                status_text = "Error loading status\n\n"
                
            if stats_response.status_code == 200:
                stats_data = stats_response.json()
                status_text += f"""Statistics:
Total Detections: {stats_data.get('total_detections', 0)}
Recent (24h): {stats_data.get('recent_detections', 0)}

Status Breakdown (Last 7 Days):"""
                
                for status in stats_data.get('status_breakdown', []):
                    status_text += f"\n- {status['status']}: {status['count']}"
                    
                latest = stats_data.get('latest_detection')
                if latest:
                    status_text += f"""

Latest Detection:
Time: {latest.get('detection_time', 'Unknown')}
Status: {latest.get('status', 'Unknown')}
Packets: {latest.get('total_packets', 0)}
Severity: {latest.get('severity_score', 0):.2f}"""
            else:
                status_text += "Error loading statistics"
                
            self.status_text.insert(tk.END, status_text)
            self.status_text.config(state="disabled")
            
        except Exception as e:
            self.status_text.config(state="normal")
            self.status_text.delete("1.0", tk.END)
            self.status_text.insert(tk.END, f"Error loading status: {str(e)}")
            self.status_text.config(state="disabled")
    
    def handle_logout(self):
        """Handle logout - call parent app's logout method if available"""
        if self.app and hasattr(self.app, 'logout'):
            self.app.logout()
        else:
            messagebox.showwarning("Logout", "Logout functionality is not available. Please use the logout button in the main menu.")
