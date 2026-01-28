"""
MySQL Health Check Module
Verifies MySQL/XAMPP connectivity before app startup
"""
import logging
import os
import socket
import subprocess
from datetime import datetime
from db import get_connection, DatabaseConnectionError

logger = logging.getLogger(__name__)


class HealthCheckResult:
    """Container for health check results"""
    def __init__(self):
        self.mysql_running = False
        self.mysql_connectable = False
        self.credentials_valid = False
        self.database_exists = False
        self.all_passed = False
        self.error_message = ""
        self.warnings = []


def check_mysql_port(host="127.0.0.1", port=3306, timeout=2):
    """Check if MySQL port is listening"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception as e:
        logger.warning(f"Port check failed: {e}")
        return False


def run_health_check():
    """
    Run comprehensive MySQL health check
    Returns: HealthCheckResult object
    """
    result = HealthCheckResult()
    health_log_path = os.path.join(os.path.dirname(__file__), "mysql_health_check.log")
    
    def log_check(message):
        """Log to both logger and health check log"""
        logger.info(message)
        try:
            with open(health_log_path, 'a', encoding='utf-8') as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
        except Exception:
            pass
    
    # Clear previous log
    try:
        if os.path.exists(health_log_path):
            os.remove(health_log_path)
    except Exception:
        pass
    
    log_check("=" * 60)
    log_check("WINYFI MySQL Health Check Started")
    log_check("=" * 60)
    
    # Check 1: MySQL Port Listening
    log_check("\n[CHECK 1] Verifying MySQL port 3306 is listening...")
    if check_mysql_port():
        log_check("✅ MySQL is listening on port 3306")
        result.mysql_running = True
    else:
        log_check("❌ MySQL is NOT listening on port 3306")
        log_check("   XAMPP MySQL service may not be running")
        log_check("   Solution: Start MySQL in XAMPP Control Panel")
        result.error_message = "MySQL is not running. Please start XAMPP MySQL service."
        return result
    
    # Check 2: Database Credentials
    log_check("\n[CHECK 2] Testing MySQL credentials...")
    try:
        conn = get_connection(max_retries=1, retry_delay=0, show_dialog=False)
        log_check("✅ MySQL credentials are valid")
        result.mysql_connectable = True
        result.credentials_valid = True
        
        # Check 3: Database Exists
        log_check("\n[CHECK 3] Checking if 'winyfi' database exists...")
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT DATABASE()")
            db_name = cursor.fetchone()[0]
            if db_name == "winyfi":
                log_check("✅ 'winyfi' database is accessible")
                result.database_exists = True
                log_check("\n" + "=" * 60)
                log_check("✅ ALL CHECKS PASSED - App is ready to run")
                log_check("=" * 60)
                result.all_passed = True
            else:
                log_check(f"⚠️  Connected to '{db_name}' instead of 'winyfi'")
                result.warnings.append("Wrong database selected")
            cursor.close()
        except Exception as e:
            log_check(f"⚠️  Could not verify database: {e}")
            result.warnings.append(f"Database check failed: {str(e)}")
        finally:
            try:
                conn.close()
            except Exception:
                pass
                
    except DatabaseConnectionError as e:
        log_check(f"❌ MySQL connection failed: {str(e)}")
        log_check("   Possible causes:")
        log_check("   1. MySQL user 'winyfi' does not exist")
        log_check("   2. Password in db_config.json is incorrect")
        log_check("   3. User lacks connection privileges")
        result.mysql_connectable = False
        result.error_message = f"MySQL connection failed.\n\nCheck db_config.json credentials:\n{str(e)[:100]}"
        return result
    except Exception as e:
        log_check(f"❌ Unexpected error: {str(e)}")
        result.error_message = f"Unexpected error during health check: {str(e)}"
        return result
    
    return result


def show_health_check_result(root_window, result):
    """
    Display health check results to user
    Returns: True if all checks passed, False otherwise
    """
    if result.all_passed:
        return True
    
    # Build error message
    error_title = "MySQL Configuration Issue"
    
    if not result.mysql_running:
        error_message = (
            "MySQL is not running!\n\n"
            "To fix this:\n"
            "1. Open XAMPP Control Panel\n"
            "2. Click 'Start' next to MySQL\n"
            "3. Wait for it to show 'Running'\n"
            "4. Restart Winyfi"
        )
    elif not result.credentials_valid:
        error_message = (
            "MySQL connection failed!\n\n"
            f"Error: {result.error_message}\n\n"
            "To fix this:\n"
            "1. Open db_config.json in the Winyfi folder\n"
            "2. Verify username and password are correct\n"
            "3. Check that user 'winyfi' exists in MySQL\n"
            "4. Use phpMyAdmin to verify: http://localhost/phpmyadmin"
        )
    elif not result.database_exists:
        error_message = (
            "MySQL database 'winyfi' not found!\n\n"
            "To fix this:\n"
            "1. Open phpMyAdmin: http://localhost/phpmyadmin\n"
            "2. Create a new database named 'winyfi'\n"
            "3. Import winyfi.sql from the Winyfi folder\n"
            "4. Restart Winyfi"
        )
    else:
        error_message = result.error_message or "Unknown health check error"
    
    # Show error dialog
    try:
        import tkinter as tk
        from tkinter import messagebox
        
        if root_window is None:
            root_window = tk.Tk()
            root_window.withdraw()
        
        messagebox.showerror(error_title, error_message, parent=root_window)
        return False
    except Exception as e:
        logger.error(f"Could not show error dialog: {e}")
        print(f"\n⚠️  {error_title}")
        print(f"{error_message}\n")
        return False
