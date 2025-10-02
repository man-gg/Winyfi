import mysql.connector
import json
from datetime import datetime

def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="winyfi"
    )

def create_loop_detections_table():
    """Create the loop_detections table if it doesn't exist."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS loop_detections (
            id INT AUTO_INCREMENT PRIMARY KEY,
            detection_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_packets INT,
            offenders_count INT,
            offenders_data JSON,
            severity_score FLOAT,
            network_interface VARCHAR(100),
            detection_duration INT,
            status ENUM('clean', 'suspicious', 'loop_detected') DEFAULT 'clean'
        )
        """
        
        cursor.execute(create_table_sql)
        conn.commit()
        cursor.close()
        conn.close()
        print("Loop detections table created/verified")
        
    except Exception as e:
        print(f"Error creating loop_detections table: {e}")

def save_loop_detection(total_packets, offenders, stats, status, severity_score, interface="Wi-Fi", duration=3):
    """Save a loop detection result to the database."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Prepare offenders data for JSON storage
        offenders_data = {
            "offenders": offenders if isinstance(offenders, list) else [],
            "stats": stats
        }
        
        insert_sql = """
        INSERT INTO loop_detections 
        (total_packets, offenders_count, offenders_data, severity_score, network_interface, detection_duration, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        offenders_count = len(offenders) if isinstance(offenders, list) else offenders
        
        cursor.execute(insert_sql, (
            total_packets,
            offenders_count,
            json.dumps(offenders_data),
            severity_score,
            interface,
            duration,
            status
        ))
        
        conn.commit()
        detection_id = cursor.lastrowid
        cursor.close()
        conn.close()
        
        print(f" Loop detection saved to database (ID: {detection_id})")
        return detection_id
        
    except Exception as e:
        print(f" Error saving loop detection: {e}")
        return None

def get_loop_detections_history(limit=100):
    """Get loop detection history from database."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        select_sql = """
        SELECT * FROM loop_detections 
        ORDER BY detection_time DESC 
        LIMIT %s
        """
        
        cursor.execute(select_sql, (limit,))
        results = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return results
        
    except Exception as e:
        print(f" Error loading loop detection history: {e}")
        return []

def get_loop_detection_stats():
    """Get loop detection statistics from database."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get total detections
        cursor.execute("SELECT COUNT(*) FROM loop_detections")
        total_detections = cursor.fetchone()[0]
        
        # Get loops detected
        cursor.execute("SELECT COUNT(*) FROM loop_detections WHERE status = 'loop_detected'")
        loops_detected = cursor.fetchone()[0]
        
        # Get suspicious activity
        cursor.execute("SELECT COUNT(*) FROM loop_detections WHERE status = 'suspicious'")
        suspicious_activity = cursor.fetchone()[0]
        
        # Get clean detections
        cursor.execute("SELECT COUNT(*) FROM loop_detections WHERE status = 'clean'")
        clean_detections = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return {
            "total_detections": total_detections,
            "loops_detected": loops_detected,
            "suspicious_activity": suspicious_activity,
            "clean_detections": clean_detections
        }
        
    except Exception as e:
        print(f" Error loading loop detection stats: {e}")
        return {
            "total_detections": 0,
            "loops_detected": 0,
            "suspicious_activity": 0,
            "clean_detections": 0
        }

def create_network_clients_table():
    """Create the network_clients table if it doesn't exist."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS network_clients (
            id INT AUTO_INCREMENT PRIMARY KEY,
            mac_address VARCHAR(17) NOT NULL,
            ip_address VARCHAR(15),
            hostname VARCHAR(255),
            vendor VARCHAR(255),
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            is_online BOOLEAN DEFAULT TRUE,
            ping_latency_ms INT,
            connection_count INT DEFAULT 1,
            device_type VARCHAR(100),
            notes TEXT,
            UNIQUE KEY unique_mac (mac_address)
        )
        """
        
        cursor.execute(create_table_sql)
        conn.commit()
        print(" Network clients table created/verified")
        
        # Create connection history table
        create_history_table_sql = """
        CREATE TABLE IF NOT EXISTS connection_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            mac_address VARCHAR(17) NOT NULL,
            ip_address VARCHAR(15),
            event_type ENUM('CONNECT', 'DISCONNECT', 'IP_CHANGE') NOT NULL,
            event_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            previous_ip VARCHAR(15),
            ping_latency_ms INT,
            hostname VARCHAR(255),
            vendor VARCHAR(255),
            session_duration_seconds INT,
            INDEX idx_mac_timestamp (mac_address, event_timestamp),
            INDEX idx_event_type (event_type),
            INDEX idx_timestamp (event_timestamp)
        )
        """
        
        cursor.execute(create_history_table_sql)
        conn.commit()
        print(" Connection history table created/verified")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error creating network_clients table: {e}")

def create_connection_history_table():
    """Create the connection_history table if it doesn't exist."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        create_history_table_sql = """
        CREATE TABLE IF NOT EXISTS connection_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            mac_address VARCHAR(17) NOT NULL,
            ip_address VARCHAR(15),
            event_type ENUM('CONNECT', 'DISCONNECT', 'IP_CHANGE') NOT NULL,
            event_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            previous_ip VARCHAR(15),
            ping_latency_ms INT,
            hostname VARCHAR(255),
            vendor VARCHAR(255),
            session_duration_seconds INT,
            INDEX idx_mac_timestamp (mac_address, event_timestamp),
            INDEX idx_event_type (event_type),
            INDEX idx_timestamp (event_timestamp)
        )
        """
        
        cursor.execute(create_history_table_sql)
        conn.commit()
        cursor.close()
        conn.close()
        print(" Connection history table created/verified")
        
    except Exception as e:
        print(f" Error creating connection_history table: {e}")

def save_network_client(mac_address, ip_address=None, hostname=None, vendor=None, 
                       ping_latency=None, device_type=None, notes=None):
    """Save or update a network client in the database."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if client exists
        cursor.execute("SELECT id, connection_count FROM network_clients WHERE mac_address = %s", (mac_address,))
        existing_client = cursor.fetchone()
        
        if existing_client:
            # Update existing client
            client_id, connection_count = existing_client
            update_sql = """
            UPDATE network_clients 
            SET ip_address = COALESCE(%s, ip_address),
                hostname = COALESCE(%s, hostname),
                vendor = COALESCE(%s, vendor),
                last_seen = CURRENT_TIMESTAMP,
                is_online = TRUE,
                ping_latency_ms = %s,
                connection_count = connection_count + 1,
                device_type = COALESCE(%s, device_type),
                notes = COALESCE(%s, notes)
            WHERE id = %s
            """
            cursor.execute(update_sql, (ip_address, hostname, vendor, ping_latency, 
                                      device_type, notes, client_id))
        else:
            # Insert new client
            insert_sql = """
            INSERT INTO network_clients 
            (mac_address, ip_address, hostname, vendor, ping_latency_ms, device_type, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_sql, (mac_address, ip_address, hostname, vendor, 
                                      ping_latency, device_type, notes))
            client_id = cursor.lastrowid
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return client_id
        
    except Exception as e:
        print(f" Error saving network client: {e}")
        return None

def get_network_clients(online_only=False, limit=100):
    """Get network clients from database."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        if online_only:
            select_sql = """
            SELECT * FROM network_clients 
            WHERE is_online = TRUE
            ORDER BY last_seen DESC 
            LIMIT %s
            """
            cursor.execute(select_sql, (limit,))
        else:
            select_sql = """
            SELECT * FROM network_clients 
            ORDER BY last_seen DESC 
            LIMIT %s
            """
            cursor.execute(select_sql, (limit,))
        
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return results
        
    except Exception as e:
        print(f" Error loading network clients: {e}")
        return []

def update_client_offline_status(mac_address):
    """Mark a client as offline."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        update_sql = "UPDATE network_clients SET is_online = FALSE WHERE mac_address = %s"
        cursor.execute(update_sql, (mac_address,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f" Error updating client offline status: {e}")

def log_connection_event(mac_address, event_type, ip_address=None, previous_ip=None, 
                        ping_latency=None, hostname=None, vendor=None, session_duration=None):
    """Log a connection event to the history table."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        insert_sql = """
        INSERT INTO connection_history 
        (mac_address, ip_address, event_type, previous_ip, ping_latency_ms, 
         hostname, vendor, session_duration_seconds)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(insert_sql, (mac_address, ip_address, event_type, previous_ip, 
                                   ping_latency, hostname, vendor, session_duration))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return cursor.lastrowid
        
    except Exception as e:
        print(f" Error logging connection event: {e}")
        return None

def get_connection_history(mac_address=None, limit=100, event_type=None):
    """Get connection history for a specific client or all clients."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        if mac_address:
            if event_type:
                select_sql = """
                SELECT * FROM connection_history 
                WHERE mac_address = %s AND event_type = %s
                ORDER BY event_timestamp DESC 
                LIMIT %s
                """
                cursor.execute(select_sql, (mac_address, event_type, limit))
            else:
                select_sql = """
                SELECT * FROM connection_history 
                WHERE mac_address = %s
                ORDER BY event_timestamp DESC 
                LIMIT %s
                """
                cursor.execute(select_sql, (mac_address, limit))
        else:
            if event_type:
                select_sql = """
                SELECT * FROM connection_history 
                WHERE event_type = %s
                ORDER BY event_timestamp DESC 
                LIMIT %s
                """
                cursor.execute(select_sql, (event_type, limit))
            else:
                select_sql = """
                SELECT * FROM connection_history 
                ORDER BY event_timestamp DESC 
                LIMIT %s
                """
                cursor.execute(select_sql, (limit,))
        
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return results
        
    except Exception as e:
        print(f" Error getting connection history: {e}")
        return []

def get_client_connection_stats(mac_address):
    """Get connection statistics for a specific client."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get total connections
        cursor.execute("""
            SELECT COUNT(*) as total_connections 
            FROM connection_history 
            WHERE mac_address = %s AND event_type = 'CONNECT'
        """, (mac_address,))
        total_connections = cursor.fetchone()['total_connections']
        
        # Get first and last connection
        cursor.execute("""
            SELECT MIN(event_timestamp) as first_connection, 
                   MAX(event_timestamp) as last_connection
            FROM connection_history 
            WHERE mac_address = %s
        """, (mac_address,))
        connection_dates = cursor.fetchone()
        
        # Get average session duration
        cursor.execute("""
            SELECT AVG(session_duration_seconds) as avg_session_duration
            FROM connection_history 
            WHERE mac_address = %s AND session_duration_seconds IS NOT NULL
        """, (mac_address,))
        avg_duration = cursor.fetchone()['avg_session_duration']
        
        # Get recent activity (last 24 hours)
        cursor.execute("""
            SELECT COUNT(*) as recent_connections
            FROM connection_history 
            WHERE mac_address = %s AND event_timestamp >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
        """, (mac_address,))
        recent_activity = cursor.fetchone()['recent_connections']
        
        cursor.close()
        conn.close()
        
        return {
            'total_connections': total_connections,
            'first_connection': connection_dates['first_connection'],
            'last_connection': connection_dates['last_connection'],
            'avg_session_duration': avg_duration,
            'recent_activity_24h': recent_activity
        }
        
    except Exception as e:
        print(f" Error getting client connection stats: {e}")
        return {}

def get_network_activity_summary(hours=24):
    """Get network activity summary for the last N hours."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get activity summary
        cursor.execute("""
            SELECT 
                event_type,
                COUNT(*) as event_count,
                COUNT(DISTINCT mac_address) as unique_devices
            FROM connection_history 
            WHERE event_timestamp >= DATE_SUB(NOW(), INTERVAL %s HOUR)
            GROUP BY event_type
        """, (hours,))
        
        activity_summary = cursor.fetchall()
        
        # Get most active devices
        cursor.execute("""
            SELECT 
                mac_address,
                COUNT(*) as activity_count,
                MAX(hostname) as hostname,
                MAX(vendor) as vendor
            FROM connection_history 
            WHERE event_timestamp >= DATE_SUB(NOW(), INTERVAL %s HOUR)
            GROUP BY mac_address
            ORDER BY activity_count DESC
            LIMIT 10
        """, (hours,))
        
        most_active = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return {
            'activity_summary': activity_summary,
            'most_active_devices': most_active
        }
        
    except Exception as e:
        print(f" Error getting network activity summary: {e}")
        return {'activity_summary': [], 'most_active_devices': []}

def create_login_sessions_table():
    """Create the login_sessions table if it doesn't exist."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS login_sessions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            username VARCHAR(100) NOT NULL,
            device_ip VARCHAR(45),
            device_mac VARCHAR(17),
            device_hostname VARCHAR(255),
            device_platform VARCHAR(100),
            user_agent TEXT,
            login_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            logout_timestamp TIMESTAMP NULL,
            session_duration_seconds INT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            login_type ENUM('admin', 'client') NOT NULL,
            INDEX idx_user_id (user_id),
            INDEX idx_username (username),
            INDEX idx_device_mac (device_mac),
            INDEX idx_login_timestamp (login_timestamp),
            INDEX idx_is_active (is_active),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
        
        cursor.execute(create_table_sql)
        conn.commit()
        print("Login sessions table created/verified")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error creating login_sessions table: {e}")

def log_user_login(user_id, username, device_ip=None, device_mac=None, 
                  device_hostname=None, device_platform=None, user_agent=None, 
                  login_type='client'):
    """Log a user login session."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # First, mark any existing active sessions as inactive
        cursor.execute("""
            UPDATE login_sessions 
            SET is_active = FALSE, 
                logout_timestamp = CURRENT_TIMESTAMP,
                session_duration_seconds = TIMESTAMPDIFF(SECOND, login_timestamp, CURRENT_TIMESTAMP)
            WHERE user_id = %s AND is_active = TRUE
        """, (user_id,))
        
        # Insert new login session
        insert_sql = """
        INSERT INTO login_sessions 
        (user_id, username, device_ip, device_mac, device_hostname, 
         device_platform, user_agent, login_type)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(insert_sql, (user_id, username, device_ip, device_mac, 
                                   device_hostname, device_platform, user_agent, login_type))
        
        session_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"Login session logged (ID: {session_id})")
        return session_id
        
    except Exception as e:
        print(f"Error logging user login: {e}")
        return None

def log_user_logout(user_id):
    """Log a user logout session."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Update the most recent active session
        cursor.execute("""
            UPDATE login_sessions 
            SET is_active = FALSE, 
                logout_timestamp = CURRENT_TIMESTAMP,
                session_duration_seconds = TIMESTAMPDIFF(SECOND, login_timestamp, CURRENT_TIMESTAMP)
            WHERE user_id = %s AND is_active = TRUE
            ORDER BY login_timestamp DESC
            LIMIT 1
        """, (user_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"Logout session logged for user {user_id}")
        return True
        
    except Exception as e:
        print(f"Error logging user logout: {e}")
        return False

def get_user_last_login_info(user_id):
    """Get the last login information for a user."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        select_sql = """
        SELECT 
            device_ip,
            device_mac,
            device_hostname,
            device_platform,
            login_timestamp,
            session_duration_seconds
        FROM login_sessions 
        WHERE user_id = %s 
        ORDER BY login_timestamp DESC 
        LIMIT 1
        """
        
        cursor.execute(select_sql, (user_id,))
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return result
        
    except Exception as e:
        print(f"Error getting user last login info: {e}")
        return None

def get_user_login_history(user_id, limit=10):
    """Get login history for a user."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        select_sql = """
        SELECT 
            device_ip,
            device_mac,
            device_hostname,
            device_platform,
            login_timestamp,
            logout_timestamp,
            session_duration_seconds,
            is_active,
            login_type
        FROM login_sessions 
        WHERE user_id = %s 
        ORDER BY login_timestamp DESC 
        LIMIT %s
        """
        
        cursor.execute(select_sql, (user_id, limit))
        results = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return results
        
    except Exception as e:
        print(f"Error getting user login history: {e}")
        return []

def get_all_login_sessions(limit=100, active_only=False):
    """Get all login sessions."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        if active_only:
            select_sql = """
            SELECT 
                ls.*,
                u.first_name,
                u.last_name
            FROM login_sessions ls
            JOIN users u ON ls.user_id = u.id
            WHERE ls.is_active = TRUE
            ORDER BY ls.login_timestamp DESC 
            LIMIT %s
            """
            cursor.execute(select_sql, (limit,))
        else:
            select_sql = """
            SELECT 
                ls.*,
                u.first_name,
                u.last_name
            FROM login_sessions ls
            JOIN users u ON ls.user_id = u.id
            ORDER BY ls.login_timestamp DESC 
            LIMIT %s
            """
            cursor.execute(select_sql, (limit,))
        
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return results
        
    except Exception as e:
        print(f"Error getting all login sessions: {e}")
        return []

def get_client_statistics():
    """Get network client statistics."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Total clients
        cursor.execute("SELECT COUNT(*) FROM network_clients")
        total_clients = cursor.fetchone()[0]
        
        # Online clients
        cursor.execute("SELECT COUNT(*) FROM network_clients WHERE is_online = TRUE")
        online_clients = cursor.fetchone()[0]
        
        # Offline clients
        cursor.execute("SELECT COUNT(*) FROM network_clients WHERE is_online = FALSE")
        offline_clients = cursor.fetchone()[0]
        
        # Recent connections (last 24 hours)
        cursor.execute("""
            SELECT COUNT(*) FROM network_clients 
            WHERE last_seen >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
        """)
        recent_connections = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return {
            "total_clients": total_clients,
            "online_clients": online_clients,
            "offline_clients": offline_clients,
            "recent_connections": recent_connections
        }
        
    except Exception as e:
        print(f" Error loading client statistics: {e}")
        return {
            "total_clients": 0,
            "online_clients": 0,
            "offline_clients": 0,
            "recent_connections": 0
        }