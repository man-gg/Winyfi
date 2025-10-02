#!/usr/bin/env python3
"""
Simple script to run loop simulation for testing.
"""

import time
import threading
from simulate_loop import simulate_scenario, IFACE

def run_loop_test():
    """Run a loop simulation test."""
    print("🔄 Starting Loop Detection Test")
    print("=" * 40)
    print(f"Interface: {IFACE}")
    print("Duration: 30 seconds")
    print("Scenario: Loop Detection")
    print("=" * 40)
    
    print("🚨 Starting loop simulation...")
    print("This will create network loops for 30 seconds.")
    print("Open the dashboard and check if loop detection catches them!")
    print()
    
    # Run the loop simulation
    simulate_scenario("loop")
    
    print("✅ Loop simulation completed!")
    print("Check your dashboard for detection results.")

if __name__ == "__main__":
    run_loop_test()

