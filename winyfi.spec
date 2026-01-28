# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Winyfi Network Monitor
import os
from PyInstaller.utils.hooks import collect_data_files

# Include mysql.connector locales to avoid ImportError: No localization support for language 'eng'
mysql_datas = collect_data_files('mysql.connector', includes=['locales/*'])

block_cipher = None

# Get icon path (use relative path since PyInstaller runs from spec directory)
icon_path = 'icon.ico' if os.path.exists('icon.ico') else None

print(f"[DEBUG] Icon path: {icon_path}")
print(f"[DEBUG] Icon exists: {os.path.exists('icon.ico')}")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # MySQL connector locales (explicit include for PyInstaller)
        # This is CRITICAL for PyInstaller builds to support authentication plugins
        *mysql_datas,
        ('.venv/Lib/site-packages/mysql/connector/locales', 'mysql/connector/locales'),

        # Assets and resources
        ('routerLocImg', 'routerLocImg'),  # Router images directory
        ('assets', 'assets'),              # App assets (logos, images)
        ('server', 'server'),              # Server scripts (run_app.py, run_unifi_api.py, app.py)
        
        # Service Manager launchers
        ('launch_service_manager.bat', '.'),  # Service manager batch launcher
        ('launch_service_manager.py', '.'),   # Service manager Python launcher
        
        # Configuration files
        ('db_config.json', '.'),           # Database configuration
        
        # Database and documentation
        ('winyfi.sql', '.'),               # Database schema
        ('*.md', '.'),                     # README and guides
        ('README_SETUP.txt', '.'),         # Setup instructions
        ('check_database.bat', '.'),       # Database check script (OPTIONAL)
        ('check_mysql_before_launch.bat', '.'),  # MySQL startup check (OPTIONAL)
        ('SERVICE_MANAGER_README.md', '.'),  # Service Manager documentation
        
        # Icon file
        ('icon.ico', '.'),                 # Application icon
    ],
    hiddenimports=[
        # UI Framework
        'ttkbootstrap',
        'ttkbootstrap.constants',
        'ttkbootstrap.dialogs',
        'ttkbootstrap.widgets',
        
        # Image processing
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'PIL.ImageDraw',
        
        # Plotting and visualization
        'matplotlib',
        'matplotlib.backends.backend_tkagg',
        'matplotlib.figure',
        'matplotlib.ticker',
        'matplotlib.patches',
        
        # Database - CRITICAL: MySQL authentication support for PyInstaller
        # MANDATORY: These imports MUST be explicit to bundle auth plugins in the EXE
        # Without these, PyInstaller omits MySQL auth plugins, causing runtime failures
        'mysql.connector',
        'mysql.connector.errors',
        'mysql.connector.plugins',  # CRITICAL: Plugins container module
        'mysql.connector.plugins.mysql_native_password',  # MySQL 5.7 / legacy auth
        'mysql.connector.plugins.caching_sha2_password',  # MySQL 8.0+ modern auth
        
        # System utilities
        'psutil',
        'scapy',
        'requests',
        'zeroconf',
        
        # Flask and web framework - CRITICAL for API server
        'flask',
        'flask_cors',
        'werkzeug',
        
        # Data processing
        'pandas',
        'openpyxl',
        'xlsxwriter',
        
        # Standard library
        'datetime',
        'collections',
        'threading',
        'queue',
        'logging',
        'traceback',
        'json',
        'time',
        
        # Application modules
        'resource_utils',
        'login',
        'dashboard',
        'db',
        'router_utils',
        'network_utils',
        'user_utils',
        'ticket_utils',
        'report_utils',
        'bandwidth_logger',
        'notification_utils',
        'notification_ui',
        'notification_performance',
        'print_utils',
        'device_utils',
        'activity_log_viewer',
        'service_manager',  # Service manager for Flask and UniFi API
        'server_discovery',  # Server discovery utilities
        
        # Client window and tabs
        'client_window',
        'client_window.client_app',
        'client_window.tabs',
    ],
    hookspath=['./'],  # Look for hooks in current directory
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Winyfi',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Disable UPX to avoid PE checksum issues
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,  # Your application icon
)
