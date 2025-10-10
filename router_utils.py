import subprocess
import platform
from db import get_connection, execute_with_error_handling, DatabaseConnectionError
from datetime import datetime

# Insert new router
def insert_router(name, ip, mac, brand, location, image_path):
    def _insert():
        conn = get_connection()
        cursor = conn.cursor()
        sql = """
        INSERT INTO routers (name, ip_address, mac_address, brand, location, image_path)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (name, ip, mac, brand, location, image_path))
        conn.commit()
        router_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return router_id
    
    result = execute_with_error_handling("insert_router", _insert)
    return result

# Get all routers
def get_routers():
    def _get_routers():
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM routers")
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return data
    
    result = execute_with_error_handling("get_routers", _get_routers)
    return result if result is not None else []

# Update existing router
def update_router(id, name, ip, mac, brand, location, image_path):
    conn = get_connection()
    cursor = conn.cursor()
    sql = """
    UPDATE routers
    SET name = %s, ip_address = %s, mac_address = %s, brand = %s,
        location = %s, image_path = %s
    WHERE id = %s
    """
    cursor.execute(sql, (name, ip, mac, brand, location, image_path, id))
    conn.commit()
    cursor.close()
    conn.close()

# Delete router
def delete_router(id):
    conn = get_connection()
    cursor = conn.cursor()
    sql = "DELETE FROM routers WHERE id = %s"
    cursor.execute(sql, (id,))
    conn.commit()
    cursor.close()
    conn.close()

# Ping to check online status
def is_online(ip):
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    timeout_param = '-w' if platform.system().lower() == 'windows' else '-W'
    try:
        output = subprocess.check_output(
            ['ping', param, '1', timeout_param, '1000', ip],
            stderr=subprocess.DEVNULL,
            universal_newlines=True
        )
        return "TTL=" in output or "ttl=" in output
    except subprocess.CalledProcessError:
        return False

# New function: update last_seen + save to log
def update_router_status_in_db(router_id, is_online_status):
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now()
    status_text = 'online' if is_online_status else 'offline'

    # ✅ Only update last_seen if online
    if is_online_status:
        sql_update = """
            UPDATE routers 
            SET last_seen = %s
            WHERE id = %s
        """
        cursor.execute(sql_update, (now, router_id))

    # ✅ Always insert into router_status_log (this table DOES have `status`)
    sql_log = """
        INSERT INTO router_status_log (router_id, status, timestamp)
        VALUES (%s, %s, %s)
    """
    cursor.execute(sql_log, (router_id, status_text, now))

    conn.commit()
    cursor.close()
    conn.close()

# Check if router is online based on router_status_log table
def is_router_online_by_status(router_id, timeout_seconds=5):
    """
    Check if a router is online based on the most recent 'online' status 
    in router_status_log table within the specified timeout.
    
    Args:
        router_id: The router ID to check
        timeout_seconds: Number of seconds to consider as timeout (default: 5)
    
    Returns:
        bool: True if router is online, False otherwise
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get the most recent 'online' status for this router
        sql = """
            SELECT timestamp 
            FROM router_status_log 
            WHERE router_id = %s AND status = 'online' 
            ORDER BY timestamp DESC 
            LIMIT 1
        """
        cursor.execute(sql, (router_id,))
        result = cursor.fetchone()
        
        if not result:
            # No online status found, router is offline
            return False
        
        last_online_time = result[0]
        now = datetime.now()
        
        # Handle timezone differences - ensure both times are timezone-aware or naive
        if last_online_time.tzinfo is None:
            # Database timestamp is naive, make it timezone-aware (UTC)
            from datetime import timezone
            last_online_time = last_online_time.replace(tzinfo=timezone.utc)
            now = now.replace(tzinfo=timezone.utc)
        
        # Check if the last online status is within the timeout period
        time_diff = (now - last_online_time).total_seconds()
        is_online = time_diff <= timeout_seconds
        
        return is_online
        
    except Exception as e:
        print(f"Error checking router status: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

# Get router status with additional info
def get_router_status_info(router_id, timeout_seconds=5):
    """
    Get detailed router status information including last online time and time since last update.
    
    Args:
        router_id: The router ID to check
        timeout_seconds: Number of seconds to consider as timeout (default: 5)
    
    Returns:
        dict: Status information including is_online, last_online_time, seconds_since_last_update
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get the most recent 'online' status for this router
        sql = """
            SELECT timestamp 
            FROM router_status_log 
            WHERE router_id = %s AND status = 'online' 
            ORDER BY timestamp DESC 
            LIMIT 1
        """
        cursor.execute(sql, (router_id,))
        result = cursor.fetchone()
        
        now = datetime.now()
        
        if not result:
            return {
                'is_online': False,
                'last_online_time': None,
                'seconds_since_last_update': None
            }
        
        last_online_time = result[0]
        
        # Handle timezone differences - ensure both times are timezone-aware or naive
        if last_online_time.tzinfo is None:
            # Database timestamp is naive, make it timezone-aware (UTC)
            from datetime import timezone
            last_online_time = last_online_time.replace(tzinfo=timezone.utc)
            now = now.replace(tzinfo=timezone.utc)
        
        seconds_since_last_update = (now - last_online_time).total_seconds()
        is_online = seconds_since_last_update <= timeout_seconds
        
        return {
            'is_online': is_online,
            'last_online_time': last_online_time,
            'seconds_since_last_update': seconds_since_last_update
        }
        
    except Exception as e:
        print(f"Error getting router status info: {e}")
        return {
            'is_online': False,
            'last_online_time': None,
            'seconds_since_last_update': None
        }
    finally:
        cursor.close()
        conn.close()


