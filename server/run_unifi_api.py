# -*- coding: utf-8 -*-
"""
UniFi API Launcher - Ensures proper startup when run as subprocess
"""
import sys
import os

# CRITICAL: Prevent tkinter from initializing before Flask
# This prevents the login window from popping up when Flask starts
os.environ['DISPLAY'] = ''  # Headless mode on Linux
os.environ['MPLBACKEND'] = 'Agg'  # Use non-interactive matplotlib backend

# Force UTF-8 encoding for Windows compatibility
if sys.platform.startswith('win'):
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Clean environment to prevent Flask reloader issues
# Remove any Werkzeug environment variables that might cause issues in subprocess
for key in list(os.environ.keys()):
    if 'WERKZEUG' in key:
        del os.environ[key]

# Setup paths for frozen (PyInstaller) and non-frozen execution
# Detect if running from PyInstaller's temp directory (even if not frozen)
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)

# Check if we're in a PyInstaller temp directory (_MEI)
is_pyinstaller_temp = '_MEI' in script_dir or (hasattr(sys, '_MEIPASS') and sys._MEIPASS in script_dir)

if getattr(sys, 'frozen', False) or is_pyinstaller_temp:
    # Running in or from PyInstaller bundle
    if hasattr(sys, '_MEIPASS'):
        bundle_dir = sys._MEIPASS
    else:
        # Extract bundle dir from path containing _MEI
        parts = script_dir.split(os.sep)
        for i, part in enumerate(parts):
            if part.startswith('_MEI'):
                bundle_dir = os.sep.join(parts[:i+1])
                break
        else:
            bundle_dir = parent_dir
    
    script_dir = os.path.join(bundle_dir, 'server')
    parent_dir = bundle_dir

# Add parent directory to path for imports (MUST be first)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Add server directory to path
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

# Change to server directory
if os.path.exists(script_dir):
    os.chdir(script_dir)

# Disable Flask debug mode
os.environ['FLASK_DEBUG'] = 'false'

try:
    # Import and run the UniFi API
    import unifi_api
    app = unifi_api.app
    
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
