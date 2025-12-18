# Building Winyfi EXE Installer

This guide will help you create an EXE installer for the Winyfi Network Monitor application.

## Prerequisites

1. **Python** (already installed, you're using it)
2. **PyInstaller** (will be auto-installed by build script)
3. **Inno Setup** (optional, for creating installer)
   - Download from: https://jrsoftware.org/isinfo.php

## Quick Start

### Step 1: Create Your Icon

Choose your preferred logo and run:

```powershell
python create_icon.py
```

This will create `icon.ico` from `assets/images/logo1.png`.

**To use a different image**, edit `create_icon.py` and change the `source_png` variable.

### Step 2: Build Everything

Run the automated build script:

```powershell
python build.py
```

This will:
1. ✅ Clean old builds
2. ✅ Check for icon file
3. ✅ Install PyInstaller if needed
4. ✅ Build the EXE
5. ✅ Create installer (if Inno Setup is installed)

### Step 3: Test Your EXE

The EXE will be created in the `dist/` folder:

```powershell
.\dist\Winyfi.exe
```

### Step 4: Distribute

**Option A - Just the EXE:**
- Share `dist/Winyfi.exe` (users need MySQL installed)

**Option B - Full Installer:**
- Share `installer_output/Winyfi_Setup_v1.0.0.exe`
- This provides a professional installation experience

## Manual Build Commands

If you prefer manual control:

### Create Icon:
```powershell
python create_icon.py
```

### Build EXE:
```powershell
pyinstaller winyfi.spec --clean
```

### Create Installer (requires Inno Setup):
```powershell
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

## File Structure

```
Winyfi/
├── main.py                     # Entry point
├── icon.ico                    # App icon (create with create_icon.py)
├── create_icon.py             # Icon creation script
├── winyfi.spec                # PyInstaller configuration
├── installer.iss              # Inno Setup configuration
├── build.py                   # Automated build script
├── dist/                      # EXE output folder
│   └── Winyfi.exe            # Your executable
└── installer_output/          # Installer output folder
    └── Winyfi_Setup_v1.0.0.exe
```

## Customization

### Change App Icon
1. Edit `create_icon.py` to use your preferred PNG
2. Run `python create_icon.py`
3. Rebuild with `python build.py`

### Change App Name/Version
Edit `installer.iss`:
```iss
AppName=Your App Name
AppVersion=2.0.0
```

### Include Additional Files
Edit `winyfi.spec` in the `datas` section:
```python
datas=[
    ('your_folder', 'your_folder'),
    ('config.json', '.'),
],
```

## Troubleshooting

### "Icon not found" error
Run: `python create_icon.py` first

### "PyInstaller not found" error
Install: `pip install pyinstaller`

### Large EXE size
This is normal. The EXE includes Python and all dependencies (~50-100 MB).

### Missing DLL errors
Add missing imports to `hiddenimports` in `winyfi.spec`

### Application won't start
Build with console enabled for debugging:
```python
# In winyfi.spec, change:
console=True,  # Shows debug output
```

## Database Setup for Users

Your users will need MySQL installed and configured. Include these instructions:

1. Install MySQL Server
2. Create database: `winyfi`
3. Run migrations from the SQL files included with the app
4. Configure connection in the app settings

## Testing Checklist

Before distributing, test on a clean Windows machine:

- [ ] EXE runs without Python installed
- [ ] Icon displays correctly
- [ ] All images/resources load
- [ ] Database connection works
- [ ] All features function properly
- [ ] No antivirus false positives

## Distribution Notes

- **File Size**: Expect 50-100 MB for the EXE
- **Startup Time**: First launch may take 5-10 seconds
- **Windows Defender**: May need to create exception or sign the EXE
- **Code Signing**: For production, get a code signing certificate to avoid warnings

## Support

For issues, check:
1. `winyfi_error.log` in the app directory
2. Build output from `build.py`
3. GitHub Issues: https://github.com/man-gg/Winyfi/issues
