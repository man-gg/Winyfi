"""
Quick Loop Detection Test
Tests the enhanced loop detection with lower thresholds and better logging.
"""

import sys
import time
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

print("="*70)
print("🧪 LOOP DETECTION TEST - Enhanced Version")
print("="*70)
print("\nThis test verifies:")
print("  ✓ Traffic capture is working")
print("  ✓ Broadcast packets are detected")
print("  ✓ Lower thresholds trigger detection")
print("  ✓ Logging provides diagnostic info")
print("\n" + "="*70)

# Test 1: Basic traffic capture
print("\n📋 TEST 1: Basic Traffic Capture (10 seconds)")
print("-"*70)

try:
    from network_utils import detect_loops_lightweight
    
    print("⏱️  Capturing traffic for 10 seconds...")
    total, offenders, stats, status, severity, metrics = detect_loops_lightweight(
        timeout=10,
        threshold=15,  # LOWERED threshold
        iface=None,
        use_sampling=False  # DISABLED sampling
    )
    
    print(f"\n✅ Capture completed!")
    print(f"   Total packets: {total}")
    print(f"   Unique MACs: {len(stats)}")
    print(f"   Offenders: {len(offenders)}")
    print(f"   Status: {status.upper()}")
    print(f"   Max severity: {severity:.2f}")
    
    if total == 0:
        print("\n❌ CRITICAL: No packets captured!")
        print("   → Run as Administrator")
        print("   → Check network connection")
        print("   → Verify interface is active")
    else:
        print(f"\n📊 Traffic breakdown:")
        for mac, info in list(stats.items())[:5]:
            print(f"   {mac}:")
            print(f"      Total: {info['count']} packets")
            print(f"      ARPs: {info['arp_count']}")
            print(f"      Broadcasts: {info['broadcast_count']}")
            print(f"      Severity: {info['severity']:.2f}")
        
        if status == "clean":
            print("\n🟡 Status: CLEAN")
            print("   This is normal if no loop simulator is running.")
            print("   To test detection, run: python auto_loop_simulator.py")
        elif status == "suspicious":
            print("\n🟠 Status: SUSPICIOUS")
            print("   Some unusual traffic detected.")
        elif status == "loop_detected":
            print("\n🔴 Status: LOOP DETECTED!")
            print("   Loop detection is working correctly!")
    
except PermissionError:
    print("\n❌ PERMISSION ERROR")
    print("   → Right-click PowerShell and select 'Run as Administrator'")
    print("   → Then run this script again")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: Multi-interface detection
print("\n\n📋 TEST 2: Multi-Interface Detection")
print("-"*70)

try:
    from network_utils import detect_loops_multi_interface, get_all_active_interfaces
    
    interfaces = get_all_active_interfaces()
    print(f"   Active interfaces: {len(interfaces)}")
    for iface in interfaces:
        print(f"      • {iface}")
    
    print("\n⏱️  Running multi-interface scan...")
    total, offenders, stats, status, severity, metrics = detect_loops_multi_interface(
        timeout=5,
        threshold=15,  # LOWERED threshold
        use_sampling=False  # DISABLED sampling
    )
    
    print(f"\n✅ Multi-interface scan completed!")
    print(f"   Interfaces scanned: {metrics.get('interfaces_scanned', 'Unknown')}")
    print(f"   Total packets: {total}")
    print(f"   Unique MACs: {len(stats)}")
    print(f"   Offenders: {len(offenders)}")
    print(f"   Status: {status.upper()}")
    print(f"   Max severity: {severity:.2f}")
    print(f"   Cross-interface activity: {metrics.get('cross_interface_activity', False)}")
    
    if offenders:
        print(f"\n🚨 Offending MACs detected:")
        for mac in offenders[:5]:
            if mac in stats:
                info = stats[mac]
                interfaces_seen = info.get('interfaces', ['Unknown'])
                print(f"   {mac}:")
                print(f"      Interfaces: {', '.join(interfaces_seen)}")
                print(f"      Packets: {info.get('count', 0)}")
                print(f"      Severity: {info.get('severity', 0):.2f}")
    
except Exception as e:
    print(f"\n❌ Multi-interface test failed: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Check for simulator traffic
print("\n\n📋 TEST 3: Simulator Traffic Check")
print("-"*70)

if total > 100 and severity > 20:
    print("✅ Significant traffic detected!")
    print("   Loop simulator may be running or network is active.")
else:
    print("🟡 Low traffic detected.")
    print("\n💡 To test loop detection:")
    print("   1. Open another PowerShell as Administrator")
    print("   2. Run: python auto_loop_simulator.py")
    print("   3. Wait 60 seconds")
    print("   4. Run this test again")
    print("\n   The simulator generates ~50 broadcast packets/second")
    print("   which should trigger loop detection.")

# Summary
print("\n\n" + "="*70)
print("📊 TEST SUMMARY")
print("="*70)

if total > 0:
    print("✅ Traffic capture: WORKING")
else:
    print("❌ Traffic capture: FAILED (run as Administrator)")

if len(stats) > 0:
    print("✅ MAC detection: WORKING")
else:
    print("⚠️  MAC detection: No MACs detected")

if status != "clean":
    print("✅ Loop detection: WORKING (detected suspicious activity)")
elif total > 50:
    print("🟡 Loop detection: READY (no loops detected, which is normal)")
else:
    print("⚠️  Loop detection: Insufficient traffic to test")

print("\n💡 Next Steps:")
print("   • If tests passed: Loop detection is working!")
print("   • If no traffic: Check network connection and run as Admin")
print("   • To test with loop: Run auto_loop_simulator.py")
print("   • For diagnosis: Run diagnose_loop_detection.py")

print("\n" + "="*70)
