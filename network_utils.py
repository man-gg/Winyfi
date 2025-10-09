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

def ping_latency(ip, timeout=1000, bandwidth=None):
    """Return ping latency in ms, using dynamic interval. Pass bandwidth in Mbps."""
    if not ping_manager.should_ping():
        return None  # Skip ping to avoid congestion
    param = "-n" if platform.system().lower() == "windows" else "-c"
    cmd = ["ping", param, "1", "-w", str(timeout), ip]
    try:
        start = time.time()
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        end = time.time()
        if result.returncode == 0:
            latency = round((end - start) * 1000, 2)  # ms
            ping_manager.update(latency, bandwidth)
            logging.debug(f"Ping to {ip}: {latency} ms (interval: {ping_manager.current_interval}s, bandwidth: {bandwidth})")
            return latency
    except Exception as e:
        logging.error(f"Ping failed: {e}")
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



# ---------------- SETTINGS ----------------
DISABLE_BANDWIDTH = True
SPEEDTEST_COOLDOWN = 3600    # seconds (1 hour)
MINI_SPEEDTEST_INTERVAL = 1200   # seconds (6 minutes)
LATENCY_THRESHOLD = 200      # ms
ANOMALY_WINDOW = 5           # check last N pings
# ------------------------------------------

# Trackers
LAST_SPEEDTEST = 0
LAST_MINI = 0
latency_history = deque(maxlen=ANOMALY_WINDOW)


def get_speedtest_results():
    """Full Speedtest (heavy)."""
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
    """Lightweight throughput measurement."""
    counters1 = psutil.net_io_counters()
    time.sleep(interval)
    counters2 = psutil.net_io_counters()

    bytes_sent = counters2.bytes_sent - counters1.bytes_sent
    bytes_recv = counters2.bytes_recv - counters1.bytes_recv

    upload_mbps = (bytes_sent * 8) / (interval * 1_000_000)
    download_mbps = (bytes_recv * 8) / (interval * 1_000_000)

    return round(download_mbps, 2), round(upload_mbps, 2)


def get_mini_speedtest():
    """Mini speedtest (1MB download, 512KB upload)."""
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


def get_bandwidth(ip):
    """Hybrid: Ping + Throughput + Mini Speedtest + Full Speedtest.
       Returns 0 bandwidth if device is offline.
    """
    global LAST_SPEEDTEST, LAST_MINI
    latency = ping_latency(ip)

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
            }
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
            }
        }

    now = time.time()
    need_speedtest = False
    need_mini = False

    # Condition 1: full speedtest cooldown
    if now - LAST_SPEEDTEST > SPEEDTEST_COOLDOWN:
        need_speedtest = True

    # Condition 2: anomaly detection
    avg_latency = sum(latency_history) / len(latency_history)
    if avg_latency > LATENCY_THRESHOLD and (now - LAST_SPEEDTEST > 900):  # 15 min guard
        logging.warning(f"Latency anomaly detected (avg {avg_latency:.1f} ms), forcing full speedtest...")
        need_speedtest = True

    # Condition 3: mini speedtest interval
    if now - LAST_MINI > MINI_SPEEDTEST_INTERVAL:
        need_mini = True

    try:
        if need_speedtest:
            results = get_speedtest_results()
            LAST_SPEEDTEST = now
            return results
        elif need_mini:
            results = get_mini_speedtest()
            LAST_MINI = now
            return results
    except Exception as e:
        logging.error(f"Speedtest failed: {e}")

    # fallback → throughput
    dl, ul = get_throughput(interval=1)
    return {
        "latency": latency,
        "download": dl,
        "upload": ul,
        "quality": {
            "latency": _rate_latency(latency),
            "download": _rate_bandwidth(dl),
            "upload": _rate_bandwidth(ul)
        }
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

def detect_loops(timeout=10, threshold=100, iface=None):
    """
    Detect broadcast storms or loops with severity scoring.
    Returns (total_count, offenders, stats).
    stats[mac] = {
        "count": int,
        "arp_count": int,
        "dhcp_count": int,
        "mdns_count": int,
        "nbns_count": int,
        "other_count": int,
        "ips": [list],
        "hosts": [list],
        "fingerprints": {pkt_sig: count},
        "severity": float
    }
    """
    stats = defaultdict(lambda: {
        "count": 0,
        "arp_count": 0,
        "dhcp_count": 0,
        "mdns_count": 0,
        "nbns_count": 0,
        "other_count": 0,
        "ips": set(),
        "hosts": set(),
        "fingerprints": {},
        "severity": 0.0
    })

    def pkt_handler(pkt):
        try:
            if pkt.haslayer(Ether):
                src = pkt[Ether].src

                # ARP broadcast
                if pkt.haslayer(ARP) and pkt[ARP].op == 1 and pkt[Ether].dst == "ff:ff:ff:ff:ff:ff":
                    stats[src]["count"] += 1
                    stats[src]["arp_count"] += 1
                    if pkt[ARP].psrc:
                        stats[src]["ips"].add(pkt[ARP].psrc)

                # IPv4 broadcast
                elif pkt.haslayer(IP) and pkt[IP].dst == "255.255.255.255":
                    stats[src]["count"] += 1

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

                    stats[src]["ips"].add(pkt[IP].src)

                else:
                    stats[src]["count"] += 1
                    stats[src]["other_count"] += 1

                sig = pkt.summary()
                stats[src]["fingerprints"][sig] = stats[src]["fingerprints"].get(sig, 0) + 1
        except Exception:
            pass

    sniff(prn=pkt_handler, timeout=timeout, store=0, iface=iface)

    # Convert sets → lists + reverse DNS
    for mac, info in stats.items():
        ip_list = list(info["ips"])
        info["ips"] = ip_list

        hosts = []
        for ip in ip_list:
            try:
                hosts.append(socket.gethostbyaddr(ip)[0])
            except Exception:
                pass
        info["hosts"] = hosts if hosts else ["Unknown"]

        # Weighted severity scoring
        info["severity"] = (
            info["arp_count"] * 2 +
            info["dhcp_count"] * 1 +
            info["mdns_count"] * 0.5 +
            info["nbns_count"] * 0.5 +
            info["other_count"] * 3
        ) / max(1, timeout)

    total_count = sum(info["count"] for info in stats.values())

    offenders = []
    for mac, info in stats.items():
        if info["severity"] > threshold:
            offenders.append(mac)

    return total_count, list(set(offenders)), stats


def detect_loops_lightweight(timeout=5, threshold=50, iface=None):
    """
    Optimized lightweight loop detection for automatic monitoring.
    Uses shorter timeout, reduced packet analysis, and simplified scoring.
    Returns (total_count, offenders, stats, status, severity_score).
    """
    stats = defaultdict(lambda: {
        "count": 0,
        "arp_count": 0,
        "broadcast_count": 0,
        "ips": set(),
        "severity": 0.0
    })
    
    packet_count = 0
    start_time = time.time()

    def pkt_handler(pkt):
        nonlocal packet_count
        try:
            packet_count += 1
            
            # Early exit if too many packets (potential storm)
            if packet_count > 1000:
                return
                
            if pkt.haslayer(Ether):
                src = pkt[Ether].src

                # Only check for broadcast traffic (most relevant for loops)
                if pkt[Ether].dst == "ff:ff:ff:ff:ff:ff":
                    stats[src]["count"] += 1
                    
                    # ARP broadcast
                    if pkt.haslayer(ARP) and pkt[ARP].op == 1:
                        stats[src]["arp_count"] += 1
                        if pkt[ARP].psrc:
                            stats[src]["ips"].add(pkt[ARP].psrc)
                    
                    # IPv4 broadcast
                    elif pkt.haslayer(IP) and pkt[IP].dst == "255.255.255.255":
                        stats[src]["broadcast_count"] += 1
                        stats[src]["ips"].add(pkt[IP].src)
                        
        except Exception:
            pass

    try:
        sniff(prn=pkt_handler, timeout=timeout, store=0, iface=iface)
    except Exception as e:
        logging.error(f"Loop detection failed: {e}")
        return 0, [], {}, "error", 0.0

    # Convert sets to lists
    for mac, info in stats.items():
        info["ips"] = list(info["ips"])
        
        # Simplified severity scoring
        info["severity"] = (
            info["arp_count"] * 3 +  # ARP storms are more concerning
            info["broadcast_count"] * 1
        ) / max(1, timeout)

    total_count = sum(info["count"] for info in stats.values())
    max_severity = max((info["severity"] for info in stats.values()), default=0.0)
    
    # Determine status
    if max_severity > threshold * 2:
        status = "loop_detected"
    elif max_severity > threshold:
        status = "suspicious"
    else:
        status = "clean"
    
    # Find offenders
    offenders = []
    for mac, info in stats.items():
        if info["severity"] > threshold:
            offenders.append(mac)

    return total_count, offenders, dict(stats), status, max_severity


def auto_loop_detection(iface=None, save_to_db=True, api_base_url="http://localhost:5000"):
    """
    Automatic loop detection with database saving.
    Optimized for background monitoring.
    """
    try:
        if iface is None:
            iface = get_default_iface()
            
        # Run lightweight detection
        total_packets, offenders, stats, status, severity_score = detect_loops_lightweight(
            timeout=3,  # Very short timeout for efficiency
            threshold=30,  # Lower threshold for sensitivity
            iface=iface
        )
        
        # Prepare data for database
        detection_data = {
            "total_packets": total_packets,
            "offenders_count": len(offenders),
            "offenders_data": {
                "offenders": offenders,
                "stats": stats
            },
            "severity_score": severity_score,
            "network_interface": iface or "unknown",
            "detection_duration": 3,
            "status": status
        }
        
        # Save to database if requested
        if save_to_db:
            try:
                import requests
                import json
                
                response = requests.post(
                    f"{api_base_url}/api/loop-detection",
                    json=detection_data,
                    timeout=5
                )
                
                if response.status_code == 200:
                    logging.info("Loop detection result saved to database")
                else:
                    logging.warning(f"Failed to save loop detection: {response.text}")
                    
            except Exception as e:
                logging.error(f"Database save failed: {e}")
        
        return {
            "success": True,
            "total_packets": total_packets,
            "offenders": offenders,
            "status": status,
            "severity_score": severity_score,
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