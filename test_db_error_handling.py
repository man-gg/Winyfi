#!/usr/bin/env python3
"""
Test script for MySQL error handling
This script tests the database connection error handling functionality
"""

import sys
import os

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db import (
    check_mysql_server_status, 
    get_connection, 
    database_health_check, 
    get_database_info,
    DatabaseConnectionError
)

def test_mysql_connection():
    """Test MySQL connection with different scenarios"""
    print("=== MySQL Connection Error Handling Test ===\n")
    
    # Test 1: Check MySQL server status
    print("1. Testing MySQL server status check...")
    try:
        is_running, message = check_mysql_server_status()
        print(f"   Server Status: {'✅ Running' if is_running else '❌ Not Running'}")
        print(f"   Message: {message}")
    except Exception as e:
        print(f"   Error checking server status: {e}")
    
    print()
    
    # Test 2: Test database connection
    print("2. Testing database connection...")
    try:
        conn = get_connection()
        print("   ✅ Connection successful!")
        
        # Test a simple query
        cursor = conn.cursor()
        cursor.execute("SELECT 1 as test")
        result = cursor.fetchone()
        print(f"   ✅ Query test successful: {result}")
        
        cursor.close()
        conn.close()
        
    except DatabaseConnectionError as e:
        print(f"   ❌ Database Connection Error: {e}")
    except Exception as e:
        print(f"   ❌ Unexpected Error: {e}")
    
    print()
    
    # Test 3: Database health check
    print("3. Testing database health check...")
    try:
        health_status = database_health_check()
        print(f"   Status: {health_status['status']}")
        print(f"   Message: {health_status['message']}")
        
        if 'details' in health_status:
            print("   Details:")
            for key, value in health_status['details'].items():
                print(f"     {key}: {value}")
                
    except Exception as e:
        print(f"   ❌ Error during health check: {e}")
    
    print()
    
    # Test 4: Get database info
    print("4. Testing database info retrieval...")
    try:
        db_info = get_database_info()
        print("   Database Information:")
        for key, value in db_info.items():
            print(f"     {key}: {value}")
            
    except Exception as e:
        print(f"   ❌ Error getting database info: {e}")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    test_mysql_connection()