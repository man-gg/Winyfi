# Test file to verify import resolution
import sys
import os

# Add the client_window directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Test the imports
try:
    from client_window.client_app import ClientDashboard
    print("✅ ClientDashboard import successful")
except ImportError as e:
    print(f"❌ Import failed: {e}")

try:
    # Test tab imports
    from client_window.tabs.dashboard_tab import DashboardTab
    from client_window.tabs.routers_tab import RoutersTab
    from client_window.tabs.reports_tab import ReportsTab
    from client_window.tabs.bandwidth_tab import BandwidthTab
    from client_window.tabs.settings_tab import SettingsTab
    print("✅ Tab imports successful")
except ImportError as e:
    print(f"❌ Tab import failed: {e}")