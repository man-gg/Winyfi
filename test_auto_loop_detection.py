#!/usr/bin/env python3
"""
Test script for automatic loop detection functionality.
This script demonstrates the optimized loop detection system.
"""

import time
import sys
import os

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from network_utils import auto_loop_detection, detect_loops_lightweight
from datetime import datetime

def test_lightweight_detection():
    """Test the lightweight loop detection function."""
    print("🔍 Testing lightweight loop detection...")
    print("=" * 50)
    
    try:
        # Run lightweight detection
        total_packets, offenders, stats, status, severity_score = detect_loops_lightweight(
            timeout=3,  # 3 seconds for testing
            threshold=30,
            iface="Wi-Fi"
        )
        
        print(f"📊 Detection Results:")
        print(f"   Total Packets: {total_packets}")
        print(f"   Status: {status}")
        print(f"   Severity Score: {severity_score:.2f}")
        print(f"   Offenders: {len(offenders)}")
        
        if offenders:
            print(f"   Offender MACs: {', '.join(offenders)}")
        
        # Show stats for each MAC
        if stats:
            print(f"\n📈 Detailed Stats:")
            for mac, info in stats.items():
                print(f"   {mac}:")
                print(f"     - Total packets: {info['count']}")
                print(f"     - ARP packets: {info['arp_count']}")
                print(f"     - Broadcast packets: {info['broadcast_count']}")
                print(f"     - Severity: {info['severity']:.2f}")
                if info['ips']:
                    print(f"     - IPs: {', '.join(info['ips'])}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during detection: {e}")
        return False

def test_auto_detection():
    """Test the automatic loop detection with database saving."""
    print("\n🔄 Testing automatic loop detection...")
    print("=" * 50)
    
    try:
        # Run auto detection (without database saving for this test)
        result = auto_loop_detection(
            iface="Wi-Fi",
            save_to_db=False,  # Don't save to DB for this test
            api_base_url="http://localhost:5000"
        )
        
        print(f"📊 Auto Detection Results:")
        print(f"   Success: {result.get('success', False)}")
        print(f"   Status: {result.get('status', 'unknown')}")
        print(f"   Total Packets: {result.get('total_packets', 0)}")
        print(f"   Severity Score: {result.get('severity_score', 0):.2f}")
        print(f"   Offenders: {len(result.get('offenders', []))}")
        print(f"   Timestamp: {result.get('timestamp', 'unknown')}")
        
        if result.get('error'):
            print(f"   Error: {result['error']}")
        
        return result.get('success', False)
        
    except Exception as e:
        print(f"❌ Error during auto detection: {e}")
        return False

def simulate_network_activity():
    """Simulate some network activity for testing."""
    print("\n🌐 Simulating network activity...")
    print("   (This will generate some network traffic for detection)")
    
    import subprocess
    import platform
    
    # Ping some common addresses to generate traffic
    targets = ["8.8.8.8", "1.1.1.1", "192.168.1.1"]
    
    for target in targets:
        try:
            if platform.system().lower() == "windows":
                subprocess.run(["ping", "-n", "1", target], 
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
            else:
                subprocess.run(["ping", "-c", "1", target], 
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
            print(f"   ✅ Pinged {target}")
        except:
            print(f"   ⚠️ Could not ping {target}")
    
    time.sleep(1)  # Brief pause

def main():
    """Main test function."""
    print("🚀 Automatic Loop Detection Test")
    print("=" * 50)
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test 1: Lightweight detection
    print("\n1️⃣ Testing lightweight detection...")
    success1 = test_lightweight_detection()
    
    # Simulate some network activity
    simulate_network_activity()
    
    # Test 2: Auto detection
    print("\n2️⃣ Testing automatic detection...")
    success2 = test_auto_detection()
    
    # Summary
    print("\n📋 Test Summary:")
    print("=" * 50)
    print(f"Lightweight Detection: {'✅ PASS' if success1 else '❌ FAIL'}")
    print(f"Auto Detection: {'✅ PASS' if success2 else '❌ FAIL'}")
    
    if success1 and success2:
        print("\n🎉 All tests passed! Loop detection is working correctly.")
        print("\n💡 To enable automatic loop detection in the dashboard:")
        print("   1. Start the server: python server/app.py")
        print("   2. Run the dashboard: python main.py")
        print("   3. Go to Settings tab")
        print("   4. Click 'Configure Detection' to set up automatic monitoring")
    else:
        print("\n⚠️ Some tests failed. Check the error messages above.")
    
    return success1 and success2

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
