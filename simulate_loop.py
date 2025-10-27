import time
import threading
import random
import ipaddress
from scapy.all import Ether, IP, ARP, sendp, sniff, get_if_list, TCP, UDP, ICMP
from scapy.layers.inet import UDP
from scapy.layers.l2 import ARP

# ---------------------------
# Configuration
# ---------------------------
# Auto-detect interface or set manually
def get_default_interface():
    """Auto-detect the best network interface."""
    try:
        interfaces = get_if_list()
        # Common interface names to try
        preferred_interfaces = ["Wi-Fi", "wlan0", "eth0", "Ethernet", "en0", "wlan1"]
        
        for preferred in preferred_interfaces:
            if preferred in interfaces:
                return preferred
        
        # If no preferred interface found, return the first available
        if interfaces:
            return interfaces[0]
        return None
    except:
        return None

IFACE = get_default_interface() or "Wi-Fi"  # Auto-detect or fallback
SRC_IP = "192.168.1.12"
CHECK_INTERVAL = 3     # seconds (matches dashboard detection)
STORM_THRESHOLD = 30   # packets per interval

# Enhanced Test Scenarios - Testing all loop detection features
TEST_SCENARIOS = {
    # Basic scenarios
    "clean": {
        "packets_per_sec": 2,
        "duration": 10,
        "description": "Clean network - Normal traffic",
        "loop_type": "none"
    },
    "suspicious": {
        "packets_per_sec": 15,
        "duration": 10,
        "description": "Suspicious activity - Elevated traffic",
        "loop_type": "mild"
    },
    
    # Advanced loop types matching detection engine
    "broadcast_storm": {
        "packets_per_sec": 80,
        "duration": 15,
        "description": "Broadcast Storm - Massive broadcast flooding",
        "loop_type": "broadcast"
    },
    "arp_storm": {
        "packets_per_sec": 60,
        "duration": 15,
        "description": "ARP Storm - Excessive ARP requests",
        "loop_type": "arp"
    },
    "spanning_tree_loop": {
        "packets_per_sec": 50,
        "duration": 20,
        "description": "Spanning Tree Loop - BPDU storm simulation",
        "loop_type": "bpdu"
    },
    "multicast_storm": {
        "packets_per_sec": 70,
        "duration": 15,
        "description": "Multicast Storm - Excessive multicast traffic",
        "loop_type": "multicast"
    },
    "mac_flapping": {
        "packets_per_sec": 40,
        "duration": 15,
        "description": "MAC Flapping - Same MAC on multiple ports",
        "loop_type": "mac_flap"
    },
    "cross_subnet_loop": {
        "packets_per_sec": 50,
        "duration": 20,
        "description": "Cross-Subnet Loop - Traffic between subnets",
        "loop_type": "cross_subnet"
    },
    "duplicate_packets": {
        "packets_per_sec": 45,
        "duration": 15,
        "description": "Duplicate Packets - Same packets repeated",
        "loop_type": "duplicate"
    },
    "burst_loop": {
        "packets_per_sec": 0,  # Special handling
        "duration": 20,
        "description": "Burst Loop - Intermittent high-traffic bursts",
        "loop_type": "burst"
    },
    "entropy_test": {
        "packets_per_sec": 35,
        "duration": 15,
        "description": "Low Entropy - Repetitive patterns",
        "loop_type": "low_entropy"
    },
    "multi_protocol_storm": {
        "packets_per_sec": 65,
        "duration": 18,
        "description": "Multi-Protocol Storm - Mixed ARP/ICMP/UDP",
        "loop_type": "multi_protocol"
    }
}

# ---------------------------
# Enhanced Loop Detection (matches dashboard)
# ---------------------------
def detect_loops_lightweight(timeout=3, threshold=30, iface=None):
    """Enhanced loop detection matching dashboard implementation."""
    from collections import defaultdict
    
    stats = defaultdict(lambda: {
        "count": 0, "arp_count": 0, "broadcast_count": 0, 
        "ips": set(), "hosts": set(), "fingerprints": defaultdict(int)
    })
    
    offenders = []
    total_count = 0
    
    def _process(pkt):
        nonlocal total_count
        total_count += 1
        
        if pkt.haslayer(Ether):
            src_mac = pkt[Ether].src
            stats[src_mac]["count"] += 1
            
            # Check for ARP packets
            if pkt.haslayer(ARP):
                stats[src_mac]["arp_count"] += 1
                if pkt[ARP].psrc:
                    stats[src_mac]["ips"].add(pkt[ARP].psrc)
            
            # Check for broadcast packets
            if pkt[Ether].dst == "ff:ff:ff:ff:ff:ff:ff:ff" or pkt[Ether].dst == "ff:ff:ff:ff:ff:ff":
                stats[src_mac]["broadcast_count"] += 1
            
            # Create packet fingerprint for duplicate detection
            if pkt.haslayer(IP):
                fingerprint = f"{pkt[IP].src}:{pkt[IP].dst}:{pkt[IP].len}"
                stats[src_mac]["fingerprints"][fingerprint] += 1
    
    try:
        sniff(iface=iface, prn=_process, store=False, timeout=timeout)
    except Exception as e:
        print(f"❌ Detection error: {e}")
        return 0, [], {}, "error", 0.0
    
    # Analyze results
    max_severity = 0
    for mac, info in stats.items():
        if info["count"] > threshold:
            # Calculate severity score
            severity = (info["count"] / threshold) * 100
            max_severity = max(max_severity, severity)
            
            # Check for repeated packets (loop indicator)
            repeated = [sig for sig, cnt in info["fingerprints"].items() if cnt > 5]
            if repeated:
                offenders.append(mac)
                info["severity"] = severity
    
    # Determine status
    if len(offenders) > 0:
        status = "loop_detected"
    elif total_count > threshold * 2:
        status = "suspicious"
    else:
        status = "clean"
    
    return total_count, offenders, dict(stats), status, max_severity


def checker():
    """Background checker using enhanced detection."""
    print("🔍 Starting enhanced loop detection checker...")
    while True:
        try:
            total_packets, offenders, stats, status, severity_score = detect_loops_lightweight(
                timeout=CHECK_INTERVAL,
                threshold=STORM_THRESHOLD,
                iface=IFACE
            )
            
            if status == "loop_detected":
                print(f"⚠️ LOOP DETECTED! Severity: {severity_score:.2f}, Offenders: {len(offenders)}")
                print(f"   Total packets: {total_packets}, Offenders: {offenders}")
            elif status == "suspicious":
                print(f"🔍 Suspicious activity detected. Severity: {severity_score:.2f}")
                print(f"   Total packets: {total_packets}")
            else:
                print(f"✅ Network clean. Severity: {severity_score:.2f}")
                print(f"   Total packets: {total_packets}")
                
        except Exception as e:
            print(f"❌ Checker error: {e}")
        
        time.sleep(2)  # Brief pause between checks


# ---------------------------
# Advanced Packet Generators
# ---------------------------
def create_broadcast_packet():
    """Generate broadcast packet (tests broadcast detection)."""
    return Ether(dst="ff:ff:ff:ff:ff:ff") / IP(src=SRC_IP, dst="255.255.255.255") / UDP(sport=random.randint(1024, 65535), dport=67)


def create_arp_packet(target_ip=None):
    """Generate ARP request (tests ARP storm detection)."""
    if target_ip is None:
        target_ip = f"192.168.1.{random.randint(1, 254)}"
    return Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(op=1, psrc=SRC_IP, pdst=target_ip, hwsrc="00:11:22:33:44:55")


def create_multicast_packet():
    """Generate multicast packet (tests multicast storm detection)."""
    multicast_addrs = ["224.0.0.1", "224.0.0.251", "239.255.255.250"]
    multicast_mac = "01:00:5e:00:00:01"
    return Ether(dst=multicast_mac) / IP(src=SRC_IP, dst=random.choice(multicast_addrs)) / UDP(sport=5353, dport=5353)


def create_icmp_packet():
    """Generate ICMP packet (tests ICMP ping floods)."""
    dst_ip = f"192.168.1.{random.randint(1, 254)}"
    return Ether(dst="ff:ff:ff:ff:ff:ff") / IP(src=SRC_IP, dst=dst_ip) / ICMP(type=8, code=0)


def create_tcp_syn_packet():
    """Generate TCP SYN packet (tests STP/control protocol detection)."""
    dst_ip = f"192.168.1.{random.randint(1, 254)}"
    return Ether(dst="ff:ff:ff:ff:ff:ff") / IP(src=SRC_IP, dst=dst_ip) / TCP(sport=random.randint(1024, 65535), dport=80, flags='S')


def create_bpdu_like_packet():
    """Generate BPDU-like packet (tests spanning tree loop detection)."""
    # BPDU multicast MAC
    bpdu_mac = "01:80:c2:00:00:00"
    return Ether(dst=bpdu_mac, src="00:11:22:33:44:55", type=0x4242)


def create_cross_subnet_packet():
    """Generate cross-subnet packet (tests cross-subnet detection)."""
    # Different subnets
    subnets = ["192.168.1", "192.168.2", "10.0.0", "172.16.0"]
    src_subnet = random.choice(subnets)
    dst_subnet = random.choice([s for s in subnets if s != src_subnet])
    
    src_ip = f"{src_subnet}.{random.randint(10, 250)}"
    dst_ip = f"{dst_subnet}.{random.randint(10, 250)}"
    
    return Ether(dst="ff:ff:ff:ff:ff:ff") / IP(src=src_ip, dst=dst_ip) / UDP()


def create_duplicate_packet(sequence=0):
    """Generate duplicate packet (tests duplicate detection)."""
    # Same packet with identical content
    return Ether(dst="ff:ff:ff:ff:ff:ff") / IP(src=SRC_IP, dst="192.168.1.1", id=sequence) / UDP(sport=12345, dport=67) / b"DUPLICATE_PAYLOAD"


def create_mac_flapping_packet(mac_index=0):
    """Generate MAC flapping packet (tests MAC flapping detection)."""
    # Same MAC but different source IPs (simulates MAC appearing on multiple ports)
    mac = "00:11:22:33:44:55"
    src_ips = [f"192.168.1.{10 + mac_index % 5}"]
    return Ether(src=mac, dst="ff:ff:ff:ff:ff:ff") / IP(src=random.choice(src_ips), dst="255.255.255.255") / UDP()


def create_low_entropy_packet(pattern_id=0):
    """Generate low entropy packet (tests entropy analysis)."""
    # Repetitive pattern with low variability
    pattern = pattern_id % 3
    dst_ip = f"192.168.1.{pattern + 1}"
    payload = bytes([pattern] * 64)  # Highly repetitive payload
    return Ether(dst="ff:ff:ff:ff:ff:ff") / IP(src=SRC_IP, dst=dst_ip) / UDP() / payload


def create_mixed_protocol_packet():
    """Generate random protocol packet (tests multi-protocol detection)."""
    protocols = [
        create_arp_packet,
        create_icmp_packet,
        create_broadcast_packet,
        create_multicast_packet,
        create_tcp_syn_packet
    ]
    return random.choice(protocols)()


# ---------------------------
# Enhanced Loop Simulators
# ---------------------------
def simulate_broadcast_storm(duration, packets_per_sec):
    """Simulate broadcast storm - massive broadcast flooding."""
    print("🌊 Simulating BROADCAST STORM...")
    start_time = time.time()
    count = 0
    
    while time.time() - start_time < duration:
        pkt = create_broadcast_packet()
        for _ in range(max(1, packets_per_sec // 10)):
            sendp(pkt, iface=IFACE, verbose=False)
            count += 1
        time.sleep(0.1)
    
    print(f"   Sent {count} broadcast packets")


def simulate_arp_storm(duration, packets_per_sec):
    """Simulate ARP storm - excessive ARP requests."""
    print("🔍 Simulating ARP STORM...")
    start_time = time.time()
    count = 0
    
    while time.time() - start_time < duration:
        # Generate ARP requests for different IPs
        pkt = create_arp_packet()
        for _ in range(max(1, packets_per_sec // 10)):
            sendp(pkt, iface=IFACE, verbose=False)
            count += 1
        time.sleep(0.1)
    
    print(f"   Sent {count} ARP packets")


def simulate_multicast_storm(duration, packets_per_sec):
    """Simulate multicast storm."""
    print("📡 Simulating MULTICAST STORM...")
    start_time = time.time()
    count = 0
    
    while time.time() - start_time < duration:
        pkt = create_multicast_packet()
        for _ in range(max(1, packets_per_sec // 10)):
            sendp(pkt, iface=IFACE, verbose=False)
            count += 1
        time.sleep(0.1)
    
    print(f"   Sent {count} multicast packets")


def simulate_bpdu_storm(duration, packets_per_sec):
    """Simulate BPDU/Spanning Tree storm."""
    print("🌳 Simulating SPANNING TREE LOOP (BPDU Storm)...")
    start_time = time.time()
    count = 0
    
    while time.time() - start_time < duration:
        pkt = create_bpdu_like_packet()
        for _ in range(max(1, packets_per_sec // 10)):
            sendp(pkt, iface=IFACE, verbose=False)
            count += 1
        time.sleep(0.1)
    
    print(f"   Sent {count} BPDU-like packets")


def simulate_mac_flapping(duration, packets_per_sec):
    """Simulate MAC flapping - same MAC on multiple ports."""
    print("🔀 Simulating MAC FLAPPING...")
    start_time = time.time()
    count = 0
    mac_index = 0
    
    while time.time() - start_time < duration:
        pkt = create_mac_flapping_packet(mac_index)
        for _ in range(max(1, packets_per_sec // 10)):
            sendp(pkt, iface=IFACE, verbose=False)
            count += 1
            mac_index += 1
        time.sleep(0.1)
    
    print(f"   Sent {count} MAC flapping packets")


def simulate_cross_subnet_loop(duration, packets_per_sec):
    """Simulate cross-subnet loop."""
    print("🌐 Simulating CROSS-SUBNET LOOP...")
    start_time = time.time()
    count = 0
    
    while time.time() - start_time < duration:
        pkt = create_cross_subnet_packet()
        for _ in range(max(1, packets_per_sec // 10)):
            sendp(pkt, iface=IFACE, verbose=False)
            count += 1
        time.sleep(0.1)
    
    print(f"   Sent {count} cross-subnet packets")


def simulate_duplicate_packets(duration, packets_per_sec):
    """Simulate duplicate packet storm."""
    print("📋 Simulating DUPLICATE PACKETS...")
    start_time = time.time()
    count = 0
    sequence = 0
    
    while time.time() - start_time < duration:
        # Send same packet multiple times
        pkt = create_duplicate_packet(sequence)
        for _ in range(max(1, packets_per_sec // 10)):
            sendp(pkt, iface=IFACE, verbose=False)
            count += 1
        
        # Change sequence every 50 packets to create duplicate groups
        if count % 50 == 0:
            sequence += 1
        
        time.sleep(0.1)
    
    print(f"   Sent {count} duplicate packets ({sequence + 1} unique patterns)")


def simulate_burst_loop(duration, packets_per_sec=0):
    """Simulate burst loop - intermittent high-traffic bursts."""
    print("💥 Simulating BURST LOOP (intermittent bursts)...")
    start_time = time.time()
    total_count = 0
    burst_count = 0
    
    while time.time() - start_time < duration:
        # Burst: 3 seconds of high traffic
        print(f"   💥 Burst #{burst_count + 1} starting...")
        burst_start = time.time()
        burst_packets = 0
        
        while time.time() - burst_start < 3:
            pkt = create_broadcast_packet()
            for _ in range(10):  # 100 pps during burst
                sendp(pkt, iface=IFACE, verbose=False)
                burst_packets += 1
                total_count += 1
            time.sleep(0.1)
        
        print(f"   ✓ Burst #{burst_count + 1} complete: {burst_packets} packets")
        burst_count += 1
        
        # Quiet period: 3 seconds of low traffic
        print("   ⏸️  Quiet period...")
        time.sleep(3)
        
        if time.time() - start_time >= duration:
            break
    
    print(f"   Total: {total_count} packets in {burst_count} bursts")


def simulate_low_entropy(duration, packets_per_sec):
    """Simulate low entropy traffic - repetitive patterns."""
    print("🔁 Simulating LOW ENTROPY TRAFFIC...")
    start_time = time.time()
    count = 0
    pattern_id = 0
    
    while time.time() - start_time < duration:
        pkt = create_low_entropy_packet(pattern_id)
        for _ in range(max(1, packets_per_sec // 10)):
            sendp(pkt, iface=IFACE, verbose=False)
            count += 1
        
        # Change pattern slowly (low variability)
        if count % 100 == 0:
            pattern_id += 1
        
        time.sleep(0.1)
    
    print(f"   Sent {count} low-entropy packets ({pattern_id + 1} patterns)")


def simulate_multi_protocol_storm(duration, packets_per_sec):
    """Simulate multi-protocol storm."""
    print("🎭 Simulating MULTI-PROTOCOL STORM...")
    start_time = time.time()
    count = 0
    protocol_counts = {"ARP": 0, "ICMP": 0, "Broadcast": 0, "Multicast": 0, "TCP": 0}
    
    while time.time() - start_time < duration:
        pkt = create_mixed_protocol_packet()
        
        # Track protocol type
        if pkt.haslayer(ARP):
            protocol_counts["ARP"] += 1
        elif pkt.haslayer(ICMP):
            protocol_counts["ICMP"] += 1
        elif pkt.haslayer(TCP):
            protocol_counts["TCP"] += 1
        elif pkt[Ether].dst.startswith("01:00:5e"):
            protocol_counts["Multicast"] += 1
        else:
            protocol_counts["Broadcast"] += 1
        
        for _ in range(max(1, packets_per_sec // 10)):
            sendp(pkt, iface=IFACE, verbose=False)
            count += 1
        time.sleep(0.1)
    
    print(f"   Sent {count} multi-protocol packets:")
    for proto, cnt in protocol_counts.items():
        print(f"     - {proto}: {cnt}")


def simulate_mild_loop(duration, packets_per_sec):
    """Simulate mild suspicious activity."""
    print("⚠️  Simulating MILD SUSPICIOUS ACTIVITY...")
    start_time = time.time()
    count = 0
    
    while time.time() - start_time < duration:
        # Mix of broadcast and ARP
        if random.random() < 0.5:
            pkt = create_broadcast_packet()
        else:
            pkt = create_arp_packet()
        
        for _ in range(max(1, packets_per_sec // 10)):
            sendp(pkt, iface=IFACE, verbose=False)
            count += 1
        time.sleep(0.1)
    
    print(f"   Sent {count} packets")


def check_interface_availability():
    """Check if the selected interface is available and working."""
    try:
        # Try to get interface info
        interfaces = get_if_list()
        if IFACE not in interfaces:
            return False, f"Interface '{IFACE}' not found in available interfaces"
        
        # Try a simple packet send to test interface
        test_pkt = Ether(dst="ff:ff:ff:ff:ff:ff") / IP(src="127.0.0.1", dst="127.0.0.1")
        sendp(test_pkt, iface=IFACE, verbose=False)
        return True, f"Interface '{IFACE}' is working"
    except Exception as e:
        return False, f"Interface '{IFACE}' error: {e}"


def simulate_scenario(scenario="loop"):
    """Simulate specific network scenarios with advanced loop types."""
    if scenario not in TEST_SCENARIOS:
        print(f"❌ Unknown scenario: {scenario}")
        print(f"Available scenarios: {list(TEST_SCENARIOS.keys())}")
        return
    
    # Check interface availability
    is_available, message = check_interface_availability()
    if not is_available:
        print(f"❌ {message}")
        print("Please select a different interface or check your network connection.")
        return
    
    config = TEST_SCENARIOS[scenario]
    loop_type = config.get('loop_type', 'none')
    
    print("\n" + "=" * 60)
    print(f"🚨 {config['description']}")
    print(f"   Loop Type: {loop_type.upper()}")
    print(f"   Packets/sec: {config['packets_per_sec']}")
    print(f"   Duration: {config['duration']} seconds")
    print(f"   Interface: {IFACE}")
    print("   Press Ctrl+C to stop.")
    print("=" * 60 + "\n")
    
    # Start background checker
    checker_thread = threading.Thread(target=checker, daemon=True)
    checker_thread.start()
    
    time.sleep(1)  # Brief pause before starting
    
    try:
        # Route to specific loop simulator based on type
        if loop_type == "none":
            # Clean network - minimal traffic
            print("✅ Simulating CLEAN NETWORK...")
            start_time = time.time()
            count = 0
            while time.time() - start_time < config['duration']:
                pkt = create_broadcast_packet()
                sendp(pkt, iface=IFACE, verbose=False)
                count += 1
                time.sleep(0.5)  # Slow rate
            print(f"   Sent {count} packets")
            
        elif loop_type == "mild":
            simulate_mild_loop(config['duration'], config['packets_per_sec'])
            
        elif loop_type == "broadcast":
            simulate_broadcast_storm(config['duration'], config['packets_per_sec'])
            
        elif loop_type == "arp":
            simulate_arp_storm(config['duration'], config['packets_per_sec'])
            
        elif loop_type == "bpdu":
            simulate_bpdu_storm(config['duration'], config['packets_per_sec'])
            
        elif loop_type == "multicast":
            simulate_multicast_storm(config['duration'], config['packets_per_sec'])
            
        elif loop_type == "mac_flap":
            simulate_mac_flapping(config['duration'], config['packets_per_sec'])
            
        elif loop_type == "cross_subnet":
            simulate_cross_subnet_loop(config['duration'], config['packets_per_sec'])
            
        elif loop_type == "duplicate":
            simulate_duplicate_packets(config['duration'], config['packets_per_sec'])
            
        elif loop_type == "burst":
            simulate_burst_loop(config['duration'], config['packets_per_sec'])
            
        elif loop_type == "low_entropy":
            simulate_low_entropy(config['duration'], config['packets_per_sec'])
            
        elif loop_type == "multi_protocol":
            simulate_multi_protocol_storm(config['duration'], config['packets_per_sec'])
        
        print("\n✅ Simulation completed!")
        print("=" * 60)
        print("📊 EXPECTED DETECTION OUTCOME:")
        
        # Show expected results based on loop type
        expected_results = {
            "none": ("✅ Clean", "No loops should be detected"),
            "mild": ("⚠️  Suspicious", "Elevated activity detected"),
            "broadcast": ("🔴 Loop Detected", "Broadcast storm detected"),
            "arp": ("🔴 Loop Detected", "ARP storm detected"),
            "bpdu": ("🔴 Loop Detected", "Spanning tree loop detected"),
            "multicast": ("🔴 Loop Detected", "Multicast storm detected"),
            "mac_flap": ("⚠️  Suspicious/Loop", "MAC flapping detected"),
            "cross_subnet": ("🔴 Loop Detected", "Cross-subnet loop detected"),
            "duplicate": ("🔴 Loop Detected", "Duplicate packets detected"),
            "burst": ("⚠️  Suspicious/Loop", "Burst pattern detected"),
            "low_entropy": ("⚠️  Suspicious/Loop", "Low entropy pattern detected"),
            "multi_protocol": ("🔴 Loop Detected", "Multi-protocol storm detected")
        }
        
        expected_status, expected_desc = expected_results.get(loop_type, ("Unknown", "Check output"))
        print(f"   Expected Status: {expected_status}")
        print(f"   Description: {expected_desc}")
        print("   ✓ Check detection results above to verify")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n⏹️  Simulation stopped by user.")
    except Exception as e:
        print(f"\n❌ Simulation error: {e}")
        import traceback
        traceback.print_exc()


def interactive_menu():
    """Interactive menu for testing different scenarios."""
    print("\n🔄 Advanced Loop Detection Test Simulator")
    print("=" * 70)
    print("🎯 Available Test Scenarios:")
    print()
    
    # Group scenarios by type
    basic_scenarios = ["clean", "suspicious"]
    advanced_scenarios = [k for k in TEST_SCENARIOS.keys() if k not in basic_scenarios]
    
    print("📊 BASIC SCENARIOS:")
    for i, key in enumerate(basic_scenarios, 1):
        config = TEST_SCENARIOS[key]
        print(f"  {i}. {key.upper():20s} - {config['description']}")
    
    print()
    print("🔥 ADVANCED LOOP TYPES:")
    for i, key in enumerate(advanced_scenarios, len(basic_scenarios) + 1):
        config = TEST_SCENARIOS[key]
        loop_type = config.get('loop_type', 'unknown')
        print(f"  {i}. {key.upper():20s} - {config['description']}")
    
    print()
    print("⚙️  SPECIAL OPTIONS:")
    custom_num = len(TEST_SCENARIOS) + 1
    continuous_num = custom_num + 1
    compare_num = continuous_num + 1
    
    print(f"  {custom_num}. CUSTOM              - Manual configuration")
    print(f"  {continuous_num}. CONTINUOUS         - Run all scenarios sequentially")
    print(f"  {compare_num}. COMPARISON         - Compare multiple loop types")
    print("  0. EXIT                - Quit simulator")
    print("=" * 70)
    
    scenario_keys = list(TEST_SCENARIOS.keys())
    custom_num = len(TEST_SCENARIOS) + 1
    continuous_num = custom_num + 1
    compare_num = continuous_num + 1
    
    while True:
        try:
            choice = input(f"\n💡 Select scenario (0-{compare_num}): ").strip()
            
            if choice == "0":
                print("👋 Goodbye!")
                break
            
            try:
                choice_num = int(choice)
                
                if 1 <= choice_num <= len(scenario_keys):
                    # Run selected scenario
                    scenario_key = scenario_keys[choice_num - 1]
                    simulate_scenario(scenario_key)
                    
                elif choice_num == custom_num:
                    custom_simulation()
                    
                elif choice_num == continuous_num:
                    run_all_scenarios()
                    
                elif choice_num == compare_num:
                    compare_scenarios()
                    
                else:
                    print(f"❌ Invalid choice. Please select 0-{compare_num}.")
                    
            except ValueError:
                print(f"❌ Please enter a number between 0 and {compare_num}.")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()


def custom_simulation():
    """Custom simulation with user-defined parameters."""
    try:
        print("\n📝 Custom Loop Simulation")
        print("=" * 50)
        
        packets_per_sec = int(input("Packets per second (1-200): "))
        duration = int(input("Duration in seconds (1-60): "))
        
        print("\nSelect packet type:")
        print("1. Broadcast Storm")
        print("2. ARP Storm")
        print("3. Multicast Storm")
        print("4. Duplicate Packets")
        print("5. Cross-Subnet")
        print("6. Mixed Protocols")
        
        choice = input("Enter choice (1-6): ").strip()
        
        packet_generators = {
            "1": ("Broadcast Storm", create_broadcast_packet),
            "2": ("ARP Storm", create_arp_packet),
            "3": ("Multicast Storm", create_multicast_packet),
            "4": ("Duplicate Packets", lambda: create_duplicate_packet(0)),
            "5": ("Cross-Subnet", create_cross_subnet_packet),
            "6": ("Mixed Protocols", create_mixed_protocol_packet)
        }
        
        if choice not in packet_generators:
            print("❌ Invalid choice")
            return
        
        loop_name, packet_gen = packet_generators[choice]
        
        print(f"\n🚨 Custom {loop_name}: {packets_per_sec} pps for {duration}s")
        print(f"   Interface: {IFACE}")
        print("   Press Ctrl+C to stop.\n")
        
        # Start background checker
        checker_thread = threading.Thread(target=checker, daemon=True)
        checker_thread.start()
        
        start_time = time.time()
        count = 0
        
        while time.time() - start_time < duration:
            pkt = packet_gen()
            for _ in range(max(1, packets_per_sec // 10)):
                sendp(pkt, iface=IFACE, verbose=False)
                count += 1
            time.sleep(0.1)
        
        print(f"\n✅ Custom simulation completed: {count} packets sent")
            
    except ValueError:
        print("❌ Invalid input. Please enter numbers only.")
    except KeyboardInterrupt:
        print("\n⏹️  Custom simulation stopped.")


def run_all_scenarios():
    """Run all test scenarios sequentially."""
    print("\n🔄 Running ALL test scenarios sequentially...")
    print("⚠️  This will take several minutes!")
    
    input("Press ENTER to start, or Ctrl+C to cancel...")
    
    results = []
    
    for i, (scenario, config) in enumerate(TEST_SCENARIOS.items(), 1):
        print(f"\n{'='*70}")
        print(f"[{i}/{len(TEST_SCENARIOS)}] Testing: {scenario.upper()}")
        print(f"{'='*70}")
        
        start_time = time.time()
        simulate_scenario(scenario)
        elapsed = time.time() - start_time
        
        results.append({
            'scenario': scenario,
            'description': config['description'],
            'duration': elapsed
        })
        
        print(f"✅ {scenario} completed in {elapsed:.1f}s")
        
        if i < len(TEST_SCENARIOS):
            print("⏸️  Pausing for 3 seconds...")
            time.sleep(3)
    
    # Summary
    print("\n" + "=" * 70)
    print("🎉 ALL SCENARIOS COMPLETED!")
    print("=" * 70)
    print("\n📊 Summary:")
    
    total_duration = sum(r['duration'] for r in results)
    
    for i, result in enumerate(results, 1):
        print(f"{i:2d}. {result['scenario']:20s} - {result['duration']:6.1f}s - {result['description']}")
    
    print(f"\n⏱️  Total execution time: {total_duration:.1f}s ({total_duration / 60:.1f} minutes)")
    print("\n💡 Review the detection results above to verify loop detection accuracy.")


def compare_scenarios():
    """Compare multiple loop scenarios side-by-side."""
    print("\n🔍 SCENARIO COMPARISON MODE")
    print("=" * 70)
    print("Select scenarios to compare (comma-separated numbers):")
    
    for i, (key, config) in enumerate(TEST_SCENARIOS.items(), 1):
        print(f"  {i}. {key.upper()}")
    
    try:
        choice = input("\nEnter scenario numbers (e.g., 1,3,5): ").strip()
        selected = [int(x.strip()) for x in choice.split(',')]
        
        scenario_keys = list(TEST_SCENARIOS.keys())
        selected_scenarios = []
        
        for num in selected:
            if 1 <= num <= len(scenario_keys):
                selected_scenarios.append(scenario_keys[num - 1])
            else:
                print(f"⚠️  Skipping invalid number: {num}")
        
        if not selected_scenarios:
            print("❌ No valid scenarios selected")
            return
        
        print(f"\n� Comparing {len(selected_scenarios)} scenarios:")
        for scenario in selected_scenarios:
            print(f"  - {scenario.upper()}: {TEST_SCENARIOS[scenario]['description']}")
        
        input("\nPress ENTER to start comparison...")
        
        results = []
        
        for i, scenario in enumerate(selected_scenarios, 1):
            print(f"\n{'='*70}")
            print(f"[{i}/{len(selected_scenarios)}] Running: {scenario.upper()}")
            print(f"{'='*70}")
            
            start_time = time.time()
            simulate_scenario(scenario)
            elapsed = time.time() - start_time
            
            results.append({
                'scenario': scenario,
                'config': TEST_SCENARIOS[scenario],
                'duration': elapsed
            })
            
            if i < len(selected_scenarios):
                print("\n⏸️  Pausing for 3 seconds before next scenario...")
                time.sleep(3)
        
        # Comparison summary
        print("\n" + "=" * 70)
        print("📊 COMPARISON RESULTS")
        print("=" * 70)
        
        print(f"\n{'Scenario':<20} {'Type':<15} {'PPS':<8} {'Duration':<10} {'Detected?':<12}")
        print("-" * 70)
        
        for result in results:
            scenario = result['scenario']
            config = result['config']
            loop_type = config.get('loop_type', 'unknown')
            pps = config['packets_per_sec']
            duration = result['duration']
            
            # Note: Detection results should be visible in console output above
            print(f"{scenario:<20} {loop_type:<15} {pps:<8} {duration:<10.1f}s {'See above':<12}")
        
        print("\n💡 Review the detection checker output above for each scenario.")
        print("   'Loop Detected' or 'Suspicious' indicates successful detection.")
        
    except ValueError:
        print("❌ Invalid input. Please enter numbers separated by commas.")
    except KeyboardInterrupt:
        print("\n⏹️  Comparison cancelled.")


def show_interfaces():
    """Show available network interfaces."""
    print("📡 Available network interfaces:")
    interfaces = get_if_list()
    for i, iface in enumerate(interfaces, 1):
        print(f"{i}. {iface}")
    print(f"\nCurrent interface: {IFACE}")
    return interfaces


def select_interface():
    """Allow user to select interface interactively."""
    interfaces = get_if_list()
    if not interfaces:
        print("❌ No network interfaces found!")
        return None
    
    print("\n📡 Select network interface:")
    for i, iface in enumerate(interfaces, 1):
        print(f"{i}. {iface}")
    
    while True:
        try:
            choice = input(f"\nSelect interface (1-{len(interfaces)}) or press Enter for auto-detected '{IFACE}': ").strip()
            
            if not choice:  # Use auto-detected interface
                return IFACE
            
            choice_num = int(choice)
            if 1 <= choice_num <= len(interfaces):
                return interfaces[choice_num - 1]
            else:
                print(f"❌ Please enter a number between 1 and {len(interfaces)}")
        except ValueError:
            print("❌ Please enter a valid number")
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            exit(0)


def show_help():
    """Show comprehensive help information."""
    help_text = """
╔════════════════════════════════════════════════════════════════════╗
║           Advanced Loop Detection Test Simulator - HELP            ║
╚════════════════════════════════════════════════════════════════════╝

🎯 PURPOSE:
   This simulator generates different types of network loop scenarios
   to test the enhanced loop detection system's capabilities.

📋 LOOP TYPES SUPPORTED:

   1. CLEAN NETWORK
      - Normal traffic patterns
      - Low packet rate (~2 pps)
      - Expected Result: "Network Clean"

   2. SUSPICIOUS ACTIVITY
      - Elevated but not critical traffic
      - Medium packet rate (~15 pps)
      - Expected Result: "Suspicious Activity"

   3. BROADCAST STORM
      - Massive broadcast flooding
      - Tests: Broadcast detection, high packet count
      - Expected Result: "Loop Detected"

   4. ARP STORM
      - Excessive ARP requests
      - Tests: ARP packet detection, protocol analysis
      - Expected Result: "Loop Detected"

   5. SPANNING TREE LOOP
      - BPDU storm simulation
      - Tests: Control protocol detection
      - Expected Result: "Loop Detected"

   6. MULTICAST STORM
      - Excessive multicast traffic
      - Tests: Multicast detection
      - Expected Result: "Loop Detected"

   7. MAC FLAPPING
      - Same MAC on multiple ports simulation
      - Tests: MAC tracking, port flapping
      - Expected Result: "Suspicious" or "Loop Detected"

   8. CROSS-SUBNET LOOP
      - Traffic between different subnets
      - Tests: Cross-subnet detection, subnet tracking
      - Expected Result: "Loop Detected"

   9. DUPLICATE PACKETS
      - Same packets repeated multiple times
      - Tests: Duplicate detection, packet fingerprinting
      - Expected Result: "Loop Detected"

  10. BURST LOOP
      - Intermittent high-traffic bursts
      - Tests: Burst detection, temporal analysis
      - Expected Result: "Suspicious" or "Loop Detected"

  11. LOW ENTROPY
      - Repetitive patterns with low variability
      - Tests: Entropy analysis, pattern detection
      - Expected Result: "Suspicious" or "Loop Detected"

  12. MULTI-PROTOCOL STORM
      - Mixed ARP/ICMP/UDP/TCP traffic
      - Tests: Multi-protocol detection
      - Expected Result: "Loop Detected"

🔧 USAGE:

   1. SELECT INTERFACE:
      - Simulator auto-detects best interface
      - Or manually select from available interfaces

   2. RUN SCENARIOS:
      - Choose individual scenarios (1-12)
      - Run custom configuration (13)
      - Run all scenarios (14)
      - Compare scenarios (15)

   3. MONITOR RESULTS:
      - Watch console output for detection results
      - Look for "Loop Detected" or "Suspicious" messages
      - Check severity scores and packet counts

⚠️  REQUIREMENTS:

   - Administrator/root privileges (for packet capture)
   - Network interface with active connection
   - Loop detection dashboard can run simultaneously

💡 TIPS:

   - Start with "Clean" and "Suspicious" to verify baseline
   - Run "Broadcast Storm" to verify loop detection works
   - Use "Comparison" mode to test multiple scenarios
   - Keep dashboard running to see real-time notifications

📊 INTERPRETING RESULTS:

   Detection Status:
   ✅ "Network Clean"      - No loops detected (good!)
   ⚠️  "Suspicious"         - Elevated activity (warning)
   🔴 "Loop Detected"      - Confirmed loop (alert!)

   Severity Score:
   0-40    = Clean/Normal
   40-80   = Suspicious
   80-100  = Loop Detected

📚 DOCUMENTATION:

   See these files for more information:
   - MULTI_INTERFACE_LOOP_DETECTION_SETUP.md
   - ENHANCED_LOOP_DETECTION_README.md
   - QUICK_START_MULTI_INTERFACE.md

═══════════════════════════════════════════════════════════════════════
"""
    print(help_text)
    input("Press ENTER to continue...")


if __name__ == "__main__":
    print("\n╔════════════════════════════════════════════════════════════════════╗")
    print("║       🔄 Advanced Loop Detection Test Simulator v2.0              ║")
    print("║                  Enhanced Multi-Interface Support                  ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    print()
    
    # Show available interfaces
    print("📡 Detecting Network Interfaces...")
    print("=" * 70)
    interfaces = show_interfaces()
    print("=" * 70)
    
    # Check if auto-detected interface exists
    if IFACE not in interfaces:
        print(f"❌ Auto-detected interface '{IFACE}' not found!")
        print(f"   Available interfaces: {', '.join(interfaces)}")
        print()
        
        # Let user select interface
        selected_interface = select_interface()
        if selected_interface:
            IFACE = selected_interface
            print(f"✅ Using interface: {IFACE}")
        else:
            print("❌ No interface selected. Exiting.")
            exit(1)
    else:
        print(f"✅ Using auto-detected interface: {IFACE}")
    
    # Update the global IFACE variable for all functions
    globals()['IFACE'] = IFACE
    
    print()
    print("💡 TIP: Run as Administrator/root for best results")
    print("💡 TIP: Type 'h' or '?' in menu for help")
    print()
    
    # Show quick help prompt
    show_help_prompt = input("Show detailed help? (y/n): ").strip().lower()
    if show_help_prompt == 'y':
        show_help()
    
    # Start interactive menu
    interactive_menu()
