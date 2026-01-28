# Next Steps for Service Manager Integration

## 1. Update the Installer (installer.iss)

Add the following to `[Files]` section:
```ini
; Service Manager launchers
Source: "launch_service_manager.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "launch_service_manager.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "SERVICE_MANAGER_README.md"; DestDir: "{app}"; Flags: ignoreversion
```

Add to `[Icons]` section to create a desktop shortcut for Service Manager:
```ini
Name: "{userdesktop}\Winyfi Service Manager"; Filename: "{app}\Winyfi.exe"; Parameters: "--service-manager-only"; WorkingDir: "{app}"; IconFilename: "{app}\icon.ico"
Name: "{userstartmenu}\Winyfi Service Manager"; Filename: "{app}\Winyfi.exe"; Parameters: "--service-manager-only"; WorkingDir: "{app}"; IconFilename: "{app}\icon.ico"
```

## 2. Update the Spec File (winyfi.spec)

Ensure launcher scripts are included in PyInstaller build:
```python
datas=[
    ('server', 'server'),
    ('launch_service_manager.bat', '.'),
    ('launch_service_manager.py', '.'),
    ('SERVICE_MANAGER_README.md', '.'),
]
```

## 3. Build Commands

```bash
# Rebuild the spec file with new data
pyinstaller winyfi.spec --clean

# Create installer
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

## 4. Documentation Updates

- Add "Service Manager Only Mode" section to README.md
- Update INSTALLATION_GUIDE.md to mention service manager shortcut
- Add keyboard shortcut info if needed

## 5. Testing Checklist

- [ ] Normal mode works (login → dashboard)
- [ ] Service manager mode works (no login, direct to service manager)
- [ ] Both modes show services as running/stopped correctly
- [ ] Services can be started/stopped in service manager mode
- [ ] Service logs display correctly
- [ ] Installer creates both shortcuts (dashboard + service manager)
- [ ] Batch and Python launchers work correctly

## Current Status

✅ **COMPLETED:**
- Modified main.py to support --service-manager-only flag
- Created launch_service_manager.bat launcher
- Created launch_service_manager.py launcher
- Created SERVICE_MANAGER_README.md documentation
- Tested basic functionality (script loads without errors)

⏳ **REMAINING:**
- Update installer.iss with new files and shortcuts
- Rebuild PyInstaller spec with launcher files
- Create final installer package
- Full end-to-end testing
- Update main README.md

## Quick Start for User

For immediate testing:
```bash
cd "C:\Users\Consigna\Desktop\Winyfi\Winyfi"
python main.py --service-manager-only
```

This should open the Service Manager window without any login prompt.
