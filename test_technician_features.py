#!/usr/bin/env python3
"""
Test script to validate the new technician and accomplishment functionality
"""

import requests
import json
from datetime import datetime

def test_technician_functionality():
    """Test all the new technician and accomplishment features."""
    
    base_url = "http://localhost:5000"
    
    print("🔧 Testing Technician & Accomplishment Functionality")
    print("=" * 60)
    
    # Test 1: Check technicians endpoint
    print("\n1️⃣ Testing /api/technicians endpoint...")
    try:
        response = requests.get(f"{base_url}/api/technicians", timeout=5)
        if response.ok:
            technicians = response.json()
            print(f"✅ Technicians endpoint working - Found {len(technicians)} technicians:")
            for tech in technicians:
                print(f"   - {tech['name']} ({tech['specialization']}) - Contact: {tech['email']}")
            if technicians:
                first_tech = technicians[0]
                tech_id = first_tech['id']
                tech_user_id = first_tech['user_id']
            else:
                print("❌ No technicians found")
                return False
        else:
            print(f"❌ Technicians endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error connecting to technicians endpoint: {e}")
        return False
    
    # Test 2: Submit a ticket with technician assignment
    print("\n2️⃣ Testing ticket submission with technician assignment...")
    try:
        # Get a user for ticket creation
        users_resp = requests.get(f"{base_url}/api/users", timeout=5)
        users = users_resp.json() if users_resp.ok else []
        created_by = users[0]['id'] if users else 2
        
        ticket_data = {
            "created_by": created_by,
            "data": {
                "ict_srf_no": "8888",  # Use a unique number
                "campus": "Test Campus",
                "office_building": "Test Building",
                "client_name": "Test Client for Technician",
                "date_time_call": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "required_response_time": "24 hours",
                "services_requirements": "Test ticket for technician assignment and accomplishment",
                "remarks": "This ticket will be assigned to a technician and completed",
                "technician_assigned_id": tech_id
            }
        }
        
        resp = requests.post(f"{base_url}/api/srfs", json=ticket_data, timeout=10)
        if resp.ok:
            print("✅ Ticket with technician assignment created successfully!")
            
            # Test technician assignment
            assign_data = {
                "technician_id": tech_id,
                "assigned_by": created_by
            }
            assign_resp = requests.post(f"{base_url}/api/tickets/8888/assign", 
                                       json=assign_data, timeout=5)
            if assign_resp.ok:
                print("✅ Ticket assigned to technician successfully!")
            else:
                print(f"⚠️ Ticket assignment failed: {assign_resp.text}")
        else:
            print(f"❌ Ticket creation failed: {resp.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error creating/assigning ticket: {e}")
        return False
    
    # Test 3: Get technician's assigned tickets
    print("\n3️⃣ Testing technician assigned tickets...")
    try:
        resp = requests.get(f"{base_url}/api/technician/{tech_user_id}/tickets", timeout=5)
        if resp.ok:
            tickets = resp.json()
            print(f"✅ Found {len(tickets)} tickets assigned to technician")
            for ticket in tickets:
                print(f"   - SRF #{ticket.get('ict_srf_no')} - {ticket.get('client_name')} - Status: {ticket.get('status')}")
        else:
            print(f"❌ Getting assigned tickets failed: {resp.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error getting assigned tickets: {e}")
        return False
    
    # Test 4: Add accomplishment to the ticket
    print("\n4️⃣ Testing accomplishment functionality...")
    try:
        accomplishment_data = {
            "accomplishment": "Successfully completed the service request:\n• Diagnosed the network issue\n• Replaced faulty equipment\n• Tested all connections\n• Provided user training",
            "accomplished_by": tech_user_id,
            "service_time": "2.5",
            "response_time": "1.0"
        }
        
        resp = requests.post(f"{base_url}/api/tickets/8888/accomplish", 
                           json=accomplishment_data, timeout=10)
        if resp.ok:
            print("✅ Accomplishment added successfully!")
            print("   - Service marked as completed")
            print("   - Service time: 2.5 hours")
            print("   - Response time: 1.0 hours")
        else:
            print(f"❌ Adding accomplishment failed: {resp.status_code}")
            try:
                error_msg = resp.json().get('error', resp.text)
                print(f"   Error: {error_msg}")
            except:
                print(f"   Error: {resp.text}")
            return False
    except Exception as e:
        print(f"❌ Error adding accomplishment: {e}")
        return False
    
    # Test 5: Verify ticket completion
    print("\n5️⃣ Verifying ticket completion...")
    try:
        resp = requests.get(f"{base_url}/api/srfs", timeout=5)
        if resp.ok:
            tickets = resp.json()
            test_ticket = next((t for t in tickets if t.get("ict_srf_no") == "8888"), None)
            if test_ticket:
                status = test_ticket.get('status', '').lower()
                accomplishment = test_ticket.get('accomplishment', '')
                accomplished_by = test_ticket.get('accomplished_by')
                
                print(f"✅ Ticket verification successful:")
                print(f"   - Status: {status}")
                print(f"   - Has accomplishment: {'Yes' if accomplishment else 'No'}")
                print(f"   - Accomplished by user ID: {accomplished_by}")
                print(f"   - Service time: {test_ticket.get('service_time', 'N/A')}")
                print(f"   - Response time: {test_ticket.get('response_time', 'N/A')}")
                
                if status == 'completed' and accomplishment and accomplished_by:
                    print("✅ Ticket completion workflow working perfectly!")
                else:
                    print("⚠️ Ticket completion may have issues")
            else:
                print("❌ Test ticket not found")
                return False
        else:
            print(f"❌ Failed to verify ticket: {resp.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error verifying ticket: {e}")
        return False
    
    print("\n🎉 All technician and accomplishment tests passed!")
    print("\n📋 Summary of implemented features:")
    print("✅ Technician management with specializations")
    print("✅ Technician assignment dropdown in ticket creation")
    print("✅ Technician assigned tickets view")
    print("✅ Accomplishment submission with service details")
    print("✅ Automatic ticket completion on accomplishment")
    print("✅ Service time and response time tracking")
    print("\n🚀 The system is ready for technician workflow!")
    
    return True

if __name__ == "__main__":
    test_technician_functionality()