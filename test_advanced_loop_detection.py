"""
Advanced Loop Detection Test Suite

This script demonstrates and tests all new features of the enhanced loop detection system.
"""

import sys
import time
from datetime import datetime
from network_utils import (
    detect_loops,
    detect_loops_lightweight,
    auto_loop_detection,
    LoopDetectionEngine,
    get_default_iface
)


def print_separator(title=""):
    """Print a visual separator."""
    if title:
        print(f"\n{'='*80}")
        print(f"  {title}")
        print(f"{'='*80}\n")
    else:
        print(f"\n{'-'*80}\n")


def test_basic_detection():
    """Test 1: Basic loop detection with advanced features."""
    print_separator("TEST 1: Basic Advanced Loop Detection")
    
    print("Running advanced loop detection for 10 seconds...")
    print("This will analyze all packet types including STP, LLDP, CDP, and ICMP redirects.\n")
    
    start_time = time.time()
    
    try:
        total, offenders, stats, metrics = detect_loops(
            timeout=10,
            threshold=50,
            enable_advanced=True
        )
        
        elapsed = time.time() - start_time
        
        print(f"✓ Detection completed in {elapsed:.2f} seconds")
        print(f"\n📊 Results:")
        print(f"  Total packets captured: {total}")
        print(f"  Offenders detected: {len(offenders)}")
        print(f"  Cross-subnet activity: {metrics['cross_subnet_activity']}")
        print(f"  Unique MACs: {metrics['total_unique_macs']}")
        print(f"  Unique IPs: {metrics['total_unique_ips']}")
        print(f"  Unique subnets: {metrics['total_unique_subnets']}")
        
        if offenders:
            print(f"\n⚠️ Offenders Details:")
            for mac in offenders:
                if mac in stats:
                    info = stats[mac]
                    severity = info['severity']
                    
                    print(f"\n  MAC: {mac}")
                    print(f"    IPs: {', '.join(info['ips'][:3])}")
                    print(f"    Subnets: {', '.join(info['subnets'])}")
                    print(f"    Legitimate: {info['is_legitimate']} ({info['legitimate_reason']})")
                    
                    if isinstance(severity, dict):
                        print(f"    Severity Breakdown:")
                        print(f"      Total: {severity['total']:.2f}")
                        print(f"      Frequency: {severity['frequency']:.2f}")
                        print(f"      Bursts: {severity['bursts']:.2f}")
                        print(f"      Entropy: {severity['entropy']:.2f}")
                        print(f"      Subnets: {severity['subnets']:.2f}")
                        print(f"      Packet Types: {severity['packet_types']:.2f}")
                        print(f"      IP Changes: {severity['ip_changes']:.2f}")
                    
                    print(f"    Packet Type Distribution:")
                    print(f"      ARP: {info['arp_count']}")
                    print(f"      STP: {info['stp_count']}")
                    print(f"      LLDP: {info['lldp_count']}")
                    print(f"      CDP: {info['cdp_count']}")
                    print(f"      ICMP Redirects: {info['icmp_redirect_count']}")
                    print(f"      DHCP: {info['dhcp_count']}")
                    print(f"      mDNS: {info['mdns_count']}")
                    print(f"      NetBIOS: {info['nbns_count']}")
                    print(f"      Other: {info['other_count']}")
        else:
            print("\n✓ No loop offenders detected - network is clean!")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_lightweight_detection():
    """Test 2: Lightweight detection with sampling."""
    print_separator("TEST 2: Lightweight Detection with Intelligent Sampling")
    
    print("Running lightweight detection for 5 seconds...")
    print("This uses intelligent sampling for efficiency.\n")
    
    try:
        total, offenders, stats, status, severity, metrics = detect_loops_lightweight(
            timeout=5,
            threshold=30,
            use_sampling=True
        )
        
        print(f"✓ Detection completed")
        print(f"\n📊 Results:")
        print(f"  Status: {status.upper()}")
        print(f"  Max severity score: {severity:.2f}")
        print(f"  Total packets: {total}")
        print(f"  Offenders: {len(offenders)}")
        
        print(f"\n⚡ Efficiency Metrics:")
        print(f"  Total packets seen: {metrics['total_packets_seen']}")
        print(f"  Packets analyzed: {metrics['packets_analyzed']}")
        print(f"  Sample rate: 1/{metrics['sample_rate']}")
        print(f"  Efficiency ratio: {metrics['efficiency_ratio']*100:.1f}%")
        print(f"  Cross-subnet detected: {metrics['cross_subnet_detected']}")
        print(f"  Unique MACs: {metrics['unique_macs']}")
        print(f"  Unique subnets: {metrics['unique_subnets']}")
        
        if status != "clean":
            print(f"\n⚠️ Warning: Network status is {status}")
            for mac in offenders:
                if mac in stats:
                    info = stats[mac]
                    print(f"\n  MAC: {mac}")
                    print(f"    Severity: {info['severity']:.2f}")
                    print(f"    IPs: {info['ips']}")
                    print(f"    Subnets: {info['subnets']}")
                    print(f"    ARP: {info['arp_count']}, STP: {info['stp_count']}, Broadcast: {info['broadcast_count']}")
        else:
            print("\n✓ Network status is clean!")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_auto_detection():
    """Test 3: Automatic detection with database integration."""
    print_separator("TEST 3: Automatic Loop Detection")
    
    print("Running auto loop detection...")
    print("This simulates background monitoring with database integration.\n")
    
    try:
        # Test without database first
        result = auto_loop_detection(
            save_to_db=False,
            use_advanced=False
        )
        
        if result["success"]:
            print(f"✓ Auto detection successful")
            print(f"\n📊 Results:")
            print(f"  Status: {result['status'].upper()}")
            print(f"  Severity: {result['severity_score']:.2f}")
            print(f"  Total packets: {result['total_packets']}")
            print(f"  Offenders: {len(result['offenders'])}")
            print(f"  Cross-subnet detected: {result['cross_subnet_detected']}")
            print(f"  Timestamp: {result['timestamp']}")
            
            print(f"\n⚡ Efficiency:")
            eff = result['efficiency_metrics']
            print(f"  Detection method: {eff.get('detection_method', 'N/A')}")
            print(f"  Packets analyzed: {eff.get('packets_analyzed', 'N/A')}")
            print(f"  Sample rate: {eff.get('sample_rate', 'N/A')}")
            
            if result['offenders']:
                print(f"\n⚠️ Offenders: {result['offenders']}")
            else:
                print("\n✓ No offenders detected!")
        else:
            print(f"❌ Auto detection failed: {result.get('error', 'Unknown error')}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_whitelist_management():
    """Test 4: Whitelist and legitimacy checking."""
    print_separator("TEST 4: Whitelist and Legitimacy Checking")
    
    print("Testing whitelist management and false positive reduction...\n")
    
    try:
        engine = LoopDetectionEngine()
        
        # Add some test whitelists
        test_router_mac = "aa:bb:cc:dd:ee:11"
        test_dhcp_mac = "aa:bb:cc:dd:ee:22"
        
        engine.legitimate_patterns["routers"].add(test_router_mac)
        engine.legitimate_patterns["dhcp_servers"].add(test_dhcp_mac)
        
        print("✓ Whitelist created:")
        print(f"  Routers: {list(engine.legitimate_patterns['routers'])}")
        print(f"  DHCP Servers: {list(engine.legitimate_patterns['dhcp_servers'])}")
        print(f"  mDNS Devices: {list(engine.legitimate_patterns['mdns_devices'])}")
        
        # Test legitimacy checking
        test_stats_dhcp = {
            "count": 50,
            "dhcp_count": 45,
            "arp_count": 5
        }
        
        is_legit, reason = engine._is_legitimate_traffic(test_dhcp_mac, test_stats_dhcp)
        
        print(f"\n📝 Legitimacy Test (DHCP Server):")
        print(f"  MAC: {test_dhcp_mac}")
        print(f"  Is Legitimate: {is_legit}")
        print(f"  Reason: {reason}")
        
        test_stats_router = {
            "count": 100,
            "arp_count": 80
        }
        
        is_legit, reason = engine._is_legitimate_traffic(test_router_mac, test_stats_router)
        
        print(f"\n📝 Legitimacy Test (Router):")
        print(f"  MAC: {test_router_mac}")
        print(f"  Is Legitimate: {is_legit}")
        print(f"  Reason: {reason}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cross_subnet_detection():
    """Test 5: Cross-subnet activity detection."""
    print_separator("TEST 5: Cross-Subnet Activity Detection")
    
    print("Testing multi-subnet loop detection capability...\n")
    
    try:
        # Get default interface
        iface = get_default_iface()
        print(f"Monitoring interface: {iface}")
        
        # Run detection focusing on cross-subnet activity
        total, offenders, stats, metrics = detect_loops(
            timeout=8,
            threshold=40,
            iface=iface,
            enable_advanced=True
        )
        
        print(f"\n📊 Cross-Subnet Analysis:")
        print(f"  Total unique subnets: {metrics['total_unique_subnets']}")
        print(f"  Cross-subnet activity detected: {metrics['cross_subnet_activity']}")
        
        # Analyze each MAC for subnet diversity
        multi_subnet_devices = []
        for mac, info in stats.items():
            if len(info.get('subnets', [])) > 1:
                multi_subnet_devices.append((mac, info))
        
        if multi_subnet_devices:
            print(f"\n⚠️ Devices appearing in multiple subnets ({len(multi_subnet_devices)}):")
            for mac, info in multi_subnet_devices:
                print(f"\n  MAC: {mac}")
                print(f"    Subnets: {info['subnets']}")
                print(f"    IPs: {info['ips']}")
                if isinstance(info['severity'], dict):
                    print(f"    Subnet severity score: {info['severity']['subnets']:.2f}")
                    print(f"    Total severity: {info['severity']['total']:.2f}")
        else:
            print("\n✓ No multi-subnet devices detected")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_performance_comparison():
    """Test 6: Performance comparison between detection methods."""
    print_separator("TEST 6: Performance Comparison")
    
    print("Comparing performance of different detection methods...\n")
    
    results = {}
    
    # Test 1: Advanced detection
    try:
        print("⏱️ Testing advanced detection...")
        start = time.time()
        total, offenders, stats, metrics = detect_loops(
            timeout=5,
            threshold=50,
            enable_advanced=True
        )
        elapsed = time.time() - start
        
        results['advanced'] = {
            'time': elapsed,
            'packets': total,
            'offenders': len(offenders),
            'unique_macs': metrics['total_unique_macs']
        }
        print(f"  ✓ Completed in {elapsed:.2f}s")
    except Exception as e:
        print(f"  ❌ Failed: {e}")
    
    time.sleep(2)
    
    # Test 2: Lightweight with sampling
    try:
        print("⏱️ Testing lightweight detection with sampling...")
        start = time.time()
        total, offenders, stats, status, severity, metrics = detect_loops_lightweight(
            timeout=5,
            threshold=50,
            use_sampling=True
        )
        elapsed = time.time() - start
        
        results['lightweight_sampling'] = {
            'time': elapsed,
            'packets': total,
            'offenders': len(offenders),
            'efficiency': metrics['efficiency_ratio'],
            'sample_rate': metrics['sample_rate']
        }
        print(f"  ✓ Completed in {elapsed:.2f}s")
    except Exception as e:
        print(f"  ❌ Failed: {e}")
    
    time.sleep(2)
    
    # Test 3: Lightweight without sampling
    try:
        print("⏱️ Testing lightweight detection without sampling...")
        start = time.time()
        total, offenders, stats, status, severity, metrics = detect_loops_lightweight(
            timeout=5,
            threshold=50,
            use_sampling=False
        )
        elapsed = time.time() - start
        
        results['lightweight_no_sampling'] = {
            'time': elapsed,
            'packets': total,
            'offenders': len(offenders)
        }
        print(f"  ✓ Completed in {elapsed:.2f}s")
    except Exception as e:
        print(f"  ❌ Failed: {e}")
    
    # Display comparison
    print(f"\n📊 Performance Comparison:")
    print(f"\n{'Method':<30} {'Time (s)':<12} {'Packets':<12} {'Offenders':<12} {'Notes'}")
    print("-" * 80)
    
    for method, data in results.items():
        notes = ""
        if method == 'lightweight_sampling':
            notes = f"Eff: {data['efficiency']*100:.1f}%, Rate: 1/{data['sample_rate']}"
        
        print(f"{method:<30} {data['time']:<12.2f} {data['packets']:<12} {data['offenders']:<12} {notes}")
    
    return True


def run_all_tests():
    """Run all test cases."""
    print_separator("ADVANCED LOOP DETECTION TEST SUITE")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Interface: {get_default_iface()}")
    
    tests = [
        ("Basic Advanced Detection", test_basic_detection),
        ("Lightweight with Sampling", test_lightweight_detection),
        ("Auto Detection", test_auto_detection),
        ("Whitelist Management", test_whitelist_management),
        ("Cross-Subnet Detection", test_cross_subnet_detection),
        ("Performance Comparison", test_performance_comparison)
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except KeyboardInterrupt:
            print("\n\n⚠️ Test interrupted by user")
            break
        except Exception as e:
            print(f"\n❌ Test '{name}' crashed: {e}")
            results.append((name, False))
        
        time.sleep(1)
    
    # Summary
    print_separator("TEST SUMMARY")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    print(f"Tests run: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Success rate: {(passed/total*100):.1f}%\n")
    
    for name, success in results:
        status = "✓ PASSED" if success else "❌ FAILED"
        print(f"  {status}: {name}")
    
    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print_separator()


if __name__ == "__main__":
    try:
        # Check if user wants to run specific test
        if len(sys.argv) > 1:
            test_num = sys.argv[1]
            
            test_map = {
                "1": ("Basic Detection", test_basic_detection),
                "2": ("Lightweight Detection", test_lightweight_detection),
                "3": ("Auto Detection", test_auto_detection),
                "4": ("Whitelist Management", test_whitelist_management),
                "5": ("Cross-Subnet Detection", test_cross_subnet_detection),
                "6": ("Performance Comparison", test_performance_comparison)
            }
            
            if test_num in test_map:
                name, func = test_map[test_num]
                print(f"Running single test: {name}")
                func()
            else:
                print(f"Unknown test number: {test_num}")
                print("Available tests: 1-6, or run without arguments for all tests")
        else:
            # Run all tests
            run_all_tests()
            
    except KeyboardInterrupt:
        print("\n\n⚠️ Testing interrupted by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
