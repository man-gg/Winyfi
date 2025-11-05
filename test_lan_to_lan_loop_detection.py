"""
Test Script for LAN-to-LAN Cable Loop Detection
================================================

This script tests the enhanced loop detection system that can detect
physical cable loops (e.g., Router LAN1 connected to Router LAN2).

Detection capabilities:
- ARP broadcast storms (>200 ARP/sec)
- Broadcast packet floods (>300 broadcasts in 2 sec)
- Repetitive packet patterns (low entropy)
- High sustained packet rates (>100 PPS)

Usage:
    python test_lan_to_lan_loop_detection.py

Requirements:
    - Run as Administrator (for packet capture)
    - Network interface available
"""

import sys
import time
from datetime import datetime
from network_utils import detect_loops, get_default_iface

def print_header(text):
    """Print formatted header"""
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70 + "\n")

def print_section(text):
    """Print formatted section"""
    print(f"\n--- {text} ---")

def test_loop_detection_with_monitoring():
    """Test loop detection with real-time monitoring"""
    print_header("LAN-TO-LAN CABLE LOOP DETECTION TEST")
    
    # Get network interface
    iface = get_default_iface()
    print(f"🔍 Monitoring interface: {iface}")
    print(f"⏱️  Test duration: 5 seconds (with early exit on severe loops)")
    print(f"📊 Detection thresholds:")
    print(f"   - ARP broadcast storm: >200 ARP/sec")
    print(f"   - Broadcast flood: >300 packets/2sec")
    print(f"   - High rate: >100 packets/sec")
    print(f"   - Low entropy: <1.0 (repetitive patterns)")
    print(f"   - EARLY EXIT: >300 PPS (severe storm)")
    
    print("\n" + "="*70)
    print("🚨 INSTRUCTIONS:")
    print("="*70)
    print("1. Run this script BEFORE creating the loop (baseline)")
    print("2. Then physically connect LAN1 to LAN2 on your router")
    print("3. Run this script AGAIN (during loop)")
    print("4. Compare the results")
    print("\n⚡ NEW: Early exit detection!")
    print("   - Stops capture immediately when severe loop detected (>300 PPS)")
    print("   - Prevents network saturation during test")
    print("   - Reports findings before your internet dies")
    print("\nNOTE: If STP is enabled, the loop may be blocked immediately.")
    print("      Disable STP or test with a dumb switch for best results.")
    print("="*70)
    
    input("\n⏸️  Press ENTER to start monitoring...")
    
    print_section(f"Starting packet capture at {datetime.now().strftime('%H:%M:%S')}")
    
    try:
        # Run advanced loop detection with reduced timeout
        start_time = time.time()
        total_packets, offenders, stats, metrics = detect_loops(
            timeout=5,  # Reduced from 10 to 5 seconds
            threshold=100,
            iface=iface,
            enable_advanced=True
        )
        elapsed = time.time() - start_time
        
        print_section("DETECTION RESULTS")
        print(f"✅ Capture completed in {elapsed:.2f} seconds")
        
        # Early exit notification
        if metrics.get('early_exit', False):
            print(f"\n⚡ EARLY EXIT TRIGGERED!")
            print(f"   Reason: {metrics.get('early_exit_reason', 'Unknown')}")
            print(f"   Duration: {metrics.get('duration', 0):.2f}s / {metrics.get('requested_duration', 5)}s requested")
            print(f"   Captured before exit: {metrics.get('packets_captured', 0)} packets")
            print(f"   ⚠️  Severe loop detected - stopped capture to protect network\n")
        
        print(f"📦 Total packets analyzed: {total_packets}")
        print(f"📊 Packets captured: {metrics.get('packets_captured', total_packets)}")
        print(f"🔍 Unique MAC addresses: {metrics['total_unique_macs']}")
        print(f"🌐 Unique IP addresses: {metrics['total_unique_ips']}")
        print(f"🏢 Unique subnets: {metrics['total_unique_subnets']}")
        
        # Check for loop detection
        print_section("LOOP DETECTION STATUS")
        
        if metrics.get('arp_storm_detected', False):
            print("🚨 ARP STORM DETECTED! ⚠️")
            print(f"   Storm rate: {metrics.get('storm_rate', 0):.0f} packets/sec")
        
        if metrics.get('broadcast_flood_detected', False):
            print("🚨 BROADCAST FLOOD DETECTED! ⚠️")
            print(f"   Storm rate: {metrics.get('storm_rate', 0):.0f} packets/sec")
        
        if not metrics.get('arp_storm_detected', False) and not metrics.get('broadcast_flood_detected', False):
            print("✅ No storms detected - network appears normal")
        
        # Display offenders
        if offenders:
            print_section(f"LOOP OFFENDERS DETECTED: {len(offenders)}")
            for mac in offenders:
                if mac in stats:
                    info = stats[mac]
                    print(f"\n🔴 MAC: {mac}")
                    print(f"   Total packets: {info['count']}")
                    print(f"   ARP broadcasts: {info['arp_count']}")
                    print(f"   Other broadcasts: {info.get('broadcast_count', 0)}")
                    
                    # Check for single-router loop
                    if info.get('loop_on_single_router', False):
                        print(f"\n   ⚠️  SINGLE-ROUTER LOOP DETECTED!")
                        print(f"   📌 Reason: {info.get('loop_reason', 'Unknown')}")
                        print(f"   🔧 Action: {info.get('suggested_action', 'Investigate')}")
                    
                    # Display severity
                    severity = info.get('severity', 0)
                    if isinstance(severity, dict):
                        severity_value = severity.get('total', 0)
                        print(f"   Severity: {severity_value:.1f}")
                        print(f"   - Frequency: {severity.get('frequency', 0):.1f}")
                        print(f"   - Bursts: {severity.get('bursts', 0):.1f}")
                        print(f"   - Entropy: {severity.get('entropy', 0):.1f}")
                    else:
                        print(f"   Severity: {severity:.1f}")
                    
                    # Display IPs
                    if info.get('ips'):
                        print(f"   IPs: {', '.join(info['ips'][:3])}")
                    
                    # Legitimacy check
                    if info.get('is_legitimate', False):
                        print(f"   ℹ️  Marked as legitimate: {info.get('legitimate_reason', 'Unknown')}")
        else:
            print("✅ No offenders detected - network traffic is normal")
        
        # Summary
        print_section("SUMMARY")
        if offenders and any(stats[mac].get('loop_on_single_router', False) for mac in offenders if mac in stats):
            print("❌ LOOP DETECTED - Physical cable loop suspected!")
            print("🔧 Recommended action: Check for LAN-to-LAN cable connections")
            print("   - Disconnect any cables between LAN ports on the same device")
            print("   - Check switch ports for loops")
            print("   - Verify STP is enabled and functioning")
        elif metrics.get('arp_storm_detected', False) or metrics.get('broadcast_flood_detected', False):
            print("⚠️  BROADCAST STORM DETECTED - Possible loop condition")
            print("   - May be a transient condition")
            print("   - Monitor for continued high traffic")
        else:
            print("✅ NETWORK HEALTHY - No loops detected")
            print("   - All traffic patterns appear normal")
            print("   - No broadcast storms detected")
        
        print("\n" + "="*70)
        print("Test completed successfully!")
        print("="*70 + "\n")
        
        return metrics.get('arp_storm_detected', False) or metrics.get('broadcast_flood_detected', False)
        
    except PermissionError:
        print("\n❌ ERROR: Permission denied!")
        print("   Please run this script as Administrator/root")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n" + "="*70)
    print("  LAN-to-LAN Cable Loop Detection Test")
    print("  Enhanced Loop Detection System v2.0")
    print("="*70)
    
    try:
        loop_detected = test_loop_detection_with_monitoring()
        
        if loop_detected:
            print("\n⚠️  RECOMMENDATION:")
            print("   A loop condition was detected. If this is a test:")
            print("   1. Disconnect the LAN-to-LAN cable")
            print("   2. Wait 10 seconds for traffic to normalize")
            print("   3. Run the test again to verify it's clean")
        
        sys.exit(0 if not loop_detected else 1)
        
    except KeyboardInterrupt:
        print("\n\n⏸️  Test interrupted by user")
        sys.exit(130)
