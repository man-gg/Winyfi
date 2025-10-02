#!/usr/bin/env python3
"""
Test script for the Show Clients button functionality
"""

import tkinter as tk
import ttkbootstrap as tb
from client_window.client_app import ClientDashboard

def test_show_clients():
    """Test the Show Clients button functionality"""
    root = tb.Window(themename="flatly")
    root.title("Test Show Clients Button")
    root.geometry("1000x600")
    
    # Create the client dashboard
    dashboard = ClientDashboard(root, {'username': 'test'})
    
    print("✅ Show Clients button test created successfully!")
    print("Features available:")
    print("- Show Clients button in sidebar")
    print("- Modal window opens when clicked")
    print("- Fetches data from database via API")
    print("- Read-only view (no scanning)")
    print("- Search and filter functionality")
    print("- Export to CSV")
    print("- Sortable columns")
    print("- Statistics display")
    
    root.mainloop()

if __name__ == "__main__":
    test_show_clients()
