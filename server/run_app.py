# -*- coding: utf-8 -*-
"""
Flask App Launcher - Ensures proper startup when run as subprocess
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
is_pyinstaller_temp = '_MEI' in script_dir

print(f"[DEBUG] Script location: {script_dir}")
print(f"[DEBUG] Is PyInstaller temp: {is_pyinstaller_temp}")
print(f"[DEBUG] sys.frozen: {getattr(sys, 'frozen', False)}")
print(f"[DEBUG] Has _MEIPASS: {hasattr(sys, '_MEIPASS')}")

if getattr(sys, 'frozen', False) or is_pyinstaller_temp:
    # Running in or from PyInstaller bundle
    if hasattr(sys, '_MEIPASS'):
        bundle_dir = sys._MEIPASS
        print(f"[DEBUG] Using sys._MEIPASS: {bundle_dir}")
    else:
        # Extract bundle dir from path containing _MEI
        parts = script_dir.split(os.sep)
        for i, part in enumerate(parts):
            if part.startswith('_MEI'):
                bundle_dir = os.sep.join(parts[:i+1])
                print(f"[DEBUG] Extracted bundle dir: {bundle_dir}")
                break
        else:
            bundle_dir = parent_dir
            print(f"[DEBUG] Fallback bundle dir: {bundle_dir}")
    
    script_dir = os.path.join(bundle_dir, 'server')
    parent_dir = bundle_dir
    print(f"[DEBUG] Final parent_dir: {parent_dir}")
    print(f"[DEBUG] Final script_dir: {script_dir}")

# Add parent directory to path for imports (MUST be first)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
    print(f"[DEBUG] Added to sys.path: {parent_dir}")

# Add server directory to path
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)
    print(f"[DEBUG] Added to sys.path: {script_dir}")

print(f"[DEBUG] sys.path: {sys.path[:3]}")

# List files in parent directory to verify
if os.path.exists(parent_dir):
    files = os.listdir(parent_dir)
    print(f"[DEBUG] Files in parent_dir: {[f for f in files[:10] if f.endswith('.py')]}")

# Change to server directory
if os.path.exists(script_dir):
    os.chdir(script_dir)
    print(f"[DEBUG] Changed to: {os.getcwd()}")

# Disable Flask debug mode
os.environ['FLASK_DEBUG'] = 'false'

try:
    # Import and run the Flask app
    from app import create_app
    
    print("="*60)
    print("Starting Flask API Server")
    print("="*60)
    
    app = create_app()
    
    # Run Flask with proper settings for subprocess
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        use_reloader=False,
        threaded=True
    )
except Exception as e:
    print(f"ERROR starting Flask API: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)
