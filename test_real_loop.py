"""
Real Loop Detection Test - Verifies loop detection works in actual loop conditions

This script helps you test if loop detection correctly identifies real network loops.

SETUP OPTIONS:

Option 1 - Physical Loop (RECOMMENDED):
    1. Get an Ethernet cable
    2. Connect two ports on the same switch/hub
    3. Run this test script
    4. Should detect loop within 5-10 seconds

Option 2 - Virtual Loop (Software Simulation):
    1. Run this script with --simulate flag
    2. Generates artificial loop traffic patterns
    3. Tests detection algorithms without physical loop

⚠️ WARNING: Physical loops can disrupt your network!
   - Only test on isolated network or during maintenance window
   - Have a plan to quickly remove the loop
   - Monitor network impact carefully

"""

import sys
import os
import time
import argparse
from datetime import datetime

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from network_utils import (
    detect_loops_lightweight, 
    detect_loops_multi_interface,
    get_default_iface
)

def print_header(title):
    """Print formatted header"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")

def print_section(title):
    """Print formatted section"""
    print("\n" + "-"*80)
    print(f"  {title}")
    print("-"*80)

def monitor_for_loop(duration=30, check_interval=5):
    """
    Monitor network for loop detection over a period of time.
    
    Args:
        duration: Total monitoring time in seconds
        check_interval: How often to check (in seconds)
    """
    print_header("REAL LOOP DETECTION TEST")
    
    print("📋 Test Configuration:")
    print(f"   - Total monitoring time: {duration} seconds")
    print(f"   - Check interval: {check_interval} seconds")
    print(f"   - Detection threshold: 100 (severity score)")
    print()
    
    print("🎯 Expected Behavior:")
    print("   WITHOUT loop: Severity < 50, Status = 'clean'")
    print("   WITH loop:    Severity > 250, Status = 'loop_detected'")
    print()
    
    input("⚠️  Press Enter when ready to start monitoring...")
    print()
    
    checks_performed = 0
    loops_detected = 0
    suspicious_detected = 0
    clean_detected = 0
    
    max_severity_seen = 0.0
    start_time = time.time()
    
    print_section(f"Starting Network Monitoring - {datetime.now().strftime('%H:%M:%S')}")
    
    while time.time() - start_time < duration:
        checks_performed += 1
        check_start = time.time()
        
        print(f"\n🔍 Check #{checks_performed} at {datetime.now().strftime('%H:%M:%S')}")
        
        try:
            # Run lightweight detection
            total_packets, offenders, stats, status, severity, metrics = detect_loops_lightweight(
                timeout=check_interval,
                threshold=100,
                iface=get_default_iface(),
                use_sampling=False  # Full capture for testing
            )
            
            # Track statistics
            if status == "loop_detected":
                loops_detected += 1
                print("   🚨 STATUS: LOOP DETECTED!")
            elif status == "suspicious":
                suspicious_detected += 1
                print("   ⚠️  STATUS: Suspicious Activity")
            else:
                clean_detected += 1
                print("   ✅ STATUS: Clean")
            
            print(f"   📊 Packets: {total_packets}, Severity: {severity:.2f}, Offenders: {len(offenders)}")
            
            if severity > max_severity_seen:
                max_severity_seen = severity
            
            # Show top offender details if any
            if offenders and stats:
                print(f"   🎯 Top Offender: {offenders[0]}")
                info = stats.get(offenders[0], {})
                print(f"      - ARP: {info.get('arp_count', 0)}, Broadcast: {info.get('broadcast_count', 0)}, STP: {info.get('stp_count', 0)}")
                print(f"      - Total packets: {info.get('count', 0)}")
            
            # Alert if loop detected
            if status == "loop_detected":
                print("\n" + "🚨"*40)
                print("   NETWORK LOOP CONFIRMED!")
                print("   Action: Remove physical loop or investigate immediately")
                print("🚨"*40)
            
            # Wait for next check (minus time spent on detection)
            elapsed = time.time() - check_start
            remaining = max(0, check_interval - elapsed)
            if remaining > 0 and time.time() - start_time + remaining < duration:
                time.sleep(remaining)
                
        except PermissionError:
            print("   ❌ ERROR: Permission denied - run as Administrator")
            return
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
    
    # Print summary
    print_section("TEST SUMMARY")
    
    print(f"⏱️  Monitoring Duration: {duration} seconds")
    print(f"🔍 Checks Performed: {checks_performed}")
    print(f"📊 Max Severity Seen: {max_severity_seen:.2f}")
    print()
    
    print("Results Breakdown:")
    print(f"  ✅ Clean: {clean_detected} ({clean_detected/max(1, checks_performed)*100:.1f}%)")
    print(f"  ⚠️  Suspicious: {suspicious_detected} ({suspicious_detected/max(1, checks_performed)*100:.1f}%)")
    print(f"  🚨 Loop Detected: {loops_detected} ({loops_detected/max(1, checks_performed)*100:.1f}%)")
    print()
    
    # Verdict
    print_header("VERDICT")
    
    if loops_detected > 0:
        print("🚨 LOOP DETECTION: WORKING ✓")
        print("   Your network has a loop and it was successfully detected!")
        print(f"   Detected in {loops_detected}/{checks_performed} checks")
        print()
        print("⚠️  ACTION REQUIRED:")
        print("   1. Identify the loop source (check physical connections)")
        print("   2. Remove the loop (disconnect cable or disable port)")
        print("   3. Run test again to verify loop is gone")
    elif max_severity_seen > 100:
        print("⚠️  SUSPICIOUS ACTIVITY DETECTED")
        print("   High network activity detected but below loop threshold")
        print(f"   Max severity: {max_severity_seen:.2f} (threshold: 100)")
        print()
        print("Possible causes:")
        print("   - Heavy legitimate network traffic")
        print("   - Intermittent loop condition")
        print("   - Broadcast storm")
    else:
        print("✅ NO LOOP DETECTED")
        print("   Your network appears healthy")
        print(f"   Max severity: {max_severity_seen:.2f} (well below threshold of 100)")
        print()
        if max_severity_seen < 30:
            print("💡 To test loop detection with an actual loop:")
            print("   1. Use an Ethernet cable")
            print("   2. Connect both ends to the same switch")
            print("   3. Run this test again")
            print("   4. Should see severity > 250 within seconds")

def simulate_loop_traffic():
    """
    Simulate loop traffic patterns to test detection without physical loop.
    Uses packet injection to create artificial loop conditions.
    """
    print_header("SIMULATED LOOP TRAFFIC TEST")
    
    print("⚠️  This test simulates loop traffic patterns without creating a real loop.")
    print("   It's safe to run but requires Administrator privileges.")
    print()
    
    try:
        from scapy.all import sendp, Ether, ARP, conf
        import random
        import threading
        
        print("📡 Getting network interface...")
        iface = get_default_iface()
        print(f"   Using interface: {iface}")
        print()
        
        # Generate fake MAC addresses for simulation
        fake_macs = [
            f"02:00:00:00:{i:02x}:{j:02x}" 
            for i in range(5) 
            for j in range(10)
        ]
        
        print("🚀 Starting simulated loop traffic...")
        print("   Will generate 200 ARP packets/second for 5 seconds")
        print("   Detection runs simultaneously to catch the traffic")
        print()
        
        # Flag to stop packet generation
        stop_sending = threading.Event()
        packets_sent = [0]  # Use list to make it mutable in thread
        
        def send_packets():
            """Send packets in background thread"""
            while not stop_sending.is_set():
                src_mac = random.choice(fake_macs)
                dst_mac = "ff:ff:ff:ff:ff:ff"
                src_ip = f"192.168.1.{random.randint(1, 254)}"
                dst_ip = f"192.168.1.{random.randint(1, 254)}"
                
                pkt = Ether(src=src_mac, dst=dst_mac) / ARP(
                    op=1,  # ARP request
                    psrc=src_ip,
                    pdst=dst_ip,
                    hwsrc=src_mac
                )
                
                try:
                    sendp(pkt, iface=iface, verbose=False)
                    packets_sent[0] += 1
                except:
                    pass
                
                # Rate limiting: ~200 packets/second
                time.sleep(0.005)
        
        # Start sending packets in background
        print("📤 Starting packet generator...")
        sender_thread = threading.Thread(target=send_packets, daemon=True)
        sender_thread.start()
        
        # Small delay to let some packets start flowing
        time.sleep(0.5)
        
        print("🔍 Running loop detection (5 seconds)...")
        
        # Run detection while packets are being sent
        total_packets, offenders, stats, status, severity, metrics = detect_loops_lightweight(
            timeout=5,
            threshold=100,
            iface=iface,
            use_sampling=False
        )
        
        # Stop sending packets
        stop_sending.set()
        sender_thread.join(timeout=2)
        
        print(f"\n✅ Sent {packets_sent[0]} simulated loop packets")
        
        print_section("SIMULATION RESULTS")
        print(f"Status: {status.upper()}")
        print(f"Severity Score: {severity:.2f}")
        print(f"Packets Captured: {total_packets}")
        print(f"Offenders: {len(offenders)}")
        print()
        
        if status == "loop_detected" or severity > 100:
            print("✅ LOOP DETECTION: WORKING ✓")
            print("   Simulated loop traffic was successfully detected!")
        else:
            print("⚠️  WARNING: Simulated traffic not detected as loop")
            print(f"   Severity ({severity:.2f}) is below threshold")
            print("   This might indicate detection needs adjustment")
        
    except ImportError:
        print("❌ ERROR: Scapy not available for simulation")
        print("   Install with: pip install scapy")
    except PermissionError:
        print("❌ ERROR: Permission denied")
        print("   Run as Administrator to send packets")
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

def quick_baseline_test():
    """Quick test to establish network baseline"""
    print_header("NETWORK BASELINE TEST")
    
    print("📊 This test establishes your network's baseline metrics")
    print("   Run this BEFORE creating any loops to know what's normal")
    print()
    
    try:
        print("🔍 Scanning network for 10 seconds...")
        
        total_packets, offenders, stats, status, severity, metrics = detect_loops_lightweight(
            timeout=10,
            threshold=100,
            iface=get_default_iface(),
            use_sampling=False
        )
        
        print_section("BASELINE RESULTS")
        print(f"Status: {status.upper()}")
        print(f"Severity Score: {severity:.2f}")
        print(f"Total Packets: {total_packets}")
        print(f"Unique MACs: {metrics.get('unique_macs', len(stats))}")
        print()
        
        print("📊 Traffic Breakdown:")
        total_arp = sum(info.get('arp_count', 0) for info in stats.values())
        total_broadcast = sum(info.get('broadcast_count', 0) for info in stats.values())
        total_stp = sum(info.get('stp_count', 0) for info in stats.values())
        
        print(f"   ARP packets: {total_arp}")
        print(f"   Broadcast packets: {total_broadcast}")
        print(f"   STP packets: {total_stp}")
        print()
        
        print("💡 BASELINE INTERPRETATION:")
        if severity < 30:
            print("   ✅ Very healthy network - minimal broadcast traffic")
        elif severity < 50:
            print("   ✅ Healthy network - normal activity levels")
        elif severity < 100:
            print("   ⚠️  Moderately busy network - but within normal range")
        else:
            print("   🚨 High activity - investigate before testing loops")
        
        print()
        print("📝 Save these baseline values:")
        print(f"   - Normal severity: {severity:.2f}")
        print(f"   - Normal packets: {total_packets}")
        print()
        print("When you create a loop, severity should jump to 250+ immediately")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Test loop detection with real or simulated loops",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Get baseline (run BEFORE creating loop)
  python test_real_loop.py --baseline
  
  # Monitor for real loop (create physical loop first)
  python test_real_loop.py --monitor --duration 60
  
  # Simulate loop traffic (safe, no physical loop needed)
  python test_real_loop.py --simulate
  
  # Quick 15-second test
  python test_real_loop.py --monitor --duration 15 --interval 5
        """
    )
    
    parser.add_argument('--baseline', action='store_true',
                        help='Run baseline test to establish normal network metrics')
    parser.add_argument('--monitor', action='store_true',
                        help='Monitor network for loop detection')
    parser.add_argument('--simulate', action='store_true',
                        help='Simulate loop traffic (requires scapy)')
    parser.add_argument('--duration', type=int, default=30,
                        help='Monitoring duration in seconds (default: 30)')
    parser.add_argument('--interval', type=int, default=5,
                        help='Check interval in seconds (default: 5)')
    
    args = parser.parse_args()
    
    # If no specific test chosen, show menu
    if not (args.baseline or args.monitor or args.simulate):
        print_header("LOOP DETECTION TEST SUITE")
        print("Choose a test to run:\n")
        print("1. Baseline Test - Establish normal network metrics (SAFE)")
        print("2. Real Loop Monitor - Detect actual network loops (requires physical loop)")
        print("3. Simulated Loop Test - Test with artificial traffic (SAFE, requires admin)")
        print()
        
        choice = input("Enter choice (1-3) or 'q' to quit: ").strip()
        
        if choice == '1':
            quick_baseline_test()
        elif choice == '2':
            monitor_for_loop(duration=args.duration, check_interval=args.interval)
        elif choice == '3':
            simulate_loop_traffic()
        else:
            print("Exiting...")
            return
    else:
        # Run specified test
        if args.baseline:
            quick_baseline_test()
        elif args.monitor:
            monitor_for_loop(duration=args.duration, check_interval=args.interval)
        elif args.simulate:
            simulate_loop_traffic()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        print("Exiting...")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
