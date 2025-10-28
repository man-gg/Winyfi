"""
Router Bandwidth Monitor - Real Traffic Test
Generates actual network traffic to demonstrate bandwidth monitoring.
"""

import time
import threading
import requests
from router_bandwidth_monitor import RouterBandwidthMonitor


def download_test_file(url, duration=20):
    """Download a test file to generate real traffic."""
    print(f"📥 Downloading test file for {duration} seconds...")
    print(f"   URL: {url}")
    
    start_time = time.time()
    bytes_downloaded = 0
    
    try:
        # Stream download to generate continuous traffic
        response = requests.get(url, stream=True, timeout=duration+5)
        
        for chunk in response.iter_content(chunk_size=8192):
            if time.time() - start_time >= duration:
                break
            
            if chunk:
                bytes_downloaded += len(chunk)
        
        mbytes = bytes_downloaded / (1024 * 1024)
        elapsed = time.time() - start_time
        speed = (bytes_downloaded * 8) / (elapsed * 1_000_000)
        
        print(f"   ✓ Downloaded {mbytes:.2f} MB in {elapsed:.1f}s ({speed:.2f} Mbps)")
        
    except Exception as e:
        print(f"   ⚠️ Download error: {e}")


def upload_test(duration=10):
    """Simulate upload traffic (if you have a server to upload to)."""
    print(f"📤 Upload test not implemented (requires upload server)")
    print(f"   Tip: Use speedtest-cli or browse websites with image uploads")


def test_real_bandwidth():
    """Test bandwidth monitoring with real network traffic."""
    print("=" * 70)
    print("Router Bandwidth Monitor - REAL Traffic Test")
    print("=" * 70)
    
    router_ip = "192.168.1.1"  # Change to your router IP
    
    # Test file options (choose based on your connection speed)
    test_files = {
        "small": "http://ipv4.download.thinkbroadband.com/5MB.zip",    # 5 MB
        "medium": "http://ipv4.download.thinkbroadband.com/20MB.zip",  # 20 MB
        "large": "http://ipv4.download.thinkbroadband.com/50MB.zip",   # 50 MB
    }
    
    print("\n📊 Available test file sizes:")
    print("   1. Small  (5 MB)  - Quick test")
    print("   2. Medium (20 MB) - Recommended")
    print("   3. Large  (50 MB) - Long test")
    
    choice = input("\nSelect test file (1-3, default: 2): ").strip() or "2"
    
    test_map = {"1": "small", "2": "medium", "3": "large"}
    test_size = test_map.get(choice, "medium")
    test_url = test_files[test_size]
    
    print(f"\n✓ Selected: {test_size.upper()} test file ({test_url})")
    
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
    
    # Start download in background
    print(f"\n3. Starting download test (30 seconds)...")
    download_thread = threading.Thread(
        target=download_test_file,
        args=(test_url, 25),
        daemon=True
    )
    download_thread.start()
    
    # Monitor bandwidth during download
    print("\n4. Real-time Bandwidth Monitor:")
    print("   Time     | Download  | Upload   | Packets | Total   | Status")
    print("   " + "-" * 68)
    
    max_download = 0
    max_upload = 0
    
    for i in range(6):  # 30 seconds (6 × 5 seconds)
        time.sleep(5)
        
        bandwidth = monitor.get_router_bandwidth(router_ip)
        if bandwidth:
            dl = bandwidth['download_mbps']
            ul = bandwidth['upload_mbps']
            total = dl + ul
            packets = bandwidth['packets']
            timestamp = time.strftime('%H:%M:%S')
            
            # Track peaks
            max_download = max(max_download, dl)
            max_upload = max(max_upload, ul)
            
            # Status indicator
            if total > 1:
                status = "🟢 Active"
            elif total > 0.1:
                status = "🟡 Low"
            else:
                status = "⚪ Idle"
            
            print(f"   {timestamp}  | {dl:>8.2f}  | {ul:>7.2f}  | {packets:>7} | {total:>6.2f}  | {status}")
    
    # Wait for download to finish
    download_thread.join(timeout=5)
    
    # Get final statistics
    print("\n5. Test Results:")
    print("   " + "-" * 68)
    
    # Average bandwidth
    avg = monitor.get_average_bandwidth(router_ip, minutes=1)
    if avg:
        print(f"   📊 1-Minute Average:")
        print(f"      Download: {avg['avg_download_mbps']:>8.2f} Mbps")
        print(f"      Upload:   {avg['avg_upload_mbps']:>8.2f} Mbps")
        print(f"      Samples:  {avg['sample_count']}")
    
    # Peak bandwidth
    print(f"\n   🔝 Peak Observed:")
    print(f"      Download: {max_download:>8.2f} Mbps")
    print(f"      Upload:   {max_upload:>8.2f} Mbps")
    
    # Historical data
    history = monitor.get_router_history(router_ip, limit=6)
    if history:
        print(f"\n   📜 Recent History (last 6 samples):")
        for entry in history:
            timestamp = entry['timestamp'].split('T')[1].split('.')[0]
            total = entry['download_mbps'] + entry['upload_mbps']
            
            # Visual bar
            bar_length = int(min(total * 2, 40))
            bar = "█" * bar_length
            
            print(f"      {timestamp}  ↓{entry['download_mbps']:>7.2f}  ↑{entry['upload_mbps']:>7.2f}  {bar}")
    
    # Stop monitor
    print("\n6. Stopping monitor...")
    monitor.stop()
    print("   ✓ Monitor stopped")
    
    print("\n" + "=" * 70)
    print("Test completed!")
    print("=" * 70)
    
    # Analysis
    print("\n📈 Analysis:")
    if max_download > 1:
        print(f"   ✅ Successfully captured download traffic: {max_download:.2f} Mbps peak")
    else:
        print(f"   ⚠️  Low download bandwidth detected")
        print(f"      Possible reasons:")
        print(f"      • Slow internet connection")
        print(f"      • Network congestion")
        print(f"      • Firewall blocking test servers")
    
    if max_upload > 0.5:
        print(f"   ✅ Upload traffic detected: {max_upload:.2f} Mbps")
    else:
        print(f"   ℹ️  Minimal upload traffic (normal for download test)")
    
    print("\n💡 Next Steps:")
    print("   • Browse websites while monitoring is active")
    print("   • Stream a video (YouTube, Netflix, etc.)")
    print("   • Download files from your usual sources")
    print("   • Integrate into your dashboard for continuous monitoring")


if __name__ == "__main__":
    print("\n⚠️  Run as Administrator (Windows) or with sudo (Linux)\n")
    
    # Check for requests library
    try:
        import requests
    except ImportError:
        print("❌ Error: 'requests' library not found")
        print("   Install: pip install requests\n")
        exit(1)
    
    try:
        test_real_bandwidth()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
