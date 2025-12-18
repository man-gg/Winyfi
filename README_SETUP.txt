# Winyfi Network Monitor - Setup Instructions

## Database Setup (REQUIRED)

Winyfi requires MySQL/MariaDB to run. Follow these steps:

### 1. Install XAMPP
1. Download XAMPP from: https://www.apachefriends.org/
2. Install XAMPP (default location: `C:\xampp`)
3. Open XAMPP Control Panel
4. **Start Apache** (for web interface)
5. **Start MySQL** (required for Winyfi)

### 2. Create Database
1. Open your browser and go to: http://localhost/phpmyadmin
2. Click "New" in the left sidebar
3. Database name: `winyfi`
4. Collation: `utf8mb4_general_ci`
5. Click "Create"

### 3. Import Database Schema
1. Select the `winyfi` database
2. Click "Import" tab
3. Click "Choose File"
4. Select `winyfi.sql` (in the same folder as Winyfi.exe)
5. Click "Go" at the bottom

### 4. Configure Database Connection (Optional)

If you changed MySQL settings, edit `db_config.json`:

```json
{
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "winyfi",
    "connection_timeout": 10
}
```

**Common configurations:**

- **Default XAMPP:** (already configured)
  - Host: `localhost`
  - User: `root`
  - Password: `` (empty)

- **Custom MySQL:**
  - Update the values in `db_config.json`

### 5. Launch Winyfi

Double-click `Winyfi.exe`

**Default Login:**
- Username: `admin`
- Password: `admin123`

## Troubleshooting

### "Can't Reach Database" Error

**Check if MySQL is running:**
1. Open XAMPP Control Panel
2. Ensure "MySQL" shows green "Running" status
3. If stopped, click "Start"

**Check database exists:**
1. Go to http://localhost/phpmyadmin
2. Look for `winyfi` in the left sidebar
3. If missing, follow step 2-3 above

**Check configuration:**
1. Open `db_config.json` in Notepad
2. Verify settings match your MySQL setup
3. Save and restart Winyfi

### Banner/Images Not Showing

- Make sure the `assets` folder is in the same directory as `Winyfi.exe`
- Folder structure should be:
  ```
  Winyfi.exe
  db_config.json
  winyfi.sql
  assets/
    images/
      Banner.png
      logo1.png
      bsu_logo.png
  routerLocImg/
  ```

### Server Offline (Client Login)

The "Server" refers to the optional Flask API server (`start_unifi_server.py`).
- **Admin users** can login offline (only need MySQL)
- **Client users** require the server to be running

To start the server:
```
python start_unifi_server.py
```

## System Requirements

- Windows 10/11 (64-bit)
- 4 GB RAM minimum
- MySQL/MariaDB (via XAMPP or standalone)
- Internet connection (for some features)

## First Time Setup

1. ✅ Install XAMPP
2. ✅ Start MySQL in XAMPP
3. ✅ Create `winyfi` database
4. ✅ Import `winyfi.sql`
5. ✅ Run `Winyfi.exe`
6. ✅ Login with admin/admin123
7. ✅ Change default password

## Support

For issues or questions:
- GitHub: https://github.com/man-gg/Winyfi
- Check `winyfi_error.log` for detailed error messages

## Features

- Network router monitoring
- Bandwidth tracking
- Loop detection
- Service request forms (SRF)
- Activity logging
- User management
- Reports generation

---

**Important:** Keep XAMPP MySQL running while using Winyfi!
