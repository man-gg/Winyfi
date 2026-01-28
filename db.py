import mysql.connector
from mysql.connector import Error
import json
import time
import logging
from datetime import datetime
import os
import sys
import traceback
from resource_utils import get_resource_path

# Configure logging for database operations
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================
# CRITICAL: PyInstaller MySQL Error Logging
# =============================
# When running as a PyInstaller EXE, create a detailed error log file
# for diagnostics since users may not have access to console output
def get_mysql_error_log_path():
    """Get the path for MySQL error log file (in EXE directory when frozen)."""
    if getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS'):
        # Running as PyInstaller bundle
        exe_dir = os.path.dirname(sys.executable)
    else:
        # Running as normal Python
        exe_dir = os.path.dirname(__file__)
    
    return os.path.join(exe_dir, 'mysql_connection_error.log')

def log_mysql_error(message, level="ERROR"):
    """Write error message to both logger and mysql_connection_error.log file.
    
    This function is critical for PyInstaller debugging since the EXE
    may not have console output available.
    
    Args:
        message: The message to log
        level: Log level - "ERROR", "INFO", "WARNING" (default: "ERROR")
    """
    if level == "INFO":
        logger.info(message)
    elif level == "WARNING":
        logger.warning(message)
    else:
        logger.error(message)
    
    try:
        log_path = get_mysql_error_log_path()
        with open(log_path, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        # Silently fail if we can't write the log (don't crash the app)
        logger.debug(f"Could not write to mysql_connection_error.log: {e}")

# Load database configuration from file or use defaults
def load_db_config():
    """Load database configuration from config file or environment"""
    # Try multiple locations for config file (prefer editable file near EXE)
    possible_paths = []

    # If running frozen, prefer an external, editable config next to the EXE
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        possible_paths.append(os.path.join(exe_dir, 'db_config.json'))

    # Then try resource path (bundled inside _MEIPASS for onefile)
    possible_paths.append(get_resource_path('db_config.json'))

    # Also consider current working directory and script directory (dev)
    possible_paths.append('db_config.json')
    possible_paths.append(os.path.join(os.path.dirname(__file__), 'db_config.json'))
    
    loaded_from = None

    # Default configuration
    default_config = {
        "host": "localhost",
        "user": "root",
        "password": "",
        "database": "winyfi",
        "port": 3306,
        "charset": "utf8mb4",
        "connection_timeout": 10,
    }
    
    # Try to load from config file
    config_found = False
    for config_file in possible_paths:
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    custom_config = json.load(f)
                    default_config.update(custom_config)
                    logger.info(f"Loaded database config from {config_file}")
                    config_found = True
                    loaded_from = config_file
                    break
            except Exception as e:
                logger.warning(f"Could not load config file {config_file}: {e}")
    
    if not config_found:
        logger.info("Using default database configuration (no config file found)")
        logger.debug(f"Searched paths: {possible_paths}")
    else:
        logger.info(f"Database configuration loaded from: {loaded_from}")
    
    # Override with environment variables if set
    if os.environ.get('WINYFI_DB_HOST'):
        default_config['host'] = os.environ.get('WINYFI_DB_HOST')
        logger.info(f"Using WINYFI_DB_HOST from environment: {default_config['host']}")
    if os.environ.get('WINYFI_DB_USER'):
        default_config['user'] = os.environ.get('WINYFI_DB_USER')
        logger.info(f"Using WINYFI_DB_USER from environment: {default_config['user']}")
    if os.environ.get('WINYFI_DB_PASSWORD'):
        default_config['password'] = os.environ.get('WINYFI_DB_PASSWORD')
        logger.info("Using WINYFI_DB_PASSWORD from environment")
    if os.environ.get('WINYFI_DB_NAME'):
        default_config['database'] = os.environ.get('WINYFI_DB_NAME')
        logger.info(f"Using WINYFI_DB_NAME from environment: {default_config['database']}")
    if os.environ.get('WINYFI_DB_PORT'):
        try:
            default_config['port'] = int(os.environ.get('WINYFI_DB_PORT'))
            logger.info(f"Using WINYFI_DB_PORT from environment: {default_config['port']}")
        except Exception:
            logger.warning("Invalid WINYFI_DB_PORT environment value; ignoring")
    
    logger.info(
        f"Database config: host={default_config['host']}, port={default_config.get('port')}, "
        f"user={default_config['user']}, db={default_config['database']}"
    )
    
    return default_config

# Database connection configuration
DB_CONFIG = load_db_config()

class DatabaseConnectionError(Exception):
    """Custom exception for database connection issues"""
    pass

class DatabaseOperationError(Exception):
    """Custom exception for database operation issues"""
    pass

# =============================
# Schema ensure helpers (idempotent)
# =============================
def ensure_users_agent_column():
    """Ensure the users table has an is_agent BOOLEAN column.

    Safe to call repeatedly; if the column already exists it does nothing.
    Added so code that SELECTs is_agent won't break if migration not applied.
    """
    try:
        conn = get_connection(max_retries=1, retry_delay=0, show_dialog=False)
        cur = conn.cursor()
        # Check information_schema for column existence
        cur.execute(
            """
            SELECT COUNT(*)
              FROM information_schema.COLUMNS
             WHERE TABLE_SCHEMA = %s
               AND TABLE_NAME = 'users'
               AND COLUMN_NAME = 'is_agent'
            """,
            (DB_CONFIG.get('database'),)
        )
        exists = cur.fetchone()[0] == 1
        if not exists:
            try:
                cur.execute("ALTER TABLE users ADD COLUMN is_agent BOOLEAN DEFAULT FALSE AFTER role")
                conn.commit()
                logger.info("Added is_agent column to users table")
            except Exception as alter_err:
                logger.error(f"Failed to add is_agent column: {alter_err}")
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
    except Exception as e:
        # Non-fatal; leave a log so admin can run migration manually
        logger.warning(f"ensure_users_agent_column skipped (DB unavailable?): {e}")

# =============================
# Topology schema helpers
# =============================
def ensure_topology_schema():
    """Ensure routers table has pos_x/pos_y columns and router_connections table exists.

    Idempotent: safe to call multiple times. Designed so the topology window can
    lazily invoke schema setup without requiring a separate migration run.
    """
    try:
        conn = get_connection(max_retries=1, retry_delay=0, show_dialog=False)
    except Exception as e:
        logger.warning(f"ensure_topology_schema skipped (no connection): {e}")
        return False

    try:
        cur = conn.cursor()
        db_name = DB_CONFIG.get('database')

        # ---- Ensure pos_x column ----
        cur.execute(
            """
            SELECT COUNT(*) FROM information_schema.COLUMNS
             WHERE TABLE_SCHEMA=%s AND TABLE_NAME='routers' AND COLUMN_NAME='pos_x'
            """, (db_name,)
        )
        if cur.fetchone()[0] == 0:
            try:
                cur.execute("ALTER TABLE routers ADD COLUMN pos_x INT NULL AFTER location")
                conn.commit()
                logger.info("Added pos_x column to routers table")
            except Exception as e:
                logger.warning(f"Could not add pos_x column: {e}")

        # ---- Ensure pos_y column ----
        cur.execute(
            """
            SELECT COUNT(*) FROM information_schema.COLUMNS
             WHERE TABLE_SCHEMA=%s AND TABLE_NAME='routers' AND COLUMN_NAME='pos_y'
            """, (db_name,)
        )
        if cur.fetchone()[0] == 0:
            try:
                cur.execute("ALTER TABLE routers ADD COLUMN pos_y INT NULL AFTER pos_x")
                conn.commit()
                logger.info("Added pos_y column to routers table")
            except Exception as e:
                logger.warning(f"Could not add pos_y column: {e}")

        # ---- Ensure router_connections table ----
        create_connections_sql = (
            """
            CREATE TABLE IF NOT EXISTS router_connections (
                router_a_id INT NOT NULL,
                router_b_id INT NOT NULL,
                bend_x INT NULL,
                bend_y INT NULL,
                PRIMARY KEY (router_a_id, router_b_id),
                INDEX idx_router_b (router_b_id),
                CONSTRAINT fk_router_a FOREIGN KEY (router_a_id) REFERENCES routers(id) ON DELETE CASCADE,
                CONSTRAINT fk_router_b FOREIGN KEY (router_b_id) REFERENCES routers(id) ON DELETE CASCADE
            ) ENGINE=InnoDB
            """
        )
        try:
            cur.execute(create_connections_sql)
            conn.commit()
        except Exception as e:
            logger.warning(f"Could not create router_connections table: {e}")

        # Ensure bend_x / bend_y columns exist (older installs)
        try:
            cur.execute("SHOW COLUMNS FROM router_connections LIKE 'bend_x'")
            has_bx = cur.fetchone() is not None
            cur.execute("SHOW COLUMNS FROM router_connections LIKE 'bend_y'")
            has_by = cur.fetchone() is not None
            if not has_bx:
                try:
                    cur.execute("ALTER TABLE router_connections ADD COLUMN bend_x INT NULL AFTER router_b_id")
                    conn.commit()
                except Exception as ce:
                    logger.warning(f"Could not add bend_x column: {ce}")
            if not has_by:
                try:
                    cur.execute("ALTER TABLE router_connections ADD COLUMN bend_y INT NULL AFTER bend_x")
                    conn.commit()
                except Exception as ce:
                    logger.warning(f"Could not add bend_y column: {ce}")
        except Exception as e:
            logger.warning(f"Could not verify/add bend columns: {e}")

        # ---- Ensure topology_shapes table ----
        create_shapes_sql = (
            """
            CREATE TABLE IF NOT EXISTS topology_shapes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                type ENUM('rect','circle','line','text') NOT NULL,
                x INT NOT NULL,
                y INT NOT NULL,
                w INT NULL,
                h INT NULL,
                x2 INT NULL,
                y2 INT NULL,
                text VARCHAR(255) NULL,
                color VARCHAR(32) NULL,
                fill_color VARCHAR(32) NULL,
                stroke_width INT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_type (type)
            ) ENGINE=InnoDB
            """
        )
        try:
            cur.execute(create_shapes_sql)
            conn.commit()
        except Exception as e:
            logger.warning(f"Could not create topology_shapes table: {e}")

        # Ensure stroke_width column exists (for outline thickness)
        try:
            conn2 = get_connection(); cur2 = conn2.cursor()
            cur2.execute("SHOW COLUMNS FROM topology_shapes LIKE 'stroke_width'")
            if cur2.fetchone() is None:
                try:
                    cur2.execute("ALTER TABLE topology_shapes ADD COLUMN stroke_width INT NULL AFTER color")
                    conn2.commit(); logger.info("Added stroke_width column to topology_shapes table")
                except Exception as ce:
                    logger.warning(f"Could not add stroke_width column: {ce}")
            cur2.close(); conn2.close()
        except Exception as e:
            logger.warning(f"stroke_width column check error: {e}")

        cur.close()
        conn.close()
        return True
    except Exception as e:
        logger.warning(f"ensure_topology_schema error: {e}")
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        return False

def get_router_connections():
    """Return all router connection pairs as list of dicts (includes bend)."""
    def _fetch():
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT router_a_id, router_b_id, bend_x, bend_y FROM router_connections")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    result = execute_with_error_handling("get_router_connections", _fetch, show_dialog=False)
    return result if result is not None else []

# =============================
# Topology shapes CRUD
# =============================

def get_topology_shapes():
    """Fetch all saved shapes for the topology view."""
    def _fetch():
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM topology_shapes ORDER BY id ASC")
        rows = cur.fetchall()
        cur.close(); conn.close(); return rows
    res = execute_with_error_handling("get_topology_shapes", _fetch, show_dialog=False)
    return res if res is not None else []

def insert_topology_shape(shape_type, x, y, w=None, h=None, x2=None, y2=None, text=None, color=None, fill_color=None, stroke_width=None):
    """Insert a new shape and return its id."""
    def _ins():
        conn = get_connection(); cur = conn.cursor()
        sql = ("INSERT INTO topology_shapes (type,x,y,w,h,x2,y2,text,color,fill_color,stroke_width) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)")
        cur.execute(sql, (shape_type, int(x), int(y),
                          None if w is None else int(w),
                          None if h is None else int(h),
                          None if x2 is None else int(x2),
                          None if y2 is None else int(y2),
                          text, color, fill_color,
                          None if stroke_width is None else int(stroke_width)))
        conn.commit(); new_id = cur.lastrowid
        cur.close(); conn.close(); return new_id
    return execute_with_error_handling("insert_topology_shape", _ins, show_dialog=False)

def update_topology_shape(shape_id, **fields):
    """Update arbitrary fields for a shape (positions, text, color)."""
    allowed = {"x","y","w","h","x2","y2","text","color","fill_color","stroke_width"}
    set_parts = []; params = []
    for k,v in fields.items():
        if k in allowed:
            set_parts.append(f"{k}=%s")
            params.append(v if v is None else (int(v) if isinstance(v,(int,float)) and k not in ("text","color") else v))
    if not set_parts:
        return True
    params.append(int(shape_id))
    def _upd():
        conn = get_connection(); cur = conn.cursor()
        cur.execute(f"UPDATE topology_shapes SET {', '.join(set_parts)} WHERE id=%s", tuple(params))
        conn.commit(); cur.close(); conn.close(); return True
    return execute_with_error_handling("update_topology_shape", _upd, show_dialog=False)

def delete_topology_shape(shape_id):
    """Delete shape by id."""
    def _del():
        conn = get_connection(); cur = conn.cursor()
        cur.execute("DELETE FROM topology_shapes WHERE id=%s", (int(shape_id),))
        conn.commit(); cur.close(); conn.close(); return True
    return execute_with_error_handling("delete_topology_shape", _del, show_dialog=False)

def add_router_connection(a_id: int, b_id: int, bend_x=None, bend_y=None):
    """Add a connection between two routers (unordered) with optional bend point."""
    if a_id == b_id:
        return False
    a, b = sorted([a_id, b_id])
    def _add():
        conn = get_connection()
        cur = conn.cursor()
        sql = "INSERT IGNORE INTO router_connections (router_a_id, router_b_id, bend_x, bend_y) VALUES (%s, %s, %s, %s)"
        cur.execute(sql, (a, b, bend_x, bend_y))
        conn.commit()
        cur.close()
        conn.close()
        return True
    return execute_with_error_handling("add_router_connection", _add, show_dialog=False) or False

def remove_router_connection(a_id: int, b_id: int):
    """Remove a connection between two routers if it exists."""
    if a_id == b_id:
        return False
    a, b = sorted([a_id, b_id])
    def _rm():
        conn = get_connection()
        cur = conn.cursor()
        sql = "DELETE FROM router_connections WHERE router_a_id=%s AND router_b_id=%s"
        cur.execute(sql, (a, b))
        conn.commit()
        cur.close()
        conn.close()
        return True
    return execute_with_error_handling("remove_router_connection", _rm, show_dialog=False) or False

def update_router_connection_bend(a_id: int, b_id: int, bend_x: int, bend_y: int):
    """Update stored bend point for a connection (unordered)."""
    if a_id == b_id:
        return False
    a, b = sorted([a_id, b_id])
    def _upd():
        conn = get_connection(); cur = conn.cursor()
        cur.execute(
            "UPDATE router_connections SET bend_x=%s, bend_y=%s WHERE router_a_id=%s AND router_b_id=%s",
            (int(bend_x), int(bend_y), a, b)
        )
        conn.commit(); cur.close(); conn.close(); return True
    return execute_with_error_handling("update_router_connection_bend", _upd, show_dialog=False) or False

def update_router_position(router_id: int, x: int, y: int):
    """Persist a router's position (x,y) on topology canvas."""
    def _upd():
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE routers SET pos_x=%s, pos_y=%s WHERE id=%s", (int(x), int(y), router_id))
        conn.commit()
        cur.close()
        conn.close()
        return True
    return execute_with_error_handling("update_router_position", _upd, show_dialog=False) or False

# =============================
# Bandwidth logs helpers
# =============================
def create_bandwidth_logs_table():
    """Create the bandwidth_logs table if it doesn't exist."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        create_table_sql = """
        CREATE TABLE IF NOT EXISTS bandwidth_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            router_id INT NOT NULL,
            download_mbps DOUBLE,
            upload_mbps DOUBLE,
            latency_ms DOUBLE,
            timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_router_time (router_id, timestamp)
        )
        """

        cursor.execute(create_table_sql)
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        # Ignore "table already exists" errors since IF NOT EXISTS is used
        logger.warning(f"create_bandwidth_logs_table warning: {e}")
        return False


def insert_bandwidth_log(router_id, download_mbps, upload_mbps, latency_ms=None, when: datetime | None = None):
    """Insert a single bandwidth log row.

    Args:
        router_id (int): Router ID (FK to routers.id)
        download_mbps (float|None): Download throughput
        upload_mbps (float|None): Upload throughput
        latency_ms (float|None): Optional latency value
        when (datetime|None): Optional explicit timestamp; defaults to NOW() if None
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        if when is None:
            sql = (
                "INSERT INTO bandwidth_logs (router_id, download_mbps, upload_mbps, latency_ms) "
                "VALUES (%s, %s, %s, %s)"
            )
            params = (router_id, download_mbps, upload_mbps, latency_ms)
        else:
            sql = (
                "INSERT INTO bandwidth_logs (router_id, download_mbps, upload_mbps, latency_ms, timestamp) "
                "VALUES (%s, %s, %s, %s, %s)"
            )
            params = (router_id, download_mbps, upload_mbps, latency_ms, when)

        cursor.execute(sql, params)
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"insert_bandwidth_log failed: {e}")
        return False

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
    # Create detailed error log file near the executable when frozen for easier access
    if getattr(sys, 'frozen', False):
        error_log_base = os.path.dirname(sys.executable)
    else:
        error_log_base = os.path.dirname(__file__)
    error_log_path = os.path.join(error_log_base, "mysql_connection_error.log")
    
    def log_error(message):
        """Log error to both logger and dedicated error file"""
        logger.error(message)
        try:
            with open(error_log_path, 'a', encoding='utf-8') as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
        except Exception:
            pass
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
    
    # Log connection attempt START ONCE (no redundant banners)
    logger.info(f"Attempting MySQL connection to {DB_CONFIG.get('host')}:{DB_CONFIG.get('port')} (attempt 1/{max_retries})")
    
    for attempt in range(max_retries):
        try:
            # Attempt to connect
            # Use pure Python implementation for PyInstaller compatibility
            conn_config = dict(DB_CONFIG)
            conn_config['use_pure'] = True  # Force pure Python, no C extensions
            conn_config['use_unicode'] = True
            # Ensure charset is properly set for MySQL 8.0+
            if 'charset' not in conn_config or not conn_config['charset']:
                conn_config['charset'] = 'utf8mb4'
            # If auth_plugin is missing/None, do not send the key at all (let server choose)
            if not conn_config.get('auth_plugin'):
                conn_config.pop('auth_plugin', None)
            conn = mysql.connector.connect(**conn_config)
            
            # Test the connection
            if conn.is_connected():
                logger.info(f"✅ MySQL connection established successfully")
                return conn
            else:
                raise mysql.connector.Error("Connection established but not active")
                
        except mysql.connector.Error as err:
            last_error = err
            log_mysql_error(f"MySQL Error (Errno {err.errno}): {err.msg}", level="ERROR")
            log_mysql_error(f"Exception type: {type(err).__name__}", level="ERROR")
            
            # Log full traceback for debugging only on first attempt
            if attempt == 0:
                tb_lines = traceback.format_exc().split('\n')
                for line in tb_lines:
                    if line.strip():
                        log_mysql_error(f"  {line}", level="ERROR")

            # =====================================================
            # CRITICAL FIX: Handle authentication plugin mismatches
            # =====================================================
            # PyInstaller builds may fail with auth plugin issues on MySQL 8.x
            # This section implements fallback strategy:
            # 1. Try with server-chosen plugin (default)
            # 2. Try with caching_sha2_password (MySQL 8.0+ modern default)
            # 3. Try with mysql_native_password (MySQL 5.7 and older systems)
            plugin_message = str(err).lower()
            plugin_issue = (
                "authentication plugin" in plugin_message
                or "not supported" in plugin_message
                or err.errno == mysql.connector.errorcode.ER_NOT_SUPPORTED_AUTH_MODE
                or err.errno == 2059
            )

            if plugin_issue:
                log_mysql_error(f"🔄 Authentication plugin issue detected: {err.msg}", level="WARNING")
                logger.info(f"   Attempting plugin fallback strategy...")
                tried_plugin = conn_config.get('auth_plugin')
                
                # Build ordered list of fallback plugins to try
                # Start with server default (None), then explicit plugins in order of modern -> legacy
                ordered_plugins_to_try = []
                if tried_plugin is not None:
                    # If an explicit plugin was tried, first try server default
                    ordered_plugins_to_try.append(None)
                
                # Add plugins not yet tried, in order: modern -> legacy
                for candidate in [None, 'caching_sha2_password', 'mysql_native_password']:
                    if candidate not in ordered_plugins_to_try and candidate != tried_plugin:
                        ordered_plugins_to_try.append(candidate)
                
                for fallback_plugin in ordered_plugins_to_try:
                    try:
                        # Build fallback config with explicit auth plugin handling
                        alt_config = dict(DB_CONFIG)
                        alt_config['use_pure'] = True  # Force pure Python implementation
                        alt_config['use_unicode'] = True
                        
                        # Ensure charset is set
                        if 'charset' not in alt_config or not alt_config['charset']:
                            alt_config['charset'] = 'utf8mb4'
                        
                        # Set or unset auth_plugin
                        if fallback_plugin is None:
                            # Let server choose the plugin
                            alt_config.pop('auth_plugin', None)
                            plugin_label = "(server-chosen)"
                        else:
                            # Explicitly set the plugin
                            alt_config['auth_plugin'] = fallback_plugin
                            plugin_label = fallback_plugin
                        
                        logger.info(f"   → Trying auth_plugin={plugin_label}...")
                        
                        # Try connection with fallback plugin
                        alt_conn = mysql.connector.connect(**alt_config)
                        if alt_conn.is_connected():
                            logger.info(f"✅ Connection established with auth_plugin={plugin_label}")
                            return alt_conn
                            
                    except mysql.connector.Error as alt_err:
                        last_error = alt_err
                        logger.info(f"   ✗ Plugin {plugin_label} failed: {alt_err.errno} - {alt_err.msg}")
                        continue
                    except Exception as alt_err:
                        last_error = alt_err
                        logger.info(f"   ✗ Plugin {plugin_label} failed: {type(alt_err).__name__}: {alt_err}")
                        continue
                
                # All fallback plugins exhausted; fall through to detailed error handling
                log_mysql_error(f"❌ All authentication plugin fallbacks exhausted", level="ERROR")
                log_mysql_error(f"   Original error: {err.msg}", level="ERROR")
            
            if err.errno == mysql.connector.errorcode.ER_ACCESS_DENIED_ERROR:
                log_mysql_error(f"❌ Access denied - Check username and password", level="ERROR")
                log_mysql_error(f"   Error code: {err.errno}", level="ERROR")
                log_mysql_error(f"   Error message: {err.msg}", level="ERROR")
                log_mysql_error(f"   Attempted user: {DB_CONFIG.get('user')}@{DB_CONFIG.get('host')}", level="ERROR")
                if show_dialog and attempt == max_retries - 1:
                    show_database_error_dialog(
                        "Database Access Denied",
                        "Cannot access MySQL database due to authentication failure.",
                        f"Error {err.errno}: {err.msg}"
                    )
                # Don't retry for authentication errors
                break
            elif err.errno == mysql.connector.errorcode.ER_BAD_DB_ERROR:
                log_mysql_error(f"❌ Database not found - '{DB_CONFIG['database']}' does not exist", level="ERROR")
                log_mysql_error(f"   Error code: {err.errno}", level="ERROR")
                log_mysql_error(f"   Error message: {err.msg}", level="ERROR")
                log_mysql_error(f"   Attempted database: {DB_CONFIG.get('database')}", level="ERROR")
                log_mysql_error(f"   Solution: Create the database or import winyfi.sql", level="ERROR")
                if show_dialog and attempt == max_retries - 1:
                    show_database_error_dialog(
                        "Database Not Found",
                        f"The database '{DB_CONFIG['database']}' does not exist.\nCreate it or import winyfi.sql.",
                        f"Error {err.errno}: {err.msg}\n\nDetailed log: mysql_connection_error.log"
                    )
                # Don't retry for missing database
                break
            elif err.errno == 2003:  # Can't connect to MySQL server
                log_mysql_error(f"❌ Cannot connect to MySQL server", level="ERROR")
                log_mysql_error(f"   Error code: {err.errno}", level="ERROR")
                log_mysql_error(f"   Error message: {err.msg}", level="ERROR")
                log_mysql_error(f"   Target: {DB_CONFIG.get('host')}:{DB_CONFIG.get('port')}", level="ERROR")
                log_mysql_error(f"   Possible causes:", level="ERROR")
                log_mysql_error(f"     1. MySQL service is not running (check XAMPP)", level="ERROR")
                log_mysql_error(f"     2. Firewall blocking connection", level="ERROR")
                log_mysql_error(f"     3. Wrong host/port configuration", level="ERROR")
                if show_dialog and attempt == max_retries - 1:
                    show_database_error_dialog(
                        "MySQL Server Unreachable",
                        "Cannot connect to MySQL server. Some features may be limited.\n\nStart MySQL/XAMPP and check mysql_connection_error.log for details.",
                        f"Error {err.errno}: {err.msg}"
                    )
            elif err.errno == 1045:  # Access denied
                log_mysql_error(f"❌ Access denied for MySQL user", level="ERROR")
                log_mysql_error(f"   Error code: {err.errno}", level="ERROR")
                log_mysql_error(f"   Error message: {err.msg}", level="ERROR")
                log_mysql_error(f"   Attempted credentials: user={DB_CONFIG.get('user')}@{DB_CONFIG.get('host')}", level="ERROR")
                log_mysql_error(f"   Solution: Verify db_config.json credentials match MySQL user")
                if show_dialog and attempt == max_retries - 1:
                    show_database_error_dialog(
                        "Database Access Denied",
                        "Access denied for MySQL user. Check your credentials in db_config.json.\n\nSee mysql_connection_error.log for details.",
                        f"Error {err.errno}: {err.msg}"
                    )
                break
            elif err.errno == 2059:  # Authentication plugin error
                log_mysql_error(f"❌ Authentication plugin configuration error", level="ERROR")
                log_mysql_error(f"   Error code: {err.errno}", level="ERROR")
                log_mysql_error(f"   Error message: {err.msg}", level="ERROR")
                log_mysql_error(f"   MySQL user: {DB_CONFIG.get('user')}@{DB_CONFIG.get('host')}", level="ERROR")
                log_mysql_error(f"   Solution:", level="ERROR")
                log_mysql_error(f"     1. Ensure MySQL is running", level="ERROR")
                log_mysql_error(f"     2. Check that user exists and credentials are correct", level="ERROR")
                if show_dialog and attempt == max_retries - 1:
                    show_database_error_dialog(
                        "MySQL Configuration Issue",
                        "Authentication plugin error. Check MySQL user configuration.\n\nDetailed log: mysql_connection_error.log",
                        f"Error {err.errno}: {err.msg}"
                    )
                # Don't retry for auth plugin errors
                break
            elif err.errno == 2006:  # MySQL server has gone away
                log_mysql_error(f"⚠️  MySQL server has gone away - attempting reconnection", level="WARNING")
                log_mysql_error(f"   Error code: {err.errno}", level="WARNING")
                log_mysql_error(f"   Error message: {err.msg}", level="WARNING")
                if show_dialog and attempt == max_retries - 1:
                    show_database_warning_dialog(
                        "MySQL Connection Lost",
                        "MySQL connection was lost. Check your network and MySQL status."
                    )
            else:
                log_mysql_error(f"❌ Error {err.errno}: {err.msg}", level="ERROR")
                log_mysql_error(f"   Exception type: {type(err).__name__}", level="ERROR")
                if show_dialog and attempt == max_retries - 1:
                    show_database_error_dialog(
                        "Database Connection Error",
                        "An unexpected database error occurred.\n\nSee mysql_connection_error.log for details.",
                        f"Error {err.errno}: {err.msg}"
                    )
            
            # Wait before retrying (except on last attempt)
            if attempt < max_retries - 1:
                logger.info(f"   Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                
        except Exception as e:
            last_error = e
            log_mysql_error(f"Unexpected error on attempt {attempt + 1}/{max_retries}: {type(e).__name__}", level="ERROR")
            log_mysql_error(f"   Message: {str(e)}", level="ERROR")
            log_mysql_error(f"   Traceback:", level="ERROR")
            tb_lines = traceback.format_exc().split('\n')
            for line in tb_lines:
                if line.strip():
                    log_mysql_error(f"     {line}", level="ERROR")
            
            if show_dialog and attempt == max_retries - 1:
                show_database_error_dialog(
                    "Unexpected Database Error",
                    "An unexpected error occurred while connecting.\n\nSee mysql_connection_error.log for details.",
                    str(e)
                )
            
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
    
    # If we get here, all attempts failed
    error_details = str(last_error) if last_error else "Unknown error"
    error_log_path = get_mysql_error_log_path()
    log_mysql_error(f"\n{'='*70}", level="ERROR")
    log_mysql_error(f"❌ FAILED: All {max_retries} connection attempts failed", level="ERROR")
    log_mysql_error(f"   Last error: {error_details}")
    log_mysql_error(f"   Log file: {error_log_path}")
    log_mysql_error(f"{'='*70}")
    
    raise DatabaseConnectionError(
        f"Failed to connect to MySQL after {max_retries} attempts.\n\n"
        f"Error: {error_details}\n\n"
        f"Please check the error log file:\n"
        f"mysql_connection_error.log\n\n"
        f"Common solutions:\n"
        f"1. Ensure MySQL/XAMPP is running\n"
        f"2. Check db_config.json credentials\n"
        f"3. Create the 'winyfi' database if missing"
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

def save_loop_detection(total_packets, offenders, stats, status, severity_score, interface="Wi-Fi", duration=3, efficiency_metrics=None):
    """
    Save a loop detection result to the database with enhanced fields.
    
    Args:
        total_packets: Total packet count
        offenders: List of offending MAC addresses
        stats: Detection statistics
        status: Detection status ('clean', 'suspicious', 'loop_detected')
        severity_score: Severity score (float or dict)
        interface: Network interface name
        duration: Detection duration in seconds
        efficiency_metrics: Optional dict with efficiency data
    """
    def _save_detection():
        conn = get_connection()
        cursor = conn.cursor()
        
        # Extract efficiency metrics
        cross_subnet = False
        unique_subnets = 0
        unique_macs = 0
        packets_analyzed = total_packets
        sample_rate = 1.0
        efficiency_score = 0.0
        severity_breakdown = None
        
        if efficiency_metrics:
            cross_subnet = efficiency_metrics.get('cross_subnet_detected', False)
            unique_subnets = efficiency_metrics.get('unique_subnets', 0)
            unique_macs = efficiency_metrics.get('unique_macs', 0)
            packets_analyzed = efficiency_metrics.get('packets_analyzed', total_packets)
            sample_rate = efficiency_metrics.get('sample_rate', 1.0)
            
            # Calculate efficiency score
            if packets_analyzed > 0:
                efficiency_score = (total_packets / packets_analyzed) * 100
        
        # If severity_score is a dict (advanced mode), extract breakdown
        actual_severity = severity_score
        if isinstance(severity_score, dict):
            severity_breakdown = severity_score
            actual_severity = severity_score.get('total', 0)
        
        # Prepare offenders data for JSON storage
        offenders_data = {
            "offenders": offenders if isinstance(offenders, list) else [],
            "stats": stats
        }
        
        insert_sql_extended = (
            "INSERT INTO loop_detections "
            "(total_packets, offenders_count, offenders_data, severity_score, network_interface, detection_duration, status, "
            " cross_subnet_detected, unique_subnets, unique_macs, packets_analyzed, sample_rate, efficiency_score, severity_breakdown) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        )
        insert_sql_legacy = (
            "INSERT INTO loop_detections "
            "(total_packets, offenders_count, offenders_data, severity_score, network_interface, detection_duration, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)"
        )
        
        offenders_count = len(offenders) if isinstance(offenders, list) else offenders
        severity_json = json.dumps(severity_breakdown) if severity_breakdown else None
        
        try:
            cursor.execute(insert_sql_extended, (
                total_packets,
                offenders_count,
                json.dumps(offenders_data),
                actual_severity,
                interface,
                duration,
                status,
                cross_subnet,
                unique_subnets,
                unique_macs,
                packets_analyzed,
                sample_rate,
                efficiency_score,
                severity_json
            ))
            conn.commit()
            detection_id = cursor.lastrowid
        except mysql.connector.Error as e:
            # Fallback to legacy schema if extended columns are missing
            if getattr(e, 'errno', None) in (1054, 1136, 1146):
                cursor.execute(insert_sql_legacy, (
                    total_packets,
                    offenders_count,
                    json.dumps(offenders_data),
                    actual_severity,
                    interface,
                    duration,
                    status
                ))
                conn.commit()
                detection_id = cursor.lastrowid
            else:
                raise
        cursor.close()
        conn.close()
        
        logger.info(f"Loop detection saved to database (ID: {detection_id}, severity: {actual_severity:.2f}, cross-subnet: {cross_subnet})")
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
            router_id INT NULL,
            router_name VARCHAR(255),
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

        # Ensure backward-compat columns exist for older databases
        try:
            ensure_network_clients_router_columns()
        except Exception as _e:
            # Non-fatal: table may already have columns or permissions limited
            print(f"  Warning: could not ensure router columns: {_e}")
        
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
        # Ignore "table already exists" errors since we use IF NOT EXISTS
        if "already exists" not in str(e).lower():
            print(f"Error creating network_clients table: {e}")

def ensure_network_clients_router_columns():
    """Ensure router_id and router_name columns exist on network_clients table (for migrations)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # Check and add router_id
        cursor.execute("SHOW COLUMNS FROM network_clients LIKE 'router_id'")
        if cursor.fetchone() is None:
            cursor.execute("ALTER TABLE network_clients ADD COLUMN router_id INT NULL AFTER vendor")
            conn.commit()
        # Check and add router_name
        cursor.execute("SHOW COLUMNS FROM network_clients LIKE 'router_name'")
        if cursor.fetchone() is None:
            cursor.execute("ALTER TABLE network_clients ADD COLUMN router_name VARCHAR(255) NULL AFTER router_id")
            conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        # Log but don't crash
        print(f" Warning: ensure_network_clients_router_columns failed: {e}")

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
        # Ignore "table already exists" errors since we use IF NOT EXISTS
        if "already exists" not in str(e).lower():
            print(f" Error creating connection_history table: {e}")

def save_network_client(mac_address, ip_address=None, hostname=None, vendor=None, 
                       ping_latency=None, device_type=None, notes=None,
                       router_id=None, router_name=None):
    """Save or update a network client in the database."""
    import mysql.connector
    def _upsert(conn, cursor):
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
                router_id = COALESCE(%s, router_id),
                router_name = COALESCE(%s, router_name),
                last_seen = CURRENT_TIMESTAMP,
                is_online = TRUE,
                ping_latency_ms = %s,
                connection_count = connection_count + 1,
                device_type = COALESCE(%s, device_type),
                notes = COALESCE(%s, notes)
            WHERE id = %s
            """
            cursor.execute(update_sql, (ip_address, hostname, vendor, router_id, router_name, ping_latency, 
                                      device_type, notes, client_id))
        else:
            # Insert new client
            insert_sql = """
            INSERT INTO network_clients 
            (mac_address, ip_address, hostname, vendor, router_id, router_name, ping_latency_ms, device_type, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_sql, (mac_address, ip_address, hostname, vendor, 
                                      router_id, router_name, ping_latency, device_type, notes))
            client_id = cursor.lastrowid
        return existing_client[0] if existing_client else client_id
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        client_id = _upsert(conn, cursor)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return client_id
        
    except mysql.connector.Error as e:
        # If missing router_id/router_name columns, attempt to add and retry once
        if getattr(e, 'errno', None) == 1054 or "Unknown column 'router_id'" in str(e) or "Unknown column 'router_name'" in str(e):
            try:
                ensure_network_clients_router_columns()
                conn = get_connection()
                cursor = conn.cursor()
                client_id = _upsert(conn, cursor)
                conn.commit()
                cursor.close()
                conn.close()
                return client_id
            except Exception as inner:
                print(f" Error saving network client after migrating columns: {inner}")
                return None
        else:
            print(f" Error saving network client: {e}")
            return None

def get_network_clients(online_only=False, limit=100, router_id=None):
    """Get network clients from database. Optionally filter by router_id."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        base_sql = "SELECT * FROM network_clients"
        where_clauses = []
        params = []
        if online_only:
            where_clauses.append("is_online = TRUE")
        if router_id is not None:
            where_clauses.append("router_id = %s")
            params.append(router_id)
        if where_clauses:
            base_sql += " WHERE " + " AND ".join(where_clauses)
        base_sql += " ORDER BY last_seen DESC LIMIT %s"
        params.append(limit)
        cursor.execute(base_sql, tuple(params))
        
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


# =============================
# Activity Log Helpers
# =============================
def create_activity_logs_table():
    """Create the activity_logs table if it doesn't exist."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        create_table_sql = """
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            action VARCHAR(255) NOT NULL,
            target VARCHAR(255),
            ip_address VARCHAR(50),
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_user_id (user_id),
            INDEX idx_timestamp (timestamp),
            INDEX idx_action (action),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """

        cursor.execute(create_table_sql)
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("activity_logs table created or already exists")
        return True
    except Exception as e:
        logger.error(f"create_activity_logs_table error: {e}")
        return False


def log_activity(user_id, action, target=None, ip_address=None):
    """
    Log a user activity.
    
    Args:
        user_id (int): User ID performing the action
        action (str): Action performed (e.g., "Login", "Logout", "Add Router", "Delete User")
        target (str): Target of the action (e.g., router name, username)
        ip_address (str): IP address of the user
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        sql = """
        INSERT INTO activity_logs (user_id, action, target, ip_address)
        VALUES (%s, %s, %s, %s)
        """
        
        cursor.execute(sql, (user_id, action, target, ip_address))
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Activity logged: User {user_id} - {action} - {target}")
        return True
    except Exception as e:
        logger.error(f"log_activity error: {e}")
        return False


def get_activity_logs(limit=100, user_id=None, action_filter=None, search_term=None):
    """
    Get activity logs with optional filtering.
    
    Args:
        limit (int): Maximum number of logs to return
        user_id (int): Filter by specific user ID
        action_filter (str): Filter by action type
        search_term (str): Search in action or target fields
    
    Returns:
        list: List of activity log dictionaries
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Build dynamic query
        where_clauses = []
        params = []
        
        if user_id:
            where_clauses.append("al.user_id = %s")
            params.append(user_id)
        
        if action_filter:
            where_clauses.append("al.action LIKE %s")
            params.append(f"%{action_filter}%")
        
        if search_term:
            where_clauses.append("(al.action LIKE %s OR al.target LIKE %s)")
            params.append(f"%{search_term}%")
            params.append(f"%{search_term}%")
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        sql = f"""
        SELECT 
            al.id,
            al.user_id,
            al.action,
            al.target,
            al.ip_address,
            al.timestamp,
            CONCAT(u.first_name, ' ', u.last_name) as user_name,
            u.username,
            u.role
        FROM activity_logs al
        LEFT JOIN users u ON al.user_id = u.id
        WHERE {where_sql}
        ORDER BY al.timestamp DESC
        LIMIT %s
        """
        
        params.append(limit)
        cursor.execute(sql, tuple(params))
        results = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return results
    except Exception as e:
        logger.error(f"get_activity_logs error: {e}")
        return []


def get_activity_stats():
    """
    Get activity statistics.
    
    Returns:
        dict: Statistics about activities
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Total activities
        cursor.execute("SELECT COUNT(*) as total FROM activity_logs")
        total = cursor.fetchone()['total']
        
        # Activities by action type
        cursor.execute("""
            SELECT action, COUNT(*) as count 
            FROM activity_logs 
            GROUP BY action 
            ORDER BY count DESC
        """)
        by_action = cursor.fetchall()
        
        # Recent activities (last 24 hours)
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM activity_logs 
            WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
        """)
        recent = cursor.fetchone()['count']
        
        cursor.close()
        conn.close()
        
        return {
            'total': total,
            'by_action': by_action,
            'recent_24h': recent
        }
    except Exception as e:
        logger.error(f"get_activity_stats error: {e}")
        return {'total': 0, 'by_action': [], 'recent_24h': 0}