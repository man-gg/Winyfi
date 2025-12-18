"""
Quick test to verify all imports work before building
Run this to check for import errors: python test_build.py
"""
import sys
import os

def test_imports():
    """Test all critical imports"""
    errors = []
    
    print("Testing imports...\n")
    
    # Test main modules
    tests = [
        ('main', 'main'),
        ('login', 'login'),
        ('dashboard', 'dashboard'),
        ('db', 'db'),
        ('router_utils', 'router_utils'),
        ('network_utils', 'network_utils'),
        ('user_utils', 'user_utils'),
        ('ticket_utils', 'ticket_utils'),
        ('report_utils', 'report_utils'),
        ('bandwidth_logger', 'bandwidth_logger'),
        ('notification_utils', 'notification_utils'),
        ('notification_ui', 'notification_ui'),
        ('print_utils', 'print_utils'),
        ('device_utils', 'device_utils'),
        ('client_window', 'client_window'),
        ('client_window.client_app', 'client_window.client_app'),
        ('client_window.tabs.dashboard_tab', 'client_window.tabs.dashboard_tab'),
        ('client_window.tabs.routers_tab', 'client_window.tabs.routers_tab'),
        ('client_window.tabs.reports_tab', 'client_window.tabs.reports_tab'),
        ('client_window.tabs.bandwidth_tab', 'client_window.tabs.bandwidth_tab'),
        ('client_window.tabs.settings_tab', 'client_window.tabs.settings_tab'),
    ]
    
    for name, module in tests:
        try:
            __import__(module)
            print(f"✅ {name}")
        except Exception as e:
            print(f"❌ {name}: {e}")
            errors.append((name, str(e)))
    
    print("\n" + "="*60)
    if errors:
        print(f"❌ Found {len(errors)} import errors:")
        for name, error in errors:
            print(f"   - {name}: {error}")
        return False
    else:
        print("✅ All imports successful! Ready to build.")
        return True

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
