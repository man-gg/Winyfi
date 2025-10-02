import os
import ttkbootstrap as tb
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import messagebox, filedialog
from PIL import Image, ImageTk
import requests
from datetime import datetime, timedelta
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import threading
import time
from collections import defaultdict

# Import tab modules
from .tabs.dashboard_tab import DashboardTab
from .tabs.routers_tab import RoutersTab
from .tabs.reports_tab import ReportsTab
from .tabs.bandwidth_tab import BandwidthTab
from .tabs.settings_tab import SettingsTab

# Import notification system
from notification_utils import (
    notification_manager,
    notify_router_status_change,
    notify_loop_detected,
    notify_system_alert,
    NotificationPriority
)
from notification_ui import NotificationSystem


class ClientDashboard:
    def __init__(self, root, current_user):
        self.root = root
        self.current_user = current_user
        self.api_base_url = os.environ.get("WINYFI_API", "http://127.0.0.1:5000")
        
        # Initialize notification system
        self.notification_system = NotificationSystem(self.root)
        self.notification_count = 0
        
        # Router status monitoring
        self.router_status_history = {}
        self.status_monitoring_running = True
        self.start_router_status_monitoring()

        style = tb.Style()
        style.colors.set('primary', '#d9534f')
        style.colors.set('danger', '#b71c1c')

        style.configure('Sidebar.TFrame', background='white', borderwidth=0)
        style.configure('Sidebar.TButton',
                        background='white',
                        foreground='black',
                        font=('Segoe UI', 11, 'bold'),
                        relief='flat',
                        focusthickness=0)
        style.map('Sidebar.TButton', background=[('active', '#f8f9fa')])
        style.configure('ActiveSidebar.TButton',
                        background='#d32f2f',
                        foreground='white',
                        font=('Segoe UI', 11, 'bold'),
                        relief='flat')
        style.map('ActiveSidebar.TButton', background=[('active', '#b71c1c')])
        style.configure('Dashboard.TFrame', background='white')

        r = self.root
        r.title("WINYFI Client Portal")
        W, H = 1000, 600
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        x, y = (sw - W) // 2, 50
        r.geometry(f"{W}x{H}+{x}+{y}")

        # Sidebar and content
        self.sidebar = tb.Frame(r, style='Sidebar.TFrame', width=220)
        self.sidebar.pack(side="left", fill="y")

        self.content_frame = tb.Frame(r)
        self.content_frame.pack(side="left", fill="both", expand=True)

        # Pages
        self.dashboard_frame = tb.Frame(self.content_frame)
        self.routers_frame = tb.Frame(self.content_frame)
        self.reports_frame = tb.Frame(self.content_frame)
        self.bandwidth_frame = tb.Frame(self.content_frame)
        self.settings_frame = tb.Frame(self.content_frame)

        self.pages = {
            "Dashboard": self.dashboard_frame,
            "Routers": self.routers_frame,
            "Reports": self.reports_frame,
            "Bandwidth": self.bandwidth_frame,
            "Settings": self.settings_frame,
        }

        self.sidebar_buttons = {}

        def add_sidebar_button(text, icon):
            btn = tb.Button(self.sidebar,
                            text=f"{icon} {text}",
                            style='Sidebar.TButton',
                            width=22,
                            command=lambda: self.show_page(text))
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

        # Navigation
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
            text="",
            font=("Segoe UI", 8, "bold"),
            foreground="white",
            background="#dc3545",
            width=3
        )

        # Settings dropdown (UI only; disabled actions)
        settings_btn = tb.Button(self.sidebar,
                                 text="⚙️ Settings ▼",
                                 style='Sidebar.TButton',
                                 width=22,
                                 command=self.toggle_settings_dropdown)
        settings_btn.pack(pady=5)
        self.sidebar_buttons["Settings"] = settings_btn

        self.settings_dropdown = tb.Frame(self.sidebar, style='Sidebar.TFrame')
        self.dropdown_target_height = 90
        um_btn = tb.Button(self.settings_dropdown, text="👤 User Profile",
                           bootstyle="link", command=self.open_user_mgmt)
        sep = ttk.Separator(self.settings_dropdown, orient='horizontal')
        lo_btn = tb.Button(self.settings_dropdown, text="⏏️ Log Out",
                           bootstyle="link", command=self.logout)
        um_btn.pack(fill='x', pady=(5, 2))
        sep.pack(fill='x', pady=2)
        lo_btn.pack(fill='x', pady=(2, 5))
        self.settings_dropdown.pack_propagate(False)
        self.settings_dropdown.config(height=0)


        # Export button
        self.export_btn = tb.Button(
            self.sidebar,
            text="⬇️ Export to CSV",
            width=22,
            style='Sidebar.TButton',
            command=self.open_export_menu
        )
        self.export_btn.pack(pady=(0, 0))

        # Build page UIs using separate tab classes
        self.dashboard_tab = DashboardTab(self.dashboard_frame, self.api_base_url, self.root)
        self.routers_tab = RoutersTab(self.routers_frame, self.api_base_url, self.root)
        self.reports_tab = ReportsTab(self.reports_frame, self.api_base_url, self.root)
        self.bandwidth_tab = BandwidthTab(self.bandwidth_frame, self.api_base_url, self.root)
        self.settings_tab = SettingsTab(self.settings_frame, self.api_base_url, self.root)

        # Default tab
        self.show_page("Dashboard")

    def show_page(self, name):
        """Show the specified page and update button styles"""
        for f in self.pages.values():
            f.pack_forget()
        self.pages[name].pack(fill="both", expand=True)
        for tname, btn in self.sidebar_buttons.items():
            btn_style = 'ActiveSidebar.TButton' if tname == name else 'Sidebar.TButton'
            btn.config(style=btn_style)

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




    def open_user_mgmt(self):
        """Open user profile window"""
        self.show_user_profile()

    def show_user_profile(self):
        """Show user profile information with modern UI design"""
        # Safety check for current_user
        if not self.current_user:
            messagebox.showerror("Error", "User information not available.")
            return
        
            
        profile_modal = tb.Toplevel(self.root)
        profile_modal.title("User Profile")
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
            ("📅", "Member Since", "Recently"),
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
    
    def update_notification_count(self):
        """Update the notification count badge."""
        try:
            count = self.notification_system.get_notification_count()
            self.notification_count = count
            
            if count > 0:
                self.notification_badge.config(text=str(count), background="#dc3545")
                self.notification_badge.place(in_=self.notification_btn, x=180, y=5)
            else:
                self.notification_badge.place_forget()
        except Exception as e:
            print(f"Error updating notification count: {e}")
    
    def _center_window(self, window, width, height):
        """Center a window on the screen."""
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        window.geometry(f"{width}x{height}+{x}+{y}")
    
    def start_router_status_monitoring(self):
        """Start monitoring router status changes."""
        def monitor_router_status():
            while self.status_monitoring_running:
                try:
                    # Get routers from API
                    response = requests.get(f"{self.api_base_url}/api/routers", timeout=5)
                    if response.ok:
                        routers = response.json() or []
                        
                        for router in routers:
                            router_id = router.get('id')
                            router_name = router.get('name', f'Router {router_id}')
                            router_ip = router.get('ip_address', 'Unknown')
                            
                            # Check if router is online
                            is_online = self._is_router_online(router_ip)
                            
                            # Check for status change
                            if router_id in self.router_status_history:
                                prev_status = self.router_status_history[router_id]
                                if prev_status != is_online:
                                    # Status changed - create notification
                                    self.root.after(0, lambda: self._create_router_notification(router_name, router_ip, is_online))
                                    self.root.after(0, self.update_notification_count)
                            
                            # Update status history
                            self.router_status_history[router_id] = is_online
                    
                    # Wait before next check
                    time.sleep(30)  # Check every 30 seconds
                    
                except Exception as e:
                    print(f"Error in router status monitoring: {e}")
                    time.sleep(30)
        
        # Start monitoring in background thread
        threading.Thread(target=monitor_router_status, daemon=True).start()
    
    def _is_router_online(self, ip_address):
        """Check if a router is online by pinging it."""
        try:
            import subprocess
            # Use ping command to check connectivity
            result = subprocess.run(['ping', '-n', '1', '-w', '1000', ip_address], 
                                  capture_output=True, text=True, timeout=2)
            return result.returncode == 0
        except:
            return False
    
    def _create_router_notification(self, router_name, router_ip, is_online):
        """Create a router status change notification."""
        try:
            print(f"🔔 Client: Router status change: {router_name} ({router_ip}) - {'Online' if is_online else 'Offline'}")
            notification_id = notify_router_status_change(router_name, router_ip, is_online)
            print(f"🔔 Client: Notification created with ID: {notification_id}")
        except Exception as e:
            print(f"Error creating client router notification: {e}")
    
    def stop_router_status_monitoring(self):
        """Stop monitoring router status changes."""
        self.status_monitoring_running = False

    def logout(self):
        """Handle user logout"""
        if messagebox.askyesno("Logout", "Are you sure you want to logout?"):
            self.root.quit()



    def open_export_menu(self):
        """Open export menu"""
        messagebox.showinfo("Export", "Export functionality will be implemented here.")


def show_client_window(root, current_user):
    ClientDashboard(root, current_user)


