# -*- coding: utf-8 -*-
"""
Flask App Launcher - Ensures proper startup when run as subprocess
"""
import sys
import os

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
