# Ping Function Improvements for UniFi API Integration

## Overview
The `ping_latency()` function has been significantly improved to better support UniFi API integration and provide more robust network monitoring capabilities.

## Key Improvements

### 1. **UniFi Device Support**
```python
ping_latency(ip, is_unifi=True)
```
- **Behavior**: Immediately returns `None` for UniFi devices
- **Reason**: UniFi devices get their online status from the API, not ping
- **Benefit**: Avoids unnecessary network traffic and faster status updates

### 2. **Dynamic Ping Manager Control**
```python
ping_latency(ip, use_manager=True)   # Respects dynamic intervals
ping_latency(ip, use_manager=False)  # Always pings (manual checks)
```
- **With Manager**: Respects dynamic ping intervals to avoid network congestion
- **Without Manager**: Always pings immediately (useful for manual refresh)
- **Benefit**: Flexibility for different use cases

### 3. **Enhanced Error Handling**
- **IP Validation**: Checks for invalid IPs ("N/A", "Unknown", None, empty)
- **Timeout Protection**: Subprocess timeout prevents hanging
- **OS Detection**: Proper timeout parameter handling for Windows/Unix
- **Exception Handling**: Catches TimeoutExpired, FileNotFoundError, and general exceptions
- **Detailed Logging**: Clear debug/warning/error messages

### 4. **Better Cross-Platform Support**
- **Windows**: Uses `-w` parameter with milliseconds
- **Unix/Linux**: Uses `-W` parameter with seconds (auto-converted)
- **Subprocess Timeout**: Adds 1-second buffer to prevent hanging

### 5. **New Helper Function: `is_device_online()`**
```python
# Regular router
online = is_device_online("192.168.1.1")

# UniFi device with API check
def check_unifi(ip):
    # Your UniFi API logic
    return True  # or False
    
online = is_device_online("192.168.1.105", is_unifi=True, unifi_api_check=check_unifi)
```

## Function Signatures

### `ping_latency()`
```python
def ping_latency(ip, timeout=1000, bandwidth=None, is_unifi=False, use_manager=True):
    """
    Return ping latency in ms with improved UniFi API integration support.
    
    Args:
        ip (str): IP address to ping
        timeout (int): Ping timeout in milliseconds (default: 1000)
        bandwidth (float): Current bandwidth in Mbps for dynamic interval calculation
        is_unifi (bool): If True, skips ping and returns None (UniFi devices use API status)
        use_manager (bool): If True, uses dynamic ping manager; if False, always pings
    
    Returns:
        float or None: Latency in ms, or None if offline/skipped/UniFi device
    """
```

### `is_device_online()`
```python
def is_device_online(ip, timeout=1000, is_unifi=False, unifi_api_check=None):
    """
    Check if a device is online with support for UniFi API integration.
    
    Args:
        ip (str): IP address to check
        timeout (int): Ping timeout in milliseconds
        is_unifi (bool): If True, uses UniFi API status instead of ping
        unifi_api_check (callable): Function to check UniFi device status (optional)
    
    Returns:
        bool: True if device is online, False otherwise
    """
```

## Use Cases

### 1. Regular Router Monitoring (Background)
```python
# Uses dynamic ping manager to avoid congestion
latency = ping_latency("192.168.1.1", bandwidth=50.5)
if latency:
    print(f"Router online: {latency}ms")
else:
    print("Router offline or ping skipped")
```

### 2. Regular Router Monitoring (Manual Refresh)
```python
# Forces immediate ping, bypasses manager
latency = ping_latency("192.168.1.1", use_manager=False)
if latency:
    print(f"Router online: {latency}ms")
else:
    print("Router offline")
```

### 3. UniFi Device Monitoring
```python
# Skips ping entirely for UniFi devices
latency = ping_latency("192.168.1.105", is_unifi=True)
# Always returns None - use API for status

# Better approach:
if router.get('is_unifi'):
    # Get status from UniFi API
    status = "Online" if device_in_api_response else "Offline"
else:
    # Use ping for regular routers
    latency = ping_latency(router['ip_address'])
    status = "Online" if latency else "Offline"
```

### 4. Online Status Check
```python
# Regular router
if is_device_online("192.168.1.1"):
    print("Router is online")

# UniFi device with API
def check_unifi_status(ip):
    # Check if device exists in UniFi API response
    return ip in [d['ip'] for d in unifi_devices]

if is_device_online("192.168.1.105", is_unifi=True, unifi_api_check=check_unifi_status):
    print("UniFi device is online")
```

## Integration with Dashboard

### In `reload_routers()`:
```python
for router in all_devices:
    is_unifi = router.get('is_unifi', False)
    ip = router.get('ip_address')
    
    if is_unifi:
        # UniFi devices: status from API presence
        is_online = True  # Present in API = online
        latency = None
    else:
        # Regular routers: use ping
        latency = ping_latency(ip, bandwidth=current_bandwidth)
        is_online = latency is not None
```

### In `open_router_details()` refresh:
```python
def refresh_details():
    is_unifi = router.get('is_unifi', False)
    
    if is_unifi:
        # UniFi: Get data from API
        status = "🟢 Online (UniFi API)"
        latency_text = "N/A (UniFi)"
    else:
        # Regular router: Use ping
        latency = ping_latency(router['ip_address'], use_manager=False)
        if latency:
            status = "🟢 Online"
            latency_text = f"{latency} ms"
        else:
            status = "🔴 Offline"
            latency_text = "N/A"
```

## Performance Benefits

### Before Improvements:
- ❌ Pinged UniFi devices unnecessarily
- ❌ Poor error handling for invalid IPs
- ❌ Could hang on network issues
- ❌ Limited control over ping behavior
- ❌ Basic cross-platform support

### After Improvements:
- ✅ Skips ping for UniFi devices (faster, less traffic)
- ✅ Validates IPs before pinging
- ✅ Timeout protection prevents hanging
- ✅ Flexible manager control (background vs manual)
- ✅ Better Windows/Unix compatibility
- ✅ Detailed logging for troubleshooting
- ✅ New helper function for status checks

## Error Handling

### Invalid IP Addresses
```python
ping_latency("N/A")       # Returns None, logs warning
ping_latency("")          # Returns None, logs warning
ping_latency(None)        # Returns None, logs warning
```

### Network Timeouts
```python
ping_latency("192.168.1.999", timeout=1000)  # Returns None after ~1 second
# Logs: "Ping to 192.168.1.999 timed out after 1000ms"
```

### UniFi Devices
```python
ping_latency("192.168.1.105", is_unifi=True)  # Returns None immediately
# Logs: "Skipping ping for UniFi device 192.168.1.105 (using API status)"
```

### System Errors
```python
# If ping command not found
ping_latency("192.168.1.1")  # Returns None
# Logs: "Ping command not found on this system"
```

## Logging Output Examples

### Successful Ping (With Manager)
```
DEBUG: Ping to 192.168.1.1: 15.32 ms (interval: 10s, bandwidth: 45.2)
```

### Successful Ping (Without Manager)
```
DEBUG: Ping to 192.168.1.1: 15.32 ms (manager disabled)
```

### Skipped UniFi Device
```
DEBUG: Skipping ping for UniFi device 192.168.1.105 (using API status)
```

### Failed Ping
```
DEBUG: Ping to 192.168.1.50 failed: return code 1
```

### Timeout
```
WARNING: Ping to 192.168.1.99 timed out after 1000ms
```

### Invalid IP
```
WARNING: Invalid IP address: N/A
```

## Migration Guide

### Old Code:
```python
latency = ping_latency(ip)
```

### New Code (Regular Router):
```python
# Background monitoring (respects manager)
latency = ping_latency(ip)

# Manual refresh (always pings)
latency = ping_latency(ip, use_manager=False)
```

### New Code (UniFi Device):
```python
# Option 1: Skip ping entirely
latency = ping_latency(ip, is_unifi=True)  # Returns None

# Option 2: Don't call ping at all
if not router.get('is_unifi'):
    latency = ping_latency(ip)
```

## Testing

### Test Regular Router:
```python
from network_utils import ping_latency

# Should return latency in ms
result = ping_latency("8.8.8.8", use_manager=False)
print(f"Google DNS: {result}ms")
```

### Test UniFi Device:
```python
from network_utils import ping_latency

# Should return None immediately
result = ping_latency("192.168.1.105", is_unifi=True)
print(f"UniFi device: {result}")  # None
```

### Test Online Status:
```python
from network_utils import is_device_online

# Regular router
online = is_device_online("192.168.1.1")
print(f"Router online: {online}")

# UniFi with API check
def check_api(ip):
    return True  # Simulated API response
    
online = is_device_online("192.168.1.105", is_unifi=True, unifi_api_check=check_api)
print(f"UniFi online: {online}")
```

## Best Practices

1. **Always pass `is_unifi=True` for UniFi devices** to avoid unnecessary pings
2. **Use `use_manager=False`** for manual refresh buttons to get immediate results
3. **Use `use_manager=True`** (default) for background monitoring to avoid congestion
4. **Validate IP addresses** before passing to ping_latency
5. **Use `is_device_online()`** when you only need online/offline status
6. **Handle None returns** - None means offline, skipped, or UniFi device
7. **Check logs** for detailed debugging information

## Compatibility

- ✅ Windows (PowerShell, CMD)
- ✅ Linux (Ubuntu, Debian, RedHat, etc.)
- ✅ macOS
- ✅ UniFi API integration
- ✅ Regular routers
- ✅ Dynamic ping manager
- ✅ Background monitoring
- ✅ Manual refresh
