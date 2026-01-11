# -*- coding: utf-8 -*-
"""
UniFi API Launcher - Ensures proper startup when run as subprocess
"""
import sys
import os

# Force UTF-8 encoding for Windows compatibility
if sys.platform.startswith('win'):
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Ensure we're in the right directory
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# Add parent directory to path for imports
parent_dir = os.path.dirname(script_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Disable Flask debug mode
os.environ['FLASK_DEBUG'] = 'false'

try:
    # Import and run the UniFi API
    from unifi_api import app
    
    print("="*60)
    print("Starting UniFi API Server")
    print("="*60)
    
    # Run Flask with proper settings for subprocess
    app.run(
        host="0.0.0.0",
        port=5001,
        debug=False,
        use_reloader=False,
        threaded=True
    )
except Exception as e:
    print(f"ERROR starting UniFi API: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)
