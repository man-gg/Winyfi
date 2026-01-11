#!/usr/bin/env python3
"""
Quick test script to validate Service Manager fixes
"""
import time
import sys
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent))

from service_manager import get_service_manager

def test_service_manager():
    """Test the fixed Service Manager"""
    print("=" * 60)
    print("🧪 SERVICE MANAGER TEST SUITE")
    print("=" * 60)
    
    mgr = get_service_manager()
    
    # Test 1: Initialization
    print("\n✅ Test 1: Manager initialized successfully")
    print(f"   Services found: {list(mgr.services.keys())}")
    
    # Test 2: Get status
    print("\n✅ Test 2: Getting service statuses...")
    for service_name, service_info in mgr.services.items():
        status = mgr.get_service_status(service_name)
        print(f"   {service_info['name']}: {status}")
    
    # Test 3: Check port availability
    print("\n✅ Test 3: Checking port availability...")
    for service_name, service_info in mgr.services.items():
        in_use = mgr._is_port_in_use(service_info['port'])
        print(f"   Port {service_info['port']}: {'OCCUPIED' if in_use else 'AVAILABLE'}")
    
    # Test 4: Try starting Flask API
    print("\n✅ Test 4: Attempting to start Flask API...")
    print("   (This may take a few seconds...)")
    success = mgr.start_service('flask_api')
    if success:
        print("   ✅ Flask API started successfully!")
        status = mgr.get_service_status('flask_api')
        print(f"   Status: {status}")
        
        # Test 5: Health check
        print("\n✅ Test 5: Checking Flask API health...")
        time.sleep(2)  # Wait for startup
        health = mgr.check_service_health('flask_api')
        print(f"   Health: {'✅ HEALTHY' if health else '❌ UNHEALTHY'}")
        
        # Test 6: Stop service
        print("\n✅ Test 6: Stopping Flask API...")
        mgr.stop_service('flask_api')
        status = mgr.get_service_status('flask_api')
        print(f"   Status after stop: {status}")
        in_use = mgr._is_port_in_use(5000)
        print(f"   Port 5000 after stop: {'OCCUPIED' if in_use else 'AVAILABLE'}")
    else:
        print("   ❌ Failed to start Flask API")
        print("   Check logs at: logs/flask-api-error.log")
    
    print("\n" + "=" * 60)
    print("🏁 TEST SUITE COMPLETE")
    print("=" * 60)

if __name__ == '__main__':
    test_service_manager()
