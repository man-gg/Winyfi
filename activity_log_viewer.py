import ttkbootstrap as tb
from tkinter import ttk, messagebox
import tkinter as tk
from datetime import datetime
from db import get_activity_logs, get_activity_stats


class ActivityLogViewer:
    """Activity Log Viewer - Shows admin activity logs with search and filter"""
    
    def __init__(self, parent, current_user):
        self.parent = parent
        self.current_user = current_user
        self.window = None
        self.tree = None
        self.search_var = None
        self.action_filter_var = None
        self.logs_data = []
        
    def show(self):
        """Display the activity log viewer window"""
        # Create modal window
        self.window = tb.Toplevel(self.parent)
        self.window.title("📋 Activity Log")
        self.window.geometry("1100x700")
        self.window.transient(self.parent)
        self.window.grab_set()
        
        # Center window
        self._center_window(self.window, 1100, 700)
        
        # Build UI
        self._build_ui()
        
        # Load initial data
        self.refresh_logs()
        
    def _center_window(self, window, width, height):
        """Center window on screen"""
        window.update_idletasks()
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        window.geometry(f"{width}x{height}+{x}+{y}")
        
    def _build_ui(self):
        """Build the activity log viewer UI"""
        # Header
        header_frame = tb.Frame(self.window)
        header_frame.pack(fill="x", padx=20, pady=(20, 0))
        
        tb.Label(header_frame, text="📋 Activity Log", 
                font=("Segoe UI", 18, "bold"), bootstyle="primary").pack(anchor="w")
        tb.Label(header_frame, text="View and search system activity logs", 
                font=("Segoe UI", 11), bootstyle="secondary").pack(anchor="w", pady=(5, 0))
        
        # Statistics cards
        self._build_stats_cards()
        
        # Controls frame
        controls_frame = tb.LabelFrame(self.window, text="🔍 Search & Filter", 
                                      bootstyle="info", padding=15)
        controls_frame.pack(fill="x", padx=20, pady=(15, 0))
        
        # Search bar
        search_row = tb.Frame(controls_frame)
        search_row.pack(fill="x", pady=(0, 10))
        
        tb.Label(search_row, text="Search:", font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 10))
        
        self.search_var = tb.StringVar()
        search_entry = tb.Entry(search_row, textvariable=self.search_var, 
                               font=("Segoe UI", 10), width=30)
        search_entry.pack(side="left", padx=(0, 10))
        
        tb.Button(search_row, text="🔍 Search", bootstyle="info", 
                 command=self.refresh_logs, width=10).pack(side="left", padx=(0, 5))
        tb.Button(search_row, text="🔄 Clear", bootstyle="secondary", 
                 command=self.clear_search, width=10).pack(side="left")
        
        # Filter row
        filter_row = tb.Frame(controls_frame)
        filter_row.pack(fill="x")
        
        tb.Label(filter_row, text="Filter by Action:", font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 10))
        
        self.action_filter_var = tb.StringVar(value="All")
        action_combo = tb.Combobox(filter_row, textvariable=self.action_filter_var,
                                  values=["All", "Login", "Logout", "Add Router", "Edit Router", 
                                         "Delete Router", "Add User", "Edit User", "Delete User"],
                                  state="readonly", width=20, font=("Segoe UI", 10))
        action_combo.pack(side="left", padx=(0, 10))
        action_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_logs())
        
        # Refresh button
        tb.Button(filter_row, text="🔄 Refresh All", bootstyle="success", 
                 command=self.refresh_logs, width=12).pack(side="right")
        
        # Table frame
        table_frame = tb.LabelFrame(self.window, text="📊 Activity Records", 
                                   bootstyle="primary", padding=15)
        table_frame.pack(fill="both", expand=True, padx=20, pady=(15, 0))
        
        # Scrollbars
        tree_scroll_y = tb.Scrollbar(table_frame, orient="vertical", bootstyle="primary")
        tree_scroll_y.pack(side="right", fill="y")
        
        tree_scroll_x = tb.Scrollbar(table_frame, orient="horizontal", bootstyle="primary")
        tree_scroll_x.pack(side="bottom", fill="x")
        
        # Treeview
        columns = ("ID", "Timestamp", "User", "Action", "Target", "IP Address")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings",
                                yscrollcommand=tree_scroll_y.set,
                                xscrollcommand=tree_scroll_x.set,
                                height=18)
        
        tree_scroll_y.config(command=self.tree.yview)
        tree_scroll_x.config(command=self.tree.xview)
        
        # Configure columns
        self.tree.heading("ID", text="ID", command=lambda: self.sort_column("ID"))
        self.tree.heading("Timestamp", text="Timestamp", command=lambda: self.sort_column("Timestamp"))
        self.tree.heading("User", text="User", command=lambda: self.sort_column("User"))
        self.tree.heading("Action", text="Action", command=lambda: self.sort_column("Action"))
        self.tree.heading("Target", text="Target", command=lambda: self.sort_column("Target"))
        self.tree.heading("IP Address", text="IP Address", command=lambda: self.sort_column("IP Address"))
        
        self.tree.column("ID", width=50, anchor="center")
        self.tree.column("Timestamp", width=160, anchor="center")
        self.tree.column("User", width=180, anchor="w")
        self.tree.column("Action", width=150, anchor="w")
        self.tree.column("Target", width=200, anchor="w")
        self.tree.column("IP Address", width=140, anchor="center")
        
        self.tree.pack(fill="both", expand=True)
        
        # Bind double-click event to show details
        self.tree.bind("<Double-1>", self.show_activity_details)
        
        # Status bar
        status_frame = tb.Frame(self.window)
        status_frame.pack(fill="x", padx=20, pady=(10, 20))
        
        self.status_label = tb.Label(status_frame, text="Ready", 
                                     font=("Segoe UI", 10), bootstyle="secondary")
        self.status_label.pack(side="left")
        
        # Close button
        tb.Button(status_frame, text="Close", bootstyle="secondary", 
                 command=self.window.destroy, width=10).pack(side="right")
        
    def _build_stats_cards(self):
        """Build statistics cards"""
        stats_frame = tb.Frame(self.window)
        stats_frame.pack(fill="x", padx=20, pady=(15, 0))
        
        try:
            stats = get_activity_stats()
            
            # Total Activities Card
            card1 = tb.LabelFrame(stats_frame, text="📊 Total Activities", 
                                 bootstyle="info", padding=10)
            card1.pack(side="left", fill="x", expand=True, padx=(0, 5))
            
            tb.Label(card1, text=str(stats['total']), 
                    font=("Segoe UI", 24, "bold"), bootstyle="info").pack()
            
            # Recent Activities Card (24h)
            card2 = tb.LabelFrame(stats_frame, text="🕐 Last 24 Hours", 
                                 bootstyle="success", padding=10)
            card2.pack(side="left", fill="x", expand=True, padx=(5, 5))
            
            tb.Label(card2, text=str(stats['recent_24h']), 
                    font=("Segoe UI", 24, "bold"), bootstyle="success").pack()
            
            # Most Common Action Card
            card3 = tb.LabelFrame(stats_frame, text="⭐ Most Common", 
                                 bootstyle="warning", padding=10)
            card3.pack(side="left", fill="x", expand=True, padx=(5, 0))
            
            most_common = stats['by_action'][0]['action'] if stats['by_action'] else "N/A"
            tb.Label(card3, text=most_common, 
                    font=("Segoe UI", 14, "bold"), bootstyle="warning").pack()
            
        except Exception as e:
            print(f"Error building stats cards: {e}")
            
    def refresh_logs(self):
        """Refresh the activity logs table"""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Get filter values
        search_term = self.search_var.get().strip() if self.search_var else ""
        action_filter = self.action_filter_var.get() if self.action_filter_var else "All"
        
        # Build filter
        filter_action = None if action_filter == "All" else action_filter
        
        try:
            # Fetch logs
            self.logs_data = get_activity_logs(
                limit=500,
                action_filter=filter_action,
                search_term=search_term if search_term else None
            )
            
            # Populate table
            for log in self.logs_data:
                log_id = log.get('id', '')
                timestamp = log.get('timestamp', '')
                if isinstance(timestamp, datetime):
                    timestamp = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                
                user_name = log.get('user_name', 'Unknown')
                username = log.get('username', '')
                user_display = f"{user_name} ({username})" if username else user_name
                
                action = log.get('action', '')
                target = log.get('target', '-')
                ip_address = log.get('ip_address', '-')
                
                self.tree.insert("", "end", values=(
                    log_id, timestamp, user_display, action, target, ip_address
                ))
            
            # Update status
            count = len(self.logs_data)
            self.status_label.config(text=f"Showing {count} record(s)")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load activity logs:\n{str(e)}")
            self.status_label.config(text="Error loading logs")
            
    def clear_search(self):
        """Clear search and filter"""
        if self.search_var:
            self.search_var.set("")
        if self.action_filter_var:
            self.action_filter_var.set("All")
        self.refresh_logs()
        
    def sort_column(self, col):
        """Sort table by column"""
        try:
            # Get current data
            data = [(self.tree.set(item, col), item) for item in self.tree.get_children("")]
            
            # Sort data
            data.sort(reverse=False)
            
            # Rearrange items in sorted order
            for index, (val, item) in enumerate(data):
                self.tree.move(item, "", index)
                
        except Exception as e:
            print(f"Error sorting column: {e}")
    
    def show_activity_details(self, event):
        """Show detailed information about the selected activity log entry"""
        # Get selected item
        selection = self.tree.selection()
        if not selection:
            return
        
        # Get the values from the selected row
        item = selection[0]
        values = self.tree.item(item, "values")
        
        if not values:
            return
        
        log_id, timestamp, user, action, target, ip_address = values
        
        # Find the full log data
        log_data = None
        for log in self.logs_data:
            if str(log.get('id')) == str(log_id):
                log_data = log
                break
        
        # Create details window
        details_window = tb.Toplevel(self.window)
        details_window.title(f"📋 Activity Log Details - ID #{log_id}")
        details_window.geometry("600x500")
        details_window.transient(self.window)
        details_window.grab_set()
        
        # Center the window
        self._center_window(details_window, 600, 500)
        
        # Header
        header_frame = tb.Frame(details_window)
        header_frame.pack(fill="x", padx=20, pady=(20, 0))
        
        tb.Label(header_frame, text=f"Activity Log Details", 
                font=("Segoe UI", 16, "bold"), bootstyle="primary").pack(anchor="w")
        tb.Label(header_frame, text=f"Log ID: #{log_id}", 
                font=("Segoe UI", 11), bootstyle="secondary").pack(anchor="w", pady=(5, 0))
        
        # Details container with scrollbar
        details_container = tb.Frame(details_window)
        details_container.pack(fill="both", expand=True, padx=20, pady=(20, 0))
        
        # Create canvas for scrolling
        canvas = tk.Canvas(details_container, highlightthickness=0, bg='#f8f9fa')
        scrollbar = tb.Scrollbar(details_container, orient="vertical", command=canvas.yview, bootstyle="primary")
        scroll_frame = tb.Frame(canvas)
        
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        canvas_window = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        
        def configure_scroll(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(canvas_window, width=canvas.winfo_width())
        
        scroll_frame.bind("<Configure>", configure_scroll)
        canvas.bind("<Configure>", configure_scroll)
        
        # Activity Information Card
        info_card = tb.LabelFrame(scroll_frame, text="📊 Activity Information", 
                                 bootstyle="info", padding=20)
        info_card.pack(fill="x", pady=(0, 15))
        
        # Create detail rows
        details = [
            ("🆔 Log ID:", log_id),
            ("🕐 Timestamp:", timestamp),
            ("👤 User:", user),
            ("⚡ Action:", action),
            ("🎯 Target:", target if target and target != "-" else "N/A"),
            ("🌐 IP Address:", ip_address if ip_address and ip_address != "-" else "N/A"),
        ]
        
        for label, value in details:
            row_frame = tb.Frame(info_card)
            row_frame.pack(fill="x", pady=5)
            
            tb.Label(row_frame, text=label, font=("Segoe UI", 11, "bold"), 
                    width=15, anchor="w").pack(side="left")
            
            value_label = tb.Label(row_frame, text=str(value), 
                                  font=("Segoe UI", 11), anchor="w")
            value_label.pack(side="left", padx=(10, 0))
        
        # Additional Information Card (if available)
        if log_data:
            additional_card = tb.LabelFrame(scroll_frame, text="ℹ️ Additional Information", 
                                          bootstyle="secondary", padding=20)
            additional_card.pack(fill="x", pady=(0, 15))
            
            # Show user ID
            user_id = log_data.get('user_id', 'N/A')
            tb.Label(additional_card, text=f"User ID: {user_id}", 
                    font=("Segoe UI", 10)).pack(anchor="w", pady=2)
            
            # Show username
            username = log_data.get('username', 'N/A')
            tb.Label(additional_card, text=f"Username: {username}", 
                    font=("Segoe UI", 10)).pack(anchor="w", pady=2)
            
            # Show full user name
            user_name = log_data.get('user_name', 'N/A')
            tb.Label(additional_card, text=f"Full Name: {user_name}", 
                    font=("Segoe UI", 10)).pack(anchor="w", pady=2)
        
        # Action Description Card
        action_desc_card = tb.LabelFrame(scroll_frame, text="📝 Action Description", 
                                        bootstyle="success", padding=20)
        action_desc_card.pack(fill="x", pady=(0, 15))
        
        # Generate action description based on action type
        description = self._generate_action_description(action, target, user)
        
        tb.Label(action_desc_card, text=description, font=("Segoe UI", 10), 
                wraplength=520, justify="left").pack(anchor="w")
        
        # Button frame
        button_frame = tb.Frame(details_window)
        button_frame.pack(fill="x", padx=20, pady=(10, 20))
        
        tb.Button(button_frame, text="Close", bootstyle="secondary", 
                 command=details_window.destroy, width=12).pack(side="right")
        
        # Add copy button
        def copy_to_clipboard():
            """Copy activity details to clipboard"""
            details_text = f"""Activity Log Details
{'=' * 50}
Log ID: {log_id}
Timestamp: {timestamp}
User: {user}
Action: {action}
Target: {target if target and target != '-' else 'N/A'}
IP Address: {ip_address if ip_address and ip_address != '-' else 'N/A'}

Description:
{description}
"""
            details_window.clipboard_clear()
            details_window.clipboard_append(details_text)
            messagebox.showinfo("Success", "Activity details copied to clipboard!", parent=details_window)
        
        tb.Button(button_frame, text="📋 Copy Details", bootstyle="info", 
                 command=copy_to_clipboard, width=15).pack(side="right", padx=(0, 10))
    
    def _generate_action_description(self, action, target, user):
        """Generate a human-readable description of the action"""
        descriptions = {
            "Login": f"{user} successfully logged into the system.",
            "Logout": f"{user} logged out of the system.",
            "Add Router": f"{user} added a new router named '{target}' to the network infrastructure.",
            "Edit Router": f"{user} modified the configuration or details of router '{target}'.",
            "Delete Router": f"{user} removed router '{target}' from the network infrastructure.",
            "Add User": f"{user} created a new user account for '{target}'.",
            "Edit User": f"{user} updated the account information for user '{target}'.",
            "Delete User": f"{user} deleted the user account for '{target}'.",
        }
        
        # Return specific description or generic one
        if action in descriptions:
            return descriptions[action]
        else:
            target_text = f" on '{target}'" if target and target != "-" else ""
            return f"{user} performed action '{action}'{target_text}."


def show_activity_log(parent, current_user):
    """Show the activity log viewer"""
    viewer = ActivityLogViewer(parent, current_user)
    viewer.show()
