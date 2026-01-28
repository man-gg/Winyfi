# Build Instructions - PyInstaller & Installer

## Prerequisites

Ensure the following are installed and available:
- **Python 3.13** - Main development environment
- **PyInstaller 6.17.0** - For creating the .exe
- **Inno Setup 6** - For creating the installer (.exe setup)

## Step 1: Clean Previous Build

```powershell
# Remove old build artifacts
Remove-Item -Path "dist" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "build" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "*.spec.spec" -ErrorAction SilentlyContinue
```

## Step 2: Build PyInstaller Distribution

```powershell
# Navigate to the workspace
cd "C:\Users\Consigna\Desktop\Winyfi\Winyfi"

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Clean rebuild with the updated spec file
pyinstaller winyfi.spec --clean

# Verify dist folder was created
Get-ChildItem dist | Select-Object Name
```

### Expected Output
```
dist/Winyfi.exe (61+ MB)
dist/assets/ (directory)
dist/routerLocImg/ (directory)
dist/server/ (directory - with run_app.py, run_unifi_api.py, app.py)
dist/launch_service_manager.bat
dist/launch_service_manager.py
dist/db_config.json
dist/winyfi.sql
dist/README.md
dist/SERVICE_MANAGER_README.md
dist/icon.ico
... and other files
```

## Step 3: Create Installer

```powershell
# Build the Inno Setup installer
# Option 1: From command line
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss

# Option 2: Open in Inno Setup IDE
# C:\Program Files (x86)\Inno Setup 6\compil32.exe installer.iss
```

### Expected Output
```
installer_output/Winyfi_Setup_v1.0.0.exe
```

## Step 4: Test Packaged Distribution

Before releasing, test both the .exe and installer:

### Test 1: Direct .exe Execution
```powershell
cd "C:\Users\Consigna\Desktop\Winyfi\Winyfi\dist"

# Test normal mode (should show login)
.\Winyfi.exe

# In another terminal, test service manager mode
.\Winyfi.exe --service-manager-only
```

### Test 2: Installer Test
```powershell
# Run the installer in a test directory
"C:\Users\Consigna\Desktop\Winyfi\Winyfi\installer_output\Winyfi_Setup_v1.0.0.exe"

# After installation, test:
# - Desktop shortcuts work
# - Both Dashboard and Service Manager modes launch
# - Services (Flask, UniFi) start correctly
```

## Step 5: Verification Checklist

After build, verify:

### ✅ dist/Winyfi.exe
- [ ] File exists and is 60+ MB
- [ ] Runs without errors (normal mode)
- [ ] Shows login window
- [ ] `Winyfi.exe --service-manager-only` works
- [ ] Service Manager opens without login
- [ ] Flask API starts (port 5000)
- [ ] UniFi API starts (port 5001)

### ✅ Bundled Files in dist/
- [ ] launch_service_manager.bat exists
- [ ] launch_service_manager.py exists
- [ ] SERVICE_MANAGER_README.md exists
- [ ] server/ folder has run_app.py and run_unifi_api.py
- [ ] db_config.json exists

### ✅ installer_output/Winyfi_Setup_v1.0.0.exe
- [ ] Installer runs without errors
- [ ] Creates Start Menu shortcuts
- [ ] Creates Desktop shortcuts (Dashboard + Service Manager)
- [ ] Installed files are in `C:\Program Files\Winyfi\`
- [ ] Both launch modes work from installed location

## Build Timeline

Typical build times:
- **Clean build**: 3-5 minutes (PyInstaller)
- **Installer creation**: 1-2 minutes (Inno Setup)
- **Testing**: 5-10 minutes

**Total time**: ~15 minutes for clean build with testing

## Troubleshooting

### Issue: PyInstaller fails with "module not found"
```powershell
# Solution: Clear cache and rebuild
Remove-Item -Path "build" -Recurse -Force
pyinstaller winyfi.spec --clean
```

### Issue: Installer won't compile
```powershell
# Solution: Check paths in installer.iss
# Verify all source files exist in dist/ folder
Get-ChildItem dist | Measure-Object | Select-Object Count
```

### Issue: .exe won't start
```powershell
# Check error logs
Get-Content "dist\winyfi_error.log" -Tail 20
Get-Content "dist\winyfi_runtime_error.log" -Tail 20
```

### Issue: Service Manager doesn't launch from installer
```powershell
# Verify shortcuts in installer.iss have correct Parameters
# Should include: Parameters: "--service-manager-only"
```

## Deployment

After successful build and testing:

1. **Copy dist/ folder** to release directory
2. **Copy installer_output/Winyfi_Setup_v1.0.0.exe** to release
3. **Version bump** if needed (update AppVersion in installer.iss)
4. **Release notes** document what changed

## Next Build

For the next build:
1. Update version in `installer.iss` (AppVersion line)
2. Update `winyfi.spec` if dependencies change
3. Follow steps 1-5 above

---

**Last Updated**: 2026-01-17
**Build System**: PyInstaller 6.17.0 + Inno Setup 6
**Target**: Windows 10/11 (x64)
