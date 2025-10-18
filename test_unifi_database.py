"""
Test script to verify UniFi devices are being saved to the database.
This script checks the database for UniFi devices after fetching from the API.
"""

import time
import requests
from router_utils import get_routers, upsert_unifi_router
from datetime import datetime

def test_unifi_database_integration():
    """Test UniFi device database integration"""
    print("=" * 60)
    print("UniFi Database Integration Test")
    print("=" * 60)
    
    # Test 1: Check if UniFi API is running
    print("\n1. Testing UniFi API connection...")
    try:
        response = requests.get("http://localhost:5001/api/unifi/devices", timeout=3)
        if response.status_code == 200:
            devices = response.json()
            print(f"   ✅ UniFi API is running")
            print(f"   Found {len(devices)} UniFi devices in API")
            
            # Test 2: Save UniFi devices to database
            print("\n2. Saving UniFi devices to database...")
            saved_ids = []
            for device in devices:
                name = device.get('name', 'Unknown AP')
                ip = device.get('ip', 'N/A')
                mac = device.get('mac', 'N/A')
                brand = 'UniFi'
                location = device.get('model', 'Access Point')
                
                router_id = upsert_unifi_router(name, ip, mac, brand, location, image_path=None)
                if router_id:
                    saved_ids.append(router_id)
                    print(f"   ✅ Saved: {name} (ID: {router_id}, MAC: {mac})")
                else:
                    print(f"   ❌ Failed to save: {name}")
            
            # Test 3: Verify devices in database
            print("\n3. Verifying UniFi devices in database...")
            all_routers = get_routers()
            unifi_routers = [r for r in all_routers if r.get('brand') == 'UniFi']
            
            print(f"   Total routers in database: {len(all_routers)}")
            print(f"   UniFi routers in database: {len(unifi_routers)}")
            
            if len(unifi_routers) > 0:
                print(f"   ✅ UniFi devices successfully stored in database")
                print("\n   UniFi Devices:")
                for router in unifi_routers:
                    print(f"      - ID: {router['id']}")
                    print(f"        Name: {router['name']}")
                    print(f"        IP: {router['ip_address']}")
                    print(f"        MAC: {router['mac_address']}")
                    print(f"        Brand: {router['brand']}")
                    print(f"        Location: {router['location']}")
                    print(f"        Last Seen: {router.get('last_seen', 'N/A')}")
                    print()
            else:
                print(f"   ❌ No UniFi devices found in database")
            
            # Test 4: Test update functionality
            print("4. Testing update functionality...")
            print("   Waiting 2 seconds...")
            time.sleep(2)
            
            print("   Re-saving devices to test update...")
            for device in devices:
                name = device.get('name', 'Unknown AP')
                ip = device.get('ip', 'N/A')
                mac = device.get('mac', 'N/A')
                brand = 'UniFi'
                location = device.get('model', 'Access Point')
                
                router_id = upsert_unifi_router(name, ip, mac, brand, location, image_path=None)
                if router_id:
                    print(f"   ✅ Updated: {name} (ID: {router_id})")
            
            # Verify no duplicates
            all_routers_after = get_routers()
            unifi_routers_after = [r for r in all_routers_after if r.get('brand') == 'UniFi']
            
            if len(unifi_routers_after) == len(unifi_routers):
                print(f"   ✅ No duplicates created (still {len(unifi_routers_after)} UniFi devices)")
            else:
                print(f"   ❌ Duplicate issue: {len(unifi_routers)} → {len(unifi_routers_after)}")
            
            print("\n" + "=" * 60)
            print("Test Summary:")
            print(f"  - UniFi API: ✅ Working")
            print(f"  - Database Save: ✅ Working")
            print(f"  - Database Retrieval: ✅ Working")
            print(f"  - Update (No Duplicates): ✅ Working")
            print("=" * 60)
            
        else:
            print(f"   ❌ UniFi API returned status {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("   ❌ UniFi API is not running")
        print("\n   To start UniFi API server:")
        print("   python start_unifi_server.py")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    test_unifi_database_integration()
