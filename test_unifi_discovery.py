"""
Test script to verify UniFi auto-discovery functionality
Run this to test the new device discovery feature
"""

import requests
import json
import time

def test_unifi_discovery():
    """Test that new UniFi devices are discovered and added"""
    
    print("=" * 60)
    print("UniFi Auto-Discovery Test")
    print("=" * 60)
    
    # Check if UniFi API is running
    try:
        response = requests.get("http://localhost:5001/api/unifi/devices", timeout=2)
        if response.status_code == 200:
            devices = response.json()
            print(f"\n✅ UniFi API is running")
            print(f"📡 Current devices in API: {len(devices)}")
            print("\nDevices found:")
            for i, device in enumerate(devices, 1):
                print(f"  {i}. {device.get('name', 'Unknown')} - {device.get('mac', 'N/A')} ({device.get('ip', 'N/A')})")
        else:
            print(f"\n❌ UniFi API returned status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("\n❌ UniFi API server is not running!")
        print("   Start it with: python server/app.py")
        return False
    except Exception as e:
        print(f"\n❌ Error connecting to UniFi API: {str(e)}")
        return False
    
    # Check database connection
    try:
        from db import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM routers WHERE brand = 'UniFi'")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        print(f"\n✅ Database connection successful")
        print(f"📊 Current UniFi devices in database: {count}")
    except Exception as e:
        print(f"\n❌ Database error: {str(e)}")
        return False
    
    print("\n" + "=" * 60)
    print("Test Instructions:")
    print("=" * 60)
    print("1. Note the current device count above")
    print("2. Edit server/unifi_api.py to add a new device to MOCK_APS")
    print("3. Restart the UniFi API server")
    print("4. Open/refresh the Routers tab in the dashboard")
    print("5. Check console output for discovery messages")
    print("6. Verify new device appears with UniFi badge (📡)")
    print("\nExample device to add:")
    print("""
    {
        "model": "UAP-AC-HD",
        "name": "Test New AP",
        "mac": "AA:BB:CC:DD:EE:99",
        "ip": "192.168.1.99",
        "xput_down": 100.0,
        "xput_up": 25.0,
        "state": 1,
        "connected": True
    }
    """)
    print("\nExpected console output:")
    print("  📡 Found X UniFi device(s) from API")
    print("  ✨ New UniFi device discovered: Test New AP (MAC: AA:BB:CC:DD:EE:99, IP: 192.168.1.99)")
    print("  🎉 Added 1 new UniFi device(s) to the database and routers tab")
    
    return True

if __name__ == "__main__":
    test_unifi_discovery()
