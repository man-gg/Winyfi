"""
Router Bandwidth Monitor - Test with Traffic Generation
Demonstrates monitoring with active network traffic
"""

import time
import subprocess
import sys
from router_bandwidth_monitor import RouterBandwidthMonitor

def generate_traffic(router_ip, duration=30):
    """Generate network traffic by pinging router."""
    print(f"🔄 Generating traffic to {router_ip} for {duration} seconds...")
    
    try:
        if sys.platform == "win32":
            # Windows: ping continuously
            process = subprocess.Popen(
                ["ping", "-t", router_ip],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            # Linux/Mac: ping with count
            count = duration * 2  # ~2 pings per second
            process = subprocess.Popen(
                ["ping", "-c", str(count), router_ip],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        
        time.sleep(duration)
        
        # Stop ping
        try:
            process.terminate()
            process.wait(timeout=2)
        except:
            process.kill()
        
        print("✓ Traffic generation complete")
        
    except Exception as e:
        print(f"⚠️ Traffic generation error: {e}")


def test_with_traffic():
    """Test bandwidth monitoring with active traffic."""
    print("=" * 60)
    print("Router Bandwidth Monitor - Traffic Test")
    print("=" * 60)
    
    router_ip = "192.168.1.1"  # Change to your router IP
    
    # Create and start monitor
    print("\n1. Starting bandwidth monitor...")
    monitor = RouterBandwidthMonitor(sampling_interval=5)
    monitor.add_router(router_ip, name="Test Router")
    
    try:
        monitor.start()
        print("   ✓ Monitor started")
    except PermissionError:
        print("   ❌ Permission denied! Run as Administrator")
        return
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return
    
    print("\n2. Waiting for initial data (5 seconds)...")
    time.sleep(5)
    
    # Get baseline
    baseline = monitor.get_router_bandwidth(router_ip)
    if baseline:
        print(f"   Baseline: ↓{baseline['download_mbps']:.2f} ↑{baseline['upload_mbps']:.2f} Mbps")
    
    # Generate traffic
    print("\n3. Generating network traffic...")
    generate_traffic(router_ip, duration=30)
    
    # Monitor during traffic
    print("\n4. Monitoring bandwidth during traffic (30 seconds)...")
    print("   Time    | Download  | Upload    | Packets | Total")
    print("   " + "-" * 55)
    
    for i in range(6):  # 6 samples over 30 seconds
        time.sleep(5)
        
        bandwidth = monitor.get_router_bandwidth(router_ip)
        if bandwidth:
            total = bandwidth['download_mbps'] + bandwidth['upload_mbps']
            timestamp = time.strftime('%H:%M:%S')
            print(f"   {timestamp} | {bandwidth['download_mbps']:>8.2f}  | "
                  f"{bandwidth['upload_mbps']:>8.2f}  | {bandwidth['packets']:>7} | {total:>6.2f}")
    
    # Get statistics
    print("\n5. Traffic Statistics:")
    
    # Average bandwidth
    avg = monitor.get_average_bandwidth(router_ip, minutes=1)
    if avg:
        print(f"   1-minute average:")
        print(f"      Download: {avg['avg_download_mbps']:.2f} Mbps")
        print(f"      Upload: {avg['avg_upload_mbps']:.2f} Mbps")
        print(f"      Samples: {avg['sample_count']}")
    
    # Peak bandwidth
    peak = monitor.get_peak_bandwidth(router_ip)
    if peak:
        print(f"   Peak usage:")
        print(f"      Download: {peak['peak_download_mbps']:.2f} Mbps")
        print(f"      Upload: {peak['peak_upload_mbps']:.2f} Mbps")
    
    # History
    history = monitor.get_router_history(router_ip, limit=10)
    if history:
        print(f"\n6. Recent History:")
        for entry in history[-5:]:  # Last 5 entries
            timestamp = entry['timestamp'].split('T')[1].split('.')[0]
            total = entry['download_mbps'] + entry['upload_mbps']
            print(f"      {timestamp}: ↓{entry['download_mbps']:>6.2f} ↑{entry['upload_mbps']:>6.2f} = {total:>6.2f} Mbps ({entry['packets']} pkts)")
    
    # Stop monitor
    print("\n7. Stopping monitor...")
    monitor.stop()
    print("   ✓ Monitor stopped")
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)
    print("\n💡 Tips:")
    print("   • Higher bandwidth? Browse web, download files, stream video")
    print("   • Check router activity: Open router admin page")
    print("   • Monitor longer: Increase duration for better averages")


if __name__ == "__main__":
    print("\n⚠️  IMPORTANT: Run this script as Administrator (Windows) or with sudo (Linux)\n")
    
    try:
        test_with_traffic()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
