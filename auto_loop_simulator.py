#!/usr/bin/env python3
"""
Background Loop Simulator - Automatic Testing
Runs automatically for 60 seconds to test loop detection.
Perfect for quick testing without user interaction.
"""

import time
import random
import sys
from datetime import datetime
from scapy.all import Ether, IP, sendp, get_if_list, UDP

# Auto-configuration
DURATION = 60  # 60 seconds
PACKETS_PER_SECOND = 50  # Detectable rate
INTERFACE = None  # Auto-detect

def get_interface():
    """Auto-detect network interface."""
    interfaces = get_if_list()
    preferred = ["Wi-Fi", "wlan0", "eth0", "Ethernet", "en0"]
    
    for pref in preferred:
        if pref in interfaces:
            return pref
    
    return interfaces[0] if interfaces else None


def main():
    global INTERFACE
    
    # Banner
    print("\n" + "="*60)
    print("🔄 BACKGROUND LOOP SIMULATOR - Auto Mode")
    print("="*60)
    
    # Detect interface
    INTERFACE = get_interface()
    if not INTERFACE:
        print("❌ No network interface found!")
        sys.exit(1)
    
    print(f"📡 Interface: {INTERFACE}")
    print(f"⏱️  Duration: {DURATION} seconds")
    print(f"📊 Rate: ~{PACKETS_PER_SECOND} pps")
    print(f"🚀 Starting: {datetime.now().strftime('%H:%M:%S')}")
    print("\nGenerating traffic... (Ctrl+C to stop)")
    print("="*60 + "\n")
    
    # Run simulation
    start = time.time()
    count = 0
    
    try:
        while time.time() - start < DURATION:
            # Send batch of packets
            pkt = Ether(dst="ff:ff:ff:ff:ff:ff") / IP(src="192.168.1.100", dst="255.255.255.255") / UDP(sport=random.randint(1024, 65535), dport=67)
            
            for _ in range(5):  # 5 packets per iteration
                sendp(pkt, iface=INTERFACE, verbose=False)
                count += 1
            
            # Progress indicator
            if count % 250 == 0:
                elapsed = time.time() - start
                print(f"  ⏱️  {elapsed:.0f}s | {count} packets | {count/elapsed:.1f} pps")
            
            time.sleep(0.1)
        
        # Success
        elapsed = time.time() - start
        print(f"\n{'='*60}")
        print(f"✅ COMPLETED")
        print(f"{'='*60}")
        print(f"Sent: {count} packets in {elapsed:.1f}s ({count/elapsed:.1f} pps)")
        print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
        print(f"\n💡 Check dashboard Loop Detection Monitor for results!")
        print(f"{'='*60}\n")
        
    except KeyboardInterrupt:
        elapsed = time.time() - start
        print(f"\n\n{'='*60}")
        print(f"⏹️  STOPPED")
        print(f"{'='*60}")
        print(f"Sent: {count} packets in {elapsed:.1f}s")
        print(f"{'='*60}\n")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("Run as Administrator (Windows) or with sudo (Linux)\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Cancelled\n")
        sys.exit(0)
