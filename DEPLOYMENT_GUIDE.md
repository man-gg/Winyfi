# Winyfi Deployment Guide

## ✅ Issues Fixed

1. **Database Connection Error** - Fixed by adding `db_config.json`
2. **Missing Banner Images** - Fixed resource paths for PyInstaller
3. **Module Import Errors** - All client_window modules properly bundled

## Quick Deploy

### Build the EXE:
```powershell
python build.py
```

This automatically:
- Builds `Winyfi.exe`
- Copies `db_config.json`, `README_SETUP.txt`, `winyfi.sql` to dist/
- Creates a ready-to-distribute package

### Files in dist/ folder:
```
dist/
├── Winyfi.exe              # Main application
├── db_config.json          # Database configuration
├── README_SETUP.txt        # Setup instructions
└── winyfi.sql              # Database schema
```

## Distribution Options

### Option 1: Portable Package (Recommended)
Create a ZIP file with everything needed:

```powershell
# Create distribution folder
New-Item -ItemType Directory -Path "Winyfi_Portable" -Force
Copy-Item -Path "dist\*" -Destination "Winyfi_Portable\" -Recurse
Copy-Item -Path "assets" -Destination "Winyfi_Portable\assets" -Recurse
Copy-Item -Path "routerLocImg" -Destination "Winyfi_Portable\routerLocImg" -Recurse

# Create ZIP
Compress-Archive -Path "Winyfi_Portable\*" -DestinationPath "Winyfi_Portable.zip"
```

### Option 2: Installer (Professional)
1. Download Inno Setup: https://jrsoftware.org/isinfo.php
2. Install it
3. Run: `python build.py` (will create installer automatically)

## User Setup Instructions

Share these steps with your users:

### 1. Install XAMPP
- Download: https://www.apachefriends.org/
- Install with default settings
- Start **MySQL** in XAMPP Control Panel

### 2. Setup Database
1. Open browser: http://localhost/phpmyadmin
2. Create database: `winyfi`
3. Import `winyfi.sql` (included with Winyfi)

### 3. Run Winyfi
- Double-click `Winyfi.exe`
- Login: `admin` / `admin123`

### 4. Customize (Optional)
Edit `db_config.json` if MySQL settings differ:
```json
{
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "winyfi"
}
```

## Troubleshooting

### "Can't Reach Database" Error
✅ **Solution:**
1. Check XAMPP Control Panel - MySQL must be green/running
2. Verify database exists in phpMyAdmin
3. Check `db_config.json` settings

### Banner/Images Not Showing
✅ **Solution:**
- Assets are now bundled in the EXE
- If issue persists, ensure `assets` folder is in same directory as EXE

### Module Import Errors
✅ **Fixed:** All modules now properly included via `winyfi.spec`

## Testing Checklist

Before distributing:

- [ ] MySQL running in XAMPP
- [ ] Database `winyfi` created and imported
- [ ] Run `Winyfi.exe` from dist folder
- [ ] Login works (admin/admin123)
- [ ] Banner image displays
- [ ] All tabs load without errors
- [ ] Client login works (if server running)
- [ ] Test on clean PC without Python

## Files Structure

### For Development:
```
Winyfi/
├── main.py
├── login.py
├── dashboard.py
├── db.py (updated with config loading)
├── db_config.json (database settings)
├── winyfi.spec (PyInstaller config)
├── build.py (build automation)
├── icon.ico (app icon)
├── assets/
│   └── images/
│       ├── Banner.png
│       ├── logo1.png
│       └── bsu_logo.png
└── client_window/
    └── tabs/
```

### For Distribution:
```
dist/
├── Winyfi.exe
├── db_config.json
├── README_SETUP.txt
├── winyfi.sql
├── assets/           (if using portable package)
└── routerLocImg/     (if using portable package)
```

## Customization

### Change Database Settings
Edit `db_config.json` before building:
```json
{
    "host": "your-server",
    "user": "your-user",
    "password": "your-password",
    "database": "winyfi"
}
```

### Change App Icon
1. Replace `icon.ico` or run `python create_icon.py` with your logo
2. Rebuild: `python build.py`

### Change App Version
Edit `installer.iss`:
```iss
AppVersion=2.0.0
```

## Automated Build Script

The `build.py` script handles everything:

```powershell
python build.py
```

Does:
1. ✅ Cleans old builds
2. ✅ Checks icon exists
3. ✅ Verifies PyInstaller installed
4. ✅ Builds EXE
5. ✅ Copies config files to dist/
6. ✅ Creates installer (if Inno Setup available)

## Support

- Check `winyfi_error.log` for detailed errors
- GitHub: https://github.com/man-gg/Winyfi
- Database issues: Verify XAMPP MySQL is running

## Security Notes

- Change default password (`admin`/`admin123`) after first login
- Keep `db_config.json` secure (contains database credentials)
- For production: Use strong MySQL password
- Consider code signing certificate to avoid antivirus warnings

---

**Status:** ✅ Ready for deployment with all fixes applied!
