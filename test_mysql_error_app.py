#!/usr/bin/env python3
"""
Simple standalone test app for MySQL error dialogs
This shows how the error handling works when starting an application
"""

import sys
import os
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as tb

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db import get_connection, DatabaseConnectionError, database_health_check

class SimpleTestApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MySQL Error Handling Test")
        self.root.geometry("400x300")
        
        # Create main frame
        main_frame = tb.Frame(root, padding=20)
        main_frame.pack(fill="both", expand=True)
        
        # Title
        title = tb.Label(main_frame, text="MySQL Connection Test", 
                        font=("Arial", 16, "bold"), bootstyle="primary")
        title.pack(pady=(0, 20))
        
        # Status label
        self.status_label = tb.Label(main_frame, text="Checking database connection...", 
                                   font=("Arial", 11))
        self.status_label.pack(pady=(0, 20))
        
        # Buttons
        button_frame = tb.Frame(main_frame)
        button_frame.pack(pady=20)
        
        tb.Button(button_frame, text="Test Connection", 
                 command=self.test_connection, bootstyle="primary").pack(side="left", padx=5)
        
        tb.Button(button_frame, text="Health Check", 
                 command=self.health_check, bootstyle="info").pack(side="left", padx=5)
        
        tb.Button(button_frame, text="Force Error Dialog", 
                 command=self.force_error, bootstyle="danger").pack(side="left", padx=5)
        
        # Info text
        info_text = tb.Text(main_frame, height=8, width=50)
        info_text.pack(fill="both", expand=True, pady=(20, 0))
        info_text.insert("1.0", 
            "This app demonstrates MySQL error handling with popup dialogs.\n\n"
            "When MySQL is not running:\n"
            "• Error dialogs will appear\n"
            "• Clear error messages with solutions\n"
            "• User-friendly interface\n\n"
            "Click 'Test Connection' to see the error dialog.\n"
            "Make sure MySQL is NOT running to see the error handling."
        )
        info_text.config(state="disabled")
        
        # Perform initial connection test
        self.root.after(1000, self.initial_test)
    
    def initial_test(self):
        """Perform initial database connection test"""
        try:
            # Test connection with dialog enabled
            conn = get_connection(max_retries=1, show_dialog=True)
            self.status_label.config(text="✅ Database connected successfully!", 
                                   bootstyle="success")
            conn.close()
        except DatabaseConnectionError:
            self.status_label.config(text="❌ Database connection failed (see dialog)", 
                                   bootstyle="danger")
    
    def test_connection(self):
        """Test database connection manually"""
        try:
            conn = get_connection(max_retries=2, show_dialog=True)
            self.status_label.config(text="✅ Connection successful!", bootstyle="success")
            messagebox.showinfo("Success", "Database connected successfully!")
            conn.close()
        except DatabaseConnectionError as e:
            self.status_label.config(text="❌ Connection failed", bootstyle="danger")
    
    def health_check(self):
        """Perform database health check"""
        health = database_health_check()
        status = health["status"]
        message = health["message"]
        
        if status == "healthy":
            messagebox.showinfo("Database Health", f"✅ {message}")
            self.status_label.config(text="✅ Database healthy", bootstyle="success")
        elif status == "warning":
            messagebox.showwarning("Database Health", f"⚠️ {message}")
            self.status_label.config(text="⚠️ Database warning", bootstyle="warning")
        else:
            messagebox.showerror("Database Health", f"❌ {message}")
            self.status_label.config(text="❌ Database error", bootstyle="danger")
    
    def force_error(self):
        """Force an error dialog for demonstration"""
        from db import show_database_error_dialog
        show_database_error_dialog(
            "Demonstration Error",
            "This is a demonstration of the error dialog system.",
            "Demo Error 2003: Can't connect to MySQL server on 'localhost:3306'"
        )

def main():
    # Create the application
    root = tb.Window(themename="flatly")
    app = SimpleTestApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()