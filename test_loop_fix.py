"""
Quick Test Script for Loop Detection False Positive Fix
Run this to verify that normal network traffic is not flagged as a loop.
"""

import sys
import os

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from network_utils import detect_loops_lightweight, detect_loops_multi_interface, get_default_iface

def test_loop_detection():
    """Test loop detection with new thresholds"""
    print("="*70)
    print("LOOP DETECTION FALSE POSITIVE FIX - TEST")
    print("="*70)
    print()
    
    print("📋 Test Configuration:")
    print("   - Timeout: 5 seconds")
    print("   - Threshold: 100 (raised from 30-50)")
    print("   - Duplicate detection: ENABLED")
    print("   - Legitimate traffic recognition: ENHANCED")
    print()
    
    print("🔍 Running single interface detection...")
    print("-"*70)
    
    try:
        iface = get_default_iface()
        print(f"📡 Using interface: {iface}")
        print()
        
        total_packets, offenders, stats, status, severity, metrics = detect_loops_lightweight(
            timeout=5,
            threshold=100,
            iface=iface,
            use_sampling=True
        )
        
        print()
        print("📊 RESULTS:")
        print("-"*70)
        print(f"Total packets captured: {total_packets}")
        print(f"Unique MACs detected: {metrics.get('unique_macs', len(stats))}")
        print(f"Status: {status.upper()}")
        print(f"Max severity score: {severity:.2f}")
        print(f"Offenders detected: {len(offenders)}")
        print()
        
        # Show top 5 MACs by severity
        if stats:
            print("Top 5 devices by severity:")
            sorted_macs = sorted(stats.items(), key=lambda x: x[1].get('severity', 0), reverse=True)[:5]
            for mac, info in sorted_macs:
                print(f"  {mac}:")
                print(f"    Severity: {info.get('severity', 0):.2f}")
                print(f"    Packets: {info.get('count', 0)}")
                print(f"    ARP: {info.get('arp_count', 0)}, Broadcast: {info.get('broadcast_count', 0)}, STP: {info.get('stp_count', 0)}")
        
        print()
        print("="*70)
        print("INTERPRETATION:")
        print("="*70)
        
        if status == "clean":
            print("✅ PASSED - No loop detected (normal network behavior)")
            print("   Your network is healthy!")
        elif status == "suspicious":
            print("⚠️ WARNING - Suspicious activity detected")
            print(f"   Severity score ({severity:.2f}) is above threshold but below loop level")
            print("   This might indicate heavy network activity but not a loop")
        else:  # loop_detected
            print("🚨 LOOP DETECTED")
            print(f"   Severity score ({severity:.2f}) indicates a network loop!")
            print("   Please check your network topology")
        
        print()
        print("Expected results for NORMAL networks:")
        print("  - Status: clean")
        print("  - Severity: 10-50")
        print("  - Few or no offenders")
        print()
        
        if severity < 100 and status == "clean":
            print("🎉 TEST PASSED - False positive issue is FIXED!")
            print("   Loop detection is now working correctly.")
        elif severity < 100 and status == "suspicious":
            print("⚠️ TEST MARGINAL - Still flagging as suspicious")
            print("   Consider raising threshold further if this is a normal network.")
        else:
            print("❌ TEST NEEDS REVIEW - High severity detected")
            print("   Either you have a real loop OR thresholds need more adjustment.")
        
    except PermissionError:
        print("❌ ERROR: Permission denied!")
        print("   Please run this script as Administrator/root")
        print("   Windows: Right-click → Run as Administrator")
        print("   Linux: sudo python test_loop_fix.py")
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("="*70)
    print("For more information, see LOOP_DETECTION_FIX.md")
    print("="*70)

if __name__ == "__main__":
    test_loop_detection()
