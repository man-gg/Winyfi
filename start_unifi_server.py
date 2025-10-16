#!/usr/bin/env python3
"""
Start the UniFi API server for testing
"""
import sys
import os

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

from server.unifi_api import app

if __name__ == '__main__':
    print("🚀 Starting UniFi API Mock Server on http://localhost:5001")
    print("📡 Available endpoints:")
    print("   - GET  /api/unifi/devices       - List all UniFi APs")
    print("   - GET  /api/unifi/clients       - List all connected clients")
    print("   - GET  /api/unifi/bandwidth/total - Get total bandwidth")
    print("   - GET  /api/unifi/clients/count - Get client count")
    print("   - POST /api/unifi/mock          - Toggle mock mode")
    print("\n✨ Press Ctrl+C to stop the server\n")
    
    app.run(host='0.0.0.0', port=5001, debug=True)
