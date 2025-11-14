"""
Server Auto-Discovery Module
Automatically discovers the Flask API server on the local network using multiple methods.

Discovery Methods (in order of preference):
1. mDNS/Zeroconf - Service-based discovery (instant, requires zeroconf package)
2. Broadcast Scan - Network range scanning (reliable, takes 5-10 seconds)
3. Manual Entry - User provides IP address (always works)

Usage:
    from server_discovery import ServerDiscovery
    
    discovery = ServerDiscovery()
    server_info = discovery.discover()
    
    if server_info:
        print(f"Found server at {server_info['ip']}:{server_info['port']}")
"""

import socket
import requests
import json
import os
from typing import Optional, Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


class ServerDiscovery:
    """
    Auto-discovery for Network Monitoring API server
    """
    
    SERVICE_NAME = "network-monitoring-api"
    DEFAULT_PORT = 5000
    HEALTH_ENDPOINT = "/api/health"
    CONFIG_FILE = "server_config.json"
    TIMEOUT = 2  # seconds per host check
    MAX_WORKERS = 50  # parallel scanning threads
    
    def __init__(self):
        """Initialize discovery with saved configuration"""
        self.last_known_server = self._load_config()
        self.discovery_log = []
        
    def _load_config(self) -> Optional[Dict]:
        """Load last successful server configuration"""
        try:
            if os.path.exists(self.CONFIG_FILE):
                with open(self.CONFIG_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self._log(f"Failed to load config: {e}")
        return None
    
    def _save_config(self, server_info: Dict):
        """Save successful server configuration"""
        try:
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump(server_info, f, indent=2)
            self._log(f"Saved config: {server_info['ip']}:{server_info['port']}")
        except Exception as e:
            self._log(f"Failed to save config: {e}")
    
    def _log(self, message: str):
        """Add message to discovery log"""
        self.discovery_log.append(message)
    
    def get_log(self) -> List[str]:
        """Get discovery log messages"""
        return self.discovery_log.copy()
    
    def _verify_server(self, ip: str, port: int = DEFAULT_PORT) -> Optional[Dict]:
        """
        Verify if server is running at given IP by checking health endpoint
        
        Returns:
            Dict with server info if valid, None otherwise
        """
        try:
            url = f"http://{ip}:{port}{self.HEALTH_ENDPOINT}"
            response = requests.get(url, timeout=self.TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                
                # Verify it's our service
                if data.get('service') == self.SERVICE_NAME:
                    self._log(f"✓ Verified server at {ip}:{port}")
                    return {
                        'ip': ip,
                        'port': port,
                        'version': data.get('version', 'unknown'),
                        'status': data.get('status', 'ok')
                    }
        except Exception:
            pass
        
        return None
    
    def discover_mdns(self) -> Optional[Dict]:
        """
        Method 1: Discover server using mDNS/Zeroconf (fastest)
        
        Returns:
            Server info dict if found, None otherwise
        """
        self._log("Attempting mDNS discovery...")
        
        try:
            from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
            
            class ServerListener(ServiceListener):
                def __init__(self):
                    self.found_server = None
                    self.event = threading.Event()
                
                def add_service(self, zeroconf, service_type, name):
                    info = zeroconf.get_service_info(service_type, name)
                    if info and ServerDiscovery.SERVICE_NAME in name.lower():
                        # Extract IP from addresses
                        if info.addresses:
                            ip = socket.inet_ntoa(info.addresses[0])
                            port = info.port
                            self.found_server = {'ip': ip, 'port': port}
                            self.event.set()
                
                def remove_service(self, zeroconf, service_type, name):
                    pass
                
                def update_service(self, zeroconf, service_type, name):
                    pass
            
            listener = ServerListener()
            zeroconf = Zeroconf()
            browser = ServiceBrowser(zeroconf, "_http._tcp.local.", listener)
            
            # Wait up to 3 seconds for discovery
            listener.event.wait(timeout=3)
            
            zeroconf.close()
            
            if listener.found_server:
                return self._verify_server(
                    listener.found_server['ip'],
                    listener.found_server['port']
                )
            
            self._log("mDNS: No server found")
            
        except ImportError:
            self._log("mDNS: zeroconf package not installed (optional)")
        except Exception as e:
            self._log(f"mDNS failed: {e}")
        
        return None
    
    def _get_local_network_range(self) -> List[str]:
        """
        Get local network IP range to scan
        
        Returns:
            List of IP addresses to check (e.g., ['192.168.1.1', '192.168.1.2', ...])
        """
        try:
            # Get local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            
            # Parse network range (assumes /24 subnet)
            parts = local_ip.split('.')
            network_prefix = f"{parts[0]}.{parts[1]}.{parts[2]}"
            
            # Generate all IPs in range (skip .0 and .255)
            ip_range = [f"{network_prefix}.{i}" for i in range(1, 255)]
            
            self._log(f"Scanning network: {network_prefix}.0/24")
            return ip_range
            
        except Exception as e:
            self._log(f"Failed to determine network range: {e}")
            return []
    
    def discover_broadcast(self, progress_callback=None) -> Optional[Dict]:
        """
        Method 2: Discover server by scanning local network (most reliable)
        
        Args:
            progress_callback: Optional callback(current, total) for progress updates
        
        Returns:
            Server info dict if found, None otherwise
        """
        self._log("Starting broadcast scan...")
        
        ip_range = self._get_local_network_range()
        if not ip_range:
            return None
        
        total = len(ip_range)
        checked = 0
        found_server = None
        
        # Use thread pool for parallel scanning
        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            # Submit all verification tasks
            future_to_ip = {
                executor.submit(self._verify_server, ip): ip 
                for ip in ip_range
            }
            
            # Process completed tasks
            for future in as_completed(future_to_ip):
                checked += 1
                
                # Update progress
                if progress_callback:
                    progress_callback(checked, total)
                
                # Check if server found
                result = future.result()
                if result:
                    found_server = result
                    # Cancel remaining tasks
                    for f in future_to_ip:
                        f.cancel()
                    break
        
        if found_server:
            self._log(f"✓ Broadcast scan found server at {found_server['ip']}")
        else:
            self._log("Broadcast scan: No server found")
        
        return found_server
    
    def discover_saved(self) -> Optional[Dict]:
        """
        Try last known server configuration
        
        Returns:
            Server info dict if still valid, None otherwise
        """
        if self.last_known_server:
            self._log(f"Checking saved config: {self.last_known_server['ip']}")
            result = self._verify_server(
                self.last_known_server['ip'],
                self.last_known_server.get('port', self.DEFAULT_PORT)
            )
            if result:
                self._log("✓ Saved config still valid")
                return result
            else:
                self._log("Saved config no longer valid")
        
        return None
    
    def discover_manual(self, ip: str, port: int = DEFAULT_PORT) -> Optional[Dict]:
        """
        Method 3: Manual server verification
        
        Args:
            ip: IP address to check
            port: Port number (default: 5000)
        
        Returns:
            Server info dict if valid, None otherwise
        """
        self._log(f"Verifying manual entry: {ip}:{port}")
        return self._verify_server(ip, port)
    
    def discover(self, progress_callback=None, use_saved=True, use_mdns=True, use_broadcast=True) -> Optional[Dict]:
        """
        Automatic discovery using all available methods
        
        Discovery order:
        1. Saved configuration (if use_saved=True)
        2. mDNS/Zeroconf (if use_mdns=True and package available)
        3. Broadcast scan (if use_broadcast=True)
        
        Args:
            progress_callback: Optional callback(current, total) for broadcast scan progress
            use_saved: Try saved configuration first
            use_mdns: Try mDNS discovery
            use_broadcast: Try broadcast scanning
        
        Returns:
            Server info dict if found, None otherwise
        """
        self._log("=== Starting Auto-Discovery ===")
        
        # Try saved config first (instant)
        if use_saved:
            result = self.discover_saved()
            if result:
                return result
        
        # Try mDNS (fast, 3 seconds max)
        if use_mdns:
            result = self.discover_mdns()
            if result:
                self._save_config(result)
                return result
        
        # Try broadcast scan (slower, thorough)
        if use_broadcast:
            result = self.discover_broadcast(progress_callback)
            if result:
                self._save_config(result)
                return result
        
        self._log("=== Discovery Failed ===")
        return None


# Test/Demo code
if __name__ == "__main__":
    print("Network Monitoring API - Server Discovery Test\n")
    
    discovery = ServerDiscovery()
    
    def progress(current, total):
        """Progress callback for scanning"""
        percent = (current / total) * 100
        print(f"\rScanning network... {current}/{total} ({percent:.1f}%)", end='', flush=True)
    
    print("Discovering server...")
    server = discovery.discover(progress_callback=progress)
    
    print("\n")
    
    if server:
        print("✓ Server found!")
        print(f"  IP:      {server['ip']}")
        print(f"  Port:    {server['port']}")
        print(f"  Version: {server['version']}")
        print(f"  Status:  {server['status']}")
    else:
        print("✗ Server not found")
        print("\nDiscovery Log:")
        for msg in discovery.get_log():
            print(f"  - {msg}")
        print("\nTry manual entry:")
        print("  from server_discovery import ServerDiscovery")
        print("  discovery = ServerDiscovery()")
        print("  server = discovery.discover_manual('192.168.1.100')")
