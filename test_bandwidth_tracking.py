"""
Test Script for Enhanced Bandwidth Tracking System

This script tests the bandwidth tracking functionality without requiring
the full dashboard application to be running.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from bandwidth_tracker import BandwidthTracker, get_bandwidth_tracker
from datetime import datetime


def test_delta_calculation():
    """Test bandwidth delta calculation logic"""
    print("=" * 60)
    print("TEST 1: Delta Calculation")
    print("=" * 60)
    
    tracker = BandwidthTracker()
    
    # Simulate first check
    print("\n📊 First check (baseline):")
    rx_diff1, tx_diff1, is_reset1 = tracker.compute_delta(
        router_id=1,
        current_rx=5000000000,  # 5 GB
        current_tx=2000000000   # 2 GB
    )
    print(f"   RX diff: {tracker.format_bytes(rx_diff1)} (expected: 0 B - first time)")
    print(f"   TX diff: {tracker.format_bytes(tx_diff1)} (expected: 0 B - first time)")
    print(f"   Reset detected: {is_reset1} (expected: False)")
    
    # Simulate second check (1 MB RX, 500 KB TX transferred)
    print("\n📊 Second check (normal delta):")
    rx_diff2, tx_diff2, is_reset2 = tracker.compute_delta(
        router_id=1,
        current_rx=5001000000,  # +1 MB
        current_tx=2000500000   # +500 KB
    )
    print(f"   RX diff: {tracker.format_bytes(rx_diff2)} (expected: ~1 MB)")
    print(f"   TX diff: {tracker.format_bytes(tx_diff2)} (expected: ~500 KB)")
    print(f"   Reset detected: {is_reset2} (expected: False)")
    
    # Simulate reboot (counters reset)
    print("\n📊 Third check (reboot detected):")
    rx_diff3, tx_diff3, is_reset3 = tracker.compute_delta(
        router_id=1,
        current_rx=100000,    # Reset to small value
        current_tx=50000      # Reset to small value
    )
    print(f"   RX diff: {tracker.format_bytes(rx_diff3)} (expected: 0 B - reset)")
    print(f"   TX diff: {tracker.format_bytes(tx_diff3)} (expected: 0 B - reset)")
    print(f"   Reset detected: {is_reset3} (expected: True)")
    
    print("\n✅ Delta calculation test complete\n")


def test_format_bytes():
    """Test byte formatting function"""
    print("=" * 60)
    print("TEST 2: Byte Formatting")
    print("=" * 60)
    
    tracker = BandwidthTracker()
    
    test_cases = [
        (512, "512 B"),
        (1024, "1.00 KB"),
        (1536, "1.50 KB"),
        (1048576, "1.00 MB"),
        (1572864, "1.50 MB"),
        (1073741824, "1.00 GB"),
        (5368709120, "5.00 GB"),
    ]
    
    print("\nTesting various byte values:")
    for bytes_val, expected in test_cases:
        result = tracker.format_bytes(bytes_val)
        status = "✅" if expected in result else "❌"
        print(f"   {status} {bytes_val:,} bytes → {result} (expected: {expected})")
    
    print("\n✅ Byte formatting test complete\n")


def test_multiple_routers():
    """Test tracking multiple routers simultaneously"""
    print("=" * 60)
    print("TEST 3: Multiple Router Tracking")
    print("=" * 60)
    
    tracker = BandwidthTracker()
    
    routers = [
        {"id": 1, "name": "Living Room AP", "rx": 5000000000, "tx": 2000000000},
        {"id": 2, "name": "Bedroom AP", "rx": 3000000000, "tx": 1000000000},
        {"id": 3, "name": "Kitchen AP", "rx": 8000000000, "tx": 3500000000},
    ]
    
    print("\n📊 Initial check for all routers:")
    for router in routers:
        rx_diff, tx_diff, is_reset = tracker.compute_delta(
            router["id"],
            router["rx"],
            router["tx"]
        )
        print(f"   {router['name']}: RX {tracker.format_bytes(rx_diff)}, TX {tracker.format_bytes(tx_diff)}")
    
    print("\n📊 Second check with deltas:")
    updates = [
        {"id": 1, "rx": 5010000000, "tx": 2005000000},  # +10 MB RX, +5 MB TX
        {"id": 2, "rx": 3002000000, "tx": 1001000000},  # +2 MB RX, +1 MB TX
        {"id": 3, "rx": 8050000000, "tx": 3520000000},  # +50 MB RX, +20 MB TX
    ]
    
    for i, update in enumerate(updates):
        rx_diff, tx_diff, is_reset = tracker.compute_delta(
            update["id"],
            update["rx"],
            update["tx"]
        )
        router_name = routers[i]["name"]
        print(f"   {router_name}: RX +{tracker.format_bytes(rx_diff)}, TX +{tracker.format_bytes(tx_diff)}")
    
    print("\n✅ Multiple router tracking test complete\n")


def test_singleton_instance():
    """Test that get_bandwidth_tracker returns the same instance"""
    print("=" * 60)
    print("TEST 4: Singleton Instance")
    print("=" * 60)
    
    tracker1 = get_bandwidth_tracker()
    tracker2 = get_bandwidth_tracker()
    
    is_same = tracker1 is tracker2
    print(f"\n   Tracker 1 ID: {id(tracker1)}")
    print(f"   Tracker 2 ID: {id(tracker2)}")
    print(f"   Same instance: {is_same} (expected: True)")
    
    if is_same:
        print("\n✅ Singleton instance test passed")
    else:
        print("\n❌ Singleton instance test failed")
    print()


def test_database_connection():
    """Test database connectivity (optional - requires DB)"""
    print("=" * 60)
    print("TEST 5: Database Connection (Optional)")
    print("=" * 60)
    
    try:
        from db import get_connection
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if bandwidth_snapshots table exists
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = DATABASE() 
            AND table_name = 'bandwidth_snapshots'
        """)
        
        exists = cursor.fetchone()[0] > 0
        
        cursor.close()
        conn.close()
        
        if exists:
            print("\n✅ Database connected successfully")
            print("✅ Table 'bandwidth_snapshots' exists")
        else:
            print("\n⚠️ Database connected, but 'bandwidth_snapshots' table not found")
            print("   Run the migration script: migrations/add_bandwidth_tracking.sql")
        
    except Exception as e:
        print(f"\n⚠️ Database test skipped: {e}")
        print("   This is optional - tests can run without DB connection")
    
    print()


def run_all_tests():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("🧪 BANDWIDTH TRACKING SYSTEM - TEST SUITE")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    try:
        test_delta_calculation()
        test_format_bytes()
        test_multiple_routers()
        test_singleton_instance()
        test_database_connection()
        
        print("=" * 60)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
        print("=" * 60)
        
    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ TEST SUITE FAILED")
        print("=" * 60)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()
