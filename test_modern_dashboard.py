#!/usr/bin/env python3
"""
Test script for the modern dashboard functionality
"""

import tkinter as tk
import ttkbootstrap as tb
from dashboard import Dashboard
import sys
import os

def test_modern_dashboard():
    """Test the modern dashboard with sample data"""
    
    # Create root window
    root = tb.Window(themename="superhero")
    root.title("Modern Network Dashboard - Test")
    root.geometry("1400x900")
    
    # Mock user data
    current_user = {
        'username': 'admin',
        'role': 'administrator',
        'email': 'admin@example.com'
    }
    
    try:
        # Create dashboard instance
        dashboard = Dashboard(root, current_user)
        
        # Show the dashboard
        root.mainloop()
        
    except Exception as e:
        print(f"Error creating dashboard: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_modern_dashboard()
