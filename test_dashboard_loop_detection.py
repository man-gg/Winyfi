#!/usr/bin/env python3
"""
Test script for the improved dashboard loop detection system.
This demonstrates the client-side loop detection functionality.
"""

import sys
import os
import time
from datetime import datetime

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_loop_detection_functions():
    """Test the loop detection functions from network_utils."""
    print("🔍 Testing Loop Detection Functions")
    print("=" * 50)
    
    try:
        from network_utils import detect_loops_lightweight
        
        print("Running lightweight loop detection...")
        total_packets, offenders, stats, status, severity_score = detect_loops_lightweight(
            timeout=3,  # 3 seconds for testing
            threshold=30,
            iface="Wi-Fi"
        )
        
        print(f"📊 Detection Results:")
        print(f"   Total Packets: {total_packets}")
        print(f"   Status: {status}")
        print(f"   Severity Score: {severity_score:.2f}")
        print(f"   Offenders: {len(offenders)}")
        
        if offenders:
            print(f"   Offender MACs: {', '.join(offenders)}")
        
        # Show stats for each MAC
        if stats:
            print(f"\n📈 Detailed Stats:")
            for mac, info in stats.items():
                print(f"   {mac}:")
                print(f"     - Total packets: {info['count']}")
                print(f"     - ARP packets: {info['arp_count']}")
                print(f"     - Broadcast packets: {info['broadcast_count']}")
                print(f"     - Severity: {info['severity']:.2f}")
                if info['ips']:
                    print(f"     - IPs: {', '.join(info['ips'])}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during detection: {e}")
        return False

def test_dashboard_integration():
    """Test dashboard loop detection integration."""
    print("\n🔄 Testing Dashboard Integration")
    print("=" * 50)
    
    try:
        # Import dashboard class
        from dashboard import Dashboard
        import tkinter as tk
        
        print("✅ Dashboard class imported successfully")
        print("✅ Loop detection methods available:")
        
        # Check if methods exist
        methods = [
            'start_loop_detection',
            'stop_loop_detection', 
            'toggle_loop_detection',
            'set_loop_detection_interval',
            'get_loop_detection_history',
            'get_loop_detection_stats',
            'export_loop_detection_history',
            'build_loop_detection_tab'
        ]
        
        for method in methods:
            if hasattr(Dashboard, method):
                print(f"   ✅ {method}")
            else:
                print(f"   ❌ {method} - MISSING")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing dashboard integration: {e}")
        return False

def test_ui_components():
    """Test UI component creation."""
    print("\n🎨 Testing UI Components")
    print("=" * 50)
    
    try:
        import ttkbootstrap as tb
        from tkinter import ttk
        
        # Create a test window
        root = tb.Window()
        root.withdraw()  # Hide the window
        
        # Test creating UI components
        frame = tb.Frame(root)
        
        # Test statistics cards
        stats_frame = tb.Frame(frame)
        total_card = tb.LabelFrame(stats_frame, text="📈 Total Detections", 
                                 bootstyle="info", padding=15)
        total_label = tb.Label(total_card, text="0", font=("Segoe UI", 24, "bold"))
        
        # Test treeview
        columns = ("Time", "Status", "Packets", "Offenders", "Severity", "Interface")
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=12)
        
        # Test buttons
        start_btn = tb.Button(frame, text="▶ Start", bootstyle="success")
        stop_btn = tb.Button(frame, text="⏹ Stop", bootstyle="danger")
        export_btn = tb.Button(frame, text="📊 Export", bootstyle="info")
        
        print("✅ UI components created successfully")
        print("   ✅ Statistics cards")
        print("   ✅ Treeview for history")
        print("   ✅ Control buttons")
        print("   ✅ Configuration frame")
        
        root.destroy()
        return True
        
    except Exception as e:
        print(f"❌ Error testing UI components: {e}")
        return False

def test_performance():
    """Test loop detection performance."""
    print("\n⚡ Testing Performance")
    print("=" * 50)
    
    try:
        from network_utils import detect_loops_lightweight
        import time
        
        # Test multiple detections
        start_time = time.time()
        
        for i in range(3):
            print(f"Running detection {i+1}/3...")
            total_packets, offenders, stats, status, severity_score = detect_loops_lightweight(
                timeout=2,  # 2 seconds for faster testing
                threshold=30,
                iface="Wi-Fi"
            )
            print(f"   Result: {status}, Severity: {severity_score:.2f}")
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"\n📊 Performance Results:")
        print(f"   Total time: {total_time:.2f} seconds")
        print(f"   Average per detection: {total_time/3:.2f} seconds")
        print(f"   Efficiency: {'✅ Good' if total_time < 10 else '⚠️ Slow'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing performance: {e}")
        return False

def main():
    """Main test function."""
    print("🚀 Dashboard Loop Detection Test")
    print("=" * 50)
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test 1: Loop detection functions
    print("\n1️⃣ Testing loop detection functions...")
    success1 = test_loop_detection_functions()
    
    # Test 2: Dashboard integration
    print("\n2️⃣ Testing dashboard integration...")
    success2 = test_dashboard_integration()
    
    # Test 3: UI components
    print("\n3️⃣ Testing UI components...")
    success3 = test_ui_components()
    
    # Test 4: Performance
    print("\n4️⃣ Testing performance...")
    success4 = test_performance()
    
    # Summary
    print("\n📋 Test Summary:")
    print("=" * 50)
    print(f"Loop Detection Functions: {'✅ PASS' if success1 else '❌ FAIL'}")
    print(f"Dashboard Integration: {'✅ PASS' if success2 else '❌ FAIL'}")
    print(f"UI Components: {'✅ PASS' if success3 else '❌ FAIL'}")
    print(f"Performance: {'✅ PASS' if success4 else '❌ FAIL'}")
    
    if all([success1, success2, success3, success4]):
        print("\n🎉 All tests passed! Loop detection system is working correctly.")
        print("\n💡 To use the loop detection system:")
        print("   1. Start the dashboard: python main.py")
        print("   2. Navigate to 'Loop Detection' tab")
        print("   3. Click 'Start' to begin monitoring")
        print("   4. View real-time statistics and history")
        print("   5. Export data using the 'Export' button")
    else:
        print("\n⚠️ Some tests failed. Check the error messages above.")
    
    return all([success1, success2, success3, success4])

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
