"""
Router Bandwidth Monitor for Non-UniFi Devices
Estimates per-router bandwidth usage using Layer 2 packet inspection.
No SNMP, no port mirroring, no managed switches required.
"""

import threading
import time
from collections import defaultdict, deque
from datetime import datetime
from scapy.all import AsyncSniffer, Ether, IP, ARP
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)


class RouterBandwidthMonitor:
    """
    Monitors bandwidth usage for non-UniFi routers using packet capture.
    
    Features:
    - Per-router upload/download tracking
    - Efficient background packet sniffing
    - Adjustable sampling intervals
    - Thread-safe data access
    - Compatible with Windows and Linux
    
    Usage:
        monitor = RouterBandwidthMonitor(sampling_interval=5)
        monitor.add_router("192.168.1.1", "AA:BB:CC:DD:EE:FF")
        monitor.start()
        
        # Later...
        bandwidth = monitor.get_router_bandwidth("192.168.1.1")
        print(f"Download: {bandwidth['download_mbps']} Mbps")
    """
    
    def __init__(self, sampling_interval=5, history_size=60, iface=None):
        """
        Initialize the bandwidth monitor.
        
        Args:
            sampling_interval (int): Seconds between bandwidth calculations (default: 5)
            history_size (int): Number of historical samples to keep (default: 60)
            iface (str): Network interface to monitor (None = auto-detect)
        """
        self.sampling_interval = sampling_interval
        self.history_size = history_size
        self.iface = iface or self._get_default_interface()
        
        # Router registry: {ip: {"mac": str, "name": str}}
        self.routers = {}
        
        # Bandwidth data per router
        self.bandwidth_stats = defaultdict(lambda: {
            "download_bytes": 0,
            "upload_bytes": 0,
            "last_reset": time.time(),
            "history": deque(maxlen=history_size),
            "total_packets": 0
        })
        
        # Packet capture state
        self.sniffer = None
        self.running = False
        self.lock = threading.Lock()
        
        # Calculation thread
        self.calc_thread = None
        
        logging.info(f"RouterBandwidthMonitor initialized on interface: {self.iface}")
    
    def _get_default_interface(self):
        """Auto-detect the default network interface."""
        try:
            import psutil
            addrs = psutil.net_if_addrs()
            stats = psutil.net_if_stats()
            
            for iface, snic_list in addrs.items():
                if iface in stats and stats[iface].isup:
                    if any(snic.family.name.startswith("AF_INET") for snic in snic_list):
                        return iface
        except Exception as e:
            logging.warning(f"Could not auto-detect interface: {e}")
        
        return None
    
    def add_router(self, ip, mac=None, name=None):
        """
        Register a router for bandwidth monitoring.
        
        Args:
            ip (str): Router IP address
            mac (str): Router MAC address (optional, will be learned)
            name (str): Router name for identification (optional)
        """
        with self.lock:
            self.routers[ip] = {
                "mac": mac,
                "name": name or f"Router-{ip}"
            }
            logging.info(f"Added router: {ip} ({name or 'unnamed'})")
    
    def remove_router(self, ip):
        """Remove a router from monitoring."""
        with self.lock:
            if ip in self.routers:
                del self.routers[ip]
                del self.bandwidth_stats[ip]
                logging.info(f"Removed router: {ip}")
    
    def _packet_handler(self, packet):
        """
        Process captured packets and accumulate bandwidth data.
        Called for each packet by AsyncSniffer.
        """
        try:
            # Only process IP packets
            if not packet.haslayer(IP):
                return
            
            src_ip = packet[IP].src
            dst_ip = packet[IP].dst
            packet_size = len(packet)
            
            with self.lock:
                # Check all registered routers
                for router_ip, router_info in self.routers.items():
                    # Upload: router is source
                    if src_ip == router_ip:
                        self.bandwidth_stats[router_ip]["upload_bytes"] += packet_size
                        self.bandwidth_stats[router_ip]["total_packets"] += 1
                        
                        # Learn MAC address if not known
                        if not router_info["mac"] and packet.haslayer(Ether):
                            router_info["mac"] = packet[Ether].src
                            logging.info(f"Learned MAC for {router_ip}: {router_info['mac']}")
                    
                    # Download: router is destination
                    elif dst_ip == router_ip:
                        self.bandwidth_stats[router_ip]["download_bytes"] += packet_size
                        self.bandwidth_stats[router_ip]["total_packets"] += 1
                        
                        # Learn MAC address if not known
                        if not router_info["mac"] and packet.haslayer(Ether):
                            router_info["mac"] = packet[Ether].dst
                            logging.info(f"Learned MAC for {router_ip}: {router_info['mac']}")
        
        except Exception as e:
            logging.debug(f"Packet handler error: {e}")
    
    def _calculate_bandwidth_loop(self):
        """
        Background thread that calculates bandwidth periodically.
        Runs every sampling_interval seconds.
        """
        while self.running:
            try:
                time.sleep(self.sampling_interval)
                
                with self.lock:
                    current_time = time.time()
                    
                    for router_ip in list(self.routers.keys()):
                        stats = self.bandwidth_stats[router_ip]
                        
                        # Calculate time elapsed
                        elapsed = current_time - stats["last_reset"]
                        
                        if elapsed > 0:
                            # Calculate Mbps
                            download_mbps = (stats["download_bytes"] * 8) / (1_000_000 * elapsed)
                            upload_mbps = (stats["upload_bytes"] * 8) / (1_000_000 * elapsed)
                            
                            # Store in history
                            history_entry = {
                                "timestamp": datetime.now(),
                                "download_mbps": round(download_mbps, 2),
                                "upload_mbps": round(upload_mbps, 2),
                                "download_bytes": stats["download_bytes"],
                                "upload_bytes": stats["upload_bytes"],
                                "duration": round(elapsed, 2),
                                "packets": stats["total_packets"]
                            }
                            stats["history"].append(history_entry)
                            
                            # Log high bandwidth usage
                            if download_mbps > 50 or upload_mbps > 50:
                                logging.info(
                                    f"High bandwidth on {router_ip}: "
                                    f"↓{download_mbps:.2f} Mbps ↑{upload_mbps:.2f} Mbps"
                                )
                            
                            # Reset counters for next interval
                            stats["download_bytes"] = 0
                            stats["upload_bytes"] = 0
                            stats["total_packets"] = 0
                            stats["last_reset"] = current_time
            
            except Exception as e:
                logging.error(f"Bandwidth calculation error: {e}")
    
    def start(self):
        """
        Start bandwidth monitoring.
        Begins packet capture and calculation threads.
        """
        if self.running:
            logging.warning("Monitor already running")
            return
        
        self.running = True
        
        # Start packet sniffer
        try:
            self.sniffer = AsyncSniffer(
                iface=self.iface,
                prn=self._packet_handler,
                store=False,
                filter="ip"  # Only capture IP packets
            )
            self.sniffer.start()
            logging.info("Packet sniffer started")
        except PermissionError:
            logging.error("Permission denied! Run as Administrator/root for packet capture")
            self.running = False
            return
        except Exception as e:
            logging.error(f"Failed to start sniffer: {e}")
            self.running = False
            return
        
        # Start calculation thread
        self.calc_thread = threading.Thread(
            target=self._calculate_bandwidth_loop,
            daemon=True
        )
        self.calc_thread.start()
        logging.info("Bandwidth calculation thread started")
        
        logging.info(f"RouterBandwidthMonitor started (interval: {self.sampling_interval}s)")
    
    def stop(self):
        """
        Stop bandwidth monitoring.
        Stops packet capture and calculation threads.
        """
        if not self.running:
            return
        
        self.running = False
        
        # Stop sniffer
        if self.sniffer:
            try:
                self.sniffer.stop()
                logging.info("Packet sniffer stopped")
            except Exception as e:
                logging.error(f"Error stopping sniffer: {e}")
        
        # Wait for calculation thread
        if self.calc_thread and self.calc_thread.is_alive():
            self.calc_thread.join(timeout=2)
        
        logging.info("RouterBandwidthMonitor stopped")
    
    def get_router_bandwidth(self, router_ip):
        """
        Get the latest bandwidth data for a specific router.
        
        Args:
            router_ip (str): Router IP address
        
        Returns:
            dict: Bandwidth data or None if router not found
            {
                "router_ip": str,
                "router_mac": str,
                "router_name": str,
                "download_mbps": float,
                "upload_mbps": float,
                "timestamp": str (ISO format),
                "packets": int,
                "status": str
            }
        """
        with self.lock:
            if router_ip not in self.routers:
                return None
            
            router_info = self.routers[router_ip]
            stats = self.bandwidth_stats[router_ip]
            
            # Get most recent measurement from history
            if stats["history"]:
                latest = stats["history"][-1]
                return {
                    "router_ip": router_ip,
                    "router_mac": router_info.get("mac", "Unknown"),
                    "router_name": router_info.get("name", "Unknown"),
                    "download_mbps": latest["download_mbps"],
                    "upload_mbps": latest["upload_mbps"],
                    "timestamp": latest["timestamp"].isoformat(),
                    "packets": latest["packets"],
                    "status": "active"
                }
            else:
                # No data yet
                return {
                    "router_ip": router_ip,
                    "router_mac": router_info.get("mac", "Unknown"),
                    "router_name": router_info.get("name", "Unknown"),
                    "download_mbps": 0.0,
                    "upload_mbps": 0.0,
                    "timestamp": datetime.now().isoformat(),
                    "packets": 0,
                    "status": "no_data"
                }
    
    def get_all_routers_bandwidth(self):
        """
        Get bandwidth data for all monitored routers.
        
        Returns:
            list: List of bandwidth data dictionaries
        """
        with self.lock:
            results = []
            for router_ip in self.routers.keys():
                bandwidth = self.get_router_bandwidth(router_ip)
                if bandwidth:
                    results.append(bandwidth)
            return results
    
    def get_router_history(self, router_ip, limit=None):
        """
        Get historical bandwidth data for a router.
        
        Args:
            router_ip (str): Router IP address
            limit (int): Max number of historical entries (None = all)
        
        Returns:
            list: Historical bandwidth measurements
        """
        with self.lock:
            if router_ip not in self.bandwidth_stats:
                return []
            
            history = list(self.bandwidth_stats[router_ip]["history"])
            
            if limit:
                history = history[-limit:]
            
            # Convert timestamps to ISO format
            for entry in history:
                entry["timestamp"] = entry["timestamp"].isoformat()
            
            return history
    
    def get_average_bandwidth(self, router_ip, minutes=5):
        """
        Calculate average bandwidth over the last N minutes.
        
        Args:
            router_ip (str): Router IP address
            minutes (int): Time window in minutes
        
        Returns:
            dict: Average bandwidth data
        """
        with self.lock:
            if router_ip not in self.bandwidth_stats:
                return None
            
            history = self.bandwidth_stats[router_ip]["history"]
            
            if not history:
                return None
            
            # Filter history for time window
            cutoff_time = datetime.now().timestamp() - (minutes * 60)
            recent = [
                h for h in history 
                if h["timestamp"].timestamp() > cutoff_time
            ]
            
            if not recent:
                return None
            
            # Calculate averages
            avg_download = sum(h["download_mbps"] for h in recent) / len(recent)
            avg_upload = sum(h["upload_mbps"] for h in recent) / len(recent)
            
            return {
                "router_ip": router_ip,
                "avg_download_mbps": round(avg_download, 2),
                "avg_upload_mbps": round(avg_upload, 2),
                "sample_count": len(recent),
                "time_window_minutes": minutes
            }
    
    def get_peak_bandwidth(self, router_ip):
        """
        Get peak bandwidth values for a router.
        
        Args:
            router_ip (str): Router IP address
        
        Returns:
            dict: Peak bandwidth data
        """
        with self.lock:
            if router_ip not in self.bandwidth_stats:
                return None
            
            history = self.bandwidth_stats[router_ip]["history"]
            
            if not history:
                return None
            
            peak_download = max(h["download_mbps"] for h in history)
            peak_upload = max(h["upload_mbps"] for h in history)
            
            return {
                "router_ip": router_ip,
                "peak_download_mbps": round(peak_download, 2),
                "peak_upload_mbps": round(peak_upload, 2)
            }


# Integration function for existing get_bandwidth()
def get_router_bandwidth_realtime(router_ip, monitor_instance=None):
    """
    Get real-time bandwidth for a router.
    Integrates with existing get_bandwidth(ip) function.
    
    Args:
        router_ip (str): Router IP address
        monitor_instance (RouterBandwidthMonitor): Existing monitor instance
    
    Returns:
        dict: Bandwidth data compatible with get_bandwidth() format
    """
    if monitor_instance is None:
        logging.warning("No monitor instance provided")
        return {
            "latency": None,
            "download": 0,
            "upload": 0,
            "quality": {
                "latency": "Unknown",
                "download": "No Monitor",
                "upload": "No Monitor"
            }
        }
    
    bandwidth_data = monitor_instance.get_router_bandwidth(router_ip)
    
    if not bandwidth_data:
        return {
            "latency": None,
            "download": 0,
            "upload": 0,
            "quality": {
                "latency": "Unknown",
                "download": "Not Found",
                "upload": "Not Found"
            }
        }
    
    # Rate bandwidth quality
    def rate_bandwidth(mbps):
        if mbps >= 20:
            return "Excellent"
        elif mbps >= 10:
            return "Good"
        elif mbps >= 3:
            return "Fair"
        elif mbps > 0:
            return "Poor"
        return "None"
    
    return {
        "latency": None,  # Use existing ping_latency() for this
        "download": bandwidth_data["download_mbps"],
        "upload": bandwidth_data["upload_mbps"],
        "quality": {
            "latency": "See ping_latency()",
            "download": rate_bandwidth(bandwidth_data["download_mbps"]),
            "upload": rate_bandwidth(bandwidth_data["upload_mbps"])
        },
        "timestamp": bandwidth_data["timestamp"],
        "packets": bandwidth_data.get("packets", 0)
    }


# Example usage and testing
if __name__ == "__main__":
    # Example: Monitor two routers
    monitor = RouterBandwidthMonitor(sampling_interval=5)
    
    # Add routers (replace with your actual router IPs)
    monitor.add_router("192.168.1.1", name="Main Router")
    monitor.add_router("192.168.1.100", name="Secondary AP")
    
    # Start monitoring
    monitor.start()
    
    try:
        print("Monitoring started. Press Ctrl+C to stop...")
        print(f"Sampling interval: {monitor.sampling_interval} seconds\n")
        
        # Monitor for a while
        for i in range(60):  # 5 minutes (60 * 5 seconds)
            time.sleep(5)
            
            # Get bandwidth for all routers
            all_bandwidth = monitor.get_all_routers_bandwidth()
            
            print(f"\n--- Update {i+1} ---")
            for data in all_bandwidth:
                print(f"{data['router_name']} ({data['router_ip']}):")
                print(f"  Download: {data['download_mbps']:.2f} Mbps")
                print(f"  Upload: {data['upload_mbps']:.2f} Mbps")
                print(f"  Packets: {data['packets']}")
                print(f"  Status: {data['status']}")
    
    except KeyboardInterrupt:
        print("\n\nStopping monitor...")
        monitor.stop()
        print("Monitor stopped successfully")
