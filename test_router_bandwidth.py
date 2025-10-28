"""
Quick Test Script for RouterBandwidthMonitor
Tests the monitoring functionality with your actual network.
"""

import time
from router_bandwidth_monitor import RouterBandwidthMonitor
import subprocess
import sys


def test_basic_monitoring():
    """Test basic bandwidth monitoring functionality."""
    print("=" * 60)
    print("RouterBandwidthMonitor - Basic Test")
    print("=" * 60)
    
    # Create monitor
    print("\n1. Creating monitor instance...")
    monitor = RouterBandwidthMonitor(sampling_interval=5)
    print(f"   ✓ Monitor created on interface: {monitor.iface}")
    
    # Add test router (replace with your actual router IP)
    print("\n2. Adding test router...")
    test_router_ip = "192.168.1.1"  # CHANGE THIS to your router IP
    monitor.add_router(test_router_ip, name="Test Router")
    print(f"   ✓ Added router: {test_router_ip}")
    
    # Start monitoring
    print("\n3. Starting monitoring...")
    try:
        monitor.start()
        print("   ✓ Monitoring started")
    except PermissionError:
        print("   ❌ Permission denied!")
        print("   Run this script as Administrator (Windows) or with sudo (Linux)")
        return
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return
    
    # Generate traffic to router
    print(f"\n4. Generating traffic to {test_router_ip}...")
    print("   (Pinging router 10 times)")
    try:
        if sys.platform == "win32":
            subprocess.run(["ping", "-n", "10", test_router_ip], 
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["ping", "-c", "10", test_router_ip], 
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL)
        print("   ✓ Traffic generated")
    except Exception as e:
        print(f"   ⚠️ Could not ping router: {e}")
    
    # Wait for first sample
    print("\n5. Waiting for first bandwidth sample (15 seconds)...")
    for i in range(15, 0, -1):
        print(f"   {i}...", end="\r")
        time.sleep(1)
    print("   ✓ Sample period complete")
    
    # Get bandwidth data
    print("\n6. Retrieving bandwidth data...")
    bandwidth = monitor.get_router_bandwidth(test_router_ip)
    
    if bandwidth:
        print("   ✓ Bandwidth data retrieved:")
        print(f"      Router: {bandwidth['router_name']}")
        print(f"      IP: {bandwidth['router_ip']}")
        print(f"      MAC: {bandwidth['router_mac']}")
        print(f"      Download: {bandwidth['download_mbps']:.2f} Mbps")
        print(f"      Upload: {bandwidth['upload_mbps']:.2f} Mbps")
        print(f"      Packets: {bandwidth['packets']}")
        print(f"      Status: {bandwidth['status']}")
        print(f"      Timestamp: {bandwidth['timestamp']}")
    else:
        print("   ⚠️ No bandwidth data available")
    
    # Monitor for 30 seconds
    print("\n7. Continuous monitoring (30 seconds)...")
    print("   Press Ctrl+C to stop early\n")
    print("   Time    | Download  | Upload    | Packets | Status")
    print("   " + "-" * 60)
    
    try:
        for i in range(6):  # 6 x 5 seconds = 30 seconds
            time.sleep(5)
            
            bandwidth = monitor.get_router_bandwidth(test_router_ip)
            if bandwidth:
                timestamp = bandwidth['timestamp'].split('T')[1].split('.')[0]
                print(f"   {timestamp} | {bandwidth['download_mbps']:>8.2f}  | "
                      f"{bandwidth['upload_mbps']:>8.2f}  | {bandwidth['packets']:>7} | "
                      f"{bandwidth['status']}")
    except KeyboardInterrupt:
        print("\n   Stopped by user")
    
    # Get statistics
    print("\n8. Retrieving statistics...")
    
    # Average bandwidth
    avg = monitor.get_average_bandwidth(test_router_ip, minutes=5)
    if avg:
        print(f"   5-minute average:")
        print(f"      Download: {avg['avg_download_mbps']:.2f} Mbps")
        print(f"      Upload: {avg['avg_upload_mbps']:.2f} Mbps")
        print(f"      Samples: {avg['sample_count']}")
    
    # Peak bandwidth
    peak = monitor.get_peak_bandwidth(test_router_ip)
    if peak:
        print(f"   Peak usage:")
        print(f"      Download: {peak['peak_download_mbps']:.2f} Mbps")
        print(f"      Upload: {peak['peak_upload_mbps']:.2f} Mbps")
    
    # History
    history = monitor.get_router_history(test_router_ip, limit=5)
    if history:
        print(f"   Recent history (last 5):")
        for entry in history:
            timestamp = entry['timestamp'].split('T')[1].split('.')[0]
            print(f"      {timestamp}: ↓{entry['download_mbps']:.2f} ↑{entry['upload_mbps']:.2f} Mbps")
    
    # Stop monitoring
    print("\n9. Stopping monitor...")
    monitor.stop()
    print("   ✓ Monitor stopped")
    
    print("\n" + "=" * 60)
    print("Test completed successfully!")
    print("=" * 60)


def test_multi_router():
    """Test monitoring multiple routers."""
    print("\n" + "=" * 60)
    print("Multi-Router Monitoring Test")
    print("=" * 60)
    
    # Add your router IPs here
    routers = [
        {"ip": "192.168.1.1", "name": "Main Router"},
        {"ip": "192.168.1.100", "name": "AP Living Room"},
        # Add more routers...
    ]
    
    print(f"\n1. Creating monitor for {len(routers)} router(s)...")
    monitor = RouterBandwidthMonitor(sampling_interval=5)
    
    for router in routers:
        monitor.add_router(router['ip'], name=router['name'])
        print(f"   ✓ Added: {router['name']} ({router['ip']})")
    
    print("\n2. Starting monitoring...")
    try:
        monitor.start()
        print("   ✓ Monitoring started")
    except PermissionError:
        print("   ❌ Permission denied! Run as Administrator/sudo")
        return
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return
    
    print("\n3. Monitoring all routers (30 seconds)...")
    print("   Press Ctrl+C to stop\n")
    
    try:
        for i in range(6):  # 6 x 5 seconds
            time.sleep(5)
            
            all_bandwidth = monitor.get_all_routers_bandwidth()
            
            print(f"\n   --- Update {i+1} ---")
            for bandwidth in all_bandwidth:
                print(f"   {bandwidth['router_name']}:")
                print(f"      ↓ {bandwidth['download_mbps']:.2f} Mbps  "
                      f"↑ {bandwidth['upload_mbps']:.2f} Mbps  "
                      f"({bandwidth['packets']} packets)")
    except KeyboardInterrupt:
        print("\n   Stopped by user")
    
    print("\n4. Stopping monitor...")
    monitor.stop()
    print("   ✓ Monitor stopped")
    
    print("\n" + "=" * 60)
    print("Multi-router test completed!")
    print("=" * 60)


def test_integration_with_get_bandwidth():
    """Test integration with existing get_bandwidth() function."""
    from router_bandwidth_monitor import get_router_bandwidth_realtime
    
    print("\n" + "=" * 60)
    print("Integration Test with get_bandwidth()")
    print("=" * 60)
    
    test_router_ip = "192.168.1.1"
    
    print(f"\n1. Creating monitor...")
    monitor = RouterBandwidthMonitor(sampling_interval=5)
    monitor.add_router(test_router_ip, name="Test Router")
    
    print("\n2. Starting monitoring...")
    try:
        monitor.start()
        print("   ✓ Monitor started")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return
    
    print("\n3. Waiting for data (10 seconds)...")
    time.sleep(10)
    
    print("\n4. Testing get_router_bandwidth_realtime()...")
    result = get_router_bandwidth_realtime(test_router_ip, monitor)
    
    print("   Result (compatible with get_bandwidth() format):")
    print(f"      latency: {result['latency']}")
    print(f"      download: {result['download']:.2f} Mbps")
    print(f"      upload: {result['upload']:.2f} Mbps")
    print(f"      quality:")
    print(f"         latency: {result['quality']['latency']}")
    print(f"         download: {result['quality']['download']}")
    print(f"         upload: {result['quality']['upload']}")
    print(f"      timestamp: {result.get('timestamp', 'N/A')}")
    print(f"      packets: {result.get('packets', 0)}")
    
    print("\n5. Stopping monitor...")
    monitor.stop()
    print("   ✓ Monitor stopped")
    
    print("\n" + "=" * 60)
    print("Integration test completed!")
    print("=" * 60)


if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║  RouterBandwidthMonitor - Test Suite                    ║")
    print("╚" + "=" * 58 + "╝")
    
    print("\nIMPORTANT:")
    print("• Edit test_router_ip in test_basic_monitoring() to match your router")
    print("• Run as Administrator (Windows) or with sudo (Linux)")
    print("• Ensure your router is online and accessible")
    print("• Generate network traffic for better results\n")
    
    print("Available tests:")
    print("  1. Basic monitoring (single router)")
    print("  2. Multi-router monitoring")
    print("  3. Integration test (with get_bandwidth)")
    print("  4. Run all tests")
    print("  0. Exit")
    
    try:
        choice = input("\nSelect test (1-4, 0 to exit): ").strip()
        
        if choice == "1":
            test_basic_monitoring()
        elif choice == "2":
            test_multi_router()
        elif choice == "3":
            test_integration_with_get_bandwidth()
        elif choice == "4":
            test_basic_monitoring()
            test_multi_router()
            test_integration_with_get_bandwidth()
        elif choice == "0":
            print("Exiting...")
        else:
            print("Invalid choice")
    
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
