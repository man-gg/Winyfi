# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Winyfi Network Monitor

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Assets and resources
        ('routerLocImg', 'routerLocImg'),  # Router images directory
        ('assets', 'assets'),              # App assets (logos, images)
        
        # Configuration files
        ('db_config.json', '.'),           # Database configuration
        
        # Database and documentation
        ('winyfi.sql', '.'),               # Database schema
        ('*.md', '.'),                     # README and guides
        ('README_SETUP.txt', '.'),         # Setup instructions
        ('check_database.bat', '.'),       # Database check script
        ('check_mysql_before_launch.bat', '.'),  # MySQL startup check
        
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
        
        # Database
        'mysql.connector',
        'mysql.connector.errors',
        
        # System utilities
        'psutil',
        'scapy',
        'requests',
        'zeroconf',
        
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
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',  # Your application icon
)
