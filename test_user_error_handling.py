#!/usr/bin/env python3
"""
Test script for user_utils.py with MySQL error handling
"""

import sys
import os

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from user_utils import get_user_by_username, get_all_users, insert_user, delete_user

def test_user_functions():
    """Test user utility functions with error handling"""
    print("=== User Utils Error Handling Test ===\n")
    
    # Test 1: Get user by username
    print("1. Testing get_user_by_username...")
    try:
        user = get_user_by_username("admin")
        if user is None:
            print("   ✅ Function handled error gracefully - returned None")
        else:
            print(f"   ✅ User found: {user}")
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
    
    print()
    
    # Test 2: Get all users
    print("2. Testing get_all_users...")
    try:
        users = get_all_users()
        if users == []:
            print("   ✅ Function handled error gracefully - returned empty list")
        else:
            print(f"   ✅ Found {len(users)} users")
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
    
    print()
    
    # Test 3: Insert user
    print("3. Testing insert_user...")
    try:
        result = insert_user("testuser", "testpass", "Test", "User", "user")
        if result is None:
            print("   ✅ Function handled error gracefully - returned None")
        else:
            print(f"   ✅ User inserted with ID: {result}")
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
    
    print()
    
    # Test 4: Delete user
    print("4. Testing delete_user...")
    try:
        result = delete_user(999)  # Non-existent user ID
        if result is None:
            print("   ✅ Function handled error gracefully - returned None")
        else:
            print(f"   ✅ Delete operation result: {result}")
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    test_user_functions()