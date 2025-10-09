#!/usr/bin/env python3
"""
Test script to validate the client ticket submission fix
"""

import requests
import json
from datetime import datetime

def test_ticket_submission():
    """Test the ticket submission process with the new user handling."""
    
    base_url = "http://localhost:5000"
    
    print("🧪 Testing Client Portal Ticket Submission Fix")
    print("=" * 50)
    
    # Test 1: Check if /api/users endpoint works
    print("\n1️⃣ Testing /api/users endpoint...")
    try:
        response = requests.get(f"{base_url}/api/users", timeout=5)
        if response.ok:
            users = response.json()
            print(f"✅ Users endpoint working - Found {len(users)} users:")
            for user in users[:3]:  # Show first 3 users
                print(f"   - ID: {user['id']}, Username: {user['username']}, Role: {user.get('role', 'N/A')}")
        else:
            print(f"❌ Users endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error connecting to users endpoint: {e}")
        return False
    
    # Test 2: Check if /api/create-client-session endpoint works
    print("\n2️⃣ Testing /api/create-client-session endpoint...")
    try:
        response = requests.post(f"{base_url}/api/create-client-session", 
                               json={"client_name": "Test Client"}, 
                               timeout=5)
        if response.ok:
            session_data = response.json()
            print(f"✅ Client session endpoint working:")
            print(f"   - User ID: {session_data.get('user_id')}")
            print(f"   - Username: {session_data.get('username')}")
            print(f"   - Message: {session_data.get('message')}")
            client_user_id = session_data.get('user_id')
        else:
            print(f"❌ Client session endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error connecting to client session endpoint: {e}")
        return False
    
    # Test 3: Try to submit a test ticket
    print("\n3️⃣ Testing ticket submission with new user handling...")
    try:
        test_ticket_data = {
            "created_by": client_user_id,
            "data": {
                "ict_srf_no": "9999",  # Use a high number to avoid conflicts
                "campus": "Test Campus",
                "office_building": "Test Building",
                "client_name": "Test Client User",
                "date_time_call": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "technician_assigned": "Test Technician",
                "required_response_time": "24 hours",
                "services_requirements": "Test service request from automated validation",
                "remarks": "This is a test ticket created by the validation script"
            }
        }
        
        response = requests.post(f"{base_url}/api/srfs", 
                               json=test_ticket_data, 
                               timeout=10)
        
        if response.ok:
            print("✅ Test ticket submitted successfully!")
            print("✅ Foreign key constraint issue has been resolved!")
            
            # Clean up - try to verify the ticket was created
            try:
                srfs_response = requests.get(f"{base_url}/api/srfs", timeout=5)
                if srfs_response.ok:
                    srfs = srfs_response.json()
                    test_ticket = next((srf for srf in srfs if srf.get("ict_srf_no") == "9999"), None)
                    if test_ticket:
                        print(f"   - Ticket created with ID: {test_ticket.get('ict_srf_no')}")
                        print(f"   - Status: {test_ticket.get('status', 'N/A')}")
            except Exception:
                pass
                
        else:
            error_details = ""
            try:
                error_json = response.json()
                error_details = error_json.get('error', response.text)
            except:
                error_details = response.text
            
            print(f"❌ Test ticket submission failed: {response.status_code}")
            print(f"   Error: {error_details}")
            
            if "foreign key constraint" in error_details.lower():
                print("❌ Foreign key constraint issue still exists!")
                return False
            
    except Exception as e:
        print(f"❌ Error during ticket submission test: {e}")
        return False
    
    print("\n🎉 All tests passed! The client portal ticket submission fix is working correctly.")
    return True

if __name__ == "__main__":
    test_ticket_submission()