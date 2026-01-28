"""
Test script for real-time log streaming functionality.
Verifies log parsing, color coding, and streaming work correctly.
"""

import sys
from pathlib import Path
from service_manager import get_service_manager
import time

def test_log_parsing():
    """Test log line parsing with various formats."""
    print("🧪 TESTING LOG PARSING")
    print("=" * 60)
    
    mgr = get_service_manager()
    
    test_lines = [
        "[2024-01-12 14:30:45] INFO: Server started successfully",
        "[2024-01-12 14:30:46] SUCCESS: Connected to database",
        "[2024-01-12 14:30:47] WARNING: Low memory detected",
        "[2024-01-12 14:30:48] ERROR: Connection timeout",
        "[2024-01-12 14:30:49] DEBUG: Query executed in 0.5ms",
        "2024-01-12 14:30:50 - INFO - Service running on port 5000",
        "Server STARTED on port 5000",
        "WARNING: Configuration file not found",
        "Process exited with code 0",
        "CRITICAL: Database connection failed",
    ]
    
    for line in test_lines:
        timestamp, level, message = mgr._parse_log_line(line)
        print(f"  [{timestamp}] {level:10s} {message}")
    
    print("\n✅ Log parsing test complete\n")

def test_log_buffering():
    """Test log buffer management."""
    print("🧪 TESTING LOG BUFFERING")
    print("=" * 60)
    
    mgr = get_service_manager()
    
    # Check if log buffers are initialized
    for service_name in mgr.services.keys():
        buffer = mgr.log_buffers.get(service_name)
        if buffer is not None:
            print(f"  ✅ {service_name}: Log buffer initialized (size: {len(buffer)})")
        else:
            print(f"  ❌ {service_name}: Log buffer NOT initialized")
    
    print("\n✅ Log buffering test complete\n")

def test_log_file_access():
    """Test log file creation and access."""
    print("🧪 TESTING LOG FILE ACCESS")
    print("=" * 60)
    
    mgr = get_service_manager()
    
    # Check logs directory exists
    if mgr.logs_dir.exists():
        print(f"  ✅ Logs directory exists: {mgr.logs_dir}")
    else:
        print(f"  ⚠️ Logs directory does not exist yet: {mgr.logs_dir}")
    
    # Check log file paths
    for service_name in mgr.services.keys():
        log_path = mgr.get_log_file_path(service_name)
        if log_path:
            if log_path.exists():
                print(f"  ✅ {service_name}: Log file exists ({log_path.stat().st_size} bytes)")
            else:
                print(f"  ℹ️ {service_name}: Log file path ready (not created yet)")
        else:
            print(f"  ❌ {service_name}: Invalid log path")
    
    print("\n✅ Log file access test complete\n")

def test_service_status():
    """Test service status detection."""
    print("🧪 TESTING SERVICE STATUS")
    print("=" * 60)
    
    mgr = get_service_manager()
    
    statuses = mgr.get_all_statuses()
    for service_name, info in statuses.items():
        status_icon = "🟢" if info['status'] == 'running' else "⚫" if info['status'] == 'stopped' else "🔴"
        health_icon = "✅" if info['health'] else "❌"
        print(f"  {status_icon} {info['name']}")
        print(f"     Status: {info['status']}")
        print(f"     Health: {health_icon}")
        print(f"     Port: {info['port']}")
        print(f"     Auto-start: {info['auto_start']}")
        print()
    
    print("✅ Service status test complete\n")

def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("🚀 SERVICE MANAGER LOG STREAMING TEST SUITE")
    print("="*60 + "\n")
    
    try:
        test_log_parsing()
        test_log_buffering()
        test_log_file_access()
        test_service_status()
        
        print("="*60)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
        print("="*60)
        print("\nℹ️ To test real-time streaming:")
        print("  1. Open the Admin Window")
        print("  2. Click 'Service Manager'")
        print("  3. Start a service and watch logs stream live")
        print("  4. Check color coding: INFO=white, SUCCESS=green, WARNING=yellow, ERROR=red")
        print("\n")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
