#!/usr/bin/env python3
"""
Quick Loop Simulator - One-Click Testing
Run this alongside the dashboard to test real-time loop detection.
"""

import time
import random
import sys
from scapy.all import Ether, IP, ARP, sendp, get_if_list, UDP

# Simple configuration
DURATION = 60  # Run for 60 seconds
PACKETS_PER_SECOND = 50  # Moderate rate that should trigger detection
CHECK_INTERVAL = 0.1  # Send packets every 100ms

def get_default_interface():
    """Auto-detect the best network interface."""
    try:
        interfaces = get_if_list()
        preferred = ["Wi-Fi", "wlan0", "eth0", "Ethernet", "en0"]
        
        for pref in preferred:
            if pref in interfaces:
                return pref
        
        if interfaces:
            return interfaces[0]
        return None
    except:
        return None


def create_loop_packet():
    """Create a broadcast packet that will be detected as a loop."""
    # Generate broadcast packet (most detectable)
    return Ether(dst="ff:ff:ff:ff:ff:ff") / IP(src="192.168.1.100", dst="255.255.255.255") / UDP(sport=random.randint(1024, 65535), dport=67)


def main():
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║           🔄 Quick Loop Simulator for Testing                 ║")
    print("║        Run this while your dashboard is running               ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print()
    
    # Detect interface
    interface = get_default_interface()
    if not interface:
        print("❌ ERROR: No network interface found!")
        print("   Please check your network connection.")
        input("\nPress ENTER to exit...")
        sys.exit(1)
    
    print(f"📡 Using interface: {interface}")
    print()
    print(f"⚙️  Configuration:")
    print(f"   Duration: {DURATION} seconds")
    print(f"   Packet Rate: ~{PACKETS_PER_SECOND} packets/second")
    print(f"   Loop Type: Broadcast Storm")
    print()
    print("📊 Expected Dashboard Behavior:")
    print("   1. Loop Detection Monitor should show 'Loop Detected'")
    print("   2. Notification badge should appear")
    print("   3. Severity score should be 80-100")
    print("   4. Database should log the detection")
    print()
    print("💡 TIPS:")
    print("   - Keep dashboard running in another terminal")
    print("   - Enable automatic loop detection in dashboard")
    print("   - Check Loop Detection Monitor for results")
    print("   - Review database for logged detections")
    print()
    
    # Safety check
    response = input("⚠️  This will generate network traffic. Continue? (y/n): ").strip().lower()
    if response != 'y':
        print("❌ Cancelled by user.")
        sys.exit(0)
    
    print()
    print("=" * 70)
    print("🚀 STARTING LOOP SIMULATION")
    print("=" * 70)
    print()
    
    start_time = time.time()
    packet_count = 0
    
    try:
        print("🌊 Generating broadcast storm...")
        print("   (Press Ctrl+C to stop early)")
        print()
        
        while time.time() - start_time < DURATION:
            # Calculate packets to send in this batch
            packets_per_batch = max(1, int(PACKETS_PER_SECOND * CHECK_INTERVAL))
            
            # Generate and send packets
            pkt = create_loop_packet()
            for _ in range(packets_per_batch):
                sendp(pkt, iface=interface, verbose=False)
                packet_count += 1
            
            # Show progress every 10 seconds
            elapsed = time.time() - start_time
            if packet_count % 500 == 0:
                print(f"   ⏱️  {elapsed:.1f}s elapsed | {packet_count} packets sent | Rate: {packet_count/elapsed:.1f} pps")
            
            time.sleep(CHECK_INTERVAL)
        
        # Completion summary
        total_time = time.time() - start_time
        avg_rate = packet_count / total_time
        
        print()
        print("=" * 70)
        print("✅ SIMULATION COMPLETED")
        print("=" * 70)
        print()
        print(f"📊 Statistics:")
        print(f"   Total Duration: {total_time:.2f} seconds")
        print(f"   Total Packets: {packet_count}")
        print(f"   Average Rate: {avg_rate:.2f} packets/second")
        print(f"   Interface: {interface}")
        print()
        print("🔍 What to Check Now:")
        print()
        print("   1. DASHBOARD - Loop Detection Monitor:")
        print("      ✓ Should show 'Loop Detected' status")
        print("      ✓ Severity score should be 80-100")
        print("      ✓ Notification badge should be visible")
        print()
        print("   2. DATABASE - Check loop_detections table:")
        print("      ✓ New records should exist")
        print("      ✓ Status should be 'loop_detected' or 'suspicious'")
        print("      ✓ Total_packets should be high")
        print()
        print("   3. NOTIFICATIONS:")
        print("      ✓ Click notification icon in dashboard")
        print("      ✓ Should show loop detection alert")
        print()
        print("💡 If detection didn't trigger:")
        print("   - Check that dashboard loop detection is enabled")
        print("   - Verify detection interval (default 3-5 minutes)")
        print("   - Try running manual scan in Loop Detection Monitor")
        print("   - Check console output in dashboard for errors")
        print()
        
    except KeyboardInterrupt:
        total_time = time.time() - start_time
        avg_rate = packet_count / total_time if total_time > 0 else 0
        
        print()
        print()
        print("=" * 70)
        print("⏹️  SIMULATION STOPPED (User Interrupted)")
        print("=" * 70)
        print()
        print(f"📊 Statistics:")
        print(f"   Duration: {total_time:.2f} seconds (of {DURATION} planned)")
        print(f"   Packets Sent: {packet_count}")
        print(f"   Average Rate: {avg_rate:.2f} packets/second")
        print()
        
    except Exception as e:
        print()
        print(f"❌ ERROR: {e}")
        print()
        print("Common issues:")
        print("   - Not running as Administrator (Windows) or root (Linux)")
        print("   - Network interface disconnected")
        print("   - Firewall blocking packet generation")
        print()
        import traceback
        traceback.print_exc()
        
    input("\nPress ENTER to exit...")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress ENTER to exit...")
        sys.exit(1)
