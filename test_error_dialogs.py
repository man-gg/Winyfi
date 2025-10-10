#!/usr/bin/env python3
"""
Test script for MySQL error handling with popup dialogs
This script demonstrates the error dialog functionality
"""

import sys
import os
import tkinter as tk

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db import (
    get_connection, 
    show_database_error_dialog,
    show_database_warning_dialog,
    execute_with_error_handling,
    DatabaseConnectionError
)

def test_error_dialogs():
    """Test error dialog functionality"""
    print("=== MySQL Error Dialog Test ===\n")
    
    # Create a root window for the dialogs
    root = tk.Tk()
    root.withdraw()  # Hide the root window
    
    print("Testing error dialogs...")
    print("1. Testing custom error dialog...")
    
    # Test custom error dialog
    show_database_error_dialog(
        "Test Error Dialog",
        "This is a test of the database error dialog system.",
        "Test error details: MySQL server connection failed"
    )
    
    print("2. Testing warning dialog...")
    
    # Test warning dialog
    show_database_warning_dialog(
        "Test Warning Dialog",
        "This is a test warning about database connectivity issues."
    )
    
    print("3. Testing actual database connection (this will show real error dialog)...")
    
    # Test actual database connection - this will trigger real error dialogs
    try:
        conn = get_connection(max_retries=1, show_dialog=True)
        print("   Connection successful!")
    except DatabaseConnectionError as e:
        print(f"   Connection failed (expected): {e}")
    
    print("4. Testing database operation with error dialog...")
    
    # Test a database operation that will fail
    def dummy_operation():
        conn = get_connection(max_retries=1, show_dialog=False)  # Don't show dialog in inner function
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        return cursor.fetchone()
    
    result = execute_with_error_handling("test_operation", dummy_operation, show_dialog=True)
    print(f"   Operation result: {result}")
    
    # Clean up
    root.destroy()
    
    print("\n=== Dialog Test Complete ===")
    print("Check if error dialogs appeared on your screen!")

if __name__ == "__main__":
    test_error_dialogs()