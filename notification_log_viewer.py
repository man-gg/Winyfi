#!/usr/bin/env python3
"""
Notification Log Viewer for debugging notification system
"""

import tkinter as tk
import ttkbootstrap as tb
from notification_utils import notification_manager
from datetime import datetime

class NotificationLogViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Notification Log Viewer")
        self.root.geometry("1000x700")
        
        self._create_ui()
        self._load_logs()
    
    def _create_ui(self):
        """Create the UI for the log viewer."""
        # Main frame
        main_frame = tb.Frame(self.root, padding=10)
        main_frame.pack(fill="both", expand=True)
        
        # Header
        header_frame = tb.Frame(main_frame)
        header_frame.pack(fill="x", pady=(0, 10))
        
        # Title
        title_label = tb.Label(
            header_frame,
            text="📝 Notification Log Viewer",
            font=("Segoe UI", 16, "bold")
        )
        title_label.pack(side="left")
        
        # Refresh button
        refresh_btn = tb.Button(
            header_frame,
            text="🔄 Refresh",
            command=self._load_logs,
            style="info.TButton"
        )
        refresh_btn.pack(side="right")
        
        # Filter frame
        filter_frame = tb.Frame(main_frame)
        filter_frame.pack(fill="x", pady=(0, 10))
        
        # Event type filter
        tb.Label(filter_frame, text="Event Type:").pack(side="left")
        self.event_type_var = tk.StringVar()
        event_type_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.event_type_var,
            values=["All", "created", "callback_triggered", "toast_created", "toast_displayed", "error", "status_update"],
            state="readonly",
            width=15
        )
        event_type_combo.pack(side="left", padx=(5, 20))
        event_type_combo.set("All")
        
        # Notification ID filter
        tb.Label(filter_frame, text="Notification ID:").pack(side="left")
        self.notification_id_var = tk.StringVar()
        notification_id_entry = tb.Entry(
            filter_frame,
            textvariable=self.notification_id_var,
            width=10
        )
        notification_id_entry.pack(side="left", padx=(5, 20))
        
        # Filter button
        filter_btn = tb.Button(
            filter_frame,
            text="🔍 Filter",
            command=self._apply_filter,
            style="primary.TButton"
        )
        filter_btn.pack(side="left")
        
        # Clear filter button
        clear_btn = tb.Button(
            filter_frame,
            text="❌ Clear",
            command=self._clear_filter,
            style="secondary.TButton"
        )
        clear_btn.pack(side="left", padx=(5, 0))
        
        # Logs treeview
        columns = ("ID", "Notification ID", "Event Type", "Message", "Timestamp", "Details")
        self.tree = ttk.Treeview(main_frame, columns=columns, show="headings", height=20)
        
        # Configure columns
        self.tree.heading("ID", text="ID")
        self.tree.heading("Notification ID", text="Notification ID")
        self.tree.heading("Event Type", text="Event Type")
        self.tree.heading("Message", text="Message")
        self.tree.heading("Timestamp", text="Timestamp")
        self.tree.heading("Details", text="Details")
        
        # Column widths
        self.tree.column("ID", width=50)
        self.tree.column("Notification ID", width=100)
        self.tree.column("Event Type", width=120)
        self.tree.column("Message", width=300)
        self.tree.column("Timestamp", width=150)
        self.tree.column("Details", width=200)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack treeview and scrollbar
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Status bar
        self.status_label = tb.Label(
            main_frame,
            text="Ready",
            font=("Segoe UI", 9),
            foreground="gray"
        )
        self.status_label.pack(pady=(10, 0))
    
    def _load_logs(self):
        """Load notification logs."""
        try:
            # Get notification ID filter
            notification_id = None
            if self.notification_id_var.get().strip():
                try:
                    notification_id = int(self.notification_id_var.get().strip())
                except ValueError:
                    pass
            
            # Get logs
            logs = notification_manager.get_notification_logs(notification_id, 500)
            
            # Clear existing items
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            # Apply event type filter
            event_type_filter = self.event_type_var.get()
            if event_type_filter != "All":
                logs = [log for log in logs if log["event_type"] == event_type_filter]
            
            # Add logs to treeview
            for log in logs:
                details = log["details"]
                details_str = ""
                if details:
                    if isinstance(details, dict):
                        details_str = ", ".join([f"{k}: {v}" for k, v in details.items()])
                    else:
                        details_str = str(details)
                
                self.tree.insert("", "end", values=(
                    log["id"],
                    log["notification_id"],
                    log["event_type"],
                    log["message"][:100] + "..." if len(log["message"]) > 100 else log["message"],
                    log["timestamp"],
                    details_str[:100] + "..." if len(details_str) > 100 else details_str
                ))
            
            # Update status
            self.status_label.config(text=f"Loaded {len(logs)} log entries")
            
        except Exception as e:
            self.status_label.config(text=f"Error loading logs: {str(e)}")
    
    def _apply_filter(self):
        """Apply filters to the logs."""
        self._load_logs()
    
    def _clear_filter(self):
        """Clear all filters."""
        self.event_type_var.set("All")
        self.notification_id_var.set("")
        self._load_logs()

def main():
    root = tk.Tk()
    app = NotificationLogViewer(root)
    root.mainloop()

if __name__ == "__main__":
    main()

