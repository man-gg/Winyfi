"""
Service Manager for WinyFi
Manages Flask API (app.py) and UniFi API (unifi_api.py) as background processes
"""

import subprocess
import sys
import os
import json
from pathlib import Path
import threading
import time
import requests
import logging
import socket
import re
from collections import deque
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Runtime error log will be created in ServiceManager.__init__()
runtime_error_log = None
runtime_error_handler = None


class ServiceManager:
    """Manages background API services for WinyFi"""
    
    def __init__(self):
        # Executable dir = where logs/config should live
        # Bundle dir     = where packaged resources (server scripts) live in one-file builds (sys._MEIPASS)
        if getattr(sys, 'frozen', False):
            self.exec_dir = Path(sys.executable).parent
            self.bundle_dir = Path(getattr(sys, '_MEIPASS', self.exec_dir))
        else:
            self.exec_dir = Path(__file__).parent
            self.bundle_dir = self.exec_dir

        # Use exec_dir for config/logs (stable), bundle_dir for locating scripts
        self.app_dir = self.exec_dir
        self.config_file = self.exec_dir / "service_config.json"
        self.server_config_file = self.exec_dir / "server_config.json"
        
        # Log streaming state
        self.log_buffers = {}  # service_name -> deque of log lines
        self.log_positions = {}  # service_name -> file position
        self.log_locks = {}  # service_name -> threading.Lock
        self.stderr_threads = {}  # service_name -> stderr reader thread
        
        # Auto-detect script paths
        flask_script = self._find_script('run_app.py')
        unifi_script = self._find_script('run_unifi_api.py')
        
        # Load server configuration for API endpoints
        api_host = self._load_api_host()
        unifi_host = self._load_unifi_host()
        
        # Service definitions
        self.services = {
            'flask_api': {
                'name': 'Flask API',
                'script': str(flask_script) if flask_script else None,
                'port': 5000,
                'host': api_host,
                'health_endpoint': f'http://{api_host}:5000/api/health',
                'process': None,
                'enabled': False,
                'auto_start': False,
                'stdout_file': None,
                'stderr_file': None
            },
            'unifi_api': {
                'name': 'UniFi API',
                'script': str(unifi_script) if unifi_script else None,
                'port': 5001,
                'host': unifi_host,
                'health_endpoint': f'http://{unifi_host}:5001/api/health',
                'process': None,
                'enabled': False,
                'auto_start': False,
                'stdout_file': None,
                'stderr_file': None,
                'controller_url': 'http://127.0.0.1:8080',
                'username': 'admin',
                'password': 'admin123',
                'site': 'default',
                'ssl_verify': False
            }
        }
        
        # Load saved configuration
        self.load_config()
        
        # Ensure logs directory exists
        self.logs_dir = self.exec_dir / "logs"
        self.logs_dir.mkdir(exist_ok=True)
        
        # Create runtime error log in logs directory (accessible in dist builds)
        global runtime_error_log, runtime_error_handler
        runtime_error_log = self.logs_dir / "winyfi_runtime_error.log"
        if runtime_error_handler is None:
            runtime_error_handler = logging.FileHandler(runtime_error_log, mode='a', encoding='utf-8')
            runtime_error_handler.setLevel(logging.ERROR)
            runtime_error_formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s')
            runtime_error_handler.setFormatter(runtime_error_formatter)
            logger.addHandler(runtime_error_handler)
            logger.info(f"[SUCCESS] Runtime error logging enabled: {runtime_error_log}")
        
        # Cleanup any orphaned processes on startup
        self._cleanup_orphaned_processes()
    
    def _load_api_host(self):
        """Load Flask API host from server_config.json or use localhost"""
        try:
            if self.server_config_file.exists():
                with open(self.server_config_file, 'r') as f:
                    config = json.load(f)
                    host = config.get('ip', 'localhost')
                    logger.debug(f"[SUCCESS] Flask API host loaded from config: {host}")
                    return host
        except Exception as e:
            logger.debug(f"Error loading API host config: {e}")
        
        logger.debug("Using localhost for Flask API")
        return 'localhost'
    
    def _load_unifi_host(self):
        """Load UniFi API host from config or detect from environment"""
        try:
            # Try to load from server_config.json first
            if self.server_config_file.exists():
                with open(self.server_config_file, 'r') as f:
                    config = json.load(f)
                    # Check if there's a specific unifi_ip or unifi_host
                    if 'unifi_ip' in config:
                        host = config.get('unifi_ip', 'localhost')
                        logger.debug(f"[SUCCESS] UniFi API host loaded from config: {host}")
                        return host
                    elif 'unifi_host' in config:
                        host = config.get('unifi_host', 'localhost')
                        logger.debug(f"[SUCCESS] UniFi API host loaded from config: {host}")
                        return host
        except Exception as e:
            logger.debug(f"Error loading UniFi host config: {e}")
        
        # Check if UniFi API is running on localhost
        try:
            response = requests.get('http://localhost:5001/api/health', timeout=1)
            if response.ok:
                logger.debug("[SUCCESS] UniFi API detected on localhost")
                return 'localhost'
        except Exception:
            pass
        
        # Check if there's a network discovery hint
        try:
            # Try to find UniFi controller on the network
            if self.server_config_file.exists():
                with open(self.server_config_file, 'r') as f:
                    config = json.load(f)
                    # Use the same subnet as Flask API
                    api_ip = config.get('ip', 'localhost')
                    if api_ip != 'localhost':
                        logger.debug(f"Using same host as Flask API for UniFi: {api_ip}")
                        return api_ip
        except Exception as e:
            logger.debug(f"Error detecting UniFi host: {e}")
        
        logger.debug("Using localhost for UniFi API (fallback)")
        return 'localhost'
    
    def _find_script(self, script_name):
        """
        Auto-detect script location by searching common directories.
        Returns Path object if found, None otherwise.
        """
        search_paths = [
            self.bundle_dir / 'server' / script_name,  # packaged server/run_app.py
            self.bundle_dir / script_name,              # Direct in bundle
            self.bundle_dir / 'scripts' / script_name,  # scripts/ subdirectory
        ]
        
        for path in search_paths:
            if path.exists():
                logger.debug(f"[SUCCESS] Found {script_name} at {path}")
                # Return relative path for portability
                try:
                    return path.relative_to(self.app_dir)
                except ValueError:
                    return path
        
        logger.warning(f"[WARNING] Could not auto-detect {script_name}, using default path")
        return None
    
    def _is_port_in_use(self, port):
        """Check if a port is already in use"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                result = s.connect_ex(('localhost', port))
                return result == 0
        except Exception:
            return False
    
    def _cleanup_orphaned_processes(self):
        """Force-kill any zombie processes still occupying our ports"""
        for service_name, service in self.services.items():
            # Initialize log tracking for this service
            self.log_buffers[service_name] = deque(maxlen=1000)  # Keep last 1000 lines
            self.log_positions[service_name] = 0
            self.log_locks[service_name] = threading.Lock()
            
            port = service['port']
            if self._is_port_in_use(port):
                logger.warning(f"[WARNING] Port {port} is occupied but no process object exists for {service_name}. Attempting cleanup...")
                # Try to find and kill process using the port
                try:
                    if sys.platform == 'win32':
                        import subprocess
                        # Use netstat to find PID using the port
                        result = subprocess.run(
                            ['netstat', '-ano'],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        for line in result.stdout.split('\n'):
                            if f':{port}' in line and 'LISTENING' in line:
                                parts = line.split()
                                if parts:
                                    pid = parts[-1]
                                    try:
                                        subprocess.run(['taskkill', '/PID', pid, '/F'], timeout=3)
                                        logger.info(f"[SUCCESS] Killed orphaned process {pid} on port {port}")
                                    except Exception as e:
                                        logger.warning(f"[WARNING] Could not kill process {pid}: {e}")
                except Exception as e:
                    logger.warning(f"[WARNING] Cleanup attempt for port {port} failed: {e}")
    
    def _force_kill_port(self, port):
        """Force kill any process using the specified port"""
        if sys.platform == 'win32':
            try:
                result = subprocess.run(
                    ['netstat', '-ano'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                for line in result.stdout.split('\n'):
                    if f':{port}' in line and 'LISTENING' in line:
                        parts = line.split()
                        if parts and len(parts) > 0:
                            pid = parts[-1]
                            try:
                                subprocess.run(['taskkill', '/PID', pid, '/F'], timeout=3)
                                logger.info(f"🔨 Force-killed process {pid} on port {port}")
                            except Exception as e:
                                logger.debug(f"Could not force-kill {pid}: {e}")
            except Exception as e:
                logger.debug(f"Port kill attempt failed: {e}")
        else:
            # For Linux/Mac
            try:
                result = subprocess.run(
                    ['lsof', '-i', f':{port}'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                for line in result.stdout.split('\n')[1:]:
                    if line.strip():
                        parts = line.split()
                        if len(parts) > 1:
                            pid = parts[1]
                            try:
                                subprocess.run(['kill', '-9', pid], timeout=3)
                                logger.info(f"🔨 Force-killed process {pid} on port {port}")
                            except Exception as e:
                                logger.debug(f"Could not force-kill {pid}: {e}")
            except Exception as e:
                logger.debug(f"Port kill attempt failed: {e}")
    
    def _read_stderr(self, service_name, process, stderr_log_path, stderr_file):
        """Asynchronously read stderr from process and log all errors"""
        service = self.services.get(service_name)
        if not service or not process.stderr:
            return
        
        try:
            for line in iter(process.stderr.readline, ''):
                if not line:
                    break
                
                line = line.rstrip()
                if line:
                    # Write to stderr file
                    try:
                        stderr_file.write(f"{line}\n")
                        stderr_file.flush()
                        os.fsync(stderr_file.fileno())
                    except:
                        pass
                    
                    # Log errors and exceptions to runtime error log
                    line_lower = line.lower()
                    if any(keyword in line_lower for keyword in ['error', 'exception', 'traceback', 'failed', 'critical', 'modulenotfounderror', 'keyerror', 'importerror']):
                        logger.error(f"[{service_name}] {line}")
                        try:
                            with open(runtime_error_log, 'a', encoding='utf-8') as f:
                                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                                f.write(f"[{timestamp}] [{service_name}] {line}\n")
                                f.flush()
                                os.fsync(f.fileno())
                        except Exception as log_err:
                            logger.debug(f"Failed to write to runtime error log: {log_err}")
        except Exception as e:
            logger.debug(f"Error reading stderr for {service_name}: {e}")
        finally:
            try:
                process.stderr.close()
            except:
                pass
    
    def _wait_for_service_ready(self, service_name, timeout=10):
        """Wait for service to be ready and responding to health checks"""
        service = self.services.get(service_name)
        if not service:
            return False
        
        start_time = time.time()
        port_opened = False
        last_check_time = 0
        check_interval = 0.2  # Check every 200ms
        
        while (time.time() - start_time) < timeout:
            elapsed = time.time() - start_time
            
            # Check if process is still alive
            if service['process'] and service['process'].poll() is not None:
                logger.error(f"[ERROR] {service['name']} process died during startup (exit code: {service['process'].poll()})")
                return False
            
            # Check if port is open (every check_interval)
            current_time = time.time()
            if (current_time - last_check_time) >= check_interval:
                last_check_time = current_time
                
                if self._is_port_in_use(service['port']):
                    if not port_opened:
                        logger.info(f"[INFO] Port {service['port']} is now open for {service['name']}")
                        port_opened = True
                    
                    # Port is open, try health check
                    try:
                        response = requests.get(service['health_endpoint'], timeout=1)
                        if response.ok:
                            logger.info(f"[SUCCESS] {service['name']} is ready and healthy")
                            return True
                    except Exception as e:
                        logger.debug(f"[DEBUG] Health check failed: {e}")
                else:
                    if port_opened:
                        logger.warning(f"[WARNING] Port {service['port']} closed unexpectedly")
                        port_opened = False
            
            time.sleep(0.1)  # Sleep 100ms between iterations
        
        # Timeout reached
        if port_opened:
            # Port opened but health check failed - service might still be initializing
            logger.warning(f"⏰ {service['name']} port opened but health check failed after {timeout}s")
            return True  # Consider it ready anyway since port is responding
        else:
            logger.error(f"❌ {service['name']} failed to start - port {service['port']} never opened after {timeout}s")
            return False
    
    def load_config(self):
        """Load service configuration from JSON file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    for service_name, saved_data in config.items():
                        if service_name in self.services:
                            self.services[service_name]['enabled'] = saved_data.get('enabled', False)
                            self.services[service_name]['auto_start'] = saved_data.get('auto_start', False)
                            # Load UniFi-specific configuration
                            if service_name == 'unifi_api':
                                self.services[service_name]['controller_url'] = saved_data.get('controller_url', 'http://127.0.0.1:8080')
                                self.services[service_name]['username'] = saved_data.get('username', 'admin')
                                self.services[service_name]['password'] = saved_data.get('password', 'admin123')
                                self.services[service_name]['site'] = saved_data.get('site', 'default')
                                self.services[service_name]['ssl_verify'] = saved_data.get('ssl_verify', False)
                logger.info("[SUCCESS] Service configuration loaded")
        except Exception as e:
            logger.warning(f"[WARNING] Could not load service config: {e}")
    
    def save_config(self):
        """Save service configuration to JSON file"""
        try:
            config = {}
            for service_name, data in self.services.items():
                service_config = {
                    'enabled': data['enabled'],
                    'auto_start': data['auto_start']
                }
                # Save UniFi-specific configuration
                if service_name == 'unifi_api':
                    service_config.update({
                        'controller_url': data.get('controller_url', 'http://127.0.0.1:8080'),
                        'username': data.get('username', 'admin'),
                        'password': data.get('password', 'admin123'),
                        'site': data.get('site', 'default'),
                        'ssl_verify': data.get('ssl_verify', False)
                    })
                config[service_name] = service_config
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info("[SUCCESS] Service configuration saved")
        except Exception as e:
            logger.error(f"[ERROR] Error saving config: {e}")
    
    def _start_service_thread(self, service_name, script_path, stdout_file, stderr_file):
        """
        Start a Flask service in a separate thread (used in frozen builds without system Python).
        Returns a mock process object that behaves like subprocess.Popen.
        """
        class ThreadProcess:
            """Mock process object for thread-based service"""
            def __init__(self, name, thread, stop_event, return_ref):
                self.name = name
                self.thread = thread
                self.stop_event = stop_event
                self._return_ref = return_ref
                self.pid = id(thread)  # Use thread ID as fake PID
                self.returncode = None
                
            def poll(self):
                """Check if thread is still running"""
                if self.thread.is_alive():
                    return None
                if self.returncode is None:
                    self.returncode = self._return_ref.get('code', 0)
                return self.returncode
                
            def terminate(self):
                """Request a graceful stop"""
                self.stop_event.set()
                
            def kill(self):
                """Force stop the thread"""
                self.stop_event.set()
                
            def wait(self, timeout=None):
                """Mirror subprocess.Popen.wait for compatibility"""
                self.thread.join(timeout)
                if self.thread.is_alive():
                    raise subprocess.TimeoutExpired(cmd=self.name, timeout=timeout)
                if self.returncode is None:
                    self.returncode = self._return_ref.get('code', 0)
                return self.returncode
        
        # Create stop event for the thread
        stop_event = threading.Event()
        thread_return = {'code': None}
        
        def run_flask_service():
            """Run Flask service in thread"""
            try:
                # Clean environment to prevent Flask issues
                for key in list(os.environ.keys()):
                    if 'WERKZEUG' in key:
                        del os.environ[key]
                
                # Set headless mode and Flask config
                os.environ['DISPLAY'] = ''
                os.environ['MPLBACKEND'] = 'Agg'
                os.environ['FLASK_DEBUG'] = '0'
                os.environ['FLASK_ENV'] = 'production'
                # Do NOT set WERKZEUG_RUN_MAIN - it triggers reloader mode
                
                # Change to server directory for imports
                old_cwd = os.getcwd()
                server_dir = self.bundle_dir / 'server'
                if server_dir.exists():
                    os.chdir(server_dir)
                    if str(server_dir) not in sys.path:
                        sys.path.insert(0, str(server_dir))
                
                # Also add parent dir for utility imports
                parent_dir = self.bundle_dir
                if str(parent_dir) not in sys.path:
                    sys.path.insert(0, str(parent_dir))
                
                # Import the appropriate module
                if 'flask' in service_name or 'app' in str(script_path):
                    from app import create_app  # type: ignore
                    app = create_app()
                    port = 5000
                elif 'unifi' in service_name:
                    import unifi_api  # type: ignore
                    app = unifi_api.app
                    port = 5001
                else:
                    stdout_file.write(f"[ERROR] Unknown service type: {service_name}\n")
                    return
                
                # Restore working directory
                os.chdir(old_cwd)
                
                # Log startup
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                stdout_file.write(f"[{timestamp}] [INFO] Starting {service_name} in-process (thread mode)\n")
                stdout_file.flush()
                
                # Final cleanup: ensure WERKZEUG_SERVER_FD doesn't exist before app.run()
                # This prevents KeyError in frozen PyInstaller environments
                if 'WERKZEUG_SERVER_FD' in os.environ:
                    del os.environ['WERKZEUG_SERVER_FD']
                
                # Run Flask with a stoppable server so stop_event can shut it down
                try:
                    from werkzeug.serving import make_server
                except Exception as import_err:
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                    stdout_file.write(f"[{timestamp}] [ERROR] Failed to import werkzeug.make_server: {import_err}\n")
                    stderr_file.write(f"[{timestamp}] [ERROR] {import_err}\n")
                    stdout_file.flush()
                    stderr_file.flush()
                    thread_return['code'] = 1
                    return
                try:
                    httpd = make_server("0.0.0.0", port, app, threaded=True)
                    httpd.timeout = 1  # Prevent indefinite block so we can honor stop_event
                except Exception as server_err:
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                    stdout_file.write(f"[{timestamp}] [ERROR] Failed to start internal server: {server_err}\n")
                    stderr_file.write(f"[{timestamp}] [ERROR] {server_err}\n")
                    stdout_file.flush()
                    stderr_file.flush()
                    thread_return['code'] = 1
                    return

                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                stdout_file.write(f"[{timestamp}] [INFO] Internal server running (thread mode, stoppable)\n")
                stdout_file.flush()

                try:
                    while not stop_event.is_set():
                        httpd.handle_request()
                    thread_return['code'] = 0
                except Exception as run_err:
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                    stdout_file.write(f"[{timestamp}] [ERROR] Internal server crashed: {run_err}\n")
                    stderr_file.write(f"[{timestamp}] [ERROR] {run_err}\n")
                    thread_return['code'] = 1
                finally:
                    try:
                        httpd.server_close()
                    except Exception:
                        pass
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                    stdout_file.write(f"[{timestamp}] [INFO] Internal server stopped\n")
                    stdout_file.flush()
                
            except Exception as e:
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                stdout_file.write(f"[{timestamp}] [ERROR] Service crashed: {e}\n")
                stderr_file.write(f"[{timestamp}] [ERROR] {e}\n")
                import traceback
                traceback.print_exc(file=stderr_file)
                stdout_file.flush()
                stderr_file.flush()
        
        # Start thread
        thread = threading.Thread(target=run_flask_service, daemon=True)
        thread.start()
        
        # Return mock process
        return ThreadProcess(service_name, thread, stop_event, thread_return)
    
    def start_service(self, service_name):
        """Start a specific service"""
        if service_name not in self.services:
            error_msg = f"[ERROR] Unknown service: {service_name}"
            logger.error(error_msg)
            try:
                with open(runtime_error_log, 'a', encoding='utf-8') as f:
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                    f.write(f"[{timestamp}] [{service_name}] {error_msg}\n")
                    f.flush()
            except:
                pass
            return False
        
        service = self.services[service_name]
        
        # Check if script is configured
        if service['script'] is None:
            error_msg = f"[ERROR] Script not configured for {service['name']}"
            logger.error(error_msg)
            logger.error(f"[INFO] Expected script locations:")
            logger.error(f"   - {self.bundle_dir / 'server' / ('run_app.py' if 'flask' in service_name else 'run_unifi_api.py')}")
            logger.error(f"   - {self.bundle_dir / ('run_app.py' if 'flask' in service_name else 'run_unifi_api.py')}")
            try:
                with open(runtime_error_log, 'a', encoding='utf-8') as f:
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                    f.write(f"[{timestamp}] [{service_name}] {error_msg}\n")
                    f.write(f"[{timestamp}] [{service_name}] Check server/ directory for run scripts\n")
                    f.flush()
            except:
                pass
            return False
        
        # Check if already running
        if service['process'] is not None and service['process'].poll() is None:
            logger.info(f"[INFO] {service['name']} is already running")
            return True
        
        # Check if port is already in use
        if self._is_port_in_use(service['port']):
            logger.warning(f"[WARNING] Port {service['port']} already in use for {service['name']}")
            # Try to get existing process info
            try:
                response = requests.get(service['health_endpoint'], timeout=1)
                if response.ok:
                    logger.info(f"[INFO] {service['name']} already running on port {service['port']}")
                    service['enabled'] = True
                    return True
            except:
                pass
            logger.error(f"[ERROR] Port {service['port']} occupied but service not responding")
            return False
        
        script_path = self.bundle_dir / service['script']
        
        if not script_path.exists():
            error_msg = f"[ERROR] Script not found: {script_path}"
            logger.error(error_msg)
            logger.error(f"[WARNING] Please ensure {service['name']} script is in one of these locations:")
            logger.error(f"   - {self.bundle_dir / 'server' / service['script'].split('/')[-1]}")
            logger.error(f"   - {self.bundle_dir / service['script'].split('/')[-1]}")
            logger.error(f"   - {self.bundle_dir / 'scripts' / service['script'].split('/')[-1]}")
            # Write to runtime error log
            try:
                with open(runtime_error_log, 'a', encoding='utf-8') as f:
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                    f.write(f"[{timestamp}] [{service_name}] {error_msg}\n")
                    f.write(f"[{timestamp}] [{service_name}] Script locations checked:\n")
                    f.write(f"[{timestamp}] [{service_name}]   - {self.app_dir / 'server' / service['script'].split('/')[-1]}\n")
                    f.write(f"[{timestamp}] [{service_name}]   - {self.app_dir / service['script'].split('/')[-1]}\n")
                    f.flush()
                    os.fsync(f.fileno())
            except:
                pass
            return False
        
        try:
            # Log resolved paths for debugging
            logger.info(f"[DEBUG] Starting {service['name']}:")
            logger.info(f"  Python executable: {sys.executable}")
            logger.info(f"  Script path: {script_path}")
            logger.info(f"  Working directory: {self.app_dir}")
            
            # Prepare startup configuration for Windows
            startupinfo = None
            creationflags = 0
            
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                creationflags = subprocess.CREATE_NO_WINDOW
            
            # Setup log files
            log_name = service_name.replace('_', '-')
            stdout_log = self.logs_dir / f"{log_name}.log"
            stderr_log = self.logs_dir / f"{log_name}-error.log"
            
            try:
                stdout_file = open(stdout_log, 'a', encoding='utf-8')
                stderr_file = open(stderr_log, 'a', encoding='utf-8')
            except Exception as file_err:
                logger.error(f"[ERROR] Failed to open log files: {file_err}")
                raise
            
            # Write startup marker with clear status
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            stdout_file.write(f"\n{'='*80}\n")
            stdout_file.write(f"[{timestamp}] SUCCESS [START] STARTING {service['name'].upper()}\n")
            stdout_file.write(f"[{timestamp}] INFO    [SCRIPT] Script: {service['script']}\n")
            stdout_file.write(f"[{timestamp}] INFO    [PORT] Port: {service['port']}\n")
            stdout_file.write(f"[{timestamp}] INFO    [PYTHON] Python: {sys.executable}\n")
            stdout_file.write(f"[{timestamp}] INFO    [CWD] Working Dir: {self.app_dir}\n")
            stdout_file.write(f"[{timestamp}] INFO    [PID] Process ID: Starting...\n")
            stdout_file.write(f"{'='*80}\n")
            stdout_file.flush()
            
            # Environment variables - disable debug and reloader for Flask
            env = os.environ.copy()
            env['FLASK_DEBUG'] = '0'
            env['FLASK_ENV'] = 'production'
            env['WERKZEUG_RUN_MAIN'] = 'true'
            # Prevent Flask reloader from starting
            env.pop('WERKZEUG_SERVER_FD', None)
            # Prevent GUI from launching (headless mode)
            env['DISPLAY'] = ''
            env['MPLBACKEND'] = 'Agg'
            
            # Set UniFi API environment variables from service config
            if service_name == 'unifi_api':
                env['UNIFI_URL'] = service.get('controller_url', 'http://127.0.0.1:8080')
                env['UNIFI_USER'] = service.get('username', 'admin')
                env['UNIFI_PASS'] = service.get('password', 'admin123')
                env['UNIFI_SITE'] = service.get('site', 'default')
                env['UNIFI_VERIFY'] = 'true' if service.get('ssl_verify', False) else 'false'
            
            # CRITICAL FIX: In frozen/packaged mode, ALWAYS use thread mode
            # External Python cannot access PyInstaller bundled modules
            python_exe = sys.executable
            if getattr(sys, 'frozen', False):
                # In frozen mode, MUST run in-process as threads
                # System Python cannot access bundled modules in _MEIPASS
                logger.info(f"[INFO] Frozen mode detected - using in-process threading")
                python_exe = None
            else:
                # Development mode - can use subprocess with regular Python
                logger.info(f"[INFO] Dev mode - using subprocess with Python: {python_exe}")
            
            # Start the process with PIPE for stderr to read asynchronously
            try:
                if python_exe is None:
                    # Run in-process as a thread (fallback for frozen builds without system Python)
                    process = self._start_service_thread(service_name, script_path, stdout_file, stderr_file)
                else:
                    process = subprocess.Popen(
                        [python_exe, str(script_path)],
                        stdout=stdout_file,
                        stderr=subprocess.PIPE,  # Capture stderr separately for monitoring
                        startupinfo=startupinfo,
                        creationflags=creationflags,
                        cwd=str(self.app_dir),
                        env=env,
                        text=True,
                        bufsize=1,  # Line buffering
                        errors='replace'  # Replace invalid UTF-8 with replacement char
                    )
            except Exception as popen_err:
                error_msg = f"[ERROR] subprocess.Popen failed: {type(popen_err).__name__}: {popen_err}"
                logger.error(error_msg)
                stdout_file.write(f"\n{error_msg}\n")
                stdout_file.flush()
                # Also write to runtime error log
                try:
                    with open(runtime_error_log, 'a', encoding='utf-8') as f:
                        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                        f.write(f"[{timestamp}] [{service_name}] {error_msg}\n")
                        f.flush()
                        os.fsync(f.fileno())
                except:
                    pass
                stdout_file.close()
                stderr_file.close()
                raise
            
            # Store process AND file handles so we can close them later
            service['process'] = process
            service['stdout_file'] = stdout_file
            service['stderr_file'] = stderr_file
            service['enabled'] = True
            
            # Start async stderr reader thread
            try:
                stderr_thread = threading.Thread(
                    target=self._read_stderr,
                    args=(service_name, process, stderr_log, stderr_file),
                    daemon=True
                )
                stderr_thread.start()
                self.stderr_threads[service_name] = stderr_thread
            except Exception as thread_err:
                logger.error(f"[ERROR] Failed to start stderr reader thread: {thread_err}")
                # Continue anyway, stderr just won't be monitored
            
            # Write process started message to log
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            stdout_file.write(f"[{timestamp}] SUCCESS [STARTED] {service['name'].upper()} PROCESS STARTED (PID: {process.pid})\n")
            stdout_file.write(f"[{timestamp}] INFO    [WAIT] Waiting for service to be ready...\n")
            stdout_file.flush()
            try:
                os.fsync(stdout_file.fileno())  # Force write to disk
            except:
                pass
            
            logger.info(f"[START] Started {service['name']} (PID: {process.pid})")
            logger.info(f"[LOGS] Logs: {stdout_log}")
            
            # Wait for service to be ready (non-blocking for UI)
            logger.info(f"[WAIT] Waiting for {service['name']} to be ready...")
            if self._wait_for_service_ready(service_name, timeout=15):
                # Write ready confirmation to log
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                stdout_file.write(f"[{timestamp}] SUCCESS [READY] {service['name'].upper()} IS READY AND ACCEPTING CONNECTIONS\n")
                stdout_file.write(f"[{timestamp}] INFO    [HEALTH] Health endpoint responding at {service['health_endpoint']}\n")
                stdout_file.write(f"{'='*80}\n\n")
                stdout_file.flush()
                try:
                    os.fsync(stdout_file.fileno())
                except:
                    pass
                # Save configuration after successful startup
                self.save_config()
                return True
            else:
                # Check if process crashed
                if process.poll() is not None:
                    exit_code = process.returncode
                    error_msg = f"[ERROR] {service['name']} crashed during startup (exit code: {exit_code})"
                    logger.error(error_msg)
                    # Write to runtime error log
                    try:
                        with open(runtime_error_log, 'a', encoding='utf-8') as f:
                            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                            f.write(f"[{timestamp}] [{service_name}] {error_msg}\n")
                            f.flush()
                            os.fsync(f.fileno())
                    except:
                        pass
                    stdout_file.write(f"\n{error_msg}\n")
                    stdout_file.flush()
                    
                    # Read last few lines of error log
                    try:
                        stderr_file.flush()
                        with open(stderr_log, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = f.readlines()
                            if lines:
                                last_error = lines[-1].strip()
                                logger.error(f"Last error: {last_error}")
                                stdout_file.write(f"Last stderr: {last_error}\n")
                    except:
                        pass
                else:
                    logger.warning(f"[WARNING] {service['name']} started but not responding to health checks")
                    # Service might still be initializing, mark as enabled anyway
                    self.save_config()
                    return True
                return False
            
        except Exception as e:
            import traceback
            error_msg = f"[ERROR] Error starting {service['name']}: {type(e).__name__}: {e}\nTraceback: {traceback.format_exc()}"
            logger.error(error_msg)
            
            # Also write to runtime error log
            try:
                with open(runtime_error_log, 'a', encoding='utf-8') as f:
                    f.write(f"\n{'='*80}\n")
                    f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] STARTUP FAILURE: {service['name']}\n")
                    f.write(f"Command: {sys.executable} {script_path}\n")
                    f.write(f"CWD: {self.app_dir}\n")
                    f.write(f"{error_msg}\n")
                    f.write(f"{'='*80}\n")
            except:
                pass
            
            return False
    
    def stop_service(self, service_name):
        """Stop a specific service with proper cleanup"""
        if service_name not in self.services:
            logger.error(f"[ERROR] Unknown service: {service_name}")
            return False
        
        service = self.services[service_name]
        process = service['process']
        port = service['port']
        
        if process is None:
            # Process is None, but check if something is still using the port
            if self._is_port_in_use(port):
                logger.warning(f"[WARNING] {service['name']} port {port} still in use, force killing any process on that port...")
                self._force_kill_port(port)
            logger.info(f"[INFO] {service['name']} is not running")
            service['enabled'] = False
            self.save_config()
            return True
        
        try:
            # Write shutdown message to log file BEFORE terminating
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            log_file = self.get_log_file_path(service_name)
            
            # Write to both the open file handle and directly to the file (for redundancy)
            if service.get('stdout_file'):
                try:
                    service['stdout_file'].write(f"\n{'='*80}\n")
                    service['stdout_file'].write(f"[{timestamp}] WARNING [SHUTDOWN] SHUTDOWN REQUESTED FOR {service['name'].upper()}\n")
                    service['stdout_file'].write(f"[{timestamp}] INFO    [STOP] Terminating process (PID: {process.pid})...\n")
                    service['stdout_file'].flush()
                    os.fsync(service['stdout_file'].fileno())  # Force write to disk
                except Exception as e:
                    logger.debug(f"Error writing to stdout file: {e}")
            
            logger.info(f"Stopping {service['name']} (PID: {process.pid})...")
            
            # Check if process is still alive
            if process.poll() is not None:
                logger.info(f"[INFO] {service['name']} process already terminated")
                # Process is already dead
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                if service.get('stdout_file'):
                    try:
                        service['stdout_file'].write(f"[{timestamp}] STOPPED [DEAD] {service['name'].upper()} ALREADY TERMINATED\n")
                        service['stdout_file'].write(f"{'='*80}\n\n")
                        service['stdout_file'].flush()
                        os.fsync(service['stdout_file'].fileno())
                    except Exception as e:
                        logger.debug(f"Error writing to log: {e}")
            else:
                # Process is running, try to terminate it
                try:
                    # Gracefully terminate first
                    process.terminate()
                    
                    try:
                        # Wait for graceful shutdown (timeout 5 seconds)
                        process.wait(timeout=5)
                        
                        # Write stopped message to log before closing file
                        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                        if service.get('stdout_file'):
                            try:
                                service['stdout_file'].write(f"[{timestamp}] STOPPED [DONE] {service['name'].upper()} TERMINATED GRACEFULLY\n")
                                service['stdout_file'].write(f"[{timestamp}] INFO    [SUCCESS] Service shutdown complete\n")
                                service['stdout_file'].write(f"{'='*80}\n\n")
                                service['stdout_file'].flush()
                                os.fsync(service['stdout_file'].fileno())
                            except Exception as e:
                                logger.debug(f"Error writing to log: {e}")
                        
                        logger.info(f"[SUCCESS] {service['name']} terminated gracefully")
                    except subprocess.TimeoutExpired:
                        # Force kill if not stopped
                        logger.warning(f"[WARNING] {service['name']} did not stop gracefully, force killing...")
                        process.kill()
                        try:
                            process.wait(timeout=2)
                            # Write force kill message
                            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                            if service.get('stdout_file'):
                                try:
                                    service['stdout_file'].write(f"[{timestamp}] STOPPED [KILLED] {service['name'].upper()} FORCE KILLED\n")
                                    service['stdout_file'].write(f"[{timestamp}] INFO    [SUCCESS] Service shutdown complete\n")
                                    service['stdout_file'].write(f"{'='*80}\n\n")
                                    service['stdout_file'].flush()
                                    os.fsync(service['stdout_file'].fileno())
                                except Exception as e:
                                    logger.debug(f"Error writing to log: {e}")
                            logger.info(f"[SUCCESS] {service['name']} force killed")
                        except subprocess.TimeoutExpired:
                            logger.error(f"[ERROR] Could not kill {service['name']} process")
                except Exception as e:
                    logger.error(f"[ERROR] Error terminating process: {e}")
                    # Try force kill as last resort
                    try:
                        process.kill()
                        process.wait(timeout=2)
                    except Exception as kill_error:
                        logger.error(f"[ERROR] Force kill failed: {kill_error}")
            
            # Close and cleanup file handles AFTER process is dead
            try:
                if service.get('stdout_file'):
                    service['stdout_file'].close()
                    logger.debug(f"Closed stdout for {service['name']}")
            except Exception as e:
                logger.debug(f"Error closing stdout: {e}")
            
            try:
                if service.get('stderr_file'):
                    service['stderr_file'].close()
                    logger.debug(f"Closed stderr for {service['name']}")
            except Exception as e:
                logger.debug(f"Error closing stderr: {e}")
            
            # Cleanup port (wait for OS to release it)
            for attempt in range(5):
                if not self._is_port_in_use(port):
                    logger.info(f"[SUCCESS] Port {port} is now available")
                    break
                time.sleep(0.5)
            else:
                # Port still in use - try aggressive cleanup
                logger.warning(f"[WARNING] Port {port} still in use after process termination, force killing...")
                self._force_kill_port(port)
            
            # Reset service state
            service['process'] = None
            service['stdout_file'] = None
            service['stderr_file'] = None
            service['enabled'] = False
            
            # Reset log position so UI reads the stop messages
            with self.log_locks[service_name]:
                self.log_positions[service_name] = 0
            
            # Save configuration
            self.save_config()
            logger.info(f"[SUCCESS] {service['name']} stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"[ERROR] Error stopping {service['name']}: {e}")
            # Force cleanup even on error - but still return success if service is not running
            try:
                if service.get('stdout_file'):
                    try:
                        service['stdout_file'].close()
                    except:
                        pass
                if service.get('stderr_file'):
                    try:
                        service['stderr_file'].close()
                    except:
                        pass
            except:
                pass
            
            try:
                if process:
                    try:
                        process.kill()
                    except:
                        pass
            except:
                pass
            
            # Reset service state and check if it's actually stopped
            service['process'] = None
            service['stdout_file'] = None
            service['stderr_file'] = None
            service['enabled'] = False
            
            # Reset log position so UI reads the stop messages
            with self.log_locks[service_name]:
                self.log_positions[service_name] = 0
            
            self.save_config()
            
            # Even if there was an error, if service isn't responding, consider it stopped
            if not self._is_port_in_use(port):
                logger.info(f"[SUCCESS] {service['name']} stopped (cleanup had errors but port released)")
                return True
            else:
                # Try to force kill the port and return success anyway
                try:
                    self._force_kill_port(port)
                    time.sleep(0.5)
                except:
                    pass
                logger.warning(f"[WARNING] {service['name']} stop encountered errors, attempting port cleanup")
                return True  # Return True to allow UI to move forward
    
    def get_service_status(self, service_name):
        """
        Get current status of a service
        Returns: 'running', 'stopped', 'crashed', or 'unknown'
        """
        if service_name not in self.services:
            return 'unknown'
        
        service = self.services[service_name]
        process = service['process']
        
        # First check if we have a process object
        if process is None:
            # No process object, but check if something is running on the port
            if self._is_port_in_use(service['port']):
                # Port is occupied, check if it's our service via health check
                try:
                    response = requests.get(service['health_endpoint'], timeout=1)
                    if response.ok:
                        # Service is running but we don't have the process object
                        logger.info(f"[INFO] {service['name']} detected running without process reference")
                        return 'running'
                except:
                    pass
            return 'stopped'
        
        # We have a process object, check if it's still running
        poll_result = process.poll()
        if poll_result is None:
            # Process is still running
            return 'running'
        else:
            # Process has terminated
            exit_code = poll_result
            service['process'] = None
            service['enabled'] = False
            
            # Log crash info
            if exit_code != 0:
                logger.error(f"[ERROR] {service['name']} crashed with exit code {exit_code}")
            
            return 'crashed'
    
    def check_service_health(self, service_name):
        """
        Check if service is responding to health checks
        Returns: True if healthy, False otherwise
        """
        if service_name not in self.services:
            return False
        
        service = self.services[service_name]
        
        # First: Check if process is actually running
        status = self.get_service_status(service_name)
        if status != 'running':
            logger.warning(f"[WARNING] {service['name']} health check failed: process is not running (status: {status})")
            return False
        
        # Second: Check if port is open
        if not self._is_port_in_use(service['port']):
            logger.warning(f"[WARNING] {service['name']} health check failed: port {service['port']} not in use")
            return False
        
        # Third: Try to ping the health endpoint
        try:
            response = requests.get(
                service['health_endpoint'],
                timeout=3  # Slightly longer timeout for slow systems
            )
            if response.ok:
                logger.debug(f"[SUCCESS] {service['name']} health check passed")
                return True
            else:
                logger.warning(f"[WARNING] {service['name']} health check failed: HTTP {response.status_code}")
                return False
        except requests.ConnectionError as e:
            logger.warning(f"[WARNING] {service['name']} health check failed: Connection refused")
            return False
        except requests.Timeout:
            logger.warning(f"[WARNING] {service['name']} health check failed: Timeout")
            return False
        except Exception as e:
            logger.warning(f"[WARNING] {service['name']} health check failed: {e}")
            return False
    
    def toggle_service(self, service_name):
        """Toggle service on/off"""
        status = self.get_service_status(service_name)
        
        if status == 'running':
            return self.stop_service(service_name)
        else:
            return self.start_service(service_name)
    
    def set_auto_start(self, service_name, auto_start):
        """Set whether service should auto-start on admin login"""
        if service_name in self.services:
            self.services[service_name]['auto_start'] = auto_start
            self.save_config()
            logger.info(f"[CONFIG] {self.services[service_name]['name']} auto-start: {auto_start}")
    
    def start_all_auto_start_services(self):
        """Start all services marked for auto-start"""
        for service_name, service in self.services.items():
            if service['auto_start']:
                logger.info(f"[START] Auto-starting {service['name']}...")
                self.start_service(service_name)
    
    def stop_all_services(self):
        """Stop all running services"""
        for service_name in self.services.keys():
            if self.get_service_status(service_name) == 'running':
                self.stop_service(service_name)
    
    def restart_service(self, service_name):
        """Restart a service"""
        logger.info(f"[RESTART] Restarting {self.services[service_name]['name']}...")
        self.stop_service(service_name)
        time.sleep(1)
        return self.start_service(service_name)
    
    def get_all_statuses(self):
        """Get status of all services"""
        return {
            service_name: {
                'name': service['name'],
                'status': self.get_service_status(service_name),
                'health': self.check_service_health(service_name),
                'port': service['port'],
                'auto_start': service['auto_start']
            }
            for service_name, service in self.services.items()
        }
    
    def get_log_file_path(self, service_name):
        """Get the log file path for a service"""
        if service_name not in self.services:
            return None
        log_name = service_name.replace('_', '-')
        return self.logs_dir / f"{log_name}.log"
    
    def read_new_logs(self, service_name, max_lines=100):
        """
        Read new log lines from service log file.
        Returns list of (timestamp, level, message) tuples.
        Thread-safe and optimized for real-time streaming.
        """
        if service_name not in self.services:
            return []
        
        log_file = self.get_log_file_path(service_name)
        if not log_file or not log_file.exists():
            return []
        
        with self.log_locks[service_name]:
            try:
                new_lines = []
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    # Seek to last known position
                    current_pos = self.log_positions.get(service_name, 0)
                    f.seek(current_pos)
                    
                    # Read new lines
                    lines = f.readlines()
                    if lines:
                        # If position was reset (0), we want to show recent lines
                        # Otherwise, just show the new lines that were added
                        if current_pos == 0 and len(lines) > max_lines:
                            # Position was reset, show only the last max_lines
                            display_lines = lines[-max_lines:]
                        else:
                            # Normal case, show all new lines (up to max_lines)
                            display_lines = lines[-max_lines:] if len(lines) > max_lines else lines
                        
                        for line in display_lines:
                            line = line.rstrip()
                            if line:
                                parsed = self._parse_log_line(line)
                                new_lines.append(parsed)
                                self.log_buffers[service_name].append(parsed)
                        
                        # Update position to end of file for next read
                        self.log_positions[service_name] = f.tell()
                
                return new_lines
            except Exception as e:
                logger.debug(f"Error reading logs for {service_name}: {e}")
                return []
    
    def _parse_log_line(self, line):
        """
        Parse a log line and extract timestamp, level, and message.
        Returns (timestamp, level, message) tuple.
        """
        # Try to extract timestamp (various formats)
        timestamp = datetime.now().strftime("%H:%M:%S")
        level = "INFO"
        message = line
        
        # Pattern 1: [2024-01-12 14:30:45] LEVEL: message
        match = re.match(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s*(\w+):?\s*(.*)', line)
        if match:
            timestamp = match.group(1).split()[1]  # Extract time only
            level = match.group(2).upper()
            message = match.group(3)
            return (timestamp, level, message)
        
        # Pattern 2: YYYY-MM-DD HH:MM:SS - LEVEL - message
        match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s*[-:]?\s*(\w+)\s*[-:]?\s*(.*)', line)
        if match:
            timestamp = match.group(1).split()[1]
            level = match.group(2).upper()
            message = match.group(3)
            return (timestamp, level, message)
        
        # Pattern 3: Detect level keywords in line
        line_upper = line.upper()
        if 'ERROR' in line_upper or 'CRITICAL' in line_upper or 'EXCEPTION' in line_upper:
            level = "ERROR"
        elif 'WARNING' in line_upper or 'WARN' in line_upper:
            level = "WARNING"
        elif 'SUCCESS' in line_upper or 'STARTED' in line_upper or 'RUNNING' in line_upper:
            level = "SUCCESS"
        elif 'STOPPED' in line_upper or 'EXIT' in line_upper or 'SHUTDOWN' in line_upper:
            level = "STOPPED"
        elif 'DEBUG' in line_upper:
            level = "DEBUG"
        
        return (timestamp, level, message)
    
    def get_buffered_logs(self, service_name, max_lines=500):
        """
        Get all buffered logs for a service.
        Returns list of (timestamp, level, message) tuples.
        """
        if service_name not in self.log_buffers:
            return []
        
        with self.log_locks[service_name]:
            return list(self.log_buffers[service_name])[-max_lines:]
    
    def clear_log_buffer(self, service_name):
        """Clear the log buffer for a service"""
        if service_name in self.log_buffers:
            with self.log_locks[service_name]:
                self.log_buffers[service_name].clear()
                self.log_positions[service_name] = 0


# Global service manager instance
_service_manager = None

def get_service_manager():
    """Get or create the global service manager instance"""
    global _service_manager
    if _service_manager is None:
        _service_manager = ServiceManager()
    return _service_manager
