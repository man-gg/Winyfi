"""
Test script to verify UniFi auto-refresh implementation with ping
"""
import requests
import time
import subprocess
import platform

def ping_latency(ip, timeout=1000):
    """Ping a device and return latency in ms."""
    param = "-n" if platform.system().lower() == "windows" else "-c"
    cmd = ["ping", param, "1", "-w", str(timeout), ip]
    try:
        start = time.time()
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        end = time.time()
        if result.returncode == 0:
            latency = round((end - start) * 1000, 2)  # ms
            return latency
    except Exception as e:
        pass
    return None

def test_unifi_api_connection():
    """Test connection to UniFi API server"""
    print("=" * 60)
    print("Testing UniFi API Connection")
    print("=" * 60)
    
    try:
        response = requests.get("http://localhost:5001/api/unifi/devices", timeout=3)
        if response.status_code == 200:
            devices = response.json()
            print(f"✅ Successfully connected to UniFi API")
            print(f"   Found {len(devices)} UniFi devices:")
            for device in devices:
                print(f"   - {device.get('name', 'Unknown')}: {device.get('ip', 'N/A')}")
                print(f"     Download: {device.get('xput_down', 0):.2f} Mbps")
                print(f"     Upload: {device.get('xput_up', 0):.2f} Mbps")
            return True
        else:
            print(f"❌ API returned status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to UniFi API server")
        print("   Make sure the server is running on http://localhost:5001")
        print("   Start it with: python start_unifi_server.py")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_auto_refresh_simulation():
    """Simulate auto-refresh behavior"""
    print("\n" + "=" * 60)
    print("Simulating Auto-Refresh (3 cycles, 2 seconds each)")
    print("=" * 60)
    
    for i in range(3):
        print(f"\n🔄 Refresh cycle {i+1}/3")
        try:
            response = requests.get("http://localhost:5001/api/unifi/devices", timeout=3)
            if response.status_code == 200:
                devices = response.json()
                print(f"   ✅ Fetched {len(devices)} devices")
                for device in devices:
                    print(f"   📡 {device.get('name', 'Unknown')}: "
                          f"↓{device.get('xput_down', 0):.1f} Mbps "
                          f"↑{device.get('xput_up', 0):.1f} Mbps")
            else:
                print(f"   ❌ Failed with status: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        if i < 2:  # Don't sleep after the last cycle
            time.sleep(2)

def test_device_transformation():
    """Test device data transformation with ping"""
    print("\n" + "=" * 60)
    print("Testing Device Data Transformation with Ping")
    print("=" * 60)
    
    try:
        response = requests.get("http://localhost:5001/api/unifi/devices", timeout=3)
        if response.status_code == 200:
            devices = response.json()
            
            # Transform like dashboard does
            transformed = []
            for device in devices:
                ip = device.get('ip', 'N/A')
                device_id = f"unifi_{device.get('mac', '')}"
                
                # Ping the device
                print(f"\n   🔍 Pinging {device.get('name', 'Unknown')}: {ip}...")
                is_online = False
                latency = None
                if ip != 'N/A':
                    latency = ping_latency(ip, timeout=1000)
                    is_online = latency is not None
                
                if is_online:
                    print(f"   ✅ Device is ONLINE - Latency: {latency:.0f} ms")
                else:
                    print(f"   ❌ Device is OFFLINE - No ping response")
                
                transformed.append({
                    'id': device_id,
                    'name': device.get('name', 'Unknown AP'),
                    'ip_address': ip,
                    'mac_address': device.get('mac', 'N/A'),
                    'brand': 'UniFi',
                    'location': device.get('model', 'Access Point'),
                    'is_unifi': True,
                    'is_online': is_online,
                    'latency': latency,
                    'download_speed': device.get('xput_down', 0),
                    'upload_speed': device.get('xput_up', 0),
                })
            
            print(f"\n✅ Transformed {len(transformed)} devices:")
            for device in transformed:
                print(f"\n   Device: {device['name']}")
                print(f"   ID: {device['id']}")
                print(f"   IP: {device['ip_address']}")
                print(f"   MAC: {device['mac_address']}")
                print(f"   Model: {device['location']}")
                print(f"   Brand: {device['brand']}")
                print(f"   Status: {'🟢 Online' if device['is_online'] else '🔴 Offline'}")
                if device['latency'] is not None:
                    print(f"   Latency: {device['latency']:.0f} ms")
                else:
                    print(f"   Latency: N/A (Offline)")
                print(f"   Download: {device['download_speed']:.2f} Mbps")
                print(f"   Upload: {device['upload_speed']:.2f} Mbps")
                print(f"   Is UniFi: {device['is_unifi']}")
            return True
        else:
            print(f"❌ API returned status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("\n🚀 UniFi Auto-Refresh Implementation Test (with Ping)\n")
    
    # Test 1: API Connection
    api_ok = test_unifi_api_connection()
    
    if not api_ok:
        print("\n⚠️  UniFi API server is not running or not accessible")
        print("    Please start the server before testing the dashboard")
        return
    
    # Test 2: Data Transformation with Ping
    test_device_transformation()
    
    # Test 3: Auto-refresh simulation
    test_auto_refresh_simulation()
    
    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Keep the UniFi API server running")
    print("2. Start the dashboard: python main.py")
    print("3. Navigate to the Routers page")
    print("4. UniFi devices should appear with:")
    print("   - Blue cards with 📡 icon")
    print("   - Online/Offline status based on ping")
    print("   - Latency displayed (e.g., ⚡45ms)")
    print("   - Bandwidth from API")
    print("   - Auto-refresh every 10 seconds")
    print("\n")

if __name__ == "__main__":
    main()
