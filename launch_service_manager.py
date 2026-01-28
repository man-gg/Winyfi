#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Service Manager Launcher
Launches WinyFi in service manager only mode
"""
import sys
import subprocess
import os

def main():
    """Launch WinyFi with --service-manager-only flag"""
    
    # Get the directory containing this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Try to find and launch main.py or Winyfi.exe
    if os.path.exists(os.path.join(script_dir, 'main.py')):
        # Running from source
        main_py = os.path.join(script_dir, 'main.py')
        cmd = [sys.executable, main_py, '--service-manager-only']
    elif os.path.exists(os.path.join(script_dir, 'dist', 'Winyfi.exe')):
        # Running from dist folder
        cmd = [os.path.join(script_dir, 'dist', 'Winyfi.exe'), '--service-manager-only']
    elif os.path.exists(os.path.join(script_dir, 'Winyfi.exe')):
        # Running from installed location
        cmd = [os.path.join(script_dir, 'Winyfi.exe'), '--service-manager-only']
    else:
        print(f"Error: Could not find WinyFi executable or main.py in {script_dir}")
        sys.exit(1)
    
    # Launch the process
    try:
        subprocess.run(cmd, check=False)
    except Exception as e:
        print(f"Error launching WinyFi: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
