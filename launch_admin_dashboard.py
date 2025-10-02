#!/usr/bin/env python3
"""
Launch script for the Admin Loop Detection Dashboard
"""

import sys
import os

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from admin_loop_dashboard import show_admin_dashboard

if __name__ == "__main__":
    print("🚀 Starting Admin Loop Detection Dashboard...")
    print("=" * 50)
    print("This dashboard provides comprehensive monitoring and control")
    print("for the automatic loop detection system.")
    print("=" * 50)
    
    try:
        show_admin_dashboard()
    except KeyboardInterrupt:
        print("\n⏹️ Dashboard closed by user")
    except Exception as e:
        print(f"\n❌ Error starting dashboard: {e}")
        sys.exit(1)
