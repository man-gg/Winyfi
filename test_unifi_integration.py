#!/usr/bin/env python3
"""
Test script for UniFi Dashboard Integration
This script demonstrates the UniFi API integration in the dashboard
"""
import os
import sys
import time
import requests
import subprocess
import threading

def check_server(url, name):
    """Check if a server is running"""
    try:
        response = requests.get(url, timeout=2)
        print(f"✅ {name} is running at {url}")
        return True
    except:
        print(f"❌ {name} is NOT running at {url}")
        return False

def start_unifi_server():
    """Start the UniFi API server in a separate process"""
    print("\n🚀 Starting UniFi API Server...")
    print("=" * 60)
    
    # Start server in background
    if sys.platform == "win32":
        subprocess.Popen(
            ["python", "server/unifi_api.py"],
            cwd=os.path.dirname(__file__),
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
    else:
        subprocess.Popen(
            ["python3", "server/unifi_api.py"],
            cwd=os.path.dirname(__file__)
        )
    
    # Wait for server to start
    print("⏳ Waiting for server to start...")
    time.sleep(2)
    
    # Verify server is running
    if check_server("http://localhost:5001/api/unifi/devices", "UniFi API Server"):
        print("✅ UniFi API Server started successfully!")
        return True
    else:
        print("❌ Failed to start UniFi API Server")
        return False

def test_unifi_endpoints():
    """Test all UniFi API endpoints"""
    print("\n📡 Testing UniFi API Endpoints...")
    print("=" * 60)
    
    base_url = "http://localhost:5001"
    endpoints = [
        ("/api/unifi/devices", "List UniFi APs"),
        ("/api/unifi/clients", "List Connected Clients"),
        ("/api/unifi/bandwidth/total", "Total Bandwidth"),
        ("/api/unifi/clients/count", "Client Count"),
    ]
    
    for endpoint, description in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=2)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ {description:30} - {endpoint}")
                if isinstance(data, list):
                    print(f"   📊 Returned {len(data)} items")
                elif isinstance(data, dict):
                    print(f"   📊 Data: {data}")
            else:
                print(f"❌ {description:30} - Status: {response.status_code}")
        except Exception as e:
            print(f"❌ {description:30} - Error: {str(e)}")

def display_mock_data():
    """Display the mock UniFi data"""
    print("\n📋 Mock UniFi Data:")
    print("=" * 60)
    
    try:
        # Fetch devices
        response = requests.get("http://localhost:5001/api/unifi/devices", timeout=2)
        if response.status_code == 200:
            devices = response.json()
            print(f"\n📡 UniFi Access Points ({len(devices)}):")
            for i, device in enumerate(devices, 1):
                print(f"\n  {i}. {device['name']}")
                print(f"     Model: {device['model']}")
                print(f"     IP: {device['ip']}")
                print(f"     MAC: {device['mac']}")
                print(f"     ⬇ Download: {device['xput_down']:.2f} Mbps")
                print(f"     ⬆ Upload: {device['xput_up']:.2f} Mbps")
        
        # Fetch clients
        response = requests.get("http://localhost:5001/api/unifi/clients", timeout=2)
        if response.status_code == 200:
            clients = response.json()
            print(f"\n👥 Connected Clients ({len(clients)}):")
            for i, client in enumerate(clients, 1):
                print(f"\n  {i}. {client['hostname']}")
                print(f"     IP: {client['ip']}")
                print(f"     MAC: {client['mac']}")
                print(f"     Connected to: {client['ap_mac']}")
                print(f"     ⬇ RX: {client['rx_bytes'] / 1024 / 1024:.2f} MB")
                print(f"     ⬆ TX: {client['tx_bytes'] / 1024 / 1024:.2f} MB")
        
        # Fetch bandwidth total
        response = requests.get("http://localhost:5001/api/unifi/bandwidth/total", timeout=2)
        if response.status_code == 200:
            bandwidth = response.json()
            print(f"\n📊 Total Bandwidth:")
            print(f"     ⬇ Download: {bandwidth['total_down']:.2f} Mbps")
            print(f"     ⬆ Upload: {bandwidth['total_up']:.2f} Mbps")
            
    except Exception as e:
        print(f"❌ Error fetching data: {e}")

def main():
    print("\n" + "=" * 60)
    print("🎯 UniFi Dashboard Integration Test")
    print("=" * 60)
    
    # Check if UniFi server is already running
    if not check_server("http://localhost:5001/api/unifi/devices", "UniFi API Server"):
        # Start the server
        if not start_unifi_server():
            print("\n❌ Cannot continue without UniFi API Server")
            return
    
    # Test endpoints
    test_unifi_endpoints()
    
    # Display mock data
    display_mock_data()
    
    print("\n" + "=" * 60)
    print("✅ Integration Test Complete!")
    print("=" * 60)
    print("\n📝 Next Steps:")
    print("   1. Keep the UniFi API Server running (http://localhost:5001)")
    print("   2. Start the main dashboard: python main.py")
    print("   3. Login as admin")
    print("   4. View the Routers tab to see:")
    print("      - 📡 UniFi Access Points section (with UniFi badge)")
    print("      - 🟢 Regular Routers section")
    print("   5. UniFi devices will show real-time bandwidth from the API")
    print("\n💡 Tip: You can toggle mock mode by sending POST to /api/unifi/mock")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
