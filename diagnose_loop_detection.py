"""
Loop Detection Diagnostic Tool
Identifies why loop detection isn't working and provides detailed logging.
"""

import sys
import time
from scapy.all import sniff
from scapy.layers.l2 import Ether, ARP
from scapy.layers.inet import IP, TCP, UDP
from collections import defaultdict
import logging

# Setup detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('loop_detection_diagnostic.log'),
        logging.StreamHandler()
    ]
)

def diagnose_traffic_capture(timeout=10, iface=None):
    """
    Diagnose traffic capture to see what's actually being captured.
    """
    print("\n" + "="*70)
    print("🔍 LOOP DETECTION DIAGNOSTIC TOOL")
    print("="*70)
    print(f"\n⏱️  Capturing traffic for {timeout} seconds...")
    print(f"📡 Interface: {iface or 'Default (auto-detect)'}")
    print("\n" + "-"*70)
    
    packet_types = defaultdict(int)
    mac_packets = defaultdict(int)
    broadcast_packets = defaultdict(int)
    arp_packets = defaultdict(int)
    total_packets = 0
    
    start_time = time.time()
    
    def packet_analysis(pkt):
        nonlocal total_packets
        total_packets += 1
        
        try:
            # Log every packet for debugging
            if total_packets <= 20:  # First 20 packets
                logging.debug(f"Packet #{total_packets}: {pkt.summary()}")
            
            if pkt.haslayer(Ether):
                src_mac = pkt[Ether].src
                dst_mac = pkt[Ether].dst
                
                mac_packets[src_mac] += 1
                
                # Check for broadcast
                if dst_mac == "ff:ff:ff:ff:ff:ff":
                    broadcast_packets[src_mac] += 1
                    packet_types["Broadcast (Ethernet)"] += 1
                    logging.debug(f"  → BROADCAST from {src_mac}")
                
                # Check for ARP
                if pkt.haslayer(ARP):
                    if pkt[ARP].op == 1:  # ARP Request
                        arp_packets[src_mac] += 1
                        packet_types["ARP Request"] += 1
                        logging.debug(f"  → ARP REQUEST from {src_mac} for {pkt[ARP].pdst}")
                    elif pkt[ARP].op == 2:  # ARP Reply
                        packet_types["ARP Reply"] += 1
                        logging.debug(f"  → ARP REPLY from {src_mac}")
                
                # Check for IPv4 broadcast
                if pkt.haslayer(IP) and pkt[IP].dst == "255.255.255.255":
                    broadcast_packets[src_mac] += 1
                    packet_types["Broadcast (IP)"] += 1
                    logging.debug(f"  → IP BROADCAST from {src_mac}")
                
                # Check for UDP (DHCP, mDNS, etc.)
                if pkt.haslayer(UDP):
                    sport = pkt[UDP].sport
                    dport = pkt[UDP].dport
                    
                    if sport in (67, 68) or dport in (67, 68):
                        packet_types["DHCP"] += 1
                    elif dport == 5353 or sport == 5353:
                        packet_types["mDNS"] += 1
                    elif dport == 137 or sport == 137:
                        packet_types["NetBIOS"] += 1
                    else:
                        packet_types["UDP Other"] += 1
                
                # Check for STP
                if dst_mac == "01:80:c2:00:00:00":
                    packet_types["STP"] += 1
                    logging.debug(f"  → STP from {src_mac}")
                
                # Check for TCP
                if pkt.haslayer(TCP):
                    packet_types["TCP"] += 1
                
                # Generic IP
                if pkt.haslayer(IP) and dst_mac != "ff:ff:ff:ff:ff:ff":
                    packet_types["Unicast IP"] += 1
        
        except Exception as e:
            logging.error(f"Error analyzing packet: {e}")
    
    # Capture packets
    try:
        print("\n📦 Starting packet capture...")
        sniff(prn=packet_analysis, timeout=timeout, store=0, iface=iface)
    except PermissionError:
        print("\n❌ PERMISSION ERROR!")
        print("   → Run this script as Administrator")
        return
    except Exception as e:
        print(f"\n❌ CAPTURE ERROR: {e}")
        logging.error(f"Capture failed: {e}")
        return
    
    elapsed = time.time() - start_time
    
    # Print results
    print("\n" + "="*70)
    print("📊 DIAGNOSTIC RESULTS")
    print("="*70)
    
    print(f"\n⏱️  Capture Duration: {elapsed:.2f} seconds")
    print(f"📦 Total Packets Captured: {total_packets}")
    print(f"📈 Packets Per Second: {total_packets/elapsed:.1f}")
    
    if total_packets == 0:
        print("\n❌ CRITICAL ISSUE: NO PACKETS CAPTURED!")
        print("\nPossible Causes:")
        print("  1. Not running as Administrator")
        print("  2. Wrong network interface selected")
        print("  3. Network interface is down or disconnected")
        print("  4. Firewall blocking packet capture")
        print("  5. WinPcap/Npcap not installed properly")
        print("\n✅ Solutions:")
        print("  • Run as Administrator (right-click → Run as Administrator)")
        print("  • Check network connection (ipconfig)")
        print("  • Verify interface name")
        print("  • Install/reinstall Npcap (https://npcap.com)")
        return
    
    # Packet Types
    print(f"\n📋 Packet Types Detected:")
    if packet_types:
        for ptype, count in sorted(packet_types.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_packets) * 100
            print(f"   {ptype:25} {count:6} ({percentage:5.1f}%)")
    else:
        print("   ⚠️  No specific packet types identified")
    
    # Top MAC addresses
    print(f"\n🔝 Top 10 MAC Addresses by Packet Count:")
    sorted_macs = sorted(mac_packets.items(), key=lambda x: x[1], reverse=True)[:10]
    for mac, count in sorted_macs:
        broadcast_count = broadcast_packets.get(mac, 0)
        arp_count = arp_packets.get(mac, 0)
        print(f"   {mac}  →  {count:4} packets  (Broadcasts: {broadcast_count}, ARPs: {arp_count})")
    
    # Broadcast traffic analysis
    print(f"\n📡 Broadcast Traffic Analysis:")
    total_broadcasts = sum(broadcast_packets.values())
    total_arps = sum(arp_packets.values())
    
    if total_broadcasts == 0:
        print("   ⚠️  WARNING: NO BROADCAST TRAFFIC DETECTED!")
        print("   This is unusual for a typical network.")
        print("   Loop detection relies on broadcast traffic (ARP, DHCP, mDNS).")
    else:
        print(f"   Total Broadcast Packets: {total_broadcasts} ({(total_broadcasts/total_packets)*100:.1f}%)")
        print(f"   Total ARP Requests: {total_arps} ({(total_arps/total_packets)*100:.1f}%)")
        
        # Find potential loop indicators
        print(f"\n🚨 Potential Loop Indicators:")
        found_issues = False
        
        for mac, count in sorted(broadcast_packets.items(), key=lambda x: x[1], reverse=True)[:5]:
            broadcast_rate = count / elapsed
            arp_rate = arp_packets.get(mac, 0) / elapsed
            
            # Calculate simple severity
            severity = (count * 2 + arp_packets.get(mac, 0) * 3) / elapsed
            
            if broadcast_rate > 5:  # More than 5 broadcasts/sec
                found_issues = True
                print(f"   ⚠️  {mac}")
                print(f"      Broadcast rate: {broadcast_rate:.1f} pps")
                print(f"      ARP rate: {arp_rate:.1f} pps")
                print(f"      Severity score: {severity:.1f}")
                
                if severity > 30:
                    print(f"      🔴 WOULD TRIGGER DETECTION (threshold: 30)")
                else:
                    print(f"      🟡 Below threshold (needs {30-severity:.1f} more)")
        
        if not found_issues:
            print("   ✅ No obvious loop indicators detected")
            print("   Network appears normal or traffic rate is too low")
    
    # Detection threshold analysis
    print(f"\n🎯 Detection Threshold Analysis:")
    print(f"   Current threshold: 30 (severity score)")
    print(f"   Current timeout: 3 seconds (in dashboard)")
    
    # Calculate what would be detected
    detected_macs = []
    for mac, count in broadcast_packets.items():
        arp_count = arp_packets.get(mac, 0)
        # Simplified severity calculation (matching detect_loops_lightweight)
        severity = (arp_count * 3 + count * 1.5) / timeout
        
        if severity > 30:
            detected_macs.append((mac, severity))
    
    if detected_macs:
        print(f"\n   ✅ WOULD DETECT {len(detected_macs)} MAC(s) as loops:")
        for mac, sev in detected_macs:
            print(f"      {mac}  →  Severity: {sev:.1f}")
    else:
        print(f"\n   ⚠️  NO MACs would be detected as loops with current settings")
        print(f"   Recommendations:")
        print(f"      • Lower threshold to 15-20 for more sensitivity")
        print(f"      • Increase capture timeout to 10+ seconds")
        print(f"      • Ensure loop simulator is running")
        print(f"      • Check if broadcast traffic is being filtered")
    
    # Recommendations
    print(f"\n💡 RECOMMENDATIONS:")
    
    if total_packets < 50:
        print(f"   ⚠️  Very low packet count ({total_packets})")
        print(f"      • Network may be idle or disconnected")
        print(f"      • Try during peak hours or generate traffic")
    
    if total_broadcasts < 10:
        print(f"   ⚠️  Low broadcast traffic ({total_broadcasts})")
        print(f"      • This is essential for loop detection")
        print(f"      • Run loop simulator to generate test traffic")
        print(f"      • Check for network filters/VLANs blocking broadcasts")
    
    max_broadcast_rate = max((count/elapsed for count in broadcast_packets.values()), default=0)
    if max_broadcast_rate < 2:
        print(f"   ⚠️  Low broadcast rate ({max_broadcast_rate:.1f} pps)")
        print(f"      • May need to lower detection threshold")
        print(f"      • Recommended: threshold=15, timeout=10")
    
    # Save detailed log
    print(f"\n📄 Detailed log saved to: loop_detection_diagnostic.log")
    print("="*70)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Diagnose loop detection issues")
    parser.add_argument("--timeout", type=int, default=10, help="Capture timeout in seconds")
    parser.add_argument("--interface", type=str, default=None, help="Network interface to use")
    
    args = parser.parse_args()
    
    try:
        diagnose_traffic_capture(timeout=args.timeout, iface=args.interface)
    except KeyboardInterrupt:
        print("\n\n⚠️  Diagnostic interrupted by user")
    except Exception as e:
        print(f"\n❌ Diagnostic failed: {e}")
        logging.exception("Diagnostic failed")
