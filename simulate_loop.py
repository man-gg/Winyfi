import time
import threading
import random
from scapy.all import Ether, IP, ARP, sendp, sniff, get_if_list
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

# Test scenarios
TEST_SCENARIOS = {
    "clean": {"packets_per_sec": 1, "duration": 10, "description": "Clean network simulation"},
    "suspicious": {"packets_per_sec": 15, "duration": 10, "description": "Suspicious activity simulation"},
    "loop": {"packets_per_sec": 50, "duration": 15, "description": "Loop detection simulation"},
    "storm": {"packets_per_sec": 100, "duration": 20, "description": "Broadcast storm simulation"}
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
# Enhanced Simulator
# ---------------------------
def create_test_packet(packet_type="broadcast"):
    """Create different types of test packets."""
    if packet_type == "broadcast":
        return Ether(dst="ff:ff:ff:ff:ff:ff") / IP(src=SRC_IP, dst="255.255.255.255") / UDP()
    elif packet_type == "arp":
        return Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(psrc=SRC_IP, pdst="192.168.1.1")
    elif packet_type == "multicast":
        return Ether(dst="01:00:5e:00:00:01") / IP(src=SRC_IP, dst="224.0.0.1")
    else:
        return Ether(dst="ff:ff:ff:ff:ff:ff") / IP(src=SRC_IP, dst="255.255.255.255")


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
    """Simulate specific network scenarios."""
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
    print(f"🚨 {config['description']}")
    print(f"   Packets/sec: {config['packets_per_sec']}")
    print(f"   Duration: {config['duration']} seconds")
    print(f"   Interface: {IFACE}")
    print("Press Ctrl+C to stop.\n")
    
    # Start background checker
    checker_thread = threading.Thread(target=checker, daemon=True)
    checker_thread.start()
    
    try:
        start_time = time.time()
        packet_types = ["broadcast", "arp", "multicast"]
        
        while time.time() - start_time < config['duration']:
            # Send different packet types for variety
            packet_type = random.choice(packet_types)
            pkt = create_test_packet(packet_type)
            
            # Send multiple packets per iteration for higher rates
            for _ in range(max(1, config['packets_per_sec'] // 10)):
                sendp(pkt, iface=IFACE, verbose=False)
            
            time.sleep(0.1)  # 10 iterations per second
            
    except KeyboardInterrupt:
        print("\n✅ Simulation stopped.")
    except Exception as e:
        print(f"❌ Simulation error: {e}")


def interactive_menu():
    """Interactive menu for testing different scenarios."""
    print("🔄 Loop Detection Test Simulator")
    print("=" * 50)
    print("Available test scenarios:")
    
    for i, (key, config) in enumerate(TEST_SCENARIOS.items(), 1):
        print(f"{i}. {key.upper()}: {config['description']}")
    
    print("5. CUSTOM: Manual configuration")
    print("6. CONTINUOUS: Run all scenarios sequentially")
    print("0. EXIT")
    print("=" * 50)
    
    while True:
        try:
            choice = input("\nSelect scenario (0-6): ").strip()
            
            if choice == "0":
                print("👋 Goodbye!")
                break
            elif choice == "1":
                simulate_scenario("clean")
            elif choice == "2":
                simulate_scenario("suspicious")
            elif choice == "3":
                simulate_scenario("loop")
            elif choice == "4":
                simulate_scenario("storm")
            elif choice == "5":
                custom_simulation()
            elif choice == "6":
                run_all_scenarios()
            else:
                print("❌ Invalid choice. Please select 0-6.")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


def custom_simulation():
    """Custom simulation with user-defined parameters."""
    try:
        packets_per_sec = int(input("Packets per second (1-200): "))
        duration = int(input("Duration in seconds (1-60): "))
        
        print(f"🚨 Custom simulation: {packets_per_sec} pps for {duration}s")
        print("Press Ctrl+C to stop.\n")
        
        # Start background checker
        checker_thread = threading.Thread(target=checker, daemon=True)
        checker_thread.start()
        
        start_time = time.time()
        while time.time() - start_time < duration:
            pkt = create_test_packet("broadcast")
            for _ in range(max(1, packets_per_sec // 10)):
                sendp(pkt, iface=IFACE, verbose=False)
            time.sleep(0.1)
            
    except ValueError:
        print("❌ Invalid input. Please enter numbers only.")
    except KeyboardInterrupt:
        print("\n✅ Custom simulation stopped.")


def run_all_scenarios():
    """Run all test scenarios sequentially."""
    print("🔄 Running all test scenarios sequentially...")
    
    for scenario, config in TEST_SCENARIOS.items():
        print(f"\n{'='*20} {scenario.upper()} {'='*20}")
        simulate_scenario(scenario)
        print(f"✅ {scenario} scenario completed")
        time.sleep(2)  # Brief pause between scenarios
    
    print("\n🎉 All scenarios completed!")


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


if __name__ == "__main__":
    print("🔄 Enhanced Loop Detection Test Simulator")
    print("=" * 50)
    
    # Show available interfaces
    interfaces = show_interfaces()
    print("=" * 50)
    
    # Check if auto-detected interface exists
    if IFACE not in interfaces:
        print(f"❌ Auto-detected interface '{IFACE}' not found!")
        print("Available interfaces:", interfaces)
        
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
    
    interactive_menu()
