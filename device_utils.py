# device_utils.py
"""
Utility functions for device information detection and management.
"""

import socket
import uuid
import subprocess
import platform
import re
from typing import Optional, Dict, Any

def get_device_ip() -> Optional[str]:
    """
    Get the device's local IP address.
    Returns the first non-loopback IPv4 address found.
    """
    try:
        # Connect to a remote address to determine local IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # Connect to a remote address (doesn't actually send data)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            return local_ip
    except Exception:
        try:
            # Fallback method using hostname
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            if local_ip.startswith("127."):
                return None  # Skip loopback
            return local_ip
        except Exception:
            return None

def get_device_mac() -> Optional[str]:
    """
    Get the device's MAC address.
    Returns the MAC address of the first network interface found.
    """
    try:
        # Get MAC address using uuid
        mac = uuid.getnode()
        # Convert to proper MAC format
        mac_str = ':'.join(re.findall('..', '%012x' % mac))
        return mac_str
    except Exception:
        return None

def get_device_mac_alternative() -> Optional[str]:
    """
    Alternative method to get MAC address using system commands.
    """
    try:
        system = platform.system().lower()
        
        if system == "windows":
            # Windows method
            result = subprocess.run(
                ['getmac', '/fo', 'csv', '/nh'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if line and ',' in line:
                        mac = line.split(',')[0].strip().replace('-', ':')
                        if mac and mac != "N/A":
                            return mac
        elif system in ["linux", "darwin"]:  # Linux or macOS
            # Try to get MAC from /sys/class/net/ or ifconfig
            result = subprocess.run(
                ['ip', 'link', 'show'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                # Parse MAC from ip link output
                for line in result.stdout.split('\n'):
                    if 'link/ether' in line:
                        mac_match = re.search(r'([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})', line)
                        if mac_match:
                            return mac_match.group(1)
        
        return None
    except Exception:
        return None

def get_device_info() -> Dict[str, Any]:
    """
    Get comprehensive device information.
    Returns a dictionary with device details.
    """
    device_info = {
        'ip_address': None,
        'mac_address': None,
        'hostname': None,
        'platform': None,
        'user_agent': None
    }
    
    try:
        # Get IP address
        device_info['ip_address'] = get_device_ip()
        
        # Get MAC address (try primary method first, then alternative)
        device_info['mac_address'] = get_device_mac()
        if not device_info['mac_address']:
            device_info['mac_address'] = get_device_mac_alternative()
        
        # Get hostname
        try:
            device_info['hostname'] = socket.gethostname()
        except Exception:
            device_info['hostname'] = "Unknown"
        
        # Get platform info
        device_info['platform'] = f"{platform.system()} {platform.release()}"
        
        # Get user agent (for web requests)
        try:
            import requests
            device_info['user_agent'] = requests.utils.default_headers().get('User-Agent', 'Unknown')
        except ImportError:
            device_info['user_agent'] = "WINYFI-Client/1.0"
        
    except Exception as e:
        print(f"Error getting device info: {e}")
    
    return device_info

def format_mac_address(mac: str) -> str:
    """
    Format MAC address to standard format (XX:XX:XX:XX:XX:XX).
    """
    if not mac:
        return "Unknown"
    
    # Remove any non-hex characters and convert to uppercase
    clean_mac = re.sub(r'[^0-9a-fA-F]', '', mac)
    
    if len(clean_mac) != 12:
        return "Invalid"
    
    # Format as XX:XX:XX:XX:XX:XX
    formatted = ':'.join([clean_mac[i:i+2].upper() for i in range(0, 12, 2)])
    return formatted

def is_valid_mac(mac: str) -> bool:
    """
    Check if a MAC address is valid.
    """
    if not mac:
        return False
    
    # Clean the MAC address
    clean_mac = re.sub(r'[^0-9a-fA-F]', '', mac)
    
    # Check if it's exactly 12 hex characters
    return len(clean_mac) == 12 and all(c in '0123456789abcdefABCDEF' for c in clean_mac)

def get_network_interfaces() -> list:
    """
    Get list of network interfaces and their MAC addresses.
    Returns a list of dictionaries with interface info.
    """
    interfaces = []
    
    try:
        if platform.system().lower() == "windows":
            # Windows method using wmic
            result = subprocess.run(
                ['wmic', 'path', 'win32_networkadapter', 'get', 'name,macaddress', '/format:csv'],
                capture_output=True,
                text=True,
                timeout=15
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines[1:]:  # Skip header
                    if line and ',' in line:
                        parts = line.split(',')
                        if len(parts) >= 3:
                            name = parts[1].strip()
                            mac = parts[2].strip()
                            if mac and mac != "N/A" and is_valid_mac(mac):
                                interfaces.append({
                                    'name': name,
                                    'mac_address': format_mac_address(mac)
                                })
        else:
            # Linux/macOS method
            result = subprocess.run(
                ['ip', 'link', 'show'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                current_interface = None
                for line in result.stdout.split('\n'):
                    if line.strip().startswith(('1:', '2:', '3:', '4:', '5:', '6:', '7:', '8:', '9:')):
                        # Interface name line
                        parts = line.split(':')
                        if len(parts) >= 2:
                            current_interface = parts[1].strip()
                    elif 'link/ether' in line and current_interface:
                        # MAC address line
                        mac_match = re.search(r'([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})', line)
                        if mac_match:
                            interfaces.append({
                                'name': current_interface,
                                'mac_address': mac_match.group(1).upper()
                            })
                            current_interface = None
        
    except Exception as e:
        print(f"Error getting network interfaces: {e}")
    
    return interfaces

# Test function
if __name__ == "__main__":
    print("Device Information:")
    info = get_device_info()
    for key, value in info.items():
        print(f"  {key}: {value}")
    
    print("\nNetwork Interfaces:")
    interfaces = get_network_interfaces()
    for interface in interfaces:
        print(f"  {interface['name']}: {interface['mac_address']}")

