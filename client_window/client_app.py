import os
import sys
import csv
from typing import TYPE_CHECKING
import ttkbootstrap as tb
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import messagebox, filedialog
from ttkbootstrap.widgets import DateEntry
from PIL import Image, ImageTk
import requests
from datetime import datetime, timedelta
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt

# Suppress matplotlib warnings
import logging
matplotlib_logger = logging.getLogger('matplotlib')
matplotlib_logger.setLevel(logging.ERROR)

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import threading
import time
from collections import defaultdict

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from print_utils import print_srf_form

# Add current directory and tabs directory to path
current_dir = os.path.dirname(__file__)
tabs_dir = os.path.join(current_dir, 'tabs')
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if tabs_dir not in sys.path:
    sys.path.insert(0, tabs_dir)

# Import tab modules with explicit path handling for Pylance
# Type annotations to help Pylance understand the imports

if TYPE_CHECKING:
    # For static analysis (Pylance)
    from tabs.dashboard_tab import DashboardTab
    from tabs.routers_tab import RoutersTab
    from tabs.reports_tab import ReportsTab
    from tabs.bandwidth_tab import BandwidthTab
    from tabs.settings_tab import SettingsTab
else:
    # For runtime
    try:
        from tabs.dashboard_tab import DashboardTab
        from tabs.routers_tab import RoutersTab
        from tabs.reports_tab import ReportsTab
        from tabs.bandwidth_tab import BandwidthTab
        from tabs.settings_tab import SettingsTab
    except ImportError:
        # Fallback to direct imports
        from dashboard_tab import DashboardTab
        from routers_tab import RoutersTab
        from reports_tab import ReportsTab
        from bandwidth_tab import BandwidthTab
        from settings_tab import SettingsTab

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
        # Normalize API base URL (strip trailing slash)
        self.api_base_url = os.environ.get("WINYFI_API", "http://127.0.0.1:5000").rstrip("/")
        # Reuse HTTP connections for speed and reliability
        self.http = requests.Session()
        # Server connection state
        self.server_online = None  # unknown at start
        self._server_status_first_update = False
        # Use a re-entrant lock to avoid deadlocks when status updates nest
        self._server_status_lock = threading.RLock()
        self._server_poll_backoff = 3  # seconds
        self._server_poll_max = 60
        self._health_stop_event = threading.Event()
        # Ensure closing this window exits the whole app
        try:
            self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        except Exception:
            pass
        # Initialize notification system
        self.notification_system = NotificationSystem(self.root)
        self.notification_count = 0
        # Router status monitoring (start after UI is fully constructed)
        self.router_status_history = {}
        self.status_monitoring_running = True

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
        
        # Section header label style
        style.configure('SectionHeader.TLabel',
                        background="#830000",
                        foreground='white',
                        font=('Segoe UI', 9, 'bold'),
                        padding=(10, 5))
        
        r = self.root
        r.title("WINYFI Client Portal")
        W, H = 1000, 600
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        x, y = (sw - W) // 2, 50
        r.geometry(f"{W}x{H}+{x}+{y}")
        # Sidebar and content
        self.sidebar = tb.Frame(r, style='Sidebar.TFrame', width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        
        # Add black border line on the right side of sidebar only
        sidebar_border = tk.Frame(r, width=1, bg='#000000', bd=0, highlightthickness=3)
        sidebar_border.pack(side="left", fill="y")
        
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
        
        def add_section_header(text):
            """Add a red section header"""
            header = tb.Label(self.sidebar, 
                            text=text.upper(),
                            style='SectionHeader.TLabel')
            header.pack(fill='x', pady=(10, 0))
        
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
                     background='white', borderwidth=0).pack(pady=(15, 10))
        else:
            tb.Label(self.sidebar, text="WINYFI",
                     font=("Segoe UI", 16, "bold"),
                     foreground='#d32f2f',
                     background='white').pack(pady=15)
        
        # Overview section
        add_section_header("Overview")
        add_sidebar_button("Dashboard", "🏠")
        add_sidebar_button("Routers", "🚗")
        add_sidebar_button("Bandwidth", "📶")
        
        # Reports & Analysis section
        add_section_header("Reports & Analysis")
        add_sidebar_button("Reports", "📄")
        
        # Export button
        self.export_btn = tb.Button(
            self.sidebar,
            text="📁 Export To Csv",
            style='Sidebar.TButton',
            width=22,
            command=self.open_export_menu
        )
        self.export_btn.pack(pady=5)
        
        # Notifications section
        add_section_header("Notifications")
        
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
        
        # Account & Settings section
        add_section_header("Account & Settings")
        
        # Server status indicator (sidebar footer) with Retry (anchored at bottom)
        status_row = tb.Frame(self.sidebar, style='Sidebar.TFrame', padding=(0,0))
        status_row.pack(side='bottom', fill='x', pady=(10, 10))
        self.server_status_label = tb.Label(
            status_row,
            text="● Server: Offline",
            font=("Segoe UI", 10),
            foreground="#dc3545",
            background="white"
        )
        self.server_status_label.pack(side='left')
        self.retry_btn = tb.Button(
            status_row,
            text="Retry",
            bootstyle="link",
            command=self.check_server_now,
            width=6
        )
        self.retry_btn.pack(side='right', padx=(8,0))
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
        
        # Dropdown buttons with proper alignment and styling
        um_btn = tb.Button(self.settings_dropdown, 
                           text="  👤 User Profile",
                           style='Sidebar.TButton',
                           width=22,
                           command=self.open_user_mgmt)
        sep = ttk.Separator(self.settings_dropdown, orient='horizontal')
        lo_btn = tb.Button(self.settings_dropdown, 
                           text="  ⏏️ Log Out",
                           style='Sidebar.TButton',
                           width=22,
                           command=self.logout)
        
        um_btn.pack(fill='x', pady=2, padx=0)
        sep.pack(fill='x', pady=2)
        lo_btn.pack(fill='x', pady=2, padx=0)
        
        self.settings_dropdown.pack_propagate(False)
        self.settings_dropdown.config(height=0)
        
        # Build page UIs using separate tab classes
        self.dashboard_tab = DashboardTab(self.dashboard_frame, self.api_base_url, self.root)
        self.routers_tab = RoutersTab(self.routers_frame, self.api_base_url, self.root)
        self.reports_tab = ReportsTab(self.reports_frame, self.root)
        self.bandwidth_tab = BandwidthTab(self.bandwidth_frame, self.api_base_url, self.root)
        self.settings_tab = SettingsTab(self.settings_frame, self.api_base_url, self.root)
        # Default tab
        self.show_page("Dashboard")

        # Start lightweight server health monitoring
        self.start_server_health_monitor()
        # Run initial check after UI is fully ready (avoid race condition)
        self.root.after(200, self._initial_server_check)

        # Now that UI exists, start router status monitoring
        self.start_router_status_monitoring()

    def _add_tickets_button_to_reports(self):
        """Add a tickets button to the Reports tab"""
        # Create a frame at the top of the reports tab for the tickets button
        tickets_frame = tb.Frame(self.reports_frame)
        tickets_frame.pack(fill="x", padx=10, pady=10)
        
        # Add the tickets button
        tb.Button(
            tickets_frame,
            text="📝 ICT Service Requests",
            bootstyle="primary",
            command=self.open_ticket_window
        ).pack(side="left")

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

        # if opening, pack it directly after the Settings button
        if opening:
            self.settings_dropdown.pack(fill='x', pady=0)

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

    def refresh_current_user_info(self):
        """Refresh current user info from backend API."""
        try:
            user_id = self.current_user.get('id')
            if user_id:
                resp = self.http.get(f"{self.api_base_url}/api/users", timeout=8)
                if resp.status_code == 200:
                    users = resp.json()
                    for u in users:
                        if u['id'] == user_id:
                            self.current_user.update(u)
                            break
        except Exception:
            pass

    def show_user_profile(self):
        # Always refresh user info before showing profile
        self.refresh_current_user_info()
        """Show user profile information with modern UI design"""
        # Safety check for current_user
        if not self.current_user:
            messagebox.showerror("Error", "User information not available.")
            return

        # Use configured API base URL and shared HTTP session
        base_url = self.api_base_url

        def backend_change_password(user_id, old_password, new_password):
            """Backend logic to change user password via API."""
            try:
                resp = self.http.post(f"{base_url}/api/user/{user_id}/change-password", json={
                    "old_password": old_password,
                    "new_password": new_password
                }, timeout=10)
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                    except Exception as e:
                        return False
                    if data.get("success"):
                        return True
                    else:
                        return False
                else:
                    return False
            except requests.exceptions.Timeout:
                messagebox.showerror("Error", "Request timed out. Please try again.")
                return False
            except requests.exceptions.ConnectionError:
                messagebox.showerror("Error", "Cannot connect to server. Please check your connection.")
                return False
            except Exception as e:
                messagebox.showerror("Error", f"Unexpected error: {str(e)}")
                return False

        def backend_edit_profile(user_id, new_profile_data):
            """Backend logic to edit user profile via API."""
            try:
                resp = self.http.put(f"{base_url}/api/user/{user_id}/edit-profile", 
                                  json=new_profile_data, timeout=10)
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                    except Exception as e:
                        return False
                    if data.get("success"):
                        user_data = data.get("user", {})
                        if user_data:
                            self.current_user.update(user_data)
                        return True
                    else:
                        return False
                else:
                    return False
            except requests.exceptions.Timeout:
                messagebox.showerror("Error", "Request timed out. Please try again.")
                return False
            except requests.exceptions.ConnectionError:
                messagebox.showerror("Error", "Cannot connect to server. Please check your connection.")
                return False
            except Exception as e:
                messagebox.showerror("Error", f"Unexpected error: {str(e)}")
                return False

        def open_change_password_modal():
            modal = tb.Toplevel(self.root)
            modal.title("Change Password")
            modal.geometry("400x450")
            modal.resizable(False, False)
            modal.transient(self.root)
            modal.grab_set()
            modal.lift()
            modal.focus_force()

            # Center modal on screen
            modal.update_idletasks()
            x = (modal.winfo_screenwidth() - 400) // 2
            y = (modal.winfo_screenheight() - 450) // 2
            modal.geometry(f"400x450+{x}+{y}")

            frame = tb.Frame(modal, padding=20)
            frame.pack(fill="both", expand=True)

            tb.Label(frame, text="Change Password", font=("Segoe UI", 16, "bold"), bootstyle="primary").pack(pady=(0, 20))

            old_pass_var = tk.StringVar()
            new_pass_var = tk.StringVar()
            confirm_pass_var = tk.StringVar()

            tb.Label(frame, text="Current Password:", font=("Segoe UI", 11)).pack(anchor="w")
            old_pass_entry = tb.Entry(frame, textvariable=old_pass_var, show="*")
            old_pass_entry.pack(fill="x", pady=(0, 10))

            tb.Label(frame, text="New Password:", font=("Segoe UI", 11)).pack(anchor="w")
            new_pass_entry = tb.Entry(frame, textvariable=new_pass_var, show="*")
            new_pass_entry.pack(fill="x", pady=(0, 5))
            
            # Password strength indicator
            strength_label = tb.Label(frame, text="", font=("Segoe UI", 9))
            strength_label.pack(anchor="w", pady=(0, 10))
            
            def check_password_strength(*args):
                try:
                    password = new_pass_var.get()
                    if len(password) == 0:
                        strength_label.configure(text="", foreground="")
                    elif len(password) < 6:
                        strength_label.configure(text="⚠️ Too short (min 6 characters)", foreground="red")
                    elif password.isdigit():
                        strength_label.configure(text="⚠️ Weak (numbers only)", foreground="orange")
                    elif password.isalpha():
                        strength_label.configure(text="⚠️ Weak (letters only)", foreground="orange")
                    elif len(password) < 8:
                        strength_label.configure(text="🟡 Fair", foreground="orange")
                    else:
                        has_upper = any(c.isupper() for c in password)
                        has_lower = any(c.islower() for c in password)
                        has_digit = any(c.isdigit() for c in password)
                        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
                        
                        score = sum([has_upper, has_lower, has_digit, has_special])
                        if score >= 3:
                            strength_label.configure(text="✅ Strong", foreground="green")
                        else:
                            strength_label.configure(text="🟡 Good", foreground="darkorange")
                except Exception:
                    pass
            
            new_pass_var.trace_add("write", check_password_strength)

            tb.Label(frame, text="Confirm New Password:", font=("Segoe UI", 11)).pack(anchor="w")
            confirm_pass_entry = tb.Entry(frame, textvariable=confirm_pass_var, show="*")
            confirm_pass_entry.pack(fill="x", pady=(0, 5))
            
            # Password match indicator
            match_label = tb.Label(frame, text="", font=("Segoe UI", 9))
            match_label.pack(anchor="w", pady=(0, 15))
            
            def check_password_match(*args):
                try:
                    new_pass = new_pass_var.get()
                    confirm_pass = confirm_pass_var.get()
                    if len(confirm_pass) == 0:
                        match_label.configure(text="", foreground="")
                    elif new_pass != confirm_pass:
                        match_label.configure(text="❌ Passwords do not match", foreground="red")
                    else:
                        match_label.configure(text="✅ Passwords match", foreground="green")
                except Exception:
                    pass
            
            confirm_pass_var.trace_add("write", check_password_match)
            new_pass_var.trace_add("write", check_password_match)

            status_label = tb.Label(frame, text="", font=("Segoe UI", 10))
            status_label.pack(pady=(0, 10))

            def submit_change():
                try:
                    old_password = old_pass_var.get().strip()
                    new_password = new_pass_var.get().strip()
                    confirm_password = confirm_pass_var.get().strip()
                    
                    # Clear previous status
                    status_label.configure(text="", foreground="")
                    
                    # Validation
                    if not old_password:
                        status_label.configure(text="❌ Please enter current password", foreground="red")
                        return
                        
                    if not new_password:
                        status_label.configure(text="❌ Please enter new password", foreground="red")
                        return
                        
                    if len(new_password) < 6:
                        status_label.configure(text="❌ New password must be at least 6 characters", foreground="red")
                        return
                        
                    if new_password != confirm_password:
                        status_label.configure(text="❌ Passwords do not match", foreground="red")
                        return
                    
                    if old_password == new_password:
                        status_label.configure(text="❌ New password must be different from current password", foreground="red")
                        return
                    
                    # Show processing
                    status_label.configure(text="⏳ Changing password...", foreground="blue")
                    modal.update()
                    
                    # Call backend
                    user_id = self.current_user.get('id')
                    success = backend_change_password(user_id, old_password, new_password)
                    if success:
                        status_label.configure(text="✅ Password changed successfully!", foreground="green")
                        self.root.after(1500, modal.destroy)
                    else:
                        status_label.configure(text="❌ Current password is incorrect", foreground="red")
                        
                except Exception as e:
                    status_label.configure(text=f"❌ Error: {str(e)}", foreground="red")

            # Buttons
            button_frame = tb.Frame(frame)
            button_frame.pack(fill="x", pady=(10, 0))
            
            tb.Button(button_frame, text="Cancel", command=modal.destroy, bootstyle="secondary").pack(side="right", padx=(10, 0))
            tb.Button(button_frame, text="Change Password", command=submit_change, bootstyle="primary").pack(side="right")

            # Focus on first entry
            old_pass_entry.focus_set()
            
            # Enter key binding
            def on_enter(event):
                submit_change()
            
            modal.bind('<Return>', on_enter)

        def open_edit_profile_modal():
            modal = tb.Toplevel(self.root)
            modal.title("Edit Profile")
            modal.geometry("400x450")
            modal.resizable(False, False)
            modal.transient(self.root)
            modal.grab_set()
            modal.lift()
            modal.focus_force()

            # Center modal on screen
            modal.update_idletasks()
            x = (modal.winfo_screenwidth() - 400) // 2
            y = (modal.winfo_screenheight() - 450) // 2
            modal.geometry(f"400x450+{x}+{y}")

            frame = tb.Frame(modal, padding=20)
            frame.pack(fill="both", expand=True)

            tb.Label(frame, text="Edit Profile", font=("Segoe UI", 16, "bold"), bootstyle="success").pack(pady=(0, 20))

            first_name_var = tk.StringVar(value=self.current_user.get('first_name', ''))
            last_name_var = tk.StringVar(value=self.current_user.get('last_name', ''))
            username_var = tk.StringVar(value=self.current_user.get('username', ''))

            tb.Label(frame, text="First Name:", font=("Segoe UI", 11)).pack(anchor="w")
            first_name_entry = tb.Entry(frame, textvariable=first_name_var)
            first_name_entry.pack(fill="x", pady=(0, 10))

            tb.Label(frame, text="Last Name:", font=("Segoe UI", 11)).pack(anchor="w")
            last_name_entry = tb.Entry(frame, textvariable=last_name_var)
            last_name_entry.pack(fill="x", pady=(0, 10))

            tb.Label(frame, text="Username:", font=("Segoe UI", 11)).pack(anchor="w")
            username_entry = tb.Entry(frame, textvariable=username_var)
            username_entry.pack(fill="x", pady=(0, 15))

            # Status label for feedback
            status_label = tb.Label(frame, text="", font=("Segoe UI", 10))
            status_label.pack(pady=(0, 15))

            def submit_edit():
                try:
                    # Clear previous status
                    status_label.configure(text="", foreground="")
                    
                    # Get and validate input
                    first_name = first_name_var.get().strip()
                    last_name = last_name_var.get().strip()
                    username = username_var.get().strip()
                    
                    # Basic validation
                    if not first_name and not last_name:
                        status_label.configure(text="❌ Please provide at least first or last name", foreground="red")
                        return
                    
                    if username and len(username) < 3:
                        status_label.configure(text="❌ Username must be at least 3 characters", foreground="red")
                        return
                    
                    # Show processing
                    status_label.configure(text="⏳ Updating profile...", foreground="blue")
                    modal.update()
                    
                    new_profile = {
                        'first_name': first_name,
                        'last_name': last_name,
                        'username': username
                    }
                    user_id = self.current_user.get('id')
                    success = backend_edit_profile(user_id, new_profile)
                    
                    if success:
                        status_label.configure(text="✅ Profile updated successfully!", foreground="green")
                        self.root.after(1500, modal.destroy)
                    else:
                        status_label.configure(text="❌ Failed to update profile", foreground="red")
                        
                except Exception as e:
                    status_label.configure(text=f"❌ Error: {str(e)}", foreground="red")

            # Buttons
            button_frame = tb.Frame(frame)
            button_frame.pack(fill="x", pady=(10, 0))
            
            tb.Button(button_frame, text="Cancel", command=modal.destroy, bootstyle="secondary").pack(side="right", padx=(10, 0))
            tb.Button(button_frame, text="Save Changes", command=submit_edit, bootstyle="success").pack(side="right")

            # Focus on first entry
            first_name_entry.focus_set()
            
            # Enter key binding
            def on_enter(event):
                submit_edit()
            
            modal.bind('<Return>', on_enter)

        # Create main profile window with admin-style design
        profile_modal = tb.Toplevel(self.root)
        profile_modal.title("User Profile - Client")
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
        
        # User information in modern grid layout (copied from Admin: include Last Login details)
        user_id = self.current_user.get('id', 'N/A')

        # Fetch last login info from server, retry if not found
        import time
        last_login_display = 'No login data yet'
        device_hostname = 'No login data yet'
        device_platform = 'No login data yet'
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if user_id != 'N/A':
                    resp = self.http.get(f"{base_url}/api/user/{user_id}/login-info", timeout=8)
                    if resp.status_code == 200:
                        info = resp.json()
                        ts = info.get('login_timestamp')
                        host = info.get('device_hostname')
                        plat = info.get('device_platform')
                        if ts:
                            last_login_display = ts
                        if host:
                            device_hostname = host
                        if plat:
                            device_platform = plat
                        if ts:
                            break  # Got valid login info, stop retrying
                if last_login_display == 'No login data yet':
                    time.sleep(0.5)  # Wait before retry
            except Exception:
                time.sleep(0.5)

        user_info_data = [
            ("🆔", "User ID", str(user_id) if user_id != 'N/A' else 'Unknown'),
            ("✅", "Account Status", "Active"),
            ("🕒", "Last Login", last_login_display),
            ("🖧", "Device Hostname", device_hostname),
            ("🖥️", "Device Platform", device_platform),
        ]
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
            ("🔒", "Change Password", "primary", open_change_password_modal),
            ("✏️", "Edit Profile", "success", open_edit_profile_modal),
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
        
        # Footer with modern styling
        footer_frame = tb.Frame(main_container)
        footer_frame.pack(fill="x", pady=(10, 0))
        footer_label = tb.Label(footer_frame, text="WinyFi © 2024. All rights reserved.",
                              font=("Segoe UI", 10), foreground="#9ca3af")
        footer_label.pack(anchor="w")

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
    
    def update_notification_count(self, force_refresh=False):
        """Update the notification count badge.
        
        Args:
            force_refresh: If True, forces a refresh (unused but accepted for compatibility)
        """
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

    # -------------------------------
    # Server health and API helpers
    # -------------------------------
    def _on_server_check_result(self, online: bool, error_msg=None):
        """Update UI and state when server connectivity changes."""
        # Always update on first check, or if status changes
        with self._server_status_lock:
            # If UI widgets aren't ready yet, just record the state and exit
            if not hasattr(self, 'server_status_label'):
                self.server_online = online
                return
            if not self._server_status_first_update or self.server_online != online:
                self._server_status_first_update = True
                self.server_online = online
                try:
                    if online:
                        self.server_status_label.config(text="● Server: Online", foreground="#28a745")
                        try:
                            self.export_btn.configure(state="normal")
                        except Exception:
                            pass
                        try:
                            notify_system_alert("Server connection restored.", priority=NotificationPriority.LOW)
                        except Exception:
                            pass
                        self._server_poll_backoff = 3
                    else:
                        msg = "● Server: Offline"
                        if error_msg:
                            msg += f" ({error_msg})"
                        self.server_status_label.config(text=msg, foreground="#dc3545")
                        try:
                            self.export_btn.configure(state="disabled")
                        except Exception:
                            pass
                        try:
                            notify_system_alert("Server connection lost. Some features are unavailable.", priority=NotificationPriority.MEDIUM)
                        except Exception:
                            pass
                except Exception as ex:
                    print(f"[ERROR] Exception in _on_server_check_result: {ex}")

    def start_server_health_monitor(self):
        """Background thread: poll /api/health with exponential backoff while offline."""
        def worker():
            backoff = self._server_poll_backoff
            while not self._health_stop_event.is_set():
                ok = False
                try:
                    resp = self.http.get(f"{self.api_base_url}/api/health", timeout=(0.8, 1.5))
                    ok = resp.status_code == 200
                except Exception:
                    ok = False
                finally:
                    try:
                        self.root.after(0, lambda v=ok: self._on_server_check_result(v))
                    except Exception:
                        pass

                if ok:
                    # wait with stop awareness
                    self._health_stop_event.wait(10)
                    backoff = 3
                else:
                    self._health_stop_event.wait(backoff)
                    backoff = min(self._server_poll_max, max(3, int(backoff * 2)))

        threading.Thread(target=worker, daemon=True).start()

    def _initial_server_check(self):
        """Initial server check with extra reliability for startup detection."""
        def startup_check():
            while True:
                # Always set to Offline before each check to avoid stuck status
                def set_offline():
                    # UI update on main thread; _on_server_check_result handles locking
                    try:
                        self.server_status_label.config(text="● Server: Offline", foreground="#dc3545")
                    except Exception:
                        pass
                self.root.after(0, set_offline)
                ok = False
                error_msg = None
                try:
                    resp = self.http.get(f"{self.api_base_url}/api/health", timeout=(1.0, 2.0))
                    ok = resp.status_code == 200
                except Exception as e:
                    ok = False
                    error_msg = str(e)
                def update_status():
                    # Let _on_server_check_result manage locking; keep UI responsive
                    try:
                        self._on_server_check_result(ok, error_msg=error_msg)
                        self.retry_btn.configure(state="normal")
                    except Exception as ex:
                        print(f"[ERROR] Exception in update_status: {ex}")
                        try:
                            self.server_status_label.config(text="● Server: Offline (UI error)", foreground="#dc3545")
                            self.retry_btn.configure(state="normal")
                        except Exception:
                            pass
                self.root.after(0, update_status)
                if ok:
                    self._server_poll_backoff = 3
                    break
                time.sleep(5)
        threading.Thread(target=startup_check, daemon=True).start()

    def check_server_now(self):
        """Manual retry that triggers an immediate one-shot health check without waiting for the loop."""
        try:
            # Always set to Offline before each check to avoid stuck status
            self.server_status_label.config(text="● Server: Offline", foreground="#dc3545")
            self.server_status_label.config(text="● Server: Checking…", foreground="#6c757d")
            self.retry_btn.configure(state="disabled")
        except Exception:
            pass
        def one_shot():
            ok = False
            error_msg = None
            try:
                resp = self.http.get(f"{self.api_base_url}/api/health", timeout=(0.8, 1.5))
                ok = resp.status_code == 200
            except Exception as e:
                ok = False
                error_msg = str(e)
            finally:
                def finish():
                    try:
                        if ok:
                            self._on_server_check_result(True)
                        else:
                            msg = "● Server: Offline"
                            if error_msg:
                                msg += f" ({error_msg})"
                            try:
                                self.server_status_label.config(text=msg, foreground="#dc3545")
                            except Exception:
                                pass
                            self._on_server_check_result(False, error_msg=error_msg)
                        self.retry_btn.configure(state="normal")
                    except Exception as ex:
                        try:
                            self.server_status_label.config(text="● Server: Offline (UI error)", foreground="#dc3545")
                            self.retry_btn.configure(state="normal")
                        except Exception:
                            pass
                self.root.after(0, finish)
            if ok:
                self._server_poll_backoff = 3
        threading.Thread(target=one_shot, daemon=True).start()

    def api_get(self, path, *, timeout=(3, 10), raise_for_status=True, show_errors=True):
        """Centralized GET with connectivity tracking. Returns Response or None."""
        try:
            resp = self.http.get(f"{self.api_base_url}{path}", timeout=timeout)
            self._on_server_check_result(True)
            if raise_for_status:
                resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as e:
            self._on_server_check_result(False, error_msg=str(e))
            if show_errors:
                try:
                    messagebox.showerror("Connection Error", f"Unable to reach server. Please check your connection.\n\nDetails: {e}")
                except Exception:
                    pass
            return None

    def api_post(self, path, *, json=None, timeout=(3, 10), raise_for_status=False, show_errors=True):
        """Centralized POST with connectivity tracking. Returns Response or None."""
        try:
            resp = self.http.post(f"{self.api_base_url}{path}", json=json, timeout=timeout)
            self._on_server_check_result(True)
            if raise_for_status:
                resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as e:
            self._on_server_check_result(False, error_msg=str(e))
            if show_errors:
                try:
                    messagebox.showerror("Connection Error", f"Unable to reach server. Please check your connection.\n\nDetails: {e}")
                except Exception:
                    pass
            return None
    
    def start_router_status_monitoring(self):
        """Start monitoring router status changes."""
        def monitor_router_status():
            import requests
            while self.status_monitoring_running:
                try:
                    # Get routers from API
                    response = self.api_get("/api/routers", timeout=(2, 5), show_errors=False)
                    if response is not None and response.ok:
                        routers = response.json() or []
                        for router in routers:
                            router_id = router.get('id')
                            router_name = router.get('name', f'Router {router_id}')
                            router_ip = router.get('ip_address', 'Unknown')
                            # Fetch real-time status from backend
                            status_resp = None
                            try:
                                status_resp = requests.get(f"{self.api_base_url}/api/routers/{router_id}/status", timeout=3)
                                if status_resp.status_code == 200:
                                    status_json = status_resp.json()
                                    is_online = status_json.get('is_online', False)
                                else:
                                    is_online = False
                            except Exception:
                                is_online = False
                            # Check for status change
                            if router_id in self.router_status_history:
                                prev_status = self.router_status_history[router_id]
                                if prev_status != is_online:
                                    self.root.after(0, lambda: self._create_router_notification(router_name, router_ip, is_online))
                                    self.root.after(0, self.update_notification_count)
                            self.router_status_history[router_id] = is_online
                    time.sleep(30)
                except Exception as e:
                    print(f"Error in router status monitoring: {e}")
                    time.sleep(30)
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
        try:
            self._health_stop_event.set()
        except Exception:
            pass

    def on_close(self):
        """Confirm and exit the entire application when the Client window is closed."""
        if not messagebox.askyesno("Exit", "Are you sure you want to exit?"):
            return

        # Stop background monitoring
        try:
            self.stop_router_status_monitoring()
        except Exception:
            pass

        # Destroy this window
        try:
            self.root.destroy()
        except Exception:
            pass

        # Also destroy the hidden login root if present
        try:
            master = getattr(self.root, 'master', None)
            if master and master.winfo_exists():
                master.destroy()
        except Exception:
            pass

        # Hard-exit fallback to ensure full termination
        try:
            import os
            os._exit(0)
        except Exception:
            pass

    def logout(self):
        """Handle user logout"""
        if not messagebox.askyesno("Logout", "Are you sure you want to logout?"):
            return

        # Log logout activity via API
        try:
            # Include last known local IP from device utils if available
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
            payload = {"user_id": self.current_user.get('id')}
            if local_ip and local_ip not in ("127.0.0.1", "::1"):
                payload["device_ip"] = local_ip
            self.http.post(f"{self.api_base_url}/api/logout", json=payload, timeout=2)
        except Exception:
            pass

        # Stop any background monitoring
        try:
            self.stop_router_status_monitoring()
        except Exception:
            pass

        # Close the client window
        master = getattr(self.root, 'master', None)
        try:
            self.root.destroy()
        except Exception:
            pass

        # Return to login screen on the hidden root
        try:
            if master and master.winfo_exists():
                try:
                    master.deiconify()
                except Exception:
                    pass
                # Clear any previous children and show login
                for child in master.winfo_children():
                    try:
                        child.destroy()
                    except Exception:
                        pass
                from login import show_login
                show_login(master)
        except Exception:
            pass



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

        # Aggregation mode for reports
        tb.Label(reports_frame, text="Aggregation:").grid(row=1, column=0, sticky="w", pady=(5, 0))
        mode_var = tb.StringVar(value="weekly")
        mode_combo = ttk.Combobox(reports_frame, textvariable=mode_var, state="readonly", values=["daily", "weekly", "monthly"], width=10)
        mode_combo.grid(row=1, column=1, sticky="w", padx=(6, 15), pady=(5, 0))

        def _toggle_reports_options(*_):
            # Only toggle interactive widgets; frames/labels might not support 'state'
            try:
                if export_var.get() == "reports":
                    start_picker.configure(state="normal")
                    end_picker.configure(state="normal")
                    mode_combo.configure(state="readonly")
                else:
                    start_picker.configure(state="disabled")
                    end_picker.configure(state="disabled")
                    mode_combo.configure(state="disabled")
            except Exception:
                # Widget already destroyed, remove trace
                pass

        trace_id = export_var.trace_add("write", _toggle_reports_options)
        _toggle_reports_options()
        
        # Clean up trace when modal is destroyed to prevent errors
        def _cleanup_trace():
            try:
                export_var.trace_remove("write", trace_id)
            except Exception:
                pass
        
        modal.bind("<Destroy>", lambda e: _cleanup_trace())

        # Footer buttons
        btns = tb.Frame(outer)
        btns.pack(fill="x", pady=(15, 0))

        def do_export():
            etype = export_var.get()
            # Extract date range and mode for reports
            start_dt = end_dt = None
            mode = None
            if etype == "reports":
                try:
                    from datetime import datetime
                    s = start_picker.entry.get().strip()
                    e = end_picker.entry.get().strip()
                    # Try 4-digit year first, then 2-digit year
                    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
                        try:
                            start_dt = datetime.strptime(s, fmt)
                            end_dt = datetime.strptime(e, fmt)
                            break
                        except Exception:
                            start_dt = end_dt = None
                    if not start_dt or not end_dt:
                        raise ValueError("Invalid date format")
                except Exception:
                    messagebox.showerror("Date Error", "Please use MM/DD/YYYY format for dates.")
                    return
                mode = (mode_var.get() or "weekly").lower()
            # Kick off async export with progress
            modal.destroy()
            self.start_export_async(etype, start_dt, end_dt, mode)

        tb.Button(btns, text="Cancel", bootstyle="secondary", command=modal.destroy).pack(side="right")
        tb.Button(btns, text="Export", bootstyle="primary", command=do_export).pack(side="right", padx=(0, 8))

    def export_to_csv(self, export_type="routers"):
        """Export routers, reports, or tickets to CSV using server APIs only (client-safe)."""
        from tkinter import filedialog, messagebox
        from datetime import datetime, timedelta

        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )
        if not file_path:
            return

        data = []
        fieldnames = []

        try:
            if export_type == "routers":
                # Fetch from server API
                resp = requests.get(f"{self.api_base_url}/api/routers", timeout=(10, 60))
                resp.raise_for_status()
                routers = resp.json() or []
                fieldnames = ['id', 'name', 'ip_address', 'mac_address', 'brand', 'location', 'last_seen', 'image_path']
                data = routers

            elif export_type == "reports":
                # Parse dates from pickers and convert to server format YYYY-MM-DD
                try:
                    start_dt = datetime.strptime(self.start_date.entry.get(), "%m/%d/%Y")
                except Exception:
                    start_dt = datetime.now() - timedelta(days=30)
                try:
                    end_dt = datetime.strptime(self.end_date.entry.get(), "%m/%d/%Y")
                except Exception:
                    end_dt = datetime.now()

                # Guard against very large ranges that may timeout server-side
                try:
                    range_days = (end_dt.date() - start_dt.date()).days + 1
                    if range_days > 60:
                        if not messagebox.askyesno(
                            "Large Date Range",
                            f"You're exporting {range_days} days of data. This may take a while and could time out.\n\nContinue?"
                        ):
                            return
                except Exception:
                    pass

                start_q = start_dt.strftime("%Y-%m-%d")
                end_q = end_dt.strftime("%Y-%m-%d")

                # Call server reports endpoint
                url = f"{self.api_base_url}/api/reports/uptime"
                params = {"start_date": start_q, "end_date": end_q, "mode": "daily"}

                # Show busy cursor during potentially long request
                try:
                    self.root.config(cursor="watch")
                    self.root.update_idletasks()
                except Exception:
                    pass

                try:
                    # First attempt with moderate timeout
                    resp = requests.get(url, params=params, timeout=(10, 60))
                    resp.raise_for_status()
                except requests.exceptions.ReadTimeout:
                    # Retry once with a longer timeout
                    try:
                        resp = requests.get(url, params=params, timeout=(10, 120))
                        resp.raise_for_status()
                    except requests.exceptions.ReadTimeout:
                        messagebox.showerror(
                            "Timeout",
                            "The server took too long to generate the report (timeout at 60s).\n\n"
                            "Tip: Try a shorter date range (e.g., last 7–30 days) and try again."
                        )
                        return
                finally:
                    try:
                        self.root.config(cursor="")
                    except Exception:
                        pass
                payload = resp.json() or {}
                report_rows = payload.get("report_data", [])

                fieldnames = ["router", "uptime_percent", "downtime_hours", "bandwidth_mb"]

                # Compute downtime hours locally from server's uptime percentage
                total_hours = (end_dt - start_dt).total_seconds() / 3600.0
                for row in report_rows:
                    name = row.get("router_name") or f"Router {row.get('router_id')}"
                    uptime = float(row.get("uptime_percentage") or 0.0)
                    bandwidth_mb = float(row.get("bandwidth_mb") or 0.0)
                    downtime_hours = round((100.0 - uptime) / 100.0 * total_hours, 2)
                    data.append({
                        "router": name,
                        "uptime_percent": round(uptime, 2),
                        "downtime_hours": downtime_hours,
                        "bandwidth_mb": round(bandwidth_mb, 2)
                    })

            elif export_type == "tickets":
                # Export ICT Service Requests via API
                fieldnames = ["ict_srf_no", "campus", "services", "status", "created_by", "created_at", "updated_at"]
                try:
                    resp = requests.get(f"{self.api_base_url}/api/srfs", timeout=(10, 60))
                    resp.raise_for_status()
                    srfs = resp.json() or []
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to fetch service requests from API: {e}")
                    return

                def fmt(dt):
                    try:
                        return dt.strftime("%Y-%m-%d %H:%M:%S") if hasattr(dt, 'strftime') else str(dt)
                    except Exception:
                        return str(dt)

                for srf in srfs:
                    data.append({
                        "ict_srf_no": srf.get("ict_srf_no"),
                        "campus": srf.get("campus", ""),
                        "services": (srf.get("services_requirements", "") or "").strip().replace("\n", " ")[:200],
                        "status": srf.get("status", "open"),
                        "created_by": srf.get("created_by_username", "Unknown"),
                        "created_at": fmt(srf.get("created_at")),
                        "updated_at": fmt(srf.get("updated_at"))
                    })

            else:
                messagebox.showerror("Error", f"Unknown export type: {export_type}")
                return

            # Write to CSV
            with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for row in data:
                    writer.writerow(row)
            messagebox.showinfo("Export", f"{export_type.capitalize()} exported successfully!")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export CSV:\n{e}")
    def start_export_async(self, export_type, start_dt=None, end_dt=None, mode=None):
        """Start export in a background thread and show a progress dialog to keep UI responsive."""
        from tkinter import filedialog
        # Ask for target file first (on main thread) to avoid dialogs in worker thread
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )
        if not file_path:
            return

        # Create progress modal
        cancel_event = threading.Event()
        prog = tb.Toplevel(self.root)
        prog.title("Exporting…")
        prog.geometry("360x140")
        prog.resizable(False, False)
        prog.transient(self.root)
        prog.grab_set()
        frame = tb.Frame(prog, padding=15)
        frame.pack(fill="both", expand=True)
        lbl = tb.Label(frame, text="Contacting server…", font=("Segoe UI", 11))
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
                # Stage 1: fetch data and write file using existing method adapted for parameters
                if export_type == "routers":
                    # Fetch routers
                    lbl.after(0, lambda: lbl.config(text="Fetching routers…"))
                    resp = requests.get(f"{self.api_base_url}/api/routers", timeout=(10, 60))
                    resp.raise_for_status()
                    routers = resp.json() or []
                    fieldnames = ['id', 'name', 'ip_address', 'mac_address', 'brand', 'location', 'last_seen', 'image_path']
                    rows = routers
                elif export_type == "tickets":
                    lbl.after(0, lambda: lbl.config(text="Fetching tickets…"))
                    resp = requests.get(f"{self.api_base_url}/api/srfs", timeout=(10, 60))
                    resp.raise_for_status()
                    srfs = resp.json() or []
                    fieldnames = ["ict_srf_no", "campus", "services", "status", "created_by", "created_at", "updated_at"]
                    def fmt(dt):
                        try:
                            return dt.strftime("%Y-%m-%d %H:%M:%S") if hasattr(dt, 'strftime') else str(dt)
                        except Exception:
                            return str(dt)
                    rows = [{
                        "ict_srf_no": s.get("ict_srf_no"),
                        "campus": s.get("campus", ""),
                        "services": (s.get("services_requirements", "") or "").strip().replace("\n", " ")[:200],
                        "status": s.get("status", "open"),
                        "created_by": s.get("created_by_username", "Unknown"),
                        "created_at": fmt(s.get("created_at")),
                        "updated_at": fmt(s.get("updated_at"))
                    } for s in srfs]
                else:  # reports
                    from datetime import datetime
                    sdt = start_dt or (datetime.now() - timedelta(days=30))
                    edt = end_dt or datetime.now()
                    # Warn for very large ranges
                    try:
                        range_days = (edt.date() - sdt.date()).days + 1
                        if range_days > 60 and not cancel_event.is_set():
                            lbl.after(0, lambda: lbl.config(text=f"Large range: {range_days} days…"))
                    except Exception:
                        pass
                    start_q = sdt.strftime('%Y-%m-%d')
                    end_q = edt.strftime('%Y-%m-%d')
                    m = (mode or 'weekly').lower()
                    lbl.after(0, lambda: lbl.config(text="Generating report on server…"))
                    try:
                        resp = requests.get(
                            f"{self.api_base_url}/api/reports/uptime",
                            params={"start_date": start_q, "end_date": end_q, "mode": m},
                            timeout=(10, 120)
                        )
                        resp.raise_for_status()
                    except requests.exceptions.ReadTimeout:
                        self.root.after(0, lambda: on_done(False, "Timeout while generating report. Try a shorter range or a coarser aggregation (weekly/monthly)."))
                        return
                    payload = resp.json() or {}
                    report_rows = payload.get("report_data", [])
                    fieldnames = ["router", "uptime_percent", "downtime_hours", "bandwidth_mb"]
                    total_hours = (edt - sdt).total_seconds() / 3600.0
                    rows = []
                    for row in report_rows:
                        if cancel_event.is_set():
                            break
                        name = row.get("router_name") or f"Router {row.get('router_id')}"
                        uptime = float(row.get("uptime_percentage") or 0.0)
                        bandwidth_mb = float(row.get("bandwidth_mb") or 0.0)
                        downtime_hours = round((100.0 - uptime) / 100.0 * total_hours, 2)
                        rows.append({
                            "router": name,
                            "uptime_percent": round(uptime, 2),
                            "downtime_hours": downtime_hours,
                            "bandwidth_mb": round(bandwidth_mb, 2)
                        })

                if cancel_event.is_set():
                    self.root.after(0, lambda: on_done(False, "Export cancelled."))
                    return

                # Stage 2: write file
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
                    self.root.after(0, lambda e=e: on_done(False, f"Failed to write file: {e}"))
                    return

                if cancel_event.is_set():
                    self.root.after(0, lambda: on_done(False, "Export cancelled."))
                else:
                    self.root.after(0, lambda: on_done(True, f"{export_type.capitalize()} exported successfully!"))

            except Exception as e:
                self.root.after(0, lambda e=e: on_done(False, f"Export failed: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    # -------------------------------
    # ICT Service Requests (Client)
    # -------------------------------
    def open_ticket_window(self):
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
            command=self.open_new_ticket_modal
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
        self.load_tickets()
        self.tickets_table.bind("<Double-1>", self._on_ticket_row_click)

        # Auto-refresh
        self.root.after(5000, self.auto_refresh_tickets)

    def load_tickets(self, status=None):
        """Fetch SRFs from API and display in the table (optionally filter by status)."""
        if not hasattr(self, 'tickets_table'):
            return
        self.tickets_table.delete(*self.tickets_table.get_children())
        resp = self.api_get("/api/srfs", timeout=(3, 8), show_errors=False)
        if resp is None:
            messagebox.showerror("Server Offline", "Cannot load tickets because the server is unreachable.")
            return
        try:
            srfs = resp.json() or []
        except Exception as e:
            messagebox.showerror("Error", f"Invalid response from server: {e}")
            return

        # Optional filter: client view could show all or only self-created
        user_id = self.current_user.get('id') if self.current_user else None
        for srf in srfs:
            if status and srf.get('status') != status:
                continue
            # Example: show all; to restrict to own tickets, uncomment next 2 lines
            # if user_id and srf.get('created_by') != user_id:
            #     continue

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

    def collect_ticket_form_data(self):
        """Collect values from SRF form fields built by build_ticket_form."""
        data = {k: v.get() for k, v in getattr(self, 'form_vars', {}).items()}
        if hasattr(self, 'service_req_text'):
            data["services_requirements"] = self.service_req_text.get("1.0", "end").strip()
        if hasattr(self, 'remarks_text'):
            data["remarks"] = self.remarks_text.get("1.0", "end").strip()
        return data

    def auto_refresh_tickets(self, interval=5000):
        """Auto refresh ticket table periodically."""
        self.load_tickets()
        self.root.after(interval, self.auto_refresh_tickets)

    def _on_ticket_row_click(self, event):
        selected_item = self.tickets_table.selection()
        if not selected_item:
            return
        ticket_id = self.tickets_table.item(selected_item[0])["values"][0]
        self.open_ticket_detail_modal(ticket_id)

    def build_ticket_form(self, modal, initial_data=None, is_edit=False):
        """Reusable SRF form builder for client. Returns container for action buttons."""
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

        # Smooth scrolling (widget-scoped, avoids global bind_all)
        def _on_mousewheel(event):
            try:
                if event.delta:
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except tk.TclError:
                pass
        canvas.bind("<MouseWheel>", _on_mousewheel)
        canvas.bind("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

        def _cleanup_scroll_bindings():
            try:
                canvas.unbind("<MouseWheel>")
                canvas.unbind("<Button-4>")
                canvas.unbind("<Button-5>")
            except Exception:
                pass
        modal.bind("<Destroy>", lambda e: _cleanup_scroll_bindings(), add="+")

        # Header with logo
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

        tb.Label(scrollable_frame, text="ICT SERVICE REQUEST FORM", font=("Segoe UI", 14, "bold")).pack(fill="x", pady=(10, 20), padx=20)

        form_frame = tb.Frame(scrollable_frame)
        form_frame.pack(fill="both", expand=True, padx=20)
        for col in range(4):
            form_frame.columnconfigure(col, weight=1)

        # Variables
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

        self.service_req_text = tb.Text(form_frame, height=4, wrap="word")
        self.remarks_text = tb.Text(form_frame, height=4, wrap="word")
        if is_edit:
            self.service_req_text.insert("1.0", initial_data.get("services_requirements", ""))
            self.remarks_text.insert("1.0", initial_data.get("remarks", ""))

        vcmd = self.root.register(lambda P: P.isdigit() or P == "")

        def add_row(label1, key1, label2=None, key2=None, row_idx=0, numeric2=False):
            tb.Label(form_frame, text=label1, anchor="w").grid(row=row_idx, column=0, sticky="w", padx=5, pady=5)
            tb.Entry(form_frame, textvariable=self.form_vars[key1]).grid(row=row_idx, column=1, sticky="ew", padx=5, pady=5)
            if label2 and key2:
                tb.Label(form_frame, text=label2, anchor="w").grid(row=row_idx, column=2, sticky="w", padx=5, pady=5)
                e = tb.Entry(form_frame, textvariable=self.form_vars[key2], validate="key", validatecommand=(vcmd, "%P")) if numeric2 else tb.Entry(form_frame, textvariable=self.form_vars[key2])
                e.grid(row=row_idx, column=3, sticky="ew", padx=5, pady=5)

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

        return scrollable_frame

    def open_new_ticket_modal(self):
        """Open modal for creating a new SRF."""
        modal = tb.Toplevel(self.root)
        modal.title("ICT Service Request Form")
        modal.geometry("725x600")
        modal.resizable(False, False)
        modal.grab_set()

        button_host = self.build_ticket_form(modal)
        tb.Button(
            button_host,
            text="Submit Ticket",
            bootstyle="primary",
            command=lambda: self.submit_new_ticket(modal)
        ).pack(pady=20)

    def submit_new_ticket(self, modal):
        """Submit the SRF via API server."""
        data = self.collect_ticket_form_data()
        if not data.get("ict_srf_no"):
            messagebox.showerror("Validation", "ICT SRF No. is required and must be numeric.")
            return
        try:
            created_by = (self.current_user or {}).get('id')
            payload = {"created_by": int(created_by) if created_by else 1, "data": data}
            resp = self.api_post("/api/srfs", json=payload, timeout=(3, 10), show_errors=False)
            if resp and resp.ok:
                messagebox.showinfo("Success", "Service Request submitted successfully!")
                modal.destroy()
                self.load_tickets()
            else:
                if resp is None:
                    messagebox.showerror("Server Offline", "Cannot submit ticket because the server is unreachable.")
                else:
                    messagebox.showerror("Error", f"Ticket submission failed: {resp.text}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to submit ticket: {e}")

    def open_ticket_detail_modal(self, srf_no):
        """Open a modal showing SRF details in printable form layout (read-only for client)."""
        try:
            resp = self.api_get("/api/srfs", timeout=(3, 8), show_errors=False)
            if resp is None:
                messagebox.showerror("Server Offline", "Cannot load SRF details because the server is unreachable.")
                return
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

        # Header with logo
        header_frame = tb.Frame(modal)
        header_frame.pack(fill="x", pady=10)
        logo_path = "assets/images/bsu_logo.png"
        try:
            img = Image.open(logo_path).resize((60, 60))
            logo_img = ImageTk.PhotoImage(img)
            logo_label = tb.Label(header_frame, image=logo_img)
            logo_label.image = logo_img
            logo_label.pack(side="left", padx=10)
        except Exception:
            tb.Label(header_frame, text="LOGO", width=10, relief="solid").pack(side="left", padx=10)

        tb.Label(header_frame, text="ICT SERVICE REQUEST FORM", font=("Segoe UI", 16, "bold")).pack(side="left", padx=20)

        # SRF number
        tb.Label(modal, text=f"SRF No: {srf.get('ict_srf_no')}", font=("Segoe UI", 12, "bold")).pack(pady=5)

        # Sections
        form_frame = tb.Frame(modal, padding=10)
        form_frame.pack(fill="both", expand=True)

        tb.Label(form_frame, text="Request Information", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", pady=5, columnspan=2)
        tb.Label(form_frame, text=f"Campus: {srf.get('campus','')}").grid(row=1, column=0, sticky="w", padx=10)
        tb.Label(form_frame, text=f"Office/Building: {srf.get('office_building','')}").grid(row=2, column=0, sticky="w", padx=10)
        tb.Label(form_frame, text=f"Client: {srf.get('client_name','')}").grid(row=3, column=0, sticky="w", padx=10)
        tb.Label(form_frame, text=f"Date/Time of Call: {srf.get('date_time_call','')}").grid(row=4, column=0, sticky="w", padx=10)

        tb.Label(form_frame, text="Technician & Services", font=("Segoe UI", 12, "bold")).grid(row=5, column=0, sticky="w", pady=5, columnspan=2)
        tb.Label(form_frame, text=f"Technician: {srf.get('technician_assigned','')}").grid(row=6, column=0, sticky="w", padx=10)
        tb.Label(form_frame, text=f"Services: {srf.get('services_requirements','')}").grid(row=7, column=0, sticky="w", padx=10)

        tb.Label(form_frame, text="Status & Remarks", font=("Segoe UI", 12, "bold")).grid(row=8, column=0, sticky="w", pady=5, columnspan=2)
        tb.Label(form_frame, text=f"Status: {srf.get('status','open')}").grid(row=9, column=0, sticky="w", padx=10)
        tb.Label(form_frame, text=f"Remarks: {srf.get('remarks','')}").grid(row=10, column=0, sticky="w", padx=10)

        tb.Label(form_frame, text="System Info", font=("Segoe UI", 12, "bold")).grid(row=11, column=0, sticky="w", pady=5, columnspan=2)
        tb.Label(form_frame, text=f"Created by: {srf.get('created_by_username','Unknown')}").grid(row=12, column=0, sticky="w", padx=10)
        tb.Label(form_frame, text=f"Created at: {srf.get('created_at','')}").grid(row=13, column=0, sticky="w", padx=10)
        tb.Label(form_frame, text=f"Updated at: {srf.get('updated_at','-')}").grid(row=14, column=0, sticky="w", padx=10)

        # Buttons
        btn_frame = tb.Frame(modal)
        btn_frame.pack(pady=15)
        tb.Button(
            modal,
            text="🖨 Print",
            bootstyle="secondary",
            command=lambda: print_srf_form(srf, logo_path="assets/images/bsu_logo.png")
        ).pack(pady=10)


def show_client_window(root, current_user):
    ClientDashboard(root, current_user)


