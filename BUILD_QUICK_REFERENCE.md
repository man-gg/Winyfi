# Winyfi Installer - Quick Build Reference

## One-Command Build (Recommended)

```powershell
# Navigate to project directory
cd C:\Path\To\Winyfi

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Build everything (automatic)
python build.py
```

**Output:**
- `dist/Winyfi.exe` - Standalone executable
- `installer_output/Winyfi_Setup_v1.0.0.exe` - Windows installer (if Inno Setup installed)

---

## What Was Fixed

### 1. **Path Resolution** ✅
- Created `resource_utils.py` to handle paths in both dev and frozen environments
- All hardcoded paths now use `get_resource_path()`

### 2. **Resource Bundling** ✅
- `winyfi.spec` - Updated data files and imports
- All assets, config files, and databases included

### 3. **Build Automation** ✅
- `build.py` - Completely rewritten with comprehensive checks
- Auto-installs missing dependencies
- Verifies all required files
- Copies resources to dist/

### 4. **File Loading** ✅
- **dashboard.py** - Logo and router images
- **main.py** - Application icon
- **db.py** - Database configuration

### 5. **Installation** ✅
- **installer.iss** - Updated paths and instructions
- Clear post-installation setup guide

### 6. **Documentation** ✅
- **INSTALLATION_GUIDE.md** - Complete setup instructions
- **INSTALLER_FIXES_SUMMARY.md** - Technical details

---

## Build Steps (What Happens Automatically)

1. ✅ **Verify Files** - Checks for required files and directories
2. ✅ **Clean Build** - Removes old build artifacts
3. ✅ **Check Icon** - Verifies icon.ico exists
4. ✅ **Verify Dependencies** - Checks and installs Python packages
5. ✅ **Check PyInstaller** - Ensures PyInstaller is installed
6. ✅ **Build EXE** - Runs PyInstaller with winyfi.spec
7. ✅ **Copy Resources** - Bundles all required files to dist/
8. ✅ **Create Installer** - Optional installer creation

---

## First-Time Setup

```powershell
# 1. Create virtual environment (if not exists)
python -m venv .venv

# 2. Activate it
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Build
python build.py
```

---

## Troubleshooting

| Error | Solution |
|-------|----------|
| "PyInstaller not found" | Script auto-installs it |
| "Missing dependencies" | Script auto-installs them |
| "icon.ico not found" | Run: `python create_icon.py` |
| "Build fails" | Check terminal output for details |
| "EXE doesn't run" | Verify all files in dist/ folder |

---

## Files Modified

```
✅ resource_utils.py          (NEW - Path resolution)
✅ dashboard.py               (Path fixes)
✅ main.py                    (Icon path fix)
✅ db.py                      (Config path fix)
✅ winyfi.spec                (Data files & imports)
✅ build.py                   (Complete rewrite)
✅ installer.iss              (Path fixes)
✅ INSTALLATION_GUIDE.md      (NEW - Full guide)
✅ INSTALLER_FIXES_SUMMARY.md (NEW - Technical details)
```

---

## Key Improvements

### Before
- ❌ Hardcoded relative paths fail in frozen .exe
- ❌ Manual dependency checking required
- ❌ Resources not bundled properly
- ❌ Missing error handling
- ❌ No setup documentation

### After
- ✅ Intelligent path resolution works everywhere
- ✅ Automatic dependency verification
- ✅ Complete resource bundling
- ✅ Comprehensive error messages
- ✅ Full documentation included

---

## Testing the Build

After successful build:

```powershell
# Test the EXE
cd dist
.\Winyfi.exe

# Should see:
# - Winyfi logo ✅
# - Login screen ✅
# - No errors ✅
```

---

## Distribution

### Standalone EXE
- **File**: `dist/Winyfi.exe`
- **Size**: ~150-250 MB
- **Pros**: Single file, no installation needed
- **Cons**: Larger file size

### Installer
- **File**: `installer_output/Winyfi_Setup_v1.0.0.exe`
- **Size**: ~100-150 MB
- **Pros**: Smaller, proper installation, uninstall support
- **Cons**: Requires Inno Setup 6 to create
- **Requires**: User has admin privileges

---

## Environment Setup (One Time)

```powershell
# Install Python 3.8+ from https://www.python.org/
# Add to PATH during installation

# Install XAMPP from https://www.apachefriends.org/
# For MySQL database support

# Optional: Install Inno Setup 6 from https://jrsoftware.org/isdl.php
# For creating installer (.exe)
```

---

## Build Commands Reference

```powershell
# Full build (recommended)
python build.py

# Manual PyInstaller build (advanced)
pyinstaller winyfi.spec --clean --noconfirm

# Create installer only (requires Inno Setup)
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss

# Clean and rebuild
rmdir build dist -r
python build.py

# Check build output
Get-ChildItem dist/
Get-ChildItem installer_output/
```

---

## Configuration Files

### db_config.json
Located in: `dist/db_config.json` after build

```json
{
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "winyfi"
}
```

### Override with Environment Variables
```powershell
$env:WINYFI_DB_HOST = "192.168.1.100"
$env:WINYFI_DB_PASSWORD = "secret"
$env:WINYFI_UNIFI_API_URL = "http://192.168.1.27:5001"
```

---

## Success Checklist

- [ ] EXE builds without errors
- [ ] `dist/Winyfi.exe` exists
- [ ] `dist/assets/` contains files
- [ ] `dist/db_config.json` exists
- [ ] EXE launches and shows logo
- [ ] No error messages in console
- [ ] Installer created (if Inno Setup installed)
- [ ] All resource files copied

---

## Next Steps

1. **Run Build**
   ```powershell
   python build.py
   ```

2. **Test EXE**
   ```powershell
   dist/Winyfi.exe
   ```

3. **Setup Database**
   - Start XAMPP MySQL
   - Import winyfi.sql
   - Run Winyfi

4. **Distribute**
   - Send `dist/Winyfi.exe` or
   - Send `installer_output/Winyfi_Setup_v1.0.0.exe`

---

**Version**: 1.0.0  
**Updated**: December 2024  
**Status**: Ready for Production ✅
- [ ] Verify database connection
- [ ] Test all features

## Distribution

### Option 1: Distribute EXE Only
Share: `dist/Winyfi.exe`

**Requirements for users:**
- Windows 10/11
- MySQL database (must be configured separately)

### Option 2: Create Installer (Recommended)

1. **Install Inno Setup:**
   - Download: https://jrsoftware.org/isinfo.php
   - Install to default location

2. **Build installer:**
   ```powershell
   python build.py
   ```
   
3. **Share:**
   `installer_output/Winyfi_Setup_v1.0.0.exe`

## Important Files

| File | Purpose |
|------|---------|
| `winyfi.spec` | PyInstaller configuration with all modules |
| `build.py` | Automated build script |
| `test_build.py` | Test imports before building |
| `hook-client_window.py` | PyInstaller hook for client_window |
| `icon.ico` | Application icon |
| `installer.iss` | Inno Setup configuration |

## Troubleshooting

### EXE won't start
- Build with console enabled: Edit `winyfi.spec`, set `console=True`
- Check `winyfi_error.log` in the same directory as EXE

### Missing module errors
- Run `python test_build.py` to identify issues
- Add missing modules to `hiddenimports` in `winyfi.spec`
- Rebuild

### Large file size (51 MB)
This is normal - includes Python runtime and all dependencies.
To reduce:
- Use `--onedir` instead of `--onefile` (creates folder instead)
- Remove unused dependencies from requirements.txt

### Antivirus warnings
- Common with PyInstaller EXEs
- Sign with code signing certificate (for production)
- Add exception in antivirus

## Next Steps

1. **Test thoroughly** on your machine
2. **Test on clean Windows PC** (without Python)
3. **Configure database** for target environment
4. **Optional: Get code signing certificate** to avoid warnings
5. **Distribute!**

## Build Statistics

- Build time: ~30 seconds
- EXE size: 51.30 MB
- Dependencies included: Python 3.13 + all packages
- Startup time: 5-10 seconds (first launch)

## Support

For issues:
1. Check `winyfi_error.log`
2. Run `python test_build.py`
3. Review build output from `python build.py`
4. Check GitHub issues: https://github.com/man-gg/Winyfi
