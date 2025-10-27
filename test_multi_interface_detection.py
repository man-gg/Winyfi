#!/usr/bin/env python3
"""
Test script for multi-interface loop detection
"""

import sys
from network_utils import get_all_active_interfaces, detect_loops_multi_interface

def test_interface_detection():
    """Test 1: Check if multiple interfaces are detected"""
    print("=" * 60)
    print("TEST 1: Interface Detection")
    print("=" * 60)
    
    interfaces = get_all_active_interfaces()
    
    print(f"\n✓ Found {len(interfaces)} active interface(s):")
    for iface in interfaces:
        print(f"  - {iface}")
    
    if len(interfaces) == 0:
        print("\n❌ ERROR: No active interfaces found!")
        print("   Make sure at least one network interface is connected.")
        return False
    elif len(interfaces) == 1:
        print(f"\n⚠️  WARNING: Only 1 interface found: {interfaces[0]}")
        print("   Multi-interface detection will work but only monitor one segment.")
    else:
        print(f"\n✅ SUCCESS: {len(interfaces)} interfaces available for monitoring!")
    
    return True


def test_multi_interface_detection():
    """Test 2: Run actual multi-interface loop detection"""
    print("\n" + "=" * 60)
    print("TEST 2: Multi-Interface Loop Detection")
    print("=" * 60)
    print("\nRunning 5-second scan across all interfaces...")
    print("(This will capture real network traffic)\n")
    
    try:
        total_packets, offenders, stats, status, severity, metrics = detect_loops_multi_interface(
            timeout=5,
            threshold=30,
            use_sampling=True
        )
        
        print("\n" + "=" * 60)
        print("RESULTS:")
        print("=" * 60)
        
        print(f"\n📊 Overall Status: {status.upper()}")
        print(f"   Severity Score: {severity:.2f}/100")
        print(f"   Total Packets: {total_packets}")
        print(f"   Offenders Found: {len(offenders)}")
        print(f"   Unique MACs: {metrics.get('unique_macs', 0)}")
        
        print(f"\n🌐 Network Coverage:")
        print(f"   Interfaces Scanned: {len(metrics.get('interfaces_scanned', []))}/{metrics.get('total_interfaces', 0)}")
        print(f"   Interface Names: {', '.join(metrics.get('interfaces_scanned', []))}")
        print(f"   Cross-Interface Activity: {'⚠️ YES' if metrics.get('cross_interface_activity') else '✓ No'}")
        
        print(f"\n⚡ Performance:")
        print(f"   Scan Duration: {metrics.get('detection_duration', 0):.2f}s")
        print(f"   Packets/Second: {metrics.get('packets_per_second', 0):.1f}")
        
        # Per-interface breakdown
        interface_results = metrics.get('interface_results', [])
        if interface_results:
            print(f"\n📡 Per-Interface Breakdown:")
            for result in interface_results:
                iface = result.get('interface', 'Unknown')
                pkts = result.get('packets', 0)
                off_count = len(result.get('offenders', []))
                iface_status = result.get('status', 'unknown')
                icon = "⚠️" if iface_status in ["loop_detected", "suspicious"] else "✓"
                print(f"   {icon} {iface:20s} {pkts:5d} packets, {off_count} offenders, status: {iface_status}")
        
        # Show offenders if any
        if offenders:
            print(f"\n⚠️  OFFENDERS DETECTED:")
            for mac in offenders:
                info = stats.get(mac, {})
                interfaces = info.get('interfaces', ['Unknown'])
                sev = info.get('severity', 0)
                if isinstance(sev, dict):
                    sev = sev.get('total', 0)
                print(f"   - {mac}")
                print(f"     Severity: {sev:.2f}")
                print(f"     Seen on: {', '.join(interfaces)}")
                if len(interfaces) > 1:
                    print(f"     ⚠️  CROSS-INTERFACE ACTIVITY!")
        
        print("\n" + "=" * 60)
        
        # Assessment
        if status == "loop_detected":
            print("❌ LOOP DETECTED! Your network has suspicious activity.")
        elif status == "suspicious":
            print("⚠️  SUSPICIOUS ACTIVITY. Monitor closely.")
        else:
            print("✅ NETWORK CLEAN. All systems operating normally.")
        
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR during detection: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_save():
    """Test 3: Verify database integration works"""
    print("\n" + "=" * 60)
    print("TEST 3: Database Integration")
    print("=" * 60)
    
    try:
        from db import save_loop_detection
        
        # Test data
        test_metrics = {
            "detection_method": "multi_interface",
            "interfaces_scanned": ["Wi-Fi", "Ethernet"],
            "total_interfaces": 2,
            "cross_interface_activity": False,
            "unique_macs": 5
        }
        
        print("\nSaving test detection to database...")
        
        detection_id = save_loop_detection(
            total_packets=100,
            offenders=[],
            stats={},
            status="clean",
            severity_score=10.5,
            interface="Wi-Fi, Ethernet",
            duration=5.5,
            efficiency_metrics=test_metrics
        )
        
        if detection_id:
            print(f"✅ Successfully saved to database (ID: {detection_id})")
            print(f"   Interface: Wi-Fi, Ethernet (multi-interface)")
            return True
        else:
            print("❌ Failed to save to database")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("MULTI-INTERFACE LOOP DETECTION TEST SUITE")
    print("=" * 60)
    print("\nThis will test:")
    print("1. Interface detection (finds all active NICs)")
    print("2. Multi-interface scanning (parallel packet capture)")
    print("3. Database integration (saves results)")
    print("\n⚠️  NOTE: Requires Administrator/root privileges for packet capture")
    print("=" * 60)
    
    input("\nPress ENTER to start tests...")
    
    # Run tests
    results = []
    
    results.append(("Interface Detection", test_interface_detection()))
    results.append(("Multi-Interface Detection", test_multi_interface_detection()))
    results.append(("Database Integration", test_database_save()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name:30s} {status}")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    print("=" * 60)
    print(f"Total: {passed_count}/{total_count} tests passed")
    print("=" * 60)
    
    if passed_count == total_count:
        print("\n✅ ALL TESTS PASSED!")
        print("\nYour multi-interface loop detection is ready to use!")
        print("\nNext steps:")
        print("1. Start the dashboard: python main.py")
        print("2. Enable automatic loop detection")
        print("3. Monitor entire network regardless of connection method")
    else:
        print(f"\n⚠️  {total_count - passed_count} TEST(S) FAILED")
        print("\nPlease check:")
        print("1. Running as Administrator (Windows) or root (Linux)")
        print("2. At least one network interface is connected")
        print("3. Database connection is working")
    
    return passed_count == total_count


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
