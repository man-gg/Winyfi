"""
Improved UniFi Device Fetcher with Bandwidth Delta Tracking
This is the enhanced version of _fetch_unifi_devices() for dashboard.py

Key improvements:
- Tracks cumulative bandwidth (rx_bytes/tx_bytes) with delta calculations
- Handles router reboots gracefully (counter resets)
- Uses in-memory cache to avoid excessive DB queries
- Logs bandwidth deltas with human-readable format
- Updates router total bandwidth fields
- Maintains backward compatibility with existing code
"""

def _fetch_unifi_devices(self):
    """
    Fetch UniFi devices from the UniFi API server and save to database.
    
    Enhanced with:
    - Cumulative bandwidth tracking (rx_bytes/tx_bytes)
    - Delta calculation between checks
    - Reboot detection and handling
    - In-memory caching for performance
    - Human-readable bandwidth logging
    
    Uses aggressive timeout and error handling to prevent app slowdown.
    """
    try:
        import requests
        from requests.exceptions import ConnectionError, Timeout, RequestException
        from router_utils import upsert_unifi_router
        from db import insert_bandwidth_log, get_connection
        from bandwidth_tracker import get_bandwidth_tracker
        from datetime import datetime
        
        # Get or initialize the bandwidth tracker
        if not hasattr(self, '_bandwidth_tracker'):
            self._bandwidth_tracker = get_bandwidth_tracker()
        
        tracker = self._bandwidth_tracker
        
        # Use short timeout to prevent app slowdown (1 second connection, 2 second read)
        response = requests.get(
            f"{self.unifi_api_url}/api/unifi/devices", 
            timeout=(1, 2)  # (connect timeout, read timeout)
        )
        
        if response.status_code == 200:
            devices = response.json()
            print(f"📡 Found {len(devices)} UniFi device(s) from API")
            
            # Get existing MAC addresses from database to detect new devices
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT mac_address FROM routers WHERE brand = 'UniFi'")
                existing_macs = set(row[0] for row in cursor.fetchall())
                cursor.close()
                conn.close()
            except Exception as db_error:
                print(f"⚠️ Database error while checking existing UniFi devices: {str(db_error)}")
                existing_macs = set()
            
            # Transform UniFi devices to match router structure
            transformed = []
            new_devices_count = 0
            bandwidth_updates_count = 0
            
            for device in devices:
                try:
                    name = device.get('name', 'Unknown AP')
                    ip = device.get('ip', 'N/A')
                    mac = device.get('mac', 'N/A')
                    brand = 'UniFi'
                    location = device.get('model', 'Access Point')
                    
                    # Check if this is a new device
                    is_new_device = mac not in existing_macs
                    
                    # Save/update UniFi device in database
                    # This will add new devices or update existing ones
                    router_id = upsert_unifi_router(name, ip, mac, brand, location, image_path=None)
                    
                    if is_new_device and router_id:
                        new_devices_count += 1
                        print(f"✨ New UniFi device discovered: {name} (MAC: {mac}, IP: {ip})")
                    
                    # === ENHANCED BANDWIDTH TRACKING ===
                    
                    # 1. Get instantaneous throughput (existing functionality)
                    xput_down = device.get('xput_down', 0)
                    xput_up = device.get('xput_up', 0)
                    
                    # 2. Get cumulative byte counters (new functionality)
                    rx_bytes_current = device.get('rx_bytes', 0)
                    tx_bytes_current = device.get('tx_bytes', 0)
                    
                    if router_id and (rx_bytes_current > 0 or tx_bytes_current > 0):
                        try:
                            # Compute bandwidth delta since last check
                            rx_diff, tx_diff, is_reset = tracker.compute_delta(
                                router_id, 
                                rx_bytes_current, 
                                tx_bytes_current
                            )
                            
                            # Log the snapshot with deltas
                            if rx_diff > 0 or tx_diff > 0:
                                # Save snapshot to database
                                tracker.save_snapshot(
                                    router_id,
                                    rx_bytes_current,
                                    tx_bytes_current,
                                    rx_diff,
                                    tx_diff
                                )
                                
                                # Update router's cumulative totals
                                tracker.update_router_totals(router_id, rx_diff, tx_diff)
                                
                                # Human-readable logging with timestamp
                                timestamp = datetime.now().strftime("%H:%M:%S")
                                rx_human = tracker.format_bytes(rx_diff)
                                tx_human = tracker.format_bytes(tx_diff)
                                
                                reset_indicator = " [RESET DETECTED]" if is_reset else ""
                                print(f"[{timestamp}] 📊 {name} — RX +{rx_human}, TX +{tx_human}{reset_indicator}")
                                
                                bandwidth_updates_count += 1
                            
                            # Also log instantaneous throughput (backward compatibility)
                            if xput_down is not None or xput_up is not None:
                                insert_bandwidth_log(
                                    router_id, 
                                    float(xput_down or 0), 
                                    float(xput_up or 0), 
                                    None  # latency
                                )
                                
                        except Exception as bandwidth_error:
                            # Don't fail the whole process if bandwidth tracking fails
                            print(f"⚠️ Bandwidth tracking error for {name}: {str(bandwidth_error)}")
                    
                    # Build response data structure
                    transformed.append({
                        'id': router_id if router_id else f"unifi_{mac}",
                        'name': name,
                        'ip_address': ip,
                        'mac_address': mac,
                        'brand': brand,
                        'location': location,
                        'is_unifi': True,
                        'download_speed': xput_down,
                        'upload_speed': xput_up,
                        'rx_bytes': rx_bytes_current,  # Add cumulative counters to response
                        'tx_bytes': tx_bytes_current,
                        'last_seen': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'image_path': None
                    })
                    
                except Exception as device_error:
                    print(f"⚠️ Error processing UniFi device {device.get('name', 'Unknown')}: {str(device_error)}")
                    continue
            
            # Summary logging
            if new_devices_count > 0:
                print(f"🎉 Added {new_devices_count} new UniFi device(s) to the database")
            
            if bandwidth_updates_count > 0:
                print(f"📈 Updated bandwidth tracking for {bandwidth_updates_count} device(s)")
            
            return transformed
            
        else:
            # API returned non-200 status
            if not hasattr(self, '_unifi_api_error_logged'):
                print(f"⚠️ UniFi API returned status code: {response.status_code}")
                self._unifi_api_error_logged = True
            return []
            
    except ConnectionError:
        # Connection refused or network unreachable - log once to avoid spam
        if not hasattr(self, '_unifi_connection_error_logged'):
            print("⚠️ UniFi API server is not reachable (connection refused)")
            self._unifi_connection_error_logged = True
        return []
        
    except Timeout:
        # Request timed out - log once to avoid spam
        if not hasattr(self, '_unifi_timeout_logged'):
            print("⚠️ UniFi API request timed out (server may be slow or down)")
            self._unifi_timeout_logged = True
        return []
        
    except RequestException as e:
        # Other requests-related errors
        if not hasattr(self, '_unifi_request_error_logged'):
            print(f"⚠️ UniFi API request error: {str(e)}")
            self._unifi_request_error_logged = True
        return []
        
    except Exception as e:
        # Catch-all for any other unexpected errors
        if not hasattr(self, '_unifi_general_error_logged'):
            print(f"⚠️ Unexpected error fetching UniFi devices: {str(e)}")
            self._unifi_general_error_logged = True
        return []


# === HELPER FUNCTION FOR UPDATING ROUTER TOTALS ===

def _update_router_bandwidth_totals(router_id, rx_diff, tx_diff):
    """
    Helper function to update cumulative bandwidth totals in the routers table.
    
    This can be called independently or integrated into the bandwidth tracker.
    
    Args:
        router_id (int): Router database ID
        rx_diff (int): Bytes to add to RX total
        tx_diff (int): Bytes to add to TX total
    
    Returns:
        bool: True if successful, False otherwise
    
    Example:
        >>> _update_router_bandwidth_totals(5, 1024000, 512000)  # +1MB RX, +512KB TX
        True
    """
    try:
        from db import get_connection
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Atomic increment using MySQL
        cursor.execute("""
            UPDATE routers 
            SET 
                total_rx_bytes = COALESCE(total_rx_bytes, 0) + %s,
                total_tx_bytes = COALESCE(total_tx_bytes, 0) + %s,
                last_bandwidth_update = NOW()
            WHERE id = %s
        """, (rx_diff, tx_diff, router_id))
        
        rows_affected = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        
        return rows_affected > 0
        
    except Exception as e:
        print(f"⚠️ Failed to update bandwidth totals for router {router_id}: {e}")
        return False
