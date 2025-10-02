#!/usr/bin/env python3
"""
Test script to verify loop detection system.
This script will:
1. Start the dashboard loop detection
2. Run loop simulations
3. Monitor detection results
"""

import time
import threading
import subprocess
import sys
from datetime import datetime

def run_loop_simulation():
    """Run the loop simulation in a separate process."""
    print("🚨 Starting loop simulation...")
    try:
        # Run the simulator with loop scenario
        result = subprocess.run([
            sys.executable, "simulate_loop.py"
        ], input="3\n", text=True, capture_output=True, timeout=30)
        
        print("✅ Loop simulation completed")
        print("Simulation output:", result.stdout)
        if result.stderr:
            print("Simulation errors:", result.stderr)
            
    except subprocess.TimeoutExpired:
        print("⏰ Loop simulation timed out (expected)")
    except Exception as e:
        print(f"❌ Error running simulation: {e}")

def test_loop_detection():
    """Test the complete loop detection system."""
    print("🔄 Loop Detection System Test")
    print("=" * 50)
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    print("📋 Test Plan:")
    print("1. Start dashboard loop detection")
    print("2. Run loop simulation")
    print("3. Monitor detection results")
    print("4. Check database persistence")
    print()
    
    # Step 1: Instructions for starting dashboard
    print("🚀 STEP 1: Start the Dashboard")
    print("Please run the dashboard in a separate terminal:")
    print("   python dashboard.py")
    print("Then open the Loop Detection modal and start automatic detection.")
    print()
    
    input("Press Enter when dashboard is running and loop detection is active...")
    
    # Step 2: Run simulation
    print("🚨 STEP 2: Running Loop Simulation")
    print("Starting loop simulation for 30 seconds...")
    
    # Run simulation in background
    sim_thread = threading.Thread(target=run_loop_simulation, daemon=True)
    sim_thread.start()
    
    # Wait for simulation to complete
    time.sleep(35)
    
    print("✅ Simulation phase completed")
    print()
    
    # Step 3: Check results
    print("📊 STEP 3: Check Detection Results")
    print("Please check the dashboard for:")
    print("- Detection history in the modal")
    print("- Statistics updates")
    print("- Database persistence")
    print()
    
    print("🔍 Expected Results:")
    print("- Should detect loops during simulation")
    print("- Statistics should show increased counts")
    print("- History should show new detection records")
    print("- Database should persist the data")
    print()
    
    print("✅ Test completed!")
    print("Check the dashboard to verify loop detection is working.")

if __name__ == "__main__":
    test_loop_detection()

