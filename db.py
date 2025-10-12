import mysql.connector
from mysql.connector import Error
import json
import time
import logging
from datetime import datetime
import os

# Configure logging for database operations
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection configuration
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "winyfi",
    "connection_timeout": 10,
    "autocommit": True,
    "raise_on_warnings": True
}

class DatabaseConnectionError(Exception):
    """Custom exception for database connection issues"""
    pass

class DatabaseOperationError(Exception):
    """Custom exception for database operation issues"""
    pass

def show_database_error_dialog(title, message, error_details=None):
    """Non-intrusive handler for DB errors (logs only; UI decides on dialogs).

    This avoids any Tkinter usage at the DB layer so clients don't need local
    MySQL/XAMPP and the library remains safe for server/headless contexts.
    """
    if error_details:
        logger.error("%s - %s | Details: %s", title, message, error_details)
    else:
        logger.error("%s - %s", title, message)

def show_database_warning_dialog(title, message):
    """Log DB warnings without any GUI dependency."""
    logger.warning("%s - %s", title, message)

def check_mysql_server_status():
    """Check if MySQL server is running and accessible"""
    try:
        # Try to connect without specifying a database first
        test_config = DB_CONFIG.copy()
        test_config.pop('database', None)  # Remove database from config for initial test
        
        conn = mysql.connector.connect(**test_config)
        conn.close()
        return True, "MySQL server is running and accessible"
    except mysql.connector.Error as err:
        if err.errno == mysql.connector.errorcode.ER_ACCESS_DENIED_ERROR:
            return False, "Access denied: Check username and password"
        elif err.errno == mysql.connector.errorcode.ER_BAD_DB_ERROR:
            return False, "Database 'winyfi' does not exist"
        elif err.errno == 2003:  # Can't connect to MySQL server
            return False, "Can't connect to MySQL server. Please check if MySQL is running"
        elif err.errno == 1045:  # Access denied
            return False, "Access denied for user. Check MySQL credentials"
        else:
            return False, f"MySQL Error {err.errno}: {err.msg}"
    except Exception as e:
        return False, f"Unexpected error connecting to MySQL: {str(e)}"

def get_connection(max_retries=2, retry_delay=1, show_dialog=False):
    """
    Get database connection with error handling and retry mechanism
    
    Args:
        max_retries (int): Maximum number of connection attempts
        retry_delay (int): Delay between retry attempts in seconds
        show_dialog (bool): Whether to show error dialogs to user
    
    Returns:
        mysql.connector.connection: Database connection object
    
    Raises:
        DatabaseConnectionError: When connection cannot be established
    """
    # Allow environment overrides for retries to tune UX without code changes
    try:
        max_retries = int(os.environ.get("WINYFI_DB_RETRIES", max_retries))
    except Exception:
        pass
    try:
        retry_delay = float(os.environ.get("WINYFI_DB_RETRY_DELAY", retry_delay))
    except Exception:
        pass
    try:
        env_sd = os.environ.get("WINYFI_DB_SHOW_DIALOG")
        if env_sd is not None:
            show_dialog = str(env_sd).lower() in ("1", "true", "yes")
    except Exception:
        pass

    last_error = None
    
    for attempt in range(max_retries):
        try:
            # Attempt to connect
            conn = mysql.connector.connect(**DB_CONFIG)
            
            # Test the connection
            if conn.is_connected():
                # Silently return successful connection
                return conn
            else:
                raise mysql.connector.Error("Connection established but not active")
                
        except mysql.connector.Error as err:
            last_error = err
            error_msg = f"MySQL Error on attempt {attempt + 1}/{max_retries}: "
            
            if err.errno == mysql.connector.errorcode.ER_ACCESS_DENIED_ERROR:
                error_msg += "Access denied - Check username and password"
                logger.error(error_msg)
                if show_dialog and attempt == max_retries - 1:
                    show_database_error_dialog(
                        "Database Access Denied",
                        "Cannot access MySQL database due to authentication failure.",
                        f"Error {err.errno}: {err.msg}"
                    )
                # Don't retry for authentication errors
                break
            elif err.errno == mysql.connector.errorcode.ER_BAD_DB_ERROR:
                error_msg += f"Database '{DB_CONFIG['database']}' does not exist"
                logger.error(error_msg)
                if show_dialog and attempt == max_retries - 1:
                    show_database_error_dialog(
                        "Database Not Found",
                        f"The database '{DB_CONFIG['database']}' does not exist.",
                        f"Error {err.errno}: {err.msg}"
                    )
                # Don't retry for missing database
                break
            elif err.errno == 2003:  # Can't connect to MySQL server
                error_msg += "Cannot connect to MySQL server"
                if show_dialog:
                    logger.warning(error_msg)
                if show_dialog and attempt == max_retries - 1:
                    show_database_error_dialog(
                        "MySQL Server Unreachable",
                        "Cannot connect to MySQL server. Some features may be limited.",
                        f"Error {err.errno}: {err.msg}"
                    )
            elif err.errno == 1045:  # Access denied
                error_msg += "Access denied for user - Check MySQL credentials"
                logger.error(error_msg)
                if show_dialog and attempt == max_retries - 1:
                    show_database_error_dialog(
                        "Database Access Denied",
                        "Access denied for MySQL user. Please check your credentials.",
                        f"Error {err.errno}: {err.msg}"
                    )
                break
            elif err.errno == 2006:  # MySQL server has gone away
                error_msg += "MySQL server has gone away - Attempting reconnection"
                logger.warning(error_msg)
                if show_dialog and attempt == max_retries - 1:
                    show_database_warning_dialog(
                        "MySQL Connection Lost",
                        "MySQL server connection was lost. Please check your network connection."
                    )
            else:
                error_msg += f"Error {err.errno}: {err.msg}"
                logger.error(error_msg)
                if show_dialog and attempt == max_retries - 1:
                    show_database_error_dialog(
                        "Database Connection Error",
                        "An unexpected database error occurred.",
                        f"Error {err.errno}: {err.msg}"
                    )
            
            # Wait before retrying (except on last attempt)
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                
        except Exception as e:
            last_error = e
            logger.error(f"Unexpected error on attempt {attempt + 1}/{max_retries}: {str(e)}")
            
            if show_dialog and attempt == max_retries - 1:
                show_database_error_dialog(
                    "Unexpected Database Error",
                    "An unexpected error occurred while connecting to the database.",
                    str(e)
                )
            
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
    
    # If we get here, all attempts failed
    error_details = str(last_error) if last_error else "Unknown error"
    raise DatabaseConnectionError(
        f"Failed to connect to MySQL after {max_retries} attempts. "
        f"Last error: {error_details}. "
        f"Please ensure MySQL server is running and accessible."
    )

def execute_with_error_handling(operation_name, operation_func, show_dialog=True, *args, **kwargs):
    """
    Execute database operations with comprehensive error handling
    
    Args:
        operation_name (str): Name of the operation for logging
        operation_func (callable): Function to execute
        show_dialog (bool): Whether to show error dialogs to user
        *args, **kwargs: Arguments to pass to the operation function
    
    Returns:
        Any: Result of the operation function, or None if failed
    """
    try:
        return operation_func(*args, **kwargs)
    except DatabaseConnectionError as e:
        logger.error(f"Database connection error during {operation_name}: {e}")
        if show_dialog:
            show_database_error_dialog(
                f"Database Error - {operation_name}",
                f"Failed to perform {operation_name} due to database connection issues.",
                str(e)
            )
        return None
    except mysql.connector.Error as e:
        logger.error(f"MySQL error during {operation_name}: {e}")
        if show_dialog:
            show_database_error_dialog(
                f"Database Error - {operation_name}",
                f"A database error occurred during {operation_name}.",
                f"MySQL Error {e.errno}: {e.msg}" if hasattr(e, 'errno') else str(e)
            )
        return None
    except Exception as e:
        logger.error(f"Unexpected error during {operation_name}: {e}")
        if show_dialog:
            show_database_error_dialog(
                f"Unexpected Error - {operation_name}",
                f"An unexpected error occurred during {operation_name}.",
                str(e)
            )
        return None

def create_loop_detections_table():
    """Create the loop_detections table if it doesn't exist."""
    def _create_table():
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
        
        try:
            cursor.execute(create_table_sql)
            conn.commit()
        except mysql.connector.Error as e:
            # Silently handle table already exists error (code 1050)
            if e.errno != 1050:  # 1050 = table already exists
                raise e
        finally:
            cursor.close()
            conn.close()
        return True
    
    result = execute_with_error_handling("create_loop_detections_table", _create_table, show_dialog=False)
    if result is None:
        # Don't log errors for table creation since it's expected to fail sometimes
        return False
    return True

def save_loop_detection(total_packets, offenders, stats, status, severity_score, interface="Wi-Fi", duration=3):
    """Save a loop detection result to the database."""
    def _save_detection():
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
        
        logger.info(f"Loop detection saved to database (ID: {detection_id})")
        return detection_id
    
    result = execute_with_error_handling("save_loop_detection", _save_detection)
    if result is None:
        logger.error("Failed to save loop detection to database")
    return result

def get_loop_detections_history(limit=100):
    """Get loop detection history from database."""
    def _get_history():
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
    
    result = execute_with_error_handling("get_loop_detections_history", _get_history)
    return result if result is not None else []

def get_loop_detection_stats():
    """Get loop detection statistics from database."""
    def _get_stats():
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
    
    result = execute_with_error_handling("get_loop_detection_stats", _get_stats)
    return result if result is not None else {
        "total_detections": 0,
        "loops_detected": 0,
        "suspicious_activity": 0,
        "clean_detections": 0
    }

def database_health_check():
    """
    Comprehensive database health check
    
    Returns:
        dict: Health check results with status, message, and details
    """
    health_status = {
        "status": "unknown",
        "message": "",
        "details": {
            "server_accessible": False,
            "database_exists": False,
            "tables_accessible": False,
            "connection_time": None
        }
    }
    
    start_time = time.time()
    
    try:
        # Check if MySQL server is accessible
        server_status, server_message = check_mysql_server_status()
        health_status["details"]["server_accessible"] = server_status
        
        if not server_status:
            health_status["status"] = "error"
            health_status["message"] = server_message
            return health_status
        
        # Try to connect to the specific database
        conn = get_connection(max_retries=1)
        connection_time = time.time() - start_time
        health_status["details"]["connection_time"] = round(connection_time, 3)
        
        # Test database access
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        health_status["details"]["database_exists"] = True
        
        # Test table access (try to query a known table)
        try:
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            health_status["details"]["tables_accessible"] = len(tables) > 0
            
            # Check if essential tables exist
            table_names = [table[0] for table in tables]
            essential_tables = ["routers", "users"]  # Add your essential table names
            missing_tables = [table for table in essential_tables if table not in table_names]
            
            if missing_tables:
                health_status["status"] = "warning"
                health_status["message"] = f"Database connected but missing tables: {', '.join(missing_tables)}"
            else:
                health_status["status"] = "healthy"
                health_status["message"] = f"Database is healthy (connected in {connection_time:.3f}s)"
                
        except mysql.connector.Error as e:
            health_status["status"] = "warning"
            health_status["message"] = f"Database connected but cannot access tables: {e}"
        
        cursor.close()
        conn.close()
        
    except DatabaseConnectionError as e:
        health_status["status"] = "error"
        health_status["message"] = str(e)
    except mysql.connector.Error as e:
        health_status["status"] = "error"
        health_status["message"] = f"MySQL Error: {e}"
    except Exception as e:
        health_status["status"] = "error"
        health_status["message"] = f"Unexpected error: {e}"
    
    return health_status

def get_database_info():
    """
    Get detailed database information for diagnostics
    
    Returns:
        dict: Database information including version, settings, etc.
    """
    def _get_info():
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        info = {}
        
        # Get MySQL version
        cursor.execute("SELECT VERSION() as version")
        version_result = cursor.fetchone()
        info["mysql_version"] = version_result["version"] if version_result else "Unknown"
        
        # Get database name
        cursor.execute("SELECT DATABASE() as database_name")
        db_result = cursor.fetchone()
        info["database_name"] = db_result["database_name"] if db_result else "Unknown"
        
        # Get connection info
        cursor.execute("SELECT CONNECTION_ID() as connection_id")
        conn_result = cursor.fetchone()
        info["connection_id"] = conn_result["connection_id"] if conn_result else "Unknown"
        
        # Get table count
        cursor.execute("SELECT COUNT(*) as table_count FROM information_schema.tables WHERE table_schema = DATABASE()")
        table_result = cursor.fetchone()
        info["table_count"] = table_result["table_count"] if table_result else 0
        
        cursor.close()
        conn.close()
        
        return info
    
    result = execute_with_error_handling("get_database_info", _get_info)
    return result if result is not None else {
        "mysql_version": "Unknown",
        "database_name": "Unknown", 
        "connection_id": "Unknown",
        "table_count": 0
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
        
        try:
            cursor.execute(create_table_sql)
            conn.commit()
            # Silently handle table creation/verification
        except mysql.connector.Error as e:
            # Silently handle table already exists error (code 1050)
            if e.errno != 1050:  # 1050 = table already exists
                raise e
        finally:
            cursor.close()
            conn.close()
            
        return True
        
    except Exception as e:
        # Don't show error messages for table creation
        return False

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
        
    # Removed login notification print statement
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
        
    # Removed logout notification print statement
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

def change_user_password(user_id, old_password, new_password):
    """Change the password for a user with proper verification and hashing."""
    try:
        from werkzeug.security import generate_password_hash, check_password_hash
        
        conn = get_connection()
        cursor = conn.cursor()

        # First, get the current password hash to verify the old password
        select_sql = "SELECT password_hash FROM users WHERE id = %s"
        cursor.execute(select_sql, (user_id,))
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            conn.close()
            return False, "User not found"
        
        current_password_hash = result[0]
        
        # Verify the old password
        if not check_password_hash(current_password_hash, old_password):
            cursor.close()
            conn.close()
            return False, "Current password is incorrect"
        
        # Validate new password strength
        if len(new_password) < 6:
            cursor.close()
            conn.close()
            return False, "New password must be at least 6 characters long"
        
        # Hash the new password
        new_password_hash = generate_password_hash(new_password)

        # Update the password
        update_sql = "UPDATE users SET password_hash = %s WHERE id = %s"
        cursor.execute(update_sql, (new_password_hash, user_id))
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "Password changed successfully"
        
    except Exception as e:
        print(f"Error changing user password: {e}")
        return False, f"Database error: {str(e)}"

# =============================
# User profile helpers
# =============================
def get_user_by_id(user_id):
    """Fetch a single user by id. Returns dict or None."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        # Select only columns we show/edit to avoid leaking sensitive data
        cursor.execute(
            "SELECT id, username, first_name, last_name, role FROM users WHERE id = %s",
            (user_id,),
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row
    except Exception as e:
        print(f"Error fetching user by id: {e}")
        return None


def update_user_profile(user_id, new_profile_data):
    """
    Update user's profile safely.

    Args:
        user_id (int): target user id
        new_profile_data (dict): keys in {first_name, last_name, username}

    Returns:
        (True, updated_user_dict) on success
        (False, error_message) on failure
    """
    try:
        # Normalize inputs
        allowed_fields = {"first_name", "last_name", "username"}
        data = {k: (v.strip() if isinstance(v, str) else v)
                for k, v in (new_profile_data or {}).items()
                if k in allowed_fields}

        if not data:
            return False, "No valid fields provided"

        # Load existing user
        existing = get_user_by_id(user_id)
        if not existing:
            return False, "User not found"

        # Validation rules
        first_name = data.get("first_name", existing.get("first_name")) or ""
        last_name = data.get("last_name", existing.get("last_name")) or ""
        username = data.get("username", existing.get("username")) or ""

        if not first_name and not last_name:
            return False, "Please provide at least a first or last name"

        if username:
            if len(username) < 3:
                return False, "Username must be at least 3 characters"
            # username safe charset (letters, digits, underscore, dot, dash)
            import re
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
                return False, "Username may contain letters, numbers, '.', '_' or '-' only"

        # Dirty-check: build update set only for changed values
        updates = {}
        for field in allowed_fields:
            if field in data and (data[field] or "") != (existing.get(field) or ""):
                updates[field] = data[field]

        if not updates:
            return False, "No changes detected"

        # Ensure username uniqueness if being changed
        if "username" in updates:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM users WHERE username = %s AND id <> %s",
                (updates["username"], user_id),
            )
            taken = cursor.fetchone()
            if taken:
                cursor.close()
                conn.close()
                return False, "Username is already taken"
            cursor.close()
            conn.close()

        # Build dynamic update statement
        set_clauses = []
        params = []
        for k, v in updates.items():
            set_clauses.append(f"{k} = %s")
            params.append(v)

        if not set_clauses:
            return False, "No valid changes"

        params.append(user_id)

        conn = get_connection()
        cursor = conn.cursor()
        sql = f"UPDATE users SET {', '.join(set_clauses)} WHERE id = %s"
        cursor.execute(sql, tuple(params))
        conn.commit()
        cursor.close()
        conn.close()

        # Return fresh copy
        updated = get_user_by_id(user_id)
        return True, updated

    except Exception as e:
        print(f"Error updating user profile: {e}")
        return False, f"Database error: {str(e)}"