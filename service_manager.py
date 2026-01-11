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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ServiceManager:
    """Manages background API services for WinyFi"""
    
    def __init__(self):
        self.app_dir = Path(__file__).parent
        self.config_file = self.app_dir / "service_config.json"
        
        # Service definitions
        self.services = {
            'flask_api': {
                'name': 'Flask API',
                'script': 'server/run_app.py',
                'port': 5000,
                'health_endpoint': 'http://localhost:5000/api/health',
                'process': None,
                'enabled': False,
                'auto_start': False,
                'stdout_file': None,
                'stderr_file': None
            },
            'unifi_api': {
                'name': 'UniFi API',
                'script': 'server/run_unifi_api.py',
                'port': 5001,
                'health_endpoint': 'http://localhost:5001/api/health',
                'process': None,
                'enabled': False,
                'auto_start': False,
                'stdout_file': None,
                'stderr_file': None
            }
        }
        
        # Load saved configuration
        self.load_config()
        
        # Ensure logs directory exists
        self.logs_dir = self.app_dir / "logs"
        self.logs_dir.mkdir(exist_ok=True)
        
        # Cleanup any orphaned processes on startup
        self._cleanup_orphaned_processes()
    
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
            port = service['port']
            if self._is_port_in_use(port):
                logger.warning(f"⚠️ Port {port} is occupied but no process object exists for {service_name}. Attempting cleanup...")
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
                                        logger.info(f"✅ Killed orphaned process {pid} on port {port}")
                                    except Exception as e:
                                        logger.warning(f"⚠️ Could not kill process {pid}: {e}")
                except Exception as e:
                    logger.warning(f"⚠️ Cleanup attempt for port {port} failed: {e}")
    
    def _wait_for_service_ready(self, service_name, timeout=10):
        """Wait for service to be ready and responding to health checks"""
        service = self.services.get(service_name)
        if not service:
            return False
        
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            # Check if process is still alive
            if service['process'] and service['process'].poll() is not None:
                logger.error(f"❌ {service['name']} process died during startup")
                return False
            
            # Check if port is open
            if self._is_port_in_use(service['port']):
                # Port is open, try health check
                try:
                    response = requests.get(service['health_endpoint'], timeout=1)
                    if response.ok:
                        logger.info(f"✅ {service['name']} is ready and healthy")
                        return True
                except:
                    pass
            
            time.sleep(0.5)
        
        logger.warning(f"⏰ {service['name']} startup timeout after {timeout}s")
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
                logger.info("✅ Service configuration loaded")
        except Exception as e:
            logger.warning(f"⚠️ Could not load service config: {e}")
    
    def save_config(self):
        """Save service configuration to JSON file"""
        try:
            config = {
                service_name: {
                    'enabled': data['enabled'],
                    'auto_start': data['auto_start']
                }
                for service_name, data in self.services.items()
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info("💾 Service configuration saved")
        except Exception as e:
            logger.error(f"❌ Error saving config: {e}")
    
    def start_service(self, service_name):
        """Start a specific service"""
        if service_name not in self.services:
            logger.error(f"❌ Unknown service: {service_name}")
            return False
        
        service = self.services[service_name]
        
        # Check if already running
        if service['process'] is not None and service['process'].poll() is None:
            logger.info(f"ℹ️ {service['name']} is already running")
            return True
        
        # Check if port is already in use
        if self._is_port_in_use(service['port']):
            logger.warning(f"⚠️ Port {service['port']} already in use for {service['name']}")
            # Try to get existing process info
            try:
                response = requests.get(service['health_endpoint'], timeout=1)
                if response.ok:
                    logger.info(f"ℹ️ {service['name']} already running on port {service['port']}")
                    service['enabled'] = True
                    return True
            except:
                pass
            logger.error(f"❌ Port {service['port']} occupied but service not responding")
            return False
        
        script_path = self.app_dir / service['script']
        
        if not script_path.exists():
            logger.error(f"❌ Script not found: {script_path}")
            return False
        
        try:
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
            
            stdout_file = open(stdout_log, 'a', encoding='utf-8')
            stderr_file = open(stderr_log, 'a', encoding='utf-8')
            
            # Write startup marker
            stdout_file.write(f"\n{'='*60}\n")
            stdout_file.write(f"Starting {service['name']} at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            stdout_file.write(f"{'='*60}\n")
            stdout_file.flush()
            
            # Environment variables - disable debug and reloader for Flask
            env = os.environ.copy()
            env['FLASK_DEBUG'] = 'false'
            
            # Start the process
            process = subprocess.Popen(
                [sys.executable, str(script_path)],
                stdout=stdout_file,
                stderr=stderr_file,
                startupinfo=startupinfo,
                creationflags=creationflags,
                cwd=str(self.app_dir),
                env=env
            )
            
            # Store process AND file handles so we can close them later
            service['process'] = process
            service['stdout_file'] = stdout_file
            service['stderr_file'] = stderr_file
            service['enabled'] = True
            service['stdout_file'] = stdout_file
            service['stderr_file'] = stderr_file
            service['enabled'] = True
            
            logger.info(f"🚀 Started {service['name']} (PID: {process.pid})")
            logger.info(f"📋 Logs: {stdout_log}")
            
            # Wait for service to be ready (non-blocking for UI)
            logger.info(f"⏳ Waiting for {service['name']} to be ready...")
            if self._wait_for_service_ready(service_name, timeout=15):
                # Save configuration after successful startup
                self.save_config()
                return True
            else:
                # Check if process crashed
                if process.poll() is not None:
                    logger.error(f"❌ {service['name']} crashed during startup")
                    # Read last few lines of error log
                    try:
                        stderr_file.flush()
                        with open(stderr_log, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                            if lines:
                                logger.error(f"Last error: {lines[-1].strip()}")
                    except:
                        pass
                else:
                    logger.warning(f"⚠️ {service['name']} started but not responding to health checks")
                    # Service might still be initializing, mark as enabled anyway
                    self.save_config()
                    return True
                return False
            
        except Exception as e:
            logger.error(f"❌ Error starting {service['name']}: {e}")
            return False
    
    def stop_service(self, service_name):
        """Stop a specific service with proper cleanup"""
        if service_name not in self.services:
            logger.error(f"❌ Unknown service: {service_name}")
            return False
        
        service = self.services[service_name]
        process = service['process']
        port = service['port']
        
        if process is None:
            logger.info(f"ℹ️ {service['name']} is not running")
            service['enabled'] = False
            self.save_config()
            return True
        
        try:
            logger.info(f"Stopping {service['name']} (PID: {process.pid})...")
            
            # Gracefully terminate first
            process.terminate()
            
            try:
                # Wait for graceful shutdown (timeout 5 seconds)
                process.wait(timeout=5)
                logger.info(f"✅ {service['name']} terminated gracefully")
            except subprocess.TimeoutExpired:
                # Force kill if not stopped
                logger.warning(f"⚠️ {service['name']} did not stop gracefully, force killing...")
                process.kill()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    logger.error(f"❌ Could not kill {service['name']} process")
            
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
            import time
            for attempt in range(5):
                if not self._is_port_in_use(port):
                    logger.info(f"✅ Port {port} is now available")
                    break
                time.sleep(0.5)
            else:
                # Port still in use - try aggressive cleanup
                logger.warning(f"⚠️ Port {port} still in use after process termination")
                if sys.platform == 'win32':
                    try:
                        import subprocess
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
                                    if str(pid) != str(process.pid):  # Only kill if different PID
                                        try:
                                            subprocess.run(['taskkill', '/PID', pid, '/F'], timeout=3)
                                            logger.warning(f"🔨 Force-killed zombie process {pid} on port {port}")
                                        except Exception as e:
                                            logger.debug(f"Could not force-kill {pid}: {e}")
                    except Exception as e:
                        logger.debug(f"Netstat cleanup failed: {e}")
            
            # Reset service state
            service['process'] = None
            service['stdout_file'] = None
            service['stderr_file'] = None
            service['enabled'] = False
            
            # Save configuration
            self.save_config()
            logger.info(f"✅ {service['name']} stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error stopping {service['name']}: {e}")
            # Force cleanup even on error
            service['process'] = None
            service['stdout_file'] = None
            service['stderr_file'] = None
            service['enabled'] = False
            return False
            
            logger.info(f"⏹️ Stopped {service['name']}")
            return True
            
        except Exception as e:
            logger.error(f"⚠️ Error stopping {service['name']}: {e}")
            # Try to kill anyway
            try:
                if process:
                    process.kill()
                service['process'] = None
                service['enabled'] = False
            except:
                pass
            return False
    
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
                        logger.info(f"ℹ️ {service['name']} detected running without process reference")
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
                logger.error(f"❌ {service['name']} crashed with exit code {exit_code}")
            
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
            logger.warning(f"⚠️ {service['name']} health check failed: process is not running (status: {status})")
            return False
        
        # Second: Check if port is open
        if not self._is_port_in_use(service['port']):
            logger.warning(f"⚠️ {service['name']} health check failed: port {service['port']} not in use")
            return False
        
        # Third: Try to ping the health endpoint
        try:
            response = requests.get(
                service['health_endpoint'],
                timeout=3  # Slightly longer timeout for slow systems
            )
            if response.ok:
                logger.debug(f"✅ {service['name']} health check passed")
                return True
            else:
                logger.warning(f"⚠️ {service['name']} health check failed: HTTP {response.status_code}")
                return False
        except requests.ConnectionError as e:
            logger.warning(f"⚠️ {service['name']} health check failed: Connection refused")
            return False
        except requests.Timeout:
            logger.warning(f"⚠️ {service['name']} health check failed: Timeout")
            return False
        except Exception as e:
            logger.warning(f"⚠️ {service['name']} health check failed: {e}")
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
            logger.info(f"🔧 {self.services[service_name]['name']} auto-start: {auto_start}")
    
    def start_all_auto_start_services(self):
        """Start all services marked for auto-start"""
        for service_name, service in self.services.items():
            if service['auto_start']:
                logger.info(f"🚀 Auto-starting {service['name']}...")
                self.start_service(service_name)
    
    def stop_all_services(self):
        """Stop all running services"""
        for service_name in self.services.keys():
            if self.get_service_status(service_name) == 'running':
                self.stop_service(service_name)
    
    def restart_service(self, service_name):
        """Restart a service"""
        logger.info(f"🔄 Restarting {self.services[service_name]['name']}...")
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


# Global service manager instance
_service_manager = None

def get_service_manager():
    """Get or create the global service manager instance"""
    global _service_manager
    if _service_manager is None:
        _service_manager = ServiceManager()
    return _service_manager
