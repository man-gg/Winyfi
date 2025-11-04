import time
import logging
import speedtest
import platform
import subprocess
from scapy.all import sniff, Ether, ARP, IP, UDP, conf, srp
import psutil
from collections import defaultdict
import socket
import time
from collections import deque
from datetime import datetime
import ipaddress
import requests
import json

# Global client table
clients = {}
# Setup logging for debugging
# logging.basicConfig(level=logging.DEBUG)


# --- Dynamic Ping Manager ---

class DynamicPingManager:
    def __init__(self, min_interval=5, max_interval=60, normal_interval=10, high_bw_threshold=20, high_ping_threshold=150, window=5):
        self.min_interval = min_interval  # seconds
        self.max_interval = max_interval  # seconds
        self.normal_interval = normal_interval  # seconds
        self.high_bw_threshold = high_bw_threshold  # Mbps
        self.high_ping_threshold = high_ping_threshold  # ms
        self.window = window
        self.latency_history = deque(maxlen=window)
        self.last_ping_time = 0
        self.current_interval = normal_interval

    def update(self, latency, bandwidth=None):
        if latency is not None:
            self.latency_history.append(latency)
        avg_latency = None
        if len(self.latency_history) > 0:
            avg_latency = sum(self.latency_history) / len(self.latency_history)
        # If bandwidth is high OR ping is high, increase interval
        if (bandwidth is not None and bandwidth >= self.high_bw_threshold) or \
           (avg_latency is not None and avg_latency >= self.high_ping_threshold):
            self.current_interval = self.max_interval
        else:
            self.current_interval = self.normal_interval
        return self.current_interval

    def should_ping(self):
        now = time.time()
        if now - self.last_ping_time >= self.current_interval:
            self.last_ping_time = now
            return True
        return False

# Create a global ping manager instance
ping_manager = DynamicPingManager()

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
        
    Behavior:
        - UniFi devices (is_unifi=True): Returns None immediately (status from API)
        - Regular routers with manager: Respects dynamic ping intervals
        - Regular routers without manager: Always pings (for manual checks)
    """
    # Skip ping for UniFi devices - they get status from API
    if is_unifi:
        logging.debug(f"Skipping ping for UniFi device {ip} (using API status)")
        return None
    
    # Check if we should skip this ping based on dynamic manager
    if use_manager and not ping_manager.should_ping():
        return None  # Skip ping to avoid congestion
    
    # Validate IP address
    if not ip or ip == "N/A" or ip == "Unknown":
        logging.warning(f"Invalid IP address: {ip}")
        return None
    
    # Build ping command based on OS
    param = "-n" if platform.system().lower() == "windows" else "-c"
    timeout_param = "-w" if platform.system().lower() == "windows" else "-W"
    
    # Convert timeout to seconds for Unix-like systems
    timeout_value = str(timeout) if platform.system().lower() == "windows" else str(timeout // 1000)
    
    cmd = ["ping", param, "1", timeout_param, timeout_value, ip]
    
    try:
        start = time.time()
        result = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            timeout=timeout / 1000 + 1  # Add 1 second buffer to subprocess timeout
        )
        end = time.time()
        
        if result.returncode == 0:
            # Calculate actual latency
            latency = round((end - start) * 1000, 2)  # ms
            
            # Update ping manager if using it
            if use_manager:
                ping_manager.update(latency, bandwidth)
                logging.debug(
                    f"Ping to {ip}: {latency} ms "
                    f"(interval: {ping_manager.current_interval}s, bandwidth: {bandwidth})"
                )
            else:
                logging.debug(f"Ping to {ip}: {latency} ms (manager disabled)")
            
            return latency
        else:
            # Ping failed (host unreachable or timeout)
            logging.debug(f"Ping to {ip} failed: return code {result.returncode}")
            if use_manager:
                ping_manager.update(None, bandwidth)
            return None
            
    except subprocess.TimeoutExpired:
        logging.warning(f"Ping to {ip} timed out after {timeout}ms")
        if use_manager:
            ping_manager.update(None, bandwidth)
        return None
        
    except FileNotFoundError:
        logging.error("Ping command not found on this system")
        return None
        
    except Exception as e:
        logging.error(f"Ping to {ip} failed with error: {e}")
        if use_manager:
            ping_manager.update(None, bandwidth)
        return None

def _rate_latency(latency):
    """Rate latency quality."""
    if latency is None:
        return "Poor"
    if latency < 50:
        return "Excellent"
    elif latency < 100:
        return "Good"
    elif latency < 200:
        return "Fair"
    return "Poor"

def is_device_online(ip, timeout=1000, is_unifi=False, unifi_api_check=None):
    """
    Check if a device is online with support for UniFi API integration.
    
    Args:
        ip (str): IP address to check
        timeout (int): Ping timeout in milliseconds
        is_unifi (bool): If True, uses UniFi API status instead of ping
        unifi_api_check (callable): Function to check UniFi device status (optional)
            Should return True if online, False if offline
    
    Returns:
        bool: True if device is online, False otherwise
        
    Usage:
        # Regular router
        online = is_device_online("192.168.1.1")
        
        # UniFi device with API check
        def check_unifi_status(ip):
            # Your UniFi API logic here
            return True  # or False
        online = is_device_online("192.168.1.105", is_unifi=True, unifi_api_check=check_unifi_status)
    """
    if is_unifi and unifi_api_check:
        # Use UniFi API to check status
        try:
            return unifi_api_check(ip)
        except Exception as e:
            logging.error(f"UniFi API check failed for {ip}: {e}")
            return False
    
    # Use ping for regular routers or UniFi fallback
    latency = ping_latency(ip, timeout=timeout, is_unifi=False, use_manager=False)
    return latency is not None

def _rate_bandwidth(mbps):
    """Rate bandwidth quality."""
    if mbps >= 20:
        return "Excellent"
    elif mbps >= 10:
        return "Good"
    elif mbps >= 3:
        return "Fair"
    elif mbps > 0:
        return "Poor"
    return "None"

def get_speedtest_results():
    """Get download/upload speed using Speedtest.net."""
    st = speedtest.Speedtest()

    # Get best server
    st.get_best_server()

    # Perform the download/upload tests
    download_speed = st.download() / 1_000_000  # Convert from bits to Mbps
    upload_speed = st.upload() / 1_000_000  # Convert from bits to Mbps
    ping = st.results.ping  # Ping in ms

    logging.debug(f"Download speed: {download_speed} Mbps")
    logging.debug(f"Upload speed: {upload_speed} Mbps")
    logging.debug(f"Ping: {ping} ms")

    # Return results with quality ratings
    return {
        "latency": ping,
        "download": download_speed,
        "upload": upload_speed,
        "quality": {
            "latency": _rate_latency(ping),
            "download": _rate_bandwidth(download_speed),
            "upload": _rate_bandwidth(upload_speed)
        }
    }
"""
def get_bandwidth(ip, test_size=256_000):
    latency = ping_latency(ip)  # Optionally ping the IP for latency
    if latency is None:
        logging.debug(f"Unable to determine latency for {ip}")
        return {
            "latency": None, "download": 0, "upload": 0,
            "quality": {"latency": "Poor", "download": "None", "upload": "None"}
        }

    try:
        # Get bandwidth via Speedtest.net
        speedtest_results = get_speedtest_results()
    except speedtest.ConfigRetrievalError as e:
        logging.error(f"Failed to retrieve speedtest configuration: {e}")
        return {
            "latency": None, "download": 0, "upload": 0,
            "quality": {"latency": "Poor", "download": "None", "upload": "None"}
        }
    except Exception as e:
        logging.error(f"Unexpected error while fetching bandwidth: {e}")
        return {
            "latency": None, "download": 0, "upload": 0,
            "quality": {"latency": "Poor", "download": "None", "upload": "None"}
        }

    # Return results with quality ratings
    return speedtest_results
"""



# ============================================================
# BANDWIDTH MONITORING - ZERO DATA CONSUMPTION
# ============================================================
# 
# PRIMARY FUNCTIONS (Automatic - No Data Usage):
#   - get_bandwidth(ip): Lightweight psutil-based monitoring
#   - get_throughput(interval): Network-wide throughput snapshot
#   - get_per_device_bandwidth(timeout): Passive per-device traffic capture
#
# MANUAL FUNCTIONS (User-triggered - High Data Usage):
#   - manual_speedtest(full=False): Convenience wrapper for speed tests
#   - get_speedtest_results(manual=True): Full ISP test (~150MB)
#   - get_mini_speedtest(manual=True): Quick test (~1.5MB)
#
# IMPLEMENTATION:
#   - Uses psutil.net_io_counters() for passive monitoring
#   - Uses scapy packet capture for per-device tracking
#   - Speedtest.net ONLY available via manual trigger (prevents auto-consumption)
# ============================================================

# ---------------- SETTINGS ----------------
DISABLE_BANDWIDTH = False    # Now safe to enable (no data consumption)
BANDWIDTH_INTERVAL = 5       # seconds (measurement window) - Increased for better averaging
LATENCY_THRESHOLD = 200      # ms
ANOMALY_WINDOW = 5           # check last N pings
# ------------------------------------------

# Trackers
latency_history = deque(maxlen=ANOMALY_WINDOW)

# Per-device bandwidth tracking
device_bandwidth = {}  # {ip: {"bytes_sent": int, "bytes_recv": int, "last_update": timestamp}}


def get_speedtest_results(manual=False):
    """
    Full Speedtest (heavy - MANUAL USE ONLY).
    
    Args:
        manual (bool): Must be True to run. Prevents accidental automatic execution.
    
    WARNING: Consumes ~150MB of data per test!
    """
    if not manual:
        raise ValueError("Speedtest must be manually triggered (set manual=True). Use get_bandwidth() for automatic monitoring.")
    
    st = speedtest.Speedtest()
    st.get_best_server()
    st.download()
    st.upload()
    res = st.results.dict()

    download_speed = res["download"] / 1_000_000
    upload_speed = res["upload"] / 1_000_000
    ping = res["ping"]

    return {
        "latency": ping,
        "download": round(download_speed, 2),
        "upload": round(upload_speed, 2),
        "quality": {
            "latency": _rate_latency(ping),
            "download": _rate_bandwidth(download_speed),
            "upload": _rate_bandwidth(upload_speed)
        }
    }


def get_throughput(interval=1):
    """
    Lightweight network-wide throughput measurement using psutil.
    Measures total network interface traffic (no data consumption).
    
    Args:
        interval (float): Measurement window in seconds
    
    Returns:
        tuple: (download_mbps, upload_mbps)
    """
    counters1 = psutil.net_io_counters()
    time.sleep(interval)
    counters2 = psutil.net_io_counters()

    bytes_sent = counters2.bytes_sent - counters1.bytes_sent
    bytes_recv = counters2.bytes_recv - counters1.bytes_recv

    upload_mbps = (bytes_sent * 8) / (interval * 1_000_000)
    download_mbps = (bytes_recv * 8) / (interval * 1_000_000)

    return round(download_mbps, 2), round(upload_mbps, 2)


def get_per_device_bandwidth(timeout=5, iface=None):
    """
    Passive per-device bandwidth monitoring using packet capture.
    Measures actual traffic per IP address without generating any network traffic.
    
    Args:
        timeout (int): Capture duration in seconds
        iface (str): Network interface to monitor (auto-detected if None)
    
    Returns:
        dict: {
            ip: {
                "bytes_sent": int,
                "bytes_recv": int,
                "download_mbps": float,
                "upload_mbps": float,
                "packets_sent": int,
                "packets_recv": int,
                "mac": str
            }
        }
    
    Example:
        >>> bandwidth = get_per_device_bandwidth(timeout=10)
        >>> for ip, stats in bandwidth.items():
        ...     print(f"{ip}: ↓{stats['download_mbps']}Mbps ↑{stats['upload_mbps']}Mbps")
    """
    if iface is None:
        iface = get_default_iface()
    
    device_stats = defaultdict(lambda: {
        "bytes_sent": 0,
        "bytes_recv": 0,
        "packets_sent": 0,
        "packets_recv": 0,
        "mac": "Unknown"
    })
    
    # Get local IP to identify direction
    local_ip = None
    try:
        addrs = psutil.net_if_addrs()
        for iface_name, snic_list in addrs.items():
            for snic in snic_list:
                if snic.family.name == "AF_INET" and snic.address != "127.0.0.1":
                    local_ip = snic.address
                    break
            if local_ip:
                break
    except Exception as e:
        logging.warning(f"Could not detect local IP: {e}")
    
    def pkt_handler(pkt):
        try:
            if pkt.haslayer(IP):
                src_ip = pkt[IP].src
                dst_ip = pkt[IP].dst
                pkt_len = len(pkt)
                
                # Determine direction based on local IP
                if local_ip:
                    if src_ip == local_ip:
                        # Outgoing packet (upload from perspective of local device)
                        device_stats[dst_ip]["bytes_recv"] += pkt_len
                        device_stats[dst_ip]["packets_recv"] += 1
                    elif dst_ip == local_ip:
                        # Incoming packet (download from perspective of local device)
                        device_stats[src_ip]["bytes_sent"] += pkt_len
                        device_stats[src_ip]["packets_sent"] += 1
                else:
                    # Fallback: count both directions
                    device_stats[src_ip]["bytes_sent"] += pkt_len
                    device_stats[src_ip]["packets_sent"] += 1
                    device_stats[dst_ip]["bytes_recv"] += pkt_len
                    device_stats[dst_ip]["packets_recv"] += 1
                
                # Store MAC address
                if pkt.haslayer(Ether):
                    if src_ip in device_stats:
                        device_stats[src_ip]["mac"] = pkt[Ether].src
                    if dst_ip in device_stats:
                        device_stats[dst_ip]["mac"] = pkt[Ether].dst
                        
        except Exception as e:
            logging.debug(f"Per-device bandwidth packet error: {e}")
    
    # Capture packets
    try:
        logging.info(f"Starting per-device bandwidth capture for {timeout}s on {iface}...")
        sniff(prn=pkt_handler, timeout=timeout, store=0, iface=iface)
    except Exception as e:
        logging.error(f"Per-device capture failed: {e}")
        return {}
    
    # Calculate Mbps for each device
    results = {}
    for ip, stats in device_stats.items():
        # Skip localhost and broadcast
        if ip in ("127.0.0.1", "0.0.0.0", "255.255.255.255"):
            continue
        
        # Calculate Mbps
        download_mbps = (stats["bytes_sent"] * 8) / (timeout * 1_000_000)
        upload_mbps = (stats["bytes_recv"] * 8) / (timeout * 1_000_000)
        
        results[ip] = {
            "bytes_sent": stats["bytes_sent"],
            "bytes_recv": stats["bytes_recv"],
            "download_mbps": round(download_mbps, 3),
            "upload_mbps": round(upload_mbps, 3),
            "packets_sent": stats["packets_sent"],
            "packets_recv": stats["packets_recv"],
            "mac": stats["mac"]
        }
    
    logging.info(f"Per-device bandwidth capture complete: {len(results)} devices detected")
    return results


def get_mini_speedtest(manual=False):
    """
    Mini speedtest (1MB download, 512KB upload - MANUAL USE ONLY).
    
    Args:
        manual (bool): Must be True to run. Prevents accidental automatic execution.
    
    WARNING: Consumes ~1.5MB of data per test!
    """
    if not manual:
        raise ValueError("Mini speedtest must be manually triggered (set manual=True). Use get_bandwidth() for automatic monitoring.")
    
    st = speedtest.Speedtest()
    st.get_best_server()

    # small download
    download_speed = st.download(threads=None) / 1_000_000
    # small upload
    upload_speed = st.upload(pre_allocate=False) / 1_000_000
    ping = st.results.ping

    return {
        "latency": ping,
        "download": round(download_speed, 2),
        "upload": round(upload_speed, 2),
        "quality": {
            "latency": _rate_latency(ping),
            "download": _rate_bandwidth(download_speed),
            "upload": _rate_bandwidth(upload_speed)
        }
    }


def manual_speedtest(full=False):
    """
    Convenience function for manual speedtest execution.
    
    Args:
        full (bool): If True, run full speedtest (~150MB). If False, run mini (~1.5MB).
    
    Returns:
        dict: Speed test results with latency, download, upload, and quality ratings
    
    Example:
        >>> # Quick mini test
        >>> results = manual_speedtest()
        >>> print(f"Speed: ↓{results['download']}Mbps ↑{results['upload']}Mbps")
        
        >>> # Full ISP test
        >>> results = manual_speedtest(full=True)
    """
    if full:
        print("⚠️ Running FULL speedtest (consumes ~150MB data)...")
        return get_speedtest_results(manual=True)
    else:
        print("⚠️ Running MINI speedtest (consumes ~1.5MB data)...")
        return get_mini_speedtest(manual=True)


def get_bandwidth(ip, interval=None):
    """
    Lightweight bandwidth measurement using psutil (NO DATA CONSUMPTION).
    Measures actual network throughput passively.
    
    Args:
        ip (str): Target IP address (for status check and future per-device tracking)
        interval (float): Measurement window in seconds (default: BANDWIDTH_INTERVAL)
    
    Returns:
        dict: {
            "latency": float or None,
            "download": float (Mbps),
            "upload": float (Mbps),
            "quality": {"latency": str, "download": str, "upload": str},
            "method": "psutil" or "offline"
        }
    
    Note: For ISP speed tests, use get_speedtest_results(manual=True) or get_mini_speedtest(manual=True).
    """
    if interval is None:
        interval = BANDWIDTH_INTERVAL
    
    # Check device status first (disable ping manager to always get fresh ping)
    latency = ping_latency(ip, use_manager=False)

    # If no ping response → consider offline → return 0 bandwidth
    if latency is None:
        return {
            "latency": None,
            "download": 0,
            "upload": 0,
            "quality": {
                "latency": "Poor",
                "download": "None",
                "upload": "None"
            },
            "method": "offline"
        }

    latency_history.append(latency)

    if DISABLE_BANDWIDTH:
        return {
            "latency": latency,
            "download": 0,
            "upload": 0,
            "quality": {
                "latency": _rate_latency(latency),
                "download": "Disabled",
                "upload": "Disabled"
            },
            "method": "disabled"
        }

    # Use lightweight psutil-based throughput measurement
    try:
        dl, ul = get_throughput(interval=interval)
        return {
            "latency": latency,
            "download": dl,
            "upload": ul,
            "quality": {
                "latency": _rate_latency(latency),
                "download": _rate_bandwidth(dl),
                "upload": _rate_bandwidth(ul)
            },
            "method": "psutil"
        }
    except Exception as e:
        logging.error(f"Bandwidth measurement failed: {e}")
        return {
            "latency": latency,
            "download": 0,
            "upload": 0,
            "quality": {
                "latency": _rate_latency(latency),
                "download": "Error",
                "upload": "Error"
            },
            "method": "error"
        }



def get_default_iface():
    """
    Try to detect the active/default network interface.
    Falls back to Scapy’s default if not found.
    """
    try:
        # Get default NIC from psutil
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()

        # Pick the first 'up' interface with an IP
        for iface, snic_list in addrs.items():
            if iface in stats and stats[iface].isup:
                if any(snic.family.name.startswith("AF_INET") for snic in snic_list):
                    return iface
    except Exception:
        pass

    # Fallback: scapy’s default
    return conf.iface

# --- Advanced Loop Detection with Multi-Subnet Support ---

class LoopDetectionEngine:
    """
    Advanced loop detection engine with support for multi-router environments,
    sophisticated severity scoring, and false positive reduction.
    """
    
    def __init__(self):
        # Historical data for pattern analysis
        self.mac_history = defaultdict(lambda: {
            "packet_times": deque(maxlen=1000),
            "ip_changes": deque(maxlen=50),
            "subnets": set(),
            "first_seen": None,
            "last_ip": None
        })
        
        # Known legitimate traffic patterns (whitelist)
        self.legitimate_patterns = {
            "dhcp_servers": set(),  # Known DHCP server MACs
            "routers": {"3c:91:80:80:ac:97"},  # Known router MACs + your laptop
            "mdns_devices": set(),  # Devices with consistent mDNS
        }
        
        # Traffic baselines for anomaly detection
        self.baseline = {
            "avg_arp_rate": 0,
            "avg_broadcast_rate": 0,
            "stddev_arp": 0,
            "stddev_broadcast": 0
        }
        
    def _extract_subnet(self, ip):
        """Extract subnet from IP address (assumes /24)."""
        try:
            parts = ip.split('.')
            return '.'.join(parts[:3]) + '.0/24'
        except:
            return None
    
    def _calculate_packet_frequency(self, times):
        """Calculate packets per second over time window."""
        if len(times) < 2:
            return 0
        
        time_span = times[-1] - times[0]
        if time_span == 0:
            return 0
        
        return len(times) / time_span
    
    def _detect_packet_bursts(self, times, burst_window=1.0, burst_threshold=20):
        """
        Detect packet bursts (many packets in short time).
        Returns number of bursts detected.
        """
        if len(times) < burst_threshold:
            return 0
        
        bursts = 0
        times_list = list(times)
        
        for i in range(len(times_list)):
            window_end = times_list[i] + burst_window
            count = sum(1 for t in times_list[i:] if t <= window_end)
            if count >= burst_threshold:
                bursts += 1
        
        return bursts
    
    def _calculate_entropy(self, fingerprints):
        """
        Calculate Shannon entropy of packet fingerprints.
        Low entropy = repetitive patterns (potential loop).
        """
        if not fingerprints:
            return 0
        
        total = sum(fingerprints.values())
        entropy = 0
        
        for count in fingerprints.values():
            p = count / total
            if p > 0:
                entropy -= p * (p ** 0.5)  # Modified entropy for loop detection
        
        return entropy
    
    def _is_legitimate_traffic(self, mac, stats):
        """
        Determine if traffic pattern is likely legitimate.
        Returns (is_legitimate, reason).
        """
        # Check whitelist
        if mac in self.legitimate_patterns["dhcp_servers"]:
            if stats.get("dhcp_count", 0) > stats.get("arp_count", 0):
                return True, "Known DHCP server"
        
        if mac in self.legitimate_patterns["routers"]:
            return True, "Known router"
        
        if mac in self.legitimate_patterns["mdns_devices"]:
            if stats.get("mdns_count", 0) > 0 and stats.get("arp_count", 0) < 10:
                return True, "Legitimate mDNS device"
        
        # Check for DHCP server behavior (controlled broadcast)
        dhcp_ratio = stats.get("dhcp_count", 0) / max(1, stats.get("count", 1))
        if dhcp_ratio > 0.8 and stats.get("count", 0) < 100:
            self.legitimate_patterns["dhcp_servers"].add(mac)
            return True, "DHCP server behavior"
        
        # Check for normal mDNS pattern (periodic, low volume)
        mdns_count = stats.get("mdns_count", 0)
        if mdns_count > 0 and stats.get("count", 0) < 20:
            packet_times = self.mac_history[mac]["packet_times"]
            if len(packet_times) > 0:
                freq = self._calculate_packet_frequency(packet_times)
                if freq < 2:  # Less than 2 packets/sec
                    self.legitimate_patterns["mdns_devices"].add(mac)
                    return True, "Normal mDNS traffic"
        
        return False, None
    
    def _calculate_advanced_severity(self, mac, stats, timeout):
        """
        Calculate advanced severity score using multiple factors:
        - Packet frequency and bursts
        - Packet type distribution
        - Pattern entropy
        - Subnet diversity
        - Time-based analysis
        """
        packet_times = self.mac_history[mac]["packet_times"]
        
        # Factor 1: Packet frequency (packets/second)
        frequency = self._calculate_packet_frequency(packet_times)
        freq_score = min(frequency / 10, 10)  # Normalize to 0-10
        
        # Factor 2: Burst detection
        bursts = self._detect_packet_bursts(packet_times)
        burst_score = min(bursts / 5, 10)  # Normalize to 0-10
        
        # Factor 3: Packet type diversity (inverse entropy)
        fingerprints = stats.get("fingerprints", {})
        entropy = self._calculate_entropy(fingerprints)
        # Low entropy = high repetition = higher score
        entropy_score = max(0, 10 - entropy * 2)
        
        # Factor 4: Subnet diversity (crossing subnets = suspicious)
        subnets = self.mac_history[mac]["subnets"]
        subnet_score = min(len(subnets) * 3, 10)
        
        # Factor 5: Weighted packet type scoring
        arp_score = stats.get("arp_count", 0) * 2.5
        stp_score = stats.get("stp_count", 0) * 5  # STP loops are critical
        lldp_score = stats.get("lldp_count", 0) * 4
        cdp_score = stats.get("cdp_count", 0) * 4
        dhcp_score = stats.get("dhcp_count", 0) * 0.5  # Lower weight
        mdns_score = stats.get("mdns_count", 0) * 0.3  # Lower weight
        nbns_score = stats.get("nbns_count", 0) * 0.4
        icmp_score = stats.get("icmp_redirect_count", 0) * 3
        other_score = stats.get("other_count", 0) * 1.5
        
        packet_type_score = (
            arp_score + stp_score + lldp_score + cdp_score +
            dhcp_score + mdns_score + nbns_score + icmp_score + other_score
        ) / max(1, timeout)
        
        # Factor 6: IP change frequency (dynamic IP handling)
        ip_changes = len(self.mac_history[mac]["ip_changes"])
        ip_change_score = min(ip_changes * 0.5, 5)
        
        # Combine all factors with weights
        total_severity = (
            freq_score * 1.5 +
            burst_score * 2.0 +
            entropy_score * 1.2 +
            subnet_score * 1.8 +
            packet_type_score * 1.0 +
            ip_change_score * 0.5
        )
        
        return {
            "total": total_severity,
            "frequency": freq_score,
            "bursts": burst_score,
            "entropy": entropy_score,
            "subnets": subnet_score,
            "packet_types": packet_type_score,
            "ip_changes": ip_change_score
        }


def detect_loops(timeout=10, threshold=100, iface=None, enable_advanced=True):
    """
    Enhanced loop detection with multi-router support and advanced severity scoring.
    
    Returns (total_count, offenders, stats, advanced_metrics).
    
    stats[mac] = {
        "count": int,
        "arp_count": int,
        "dhcp_count": int,
        "mdns_count": int,
        "nbns_count": int,
        "stp_count": int,  # NEW: Spanning Tree Protocol
        "lldp_count": int,  # NEW: Link Layer Discovery Protocol
        "cdp_count": int,  # NEW: Cisco Discovery Protocol
        "icmp_redirect_count": int,  # NEW: ICMP redirects
        "other_count": int,
        "ips": [list],
        "subnets": [list],  # NEW: Subnets seen
        "hosts": [list],
        "fingerprints": {pkt_sig: count},
        "severity": float or dict,  # Simple or advanced
        "is_legitimate": bool,  # NEW: Legitimacy flag
        "legitimate_reason": str,  # NEW: Why it's legitimate
    }
    
    advanced_metrics = {
        "detection_method": str,
        "baseline_deviation": float,
        "cross_subnet_activity": bool,
        "timestamp": datetime
    }
    """
    engine = LoopDetectionEngine() if enable_advanced else None
    
    stats = defaultdict(lambda: {
        "count": 0,
        "arp_count": 0,
        "dhcp_count": 0,
        "mdns_count": 0,
        "nbns_count": 0,
        "stp_count": 0,
        "lldp_count": 0,
        "cdp_count": 0,
        "icmp_redirect_count": 0,
        "other_count": 0,
        "ips": set(),
        "subnets": set(),
        "hosts": set(),
        "fingerprints": {},
        "severity": 0.0,
        "is_legitimate": False,
        "legitimate_reason": None
    })
    
    start_time = time.time()

    def pkt_handler(pkt):
        try:
            if pkt.haslayer(Ether):
                src = pkt[Ether].src
                current_time = time.time()
                
                # Track packet timing
                if engine:
                    engine.mac_history[src]["packet_times"].append(current_time)
                    if engine.mac_history[src]["first_seen"] is None:
                        engine.mac_history[src]["first_seen"] = current_time

                # ARP broadcast
                if pkt.haslayer(ARP) and pkt[ARP].op == 1 and pkt[Ether].dst == "ff:ff:ff:ff:ff:ff":
                    stats[src]["count"] += 1
                    stats[src]["arp_count"] += 1
                    if pkt[ARP].psrc:
                        ip = pkt[ARP].psrc
                        stats[src]["ips"].add(ip)
                        
                        # Track subnet
                        if engine:
                            subnet = engine._extract_subnet(ip)
                            if subnet:
                                stats[src]["subnets"].add(subnet)
                                engine.mac_history[src]["subnets"].add(subnet)
                            
                            # Track IP changes
                            if engine.mac_history[src]["last_ip"] != ip:
                                engine.mac_history[src]["ip_changes"].append(
                                    (current_time, ip)
                                )
                                engine.mac_history[src]["last_ip"] = ip

                # IPv4 broadcast
                elif pkt.haslayer(IP) and pkt[IP].dst == "255.255.255.255":
                    stats[src]["count"] += 1
                    ip = pkt[IP].src
                    stats[src]["ips"].add(ip)
                    
                    # Track subnet
                    if engine:
                        subnet = engine._extract_subnet(ip)
                        if subnet:
                            stats[src]["subnets"].add(subnet)
                            engine.mac_history[src]["subnets"].add(subnet)

                    # DHCP (UDP/67,68)
                    if pkt.haslayer(UDP) and pkt[UDP].sport in (67, 68):
                        stats[src]["dhcp_count"] += 1

                    # mDNS (UDP/5353)
                    elif pkt.haslayer(UDP) and pkt[UDP].dport == 5353:
                        stats[src]["mdns_count"] += 1

                    # NetBIOS Name Service (UDP/137)
                    elif pkt.haslayer(UDP) and pkt[UDP].dport == 137:
                        stats[src]["nbns_count"] += 1

                    else:
                        stats[src]["other_count"] += 1
                
                # NEW: Spanning Tree Protocol (STP) - Critical for loop detection
                elif pkt.haslayer(Ether) and pkt[Ether].dst == "01:80:c2:00:00:00":
                    stats[src]["count"] += 1
                    stats[src]["stp_count"] += 1
                
                # NEW: LLDP (Link Layer Discovery Protocol)
                elif pkt.haslayer(Ether) and pkt[Ether].dst == "01:80:c2:00:00:0e":
                    stats[src]["count"] += 1
                    stats[src]["lldp_count"] += 1
                
                # NEW: CDP (Cisco Discovery Protocol)
                elif pkt.haslayer(Ether) and pkt[Ether].dst == "01:00:0c:cc:cc:cc":
                    stats[src]["count"] += 1
                    stats[src]["cdp_count"] += 1
                
                # NEW: ICMP Redirects (can indicate routing loops)
                elif pkt.haslayer(IP):
                    from scapy.layers.inet import ICMP
                    if pkt.haslayer(ICMP) and pkt[ICMP].type == 5:
                        stats[src]["count"] += 1
                        stats[src]["icmp_redirect_count"] += 1
                        stats[src]["ips"].add(pkt[IP].src)
                
                else:
                    stats[src]["count"] += 1
                    stats[src]["other_count"] += 1

                # Track packet fingerprints (for pattern analysis)
                sig = pkt.summary()
                stats[src]["fingerprints"][sig] = stats[src]["fingerprints"].get(sig, 0) + 1
                
        except Exception as e:
            logging.debug(f"Packet handler error: {e}")

    # Capture packets
    sniff(prn=pkt_handler, timeout=timeout, store=0, iface=iface)

    # Post-processing
    cross_subnet_activity = False
    
    for mac, info in stats.items():
        # Convert sets to lists
        ip_list = list(info["ips"])
        subnet_list = list(info["subnets"])
        info["ips"] = ip_list
        info["subnets"] = subnet_list
        
        # Check for cross-subnet activity
        if len(subnet_list) > 1:
            cross_subnet_activity = True

        # Reverse DNS lookup
        hosts = []
        for ip in ip_list[:5]:  # Limit to first 5 IPs for performance
            try:
                hosts.append(socket.gethostbyaddr(ip)[0])
            except Exception:
                pass
        info["hosts"] = hosts if hosts else ["Unknown"]

        # Calculate severity
        if enable_advanced and engine:
            severity_details = engine._calculate_advanced_severity(mac, info, timeout)
            info["severity"] = severity_details
            
            # Check legitimacy
            is_legit, reason = engine._is_legitimate_traffic(mac, info)
            info["is_legitimate"] = is_legit
            info["legitimate_reason"] = reason
        else:
            # Simple severity scoring (original method)
            info["severity"] = (
                info["arp_count"] * 2 +
                info["dhcp_count"] * 1 +
                info["mdns_count"] * 0.5 +
                info["nbns_count"] * 0.5 +
                info["stp_count"] * 5 +
                info["lldp_count"] * 4 +
                info["cdp_count"] * 4 +
                info["icmp_redirect_count"] * 3 +
                info["other_count"] * 3
            ) / max(1, timeout)

    total_count = sum(info["count"] for info in stats.values())

    # Identify offenders
    offenders = []
    for mac, info in stats.items():
        # Skip legitimate traffic
        if info.get("is_legitimate", False):
            continue
        
        # Check severity
        if enable_advanced and isinstance(info["severity"], dict):
            severity_value = info["severity"]["total"]
        else:
            severity_value = info["severity"]
        
        if severity_value > threshold:
            offenders.append(mac)

    # Advanced metrics
    advanced_metrics = {
        "detection_method": "advanced" if enable_advanced else "simple",
        "cross_subnet_activity": cross_subnet_activity,
        "total_unique_macs": len(stats),
        "total_unique_ips": len(set(ip for info in stats.values() for ip in info["ips"])),
        "total_unique_subnets": len(set(sub for info in stats.values() for sub in info["subnets"])),
        "timestamp": datetime.now(),
        "duration": timeout
    }

    return total_count, list(set(offenders)), stats, advanced_metrics


def detect_loops_lightweight(timeout=5, threshold=50, iface=None, use_sampling=True):
    """
    Optimized lightweight loop detection for automatic monitoring.
    Uses shorter timeout, reduced packet analysis, simplified scoring, and intelligent sampling.
    
    Args:
        timeout: Capture duration in seconds
        threshold: Severity threshold for flagging offenders (LOWERED for better sensitivity)
        iface: Network interface to monitor
        use_sampling: Enable intelligent packet sampling for efficiency
    
    Returns (total_count, offenders, stats, status, severity_score, efficiency_metrics).
    """
    # Enhanced logging for debugging
    logging.info(f"🔍 Starting lightweight loop detection (timeout={timeout}s, threshold={threshold}, iface={iface})")
    
    stats = defaultdict(lambda: {
        "count": 0,
        "arp_count": 0,
        "broadcast_count": 0,
        "stp_count": 0,
        "ips": set(),
        "subnets": set(),
        "severity": 0.0
    })
    
    packet_count = 0
    sampled_count = 0
    start_time = time.time()
    
    # Bloom filter for duplicate detection (memory efficient)
    seen_packets = set()  # For lightweight, use set (could use bloom filter library for scale)
    
    # Sampling strategy: sample every Nth packet when traffic is high
    sample_rate = 1
    high_traffic_threshold = 100  # packets/sec

    def pkt_handler(pkt):
        nonlocal packet_count, sampled_count, sample_rate
        
        try:
            packet_count += 1
            
            # Log first few packets for debugging
            if packet_count <= 10:
                logging.debug(f"Packet #{packet_count}: {pkt.summary()}")
            
            # Dynamic sampling: adjust sample rate based on traffic volume
            if use_sampling:
                elapsed = time.time() - start_time
                if elapsed > 0:
                    pps = packet_count / elapsed  # packets per second
                    if pps > high_traffic_threshold:
                        sample_rate = max(1, int(pps / high_traffic_threshold))
                    else:
                        sample_rate = 1
                
                # Skip packets based on sample rate
                if packet_count % sample_rate != 0:
                    return
            
            sampled_count += 1
            
            # Early exit if too many packets (potential storm)
            if sampled_count > 1000:
                return
                
            if pkt.haslayer(Ether):
                src = pkt[Ether].src
                
                # DISABLED duplicate detection for better capture
                # This was filtering out legitimate loop packets
                # pkt_hash = hash(pkt.summary())
                # if pkt_hash in seen_packets:
                #     return  # Skip duplicate
                # seen_packets.add(pkt_hash)
                
                # Limit seen_packets size for memory efficiency
                # if len(seen_packets) > 5000:
                #     seen_packets.clear()

                # Broadcast traffic detection (most relevant for loops)
                if pkt[Ether].dst == "ff:ff:ff:ff:ff:ff":
                    stats[src]["count"] += 1
                    
                    # ARP broadcast
                    if pkt.haslayer(ARP) and pkt[ARP].op == 1:
                        stats[src]["arp_count"] += 1
                        if pkt[ARP].psrc:
                            ip = pkt[ARP].psrc
                            stats[src]["ips"].add(ip)
                            
                            # Track subnet
                            try:
                                parts = ip.split('.')
                                subnet = '.'.join(parts[:3]) + '.0/24'
                                stats[src]["subnets"].add(subnet)
                            except:
                                pass
                    
                    # IPv4 broadcast
                    elif pkt.haslayer(IP) and pkt[IP].dst == "255.255.255.255":
                        stats[src]["broadcast_count"] += 1
                        ip = pkt[IP].src
                        stats[src]["ips"].add(ip)
                        
                        # Track subnet
                        try:
                            parts = ip.split('.')
                            subnet = '.'.join(parts[:3]) + '.0/24'
                            stats[src]["subnets"].add(subnet)
                        except:
                            pass
                
                # STP detection (critical for loops)
                elif pkt[Ether].dst == "01:80:c2:00:00:00":
                    stats[src]["count"] += 1
                    stats[src]["stp_count"] += 1
                        
        except Exception as e:
            logging.debug(f"Lightweight packet handler error: {e}")

    try:
        logging.info(f"📡 Starting packet capture on interface: {iface or 'default'}")
        sniff(prn=pkt_handler, timeout=timeout, store=0, iface=iface)
        logging.info(f"📦 Capture complete. Packets seen: {packet_count}, Analyzed: {sampled_count}")
    except PermissionError:
        logging.error("❌ Permission denied! Run as Administrator.")
        return 0, [], {}, "error", 0.0, {"error": "Permission denied"}
    except Exception as e:
        logging.error(f"Loop detection failed: {e}")
        return 0, [], {}, "error", 0.0, {"error": str(e)}

    # Log capture summary
    logging.info(f"Unique MACs detected: {len(stats)}")
    for mac, info in list(stats.items())[:5]:  # Log first 5 MACs
        logging.debug(f"  {mac}: {info['count']} packets (ARP: {info['arp_count']}, Broadcast: {info['broadcast_count']})")

    # Convert sets to lists and calculate metrics
    cross_subnet_detected = False
    
    for mac, info in stats.items():
        info["ips"] = list(info["ips"])
        subnet_list = list(info["subnets"])
        info["subnets"] = subnet_list
        
        if len(subnet_list) > 1:
            cross_subnet_detected = True
        
        # LOWERED MULTIPLIERS for better sensitivity
        subnet_penalty = len(subnet_list) * 3 if len(subnet_list) > 1 else 0
        
        # Adjusted scoring - more aggressive detection
        info["severity"] = (
            info["arp_count"] * 4 +  # Increased from 3 to 4
            info["broadcast_count"] * 2.5 +  # Increased from 1.5 to 2.5
            info["stp_count"] * 8 +  # Increased from 6 to 8
            subnet_penalty +
            info["count"] * 0.5  # Added general packet count bonus
        ) / max(1, timeout)
        
        # Log severity calculation
        if info["severity"] > 10:
            logging.info(f"  {mac}: severity={info['severity']:.1f} (ARP:{info['arp_count']}, BC:{info['broadcast_count']}, total:{info['count']})")

    total_count = sum(info["count"] for info in stats.values())
    max_severity = max((info["severity"] for info in stats.values()), default=0.0)
    
    logging.info(f"Max severity: {max_severity:.1f} (threshold: {threshold})")
    
    # LOWERED THRESHOLDS - More sensitive detection
    if max_severity > threshold * 1.5 or (cross_subnet_detected and max_severity > threshold * 0.7):
        status = "loop_detected"
    elif max_severity > threshold * 0.5:  # Lowered from threshold to threshold * 0.5
        status = "suspicious"
    else:
        status = "clean"
    
    logging.info(f"Detection status: {status.upper()}")
    
    # Find offenders
    offenders = []
    for mac, info in stats.items():
        if info["severity"] > threshold:
            offenders.append(mac)
    
    # Efficiency metrics
    efficiency_metrics = {
        "total_packets_seen": packet_count,
        "packets_analyzed": sampled_count,
        "sample_rate": sample_rate,
        "efficiency_ratio": sampled_count / max(1, packet_count),
        "cross_subnet_detected": cross_subnet_detected,
        "unique_macs": len(stats),
        "unique_subnets": len(set(sub for info in stats.values() for sub in info["subnets"]))
    }

    return total_count, offenders, dict(stats), status, max_severity, efficiency_metrics


def auto_loop_detection(iface=None, save_to_db=True, api_base_url="http://localhost:5000", use_advanced=False):
    """
    Automatic loop detection with database saving and multi-subnet support.
    Optimized for background monitoring with intelligent sampling.
    
    Args:
        iface: Network interface to monitor (auto-detected if None)
        save_to_db: Whether to save results to database
        api_base_url: Base URL for API endpoint
        use_advanced: Use advanced detection engine (more CPU intensive)
    
    Returns:
        Dictionary with detection results and metrics
    """
    try:
        if iface is None:
            iface = get_default_iface()
        
        # Choose detection method based on requirements
        if use_advanced:
            # Advanced detection with full analysis
            total_packets, offenders, stats, advanced_metrics = detect_loops(
                timeout=5,
                threshold=40,
                iface=iface,
                enable_advanced=True
            )
            
            # Extract severity from advanced stats
            severity_scores = []
            for mac, info in stats.items():
                if isinstance(info.get("severity"), dict):
                    severity_scores.append(info["severity"]["total"])
                else:
                    severity_scores.append(info.get("severity", 0))
            
            max_severity = max(severity_scores) if severity_scores else 0.0
            
            # Determine status
            if max_severity > 80 or advanced_metrics.get("cross_subnet_activity", False):
                status = "loop_detected"
            elif max_severity > 40:
                status = "suspicious"
            else:
                status = "clean"
            
            efficiency_metrics = {
                "detection_method": "advanced",
                "cross_subnet_activity": advanced_metrics.get("cross_subnet_activity", False),
                "unique_macs": advanced_metrics.get("total_unique_macs", 0),
                "unique_subnets": advanced_metrics.get("total_unique_subnets", 0)
            }
            
        else:
            # Lightweight detection with sampling
            total_packets, offenders, stats, status, max_severity, efficiency_metrics = detect_loops_lightweight(
                timeout=3,
                threshold=30,
                iface=iface,
                use_sampling=True
            )
        
        # Filter out legitimate traffic for reporting
        filtered_offenders = []
        filtered_stats = {}
        
        for mac in offenders:
            if mac in stats:
                # Skip if marked as legitimate
                if not stats[mac].get("is_legitimate", False):
                    filtered_offenders.append(mac)
                    filtered_stats[mac] = stats[mac]
        
        # Prepare data for database
        detection_data = {
            "total_packets": total_packets,
            "offenders_count": len(filtered_offenders),
            "offenders_data": {
                "offenders": filtered_offenders,
                "stats": filtered_stats
            },
            "severity_score": max_severity,
            "network_interface": iface or "unknown",
            "detection_duration": 5 if use_advanced else 3,
            "status": status,
            "cross_subnet_detected": efficiency_metrics.get("cross_subnet_detected", False) or 
                                     efficiency_metrics.get("cross_subnet_activity", False),
            "unique_subnets": efficiency_metrics.get("unique_subnets", 0),
            "efficiency_metrics": efficiency_metrics
        }
        
        # Save to database if requested
        if save_to_db:
            try:
                response = requests.post(
                    f"{api_base_url}/api/loop-detection",
                    json=detection_data,
                    timeout=5
                )
                
                if response.status_code == 200:
                    logging.info(f"Loop detection result saved: {status} (severity: {max_severity:.2f})")
                else:
                    logging.warning(f"Failed to save loop detection: {response.text}")
                    
            except Exception as e:
                logging.error(f"Database save failed: {e}")
        
        return {
            "success": True,
            "total_packets": total_packets,
            "offenders": filtered_offenders,
            "status": status,
            "severity_score": max_severity,
            "cross_subnet_detected": detection_data["cross_subnet_detected"],
            "efficiency_metrics": efficiency_metrics,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logging.error(f"Auto loop detection failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


def discover_clients(timeout=10, iface=None):
    """
    Sniff network traffic for a while and return discovered clients.
    Returns: dict {mac: {"ip": str, "vendor": str, "hostname": str, "last_seen": datetime}}
    """
    global clients

    def pkt_handler(pkt):
        try:
            if pkt.haslayer(Ether):
                mac = pkt[Ether].src
                now = datetime.now()

                if mac not in clients:
                    clients[mac] = {"ip": None, "vendor": "Unknown", "hostname": "Unknown", "last_seen": now}

                clients[mac]["last_seen"] = now

                if pkt.haslayer(IP):
                    clients[mac]["ip"] = pkt[IP].src
                    try:
                        clients[mac]["hostname"] = socket.gethostbyaddr(pkt[IP].src)[0]
                    except Exception:
                        clients[mac]["hostname"] = "Unknown"

                elif pkt.haslayer(ARP) and pkt[ARP].psrc:
                    clients[mac]["ip"] = pkt[ARP].psrc
                    try:
                        clients[mac]["hostname"] = socket.gethostbyaddr(pkt[ARP].psrc)[0]
                    except Exception:
                        clients[mac]["hostname"] = "Unknown"

        except Exception:
            pass

    sniff(prn=pkt_handler, timeout=timeout, store=0, iface=iface)
    return clients.copy()

def get_local_subnet():
    """Get the local subnet hosts based on active interface."""
    addrs = psutil.net_if_addrs()
    iface = get_default_iface()
    if not iface:
        return []

    ip = None
    netmask = None
    for snic in addrs[iface]:
        if snic.family.name == "AF_INET" and snic.address != "127.0.0.1":
            ip = snic.address
            netmask = snic.netmask
            break

    if not ip or not netmask:
        return []

    network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
    return list(network.hosts())  # all possible host IPs

def scan_subnet(iface=None, timeout=2):
    """
    Scan the local subnet using ARP and return active clients.
    Returns: dict {mac: {"ip": str, "hostname": str, "vendor": str, "last_seen": datetime}}
    """
    hosts = get_local_subnet()
    if not hosts:
        return {}

    if iface is None:
        iface = get_default_iface()

    clients = {}

    # ARP request for all hosts
    pkt = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=[str(h) for h in hosts])
    ans, _ = srp(pkt, timeout=timeout, iface=iface, verbose=0)

    for snd, rcv in ans:
        mac = rcv[Ether].src
        ip = rcv[ARP].psrc
        try:
            hostname = socket.gethostbyaddr(ip)[0]
        except Exception:
            hostname = "Unknown"

        clients[mac] = {
            "ip": ip,
            "hostname": hostname,
            "vendor": "Unknown",
            "last_seen": datetime.now()
        }

    return clients


def scan_router_subnet(router_ip, netmask="255.255.255.0", iface=None, timeout=2):
    """
    Scan a specific router's subnet based on its IP address.
    
    Args:
        router_ip: The router's IP address (e.g., "192.168.1.1")
        netmask: The subnet mask (default: "255.255.255.0" for /24)
        iface: Network interface to use (optional, auto-detected if None)
        timeout: ARP scan timeout in seconds
    
    Returns:
        dict {mac: {"ip": str, "hostname": str, "vendor": str, "last_seen": datetime}}
    """
    try:
        # Calculate the network range from router IP and netmask
        network = ipaddress.IPv4Network(f"{router_ip}/{netmask}", strict=False)
        hosts = list(network.hosts())
        
        if not hosts:
            print(f"⚠️ No hosts found in subnet {network}")
            return {}
        
        if iface is None:
            iface = get_default_iface()
        
        print(f"🔍 Scanning {len(hosts)} hosts in subnet {network} on interface {iface}...")
        
        clients = {}
        
        # ARP request for all hosts in the router's subnet
        pkt = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=[str(h) for h in hosts])
        ans, _ = srp(pkt, timeout=timeout, iface=iface, verbose=0)
        
        for snd, rcv in ans:
            mac = rcv[Ether].src
            ip = rcv[ARP].psrc
            try:
                hostname = socket.gethostbyaddr(ip)[0]
            except Exception:
                hostname = "Unknown"
            
            clients[mac] = {
                "ip": ip,
                "hostname": hostname,
                "vendor": "Unknown",
                "last_seen": datetime.now()
            }
        
        print(f"✅ Found {len(clients)} clients in subnet {network}")
        return clients
        
    except Exception as e:
        print(f"❌ Error scanning router subnet {router_ip}: {e}")
        return {}


def get_all_active_interfaces():
    """
    Get all active network interfaces (both WiFi and LAN).
    Returns list of interface names that are UP and have IP addresses.
    """
    active_interfaces = []
    try:
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        
        for iface, snic_list in addrs.items():
            # Check if interface is UP
            if iface in stats and stats[iface].isup:
                # Check if it has an IPv4 address
                has_ipv4 = any(snic.family.name.startswith("AF_INET") for snic in snic_list)
                if has_ipv4:
                    active_interfaces.append(iface)
        
        print(f"🌐 Active network interfaces detected: {', '.join(active_interfaces) if active_interfaces else 'None'}")
    except Exception as e:
        print(f"⚠️ Error detecting interfaces: {e}")
    
    return active_interfaces


def detect_loops_multi_interface(timeout=5, threshold=15, use_sampling=False):
    """
    Enhanced loop detection that monitors ALL active network interfaces simultaneously.
    Perfect for environments where:
    - APs are on LAN but admin app connects via WiFi or LAN
    - Need to detect loops across entire network regardless of connection method
    - Multiple network segments need monitoring
    
    Args:
        timeout: Packet capture duration per interface (seconds)
        threshold: Minimum severity score to consider as potential loop (LOWERED for sensitivity)
        use_sampling: Use intelligent sampling for better performance (DISABLED by default for full capture)
    
    Returns:
        Tuple: (total_packets, combined_offenders, combined_stats, overall_status, max_severity, efficiency_metrics)
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import time
    
    logging.info(f"🚀 Starting multi-interface detection (timeout={timeout}s, threshold={threshold}, sampling={use_sampling})")
    
    start_time = time.time()
    interfaces = get_all_active_interfaces()
    
    if not interfaces:
        logging.warning("⚠️ No active network interfaces found!")
        print("⚠️ No active network interfaces found!")
        return 0, [], {}, "error", 0.0, {"error": "No active interfaces"}
    
    print(f"🔍 Starting multi-interface loop detection on {len(interfaces)} interface(s)...")
    logging.info(f"Interfaces to scan: {interfaces}")
    
    combined_stats = {}
    combined_offenders = []
    total_packets = 0
    all_results = []
    interfaces_scanned = []
    
    def scan_interface(iface):
        """Scan a single interface"""
        try:
            print(f"  📡 Scanning interface: {iface}")
            result = detect_loops_lightweight(
                timeout=timeout,
                threshold=threshold,
                iface=iface,
                use_sampling=use_sampling
            )
            return (iface, result, None)
        except Exception as e:
            print(f"  ⚠️ Error scanning {iface}: {e}")
            return (iface, None, str(e))
    
    # Parallel scanning of all interfaces
    with ThreadPoolExecutor(max_workers=len(interfaces)) as executor:
        future_to_iface = {executor.submit(scan_interface, iface): iface for iface in interfaces}
        
        for future in as_completed(future_to_iface):
            iface, result, error = future.result()
            
            if error:
                print(f"  ❌ Failed to scan {iface}: {error}")
                continue
            
            if result:
                interfaces_scanned.append(iface)
                pkts, offenders, stats, status, severity, eff = result
                all_results.append({
                    'interface': iface,
                    'packets': pkts,
                    'offenders': offenders,
                    'status': status,
                    'severity': severity
                })
                
                total_packets += pkts
                
                # Merge statistics from this interface
                for mac, info in stats.items():
                    if mac not in combined_stats:
                        combined_stats[mac] = info.copy()
                        combined_stats[mac]['interfaces'] = [iface]
                    else:
                        # MAC seen on multiple interfaces - more suspicious!
                        combined_stats[mac]['interfaces'].append(iface)
                        combined_stats[mac]['count'] += info.get('count', 0)
                        
                        # Increase severity if seen on multiple interfaces
                        if len(combined_stats[mac]['interfaces']) > 1:
                            if isinstance(combined_stats[mac].get('severity'), dict):
                                combined_stats[mac]['severity']['multi_interface_bonus'] = 15
                                combined_stats[mac]['severity']['total'] = min(100, 
                                    combined_stats[mac]['severity'].get('total', 0) + 15)
                            else:
                                combined_stats[mac]['severity'] = min(100, 
                                    combined_stats[mac].get('severity', 0) + 15)
                
                # Add offenders from this interface
                for mac in offenders:
                    if mac not in combined_offenders:
                        combined_offenders.append(mac)
    
    # Calculate overall status and severity
    max_severity = 0.0
    cross_interface_activity = False
    
    for mac, info in combined_stats.items():
        # Check if MAC appears on multiple interfaces (strong loop indicator)
        if len(info.get('interfaces', [])) > 1:
            cross_interface_activity = True
            logging.warning(f"⚠️ Cross-interface activity detected for {mac} on interfaces: {info.get('interfaces')}")
        
        # Get severity score
        if isinstance(info.get('severity'), dict):
            severity = info['severity'].get('total', 0)
        else:
            severity = info.get('severity', 0)
        
        max_severity = max(max_severity, severity)
        
        # Log high severity MACs
        if severity > threshold * 0.5:
            logging.info(f"  High severity MAC: {mac}, score={severity:.1f}, packets={info.get('count', 0)}")
    
    # LOWERED THRESHOLDS - Determine overall status with more sensitivity
    if max_severity > threshold * 3 or cross_interface_activity:
        overall_status = "loop_detected"
    elif max_severity > threshold * 0.8 or len(combined_offenders) > 0:
        overall_status = "suspicious"
    else:
        overall_status = "clean"
    
    logging.info(f"Overall status: {overall_status.upper()}, max_severity={max_severity:.1f}")
    
    # Calculate efficiency metrics
    detection_duration = time.time() - start_time
    efficiency_metrics = {
        "detection_method": "multi_interface",
        "interfaces_scanned": interfaces_scanned,
        "total_interfaces": len(interfaces),
        "cross_interface_activity": cross_interface_activity,
        "unique_macs": len(combined_stats),
        "detection_duration": round(detection_duration, 2),
        "packets_per_second": round(total_packets / detection_duration, 2) if detection_duration > 0 else 0,
        "interface_results": all_results
    }
    
    # Print summary
    print(f"\n📊 Multi-Interface Scan Summary:")
    print(f"  ✓ Interfaces scanned: {len(interfaces_scanned)}/{len(interfaces)}")
    print(f"  ✓ Total packets: {total_packets}")
    print(f"  ✓ Unique MACs: {len(combined_stats)}")
    print(f"  ✓ Offenders: {len(combined_offenders)}")
    print(f"  ✓ Status: {overall_status.upper()}")
    print(f"  ✓ Max severity: {max_severity:.1f}")
    print(f"  ✓ Duration: {detection_duration:.2f}s")
    
    if cross_interface_activity:
        print(f"  ⚠️ ALERT: Cross-interface loop activity detected!")
    
    return total_packets, combined_offenders, combined_stats, overall_status, max_severity, efficiency_metrics