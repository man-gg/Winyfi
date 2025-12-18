# Winyfi Installer - Complete Setup Guide

This guide covers building the Winyfi executable and installer for Windows.

## Prerequisites

### System Requirements
- **OS**: Windows 10 or later (64-bit)
- **Python**: Python 3.8 or later
- **RAM**: 4 GB minimum
- **Disk Space**: 500 MB for installation

### Required Software
1. **Python 3.8+** - Download from https://www.python.org/
   - During installation, **check "Add Python to PATH"**
   
2. **XAMPP** (for MySQL database) - Download from https://www.apachefriends.org/
   - Includes Apache, MySQL, and phpMyAdmin
   - Required for running Winyfi
   
3. **Inno Setup 6** (optional, for creating installer) - Download from https://jrsoftware.org/isdl.php
   - Only needed if you want to create an installer (.exe)
   - Not required to run Winyfi directly

## Setup Instructions

### Step 1: Prepare Python Environment

```powershell
# Navigate to project directory
cd C:\Path\To\Winyfi

# Create virtual environment
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# If you get execution policy error, run:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Install all required packages
pip install -r requirements.txt
```

### Step 2: Verify Project Files

Ensure all required files exist in the project directory:

```
✅ winyfi.spec              (PyInstaller spec file)
✅ build.py                 (Build script)
✅ main.py                  (Entry point)
✅ db_config.json           (Database configuration)
✅ icon.ico                 (Application icon)
✅ resource_utils.py        (Resource path utility)
✅ assets/                  (Images and resources)
✅ client_window/           (Client UI package)
✅ routerLocImg/            (Router image storage)
```

Run the verification:
```powershell
python build.py
```

The script will check for all required files before building.

### Step 3: Build the Executable

#### Option A: Build with Automatic Setup

```powershell
python build.py
```

This will:
1. ✅ Verify all required files exist
2. ✅ Clean previous build artifacts
3. ✅ Check for icon.ico
4. ✅ Verify Python dependencies
5. ✅ Check PyInstaller installation
6. ✅ Build the EXE using PyInstaller
7. ✅ Copy all resources to dist/ folder
8. ✅ (Optional) Create installer with Inno Setup

#### Option B: Manual PyInstaller Build

```powershell
pyinstaller winyfi.spec --clean --noconfirm
```

### Step 4: Verify Build Output

After successful build, check:

```
dist/
├── Winyfi.exe              ← Main executable
├── db_config.json          ← Database config
├── winyfi.sql              ← Database schema
├── README_SETUP.txt        ← Setup guide
├── assets/                 ← App resources
├── routerLocImg/           ← Router images
└── migrations/             ← Database migrations
```

## Running Winyfi

### Before First Launch

1. **Start XAMPP MySQL**
   - Open XAMPP Control Panel
   - Click "Start" next to MySQL
   - Wait for "Running" status (port 3306)

2. **Create Database**
   - Open http://localhost/phpmyadmin in browser
   - Click "New" database
   - Name: `winyfi`
   - Collation: `utf8mb4_unicode_ci`
   - Click "Create"

3. **Import Database Schema**
   - In phpMyAdmin, select `winyfi` database
   - Click "Import" tab
   - Choose: `dist/winyfi.sql` or `winyfi.sql`
   - Click "Import"

### Launch Application

**From Development Environment:**
```powershell
# Activate virtual environment first
.\.venv\Scripts\Activate.ps1

python main.py
```

**From Built EXE:**
```powershell
# Navigate to dist folder
cd dist

# Run executable
.\Winyfi.exe
```

**First Time Login:**
- Username: `admin`
- Password: `admin` (or as configured in database)

## Creating an Installer

### Requirements
- Inno Setup 6 installed
- `installer.iss` file present
- `dist/Winyfi.exe` built successfully

### Build Installer

```powershell
python build.py
```

Or manually:
```powershell
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

**Output:**
```
installer_output/
└── Winyfi_Setup_v1.0.0.exe
```

### Distribute Installer

The installer file can be distributed to end users. It will:
- Install Winyfi to `C:\Program Files\Winyfi\`
- Create Start Menu shortcuts
- Show setup instructions after installation
- Require admin privileges

## Troubleshooting

### Build Issues

**"PyInstaller not found"**
```powershell
pip install pyinstaller
```

**"Missing dependencies"**
```powershell
pip install -r requirements.txt --upgrade
```

**"icon.ico not found"**
```powershell
python create_icon.py
```

**Import errors after build**
- Ensure `resource_utils.py` exists in project root
- Verify all files in `winyfi.spec` datas section
- Check that assets/ directory contains files

### Runtime Issues

**"Database connection failed"**
1. Ensure MySQL is running in XAMPP
2. Check db_config.json settings
3. Verify winyfi database exists
4. Check MySQL port (default 3306)

**"Logo not loading"**
- Verify `assets/images/logo1.png` exists in dist folder
- Ensure proper file permissions

**"Port already in use"**
- Default: localhost:5000
- Check if another instance is running
- Or modify port in db_config.json

### Distribution Issues

**"Cannot run EXE on another computer"**
- Ensure all resource files are in same directory as EXE
- Use the installer instead for easier distribution
- Check Windows Defender hasn't blocked it

**"Installer file too large"**
- Normal: 150-250 MB for bundled Python + dependencies
- Use dist/Winyfi.exe directly if size is critical

## Configuration

### Database Configuration

Edit `db_config.json`:

```json
{
    "host": "localhost",
    "user": "root",
    "password": "your_password",
    "database": "winyfi",
    "connection_timeout": 10,
    "autocommit": true
}
```

### Environment Variables

Override configuration with environment variables:

```powershell
# Set database host
$env:WINYFI_DB_HOST = "192.168.1.100"

# Set database password
$env:WINYFI_DB_PASSWORD = "your_password"

# Set UniFi API URL
$env:WINYFI_UNIFI_API_URL = "http://192.168.1.27:5001"

# Then run Winyfi
.\dist\Winyfi.exe
```

## Advanced Build Options

### Custom Icon

```powershell
# Create icon from PNG
python create_icon.py

# Or provide your own icon.ico (256x256 or larger)
```

### Modify Build Configuration

Edit `winyfi.spec` to customize:
- Add/remove hidden imports
- Change datas included
- Modify resource paths
- Adjust PyInstaller options

Then rebuild:
```powershell
pyinstaller winyfi.spec --clean --noconfirm
```

### Release Build

For production release:

1. Update version in `installer.iss`:
   ```
   AppVersion=1.0.1
   OutputBaseFilename=Winyfi_Setup_v1.0.1
   ```

2. Clean and rebuild:
   ```powershell
   python build.py
   ```

3. Output files:
   - `dist/Winyfi.exe` - Standalone executable
   - `installer_output/Winyfi_Setup_v1.0.1.exe` - Installer

## Project Structure

```
Winyfi/
├── main.py                 # Application entry point
├── build.py               # Build script (THIS IS KEY)
├── winyfi.spec            # PyInstaller spec file
├── installer.iss          # Inno Setup script
├── resource_utils.py      # Resource path utility (NEW)
│
├── dashboard.py           # Main dashboard UI
├── login.py              # Login screen
├── db.py                 # Database operations
│
├── client_window/         # Client window package
│   ├── __init__.py
│   ├── client_app.py
│   └── tabs/
│       ├── __init__.py
│       ├── dashboard_tab.py
│       └── ...
│
├── assets/               # App images and resources
│   └── images/
│       └── logo1.png
│
├── routerLocImg/         # Router image storage (created at runtime)
├── migrations/           # Database migrations
│
├── requirements.txt      # Python dependencies
├── db_config.json       # Database configuration
├── winyfi.sql           # Database schema
├── icon.ico             # Application icon
│
└── server/              # Backend API (optional)
    ├── app.py
    └── unifi_api.py
```

## Key Files for Building

### winyfi.spec
PyInstaller configuration that:
- Specifies entry point: `main.py`
- Lists all data files to include (assets, config, etc.)
- Defines hidden imports for all dependencies
- Configures output EXE name and icon

### build.py (UPDATED)
Build script that:
- Verifies all required files exist
- Checks Python dependencies
- Cleans old builds
- Runs PyInstaller with winyfi.spec
- Copies resource files to dist/
- Creates installer with Inno Setup

### resource_utils.py (NEW)
Utility module that:
- Handles path resolution for frozen vs. development
- Provides `get_resource_path()` for accessing bundled files
- Works with PyInstaller's `sys._MEIPASS`

## Support

For issues, check:
1. **GitHub Issues**: https://github.com/man-gg/Winyfi/issues
2. **Build Output**: Check terminal output for errors
3. **Logs**: Check `winyfi_error.log` in app directory

---

**Last Updated**: December 2024
**Version**: 1.0.0
