#!/usr/bin/env python3
"""
Quick test script to verify UniFi API connection
Run this to test if your configuration works before starting the full server
"""

import os
import sys
import requests
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def test_connection():
    """Test connection to UniFi Controller"""
    
    # Load config from environment or use defaults
    controller_url = os.getenv("UNIFI_URL", "https://127.0.0.1:8443").rstrip("/")
    username = os.getenv("UNIFI_USER", "admin")
    password = os.getenv("UNIFI_PASS", "admin123")
    site = os.getenv("UNIFI_SITE", "default")
    verify_ssl = os.getenv("UNIFI_VERIFY", "false").lower() == "true"
    
    print("=" * 60)
    print("UniFi Controller Connection Test")
    print("=" * 60)
    print(f"\nController URL: {controller_url}")
    print(f"Username: {username}")
    print(f"Site: {site}")
    print(f"SSL Verify: {verify_ssl}")
    print("\n" + "-" * 60)
    
    # Create session
    session = requests.Session()
    session.verify = verify_ssl
    
    # Test 1: Basic connectivity
    print("\n[1/4] Testing basic connectivity...")
    try:
        response = session.get(f"{controller_url}/", timeout=10)
        print(f"✓ Controller is reachable (status: {response.status_code})")
    except requests.exceptions.SSLError as e:
        print(f"✗ SSL Error: {e}")
        print("  → Solution: Set UNIFI_VERIFY=false")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"✗ Connection Error: {e}")
        print("  → Check if controller is running and URL is correct")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    
    # Test 2: Login (new endpoint)
    print("\n[2/4] Testing login (new auth endpoint)...")
    try:
        payload = {"username": username, "password": password}
        response = session.post(
            f"{controller_url}/api/auth/login",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        if response.status_code in (200, 204):
            print(f"✓ Login successful (new endpoint)")
            csrf_token = response.cookies.get("csrf_token")
            if csrf_token:
                print(f"✓ CSRF token obtained")
        else:
            print(f"⚠ New endpoint returned: {response.status_code}")
            # Try legacy
            print("\n[2b/4] Trying legacy login endpoint...")
            response = session.post(
                f"{controller_url}/api/login",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=15
            )
            if response.status_code in (200, 204):
                print(f"✓ Login successful (legacy endpoint)")
            else:
                print(f"✗ Login failed: {response.status_code}")
                print(f"  Response: {response.text[:200]}")
                print("  → Check username and password")
                return False
    except Exception as e:
        print(f"✗ Login error: {e}")
        return False
    
    # Test 3: Get devices
    print("\n[3/4] Testing device retrieval...")
    try:
        headers = {"Content-Type": "application/json"}
        csrf_token = session.cookies.get("csrf_token")
        if csrf_token:
            headers["X-CSRF-Token"] = csrf_token
        
        response = session.get(
            f"{controller_url}/api/s/{site}/stat/device",
            headers=headers,
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            devices = data.get("data", [])
            print(f"✓ Retrieved {len(devices)} device(s)")
            if devices:
                print(f"  Sample device: {devices[0].get('name')} ({devices[0].get('model')})")
        else:
            print(f"⚠ Unexpected status: {response.status_code}")
            print(f"  Response: {response.text[:200]}")
    except Exception as e:
        print(f"✗ Error getting devices: {e}")
    
    # Test 4: Get clients
    print("\n[4/4] Testing client retrieval...")
    try:
        response = session.get(
            f"{controller_url}/api/s/{site}/stat/sta",
            headers=headers,
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            clients = data.get("data", [])
            print(f"✓ Retrieved {len(clients)} client(s)")
            if clients:
                sample = clients[0]
                hostname = sample.get('hostname') or sample.get('name') or 'Unknown'
                print(f"  Sample client: {hostname} ({sample.get('ip')})")
        else:
            print(f"⚠ Unexpected status: {response.status_code}")
    except Exception as e:
        print(f"✗ Error getting clients: {e}")
    
    print("\n" + "=" * 60)
    print("✓ Connection test completed successfully!")
    print("=" * 60)
    print("\nYou can now start the UniFi API server:")
    print("  cd server")
    print("  python unifi_api.py")
    print("\nOr use the startup script:")
    print("  start_unifi_api.bat")
    print()
    
    return True

if __name__ == "__main__":
    try:
        success = test_connection()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
