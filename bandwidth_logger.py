# bandwidth_logger.py
import threading
import time
from network_utils import get_bandwidth
from db import get_connection   # your existing DB helper

LOG_INTERVAL = 300  # every 5 minutes

def log_bandwidth(router_id, ip_address):
    """Run bandwidth test and insert result into bandwidth_logs table."""
    try:
        bw = get_bandwidth(ip_address)

        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO bandwidth_logs (router_id, download_mbps, upload_mbps, latency_ms)
            VALUES (%s, %s, %s, %s)
        """, (
            router_id,
            bw.get("download", 0),
            bw.get("upload", 0),
            bw.get("latency", None)
        ))

        conn.commit()
        cur.close()
        conn.close()

 
    except Exception as e:
        print(f"[ERROR] Logging bandwidth for {router_id}: {e}")


def start_bandwidth_logging(get_router_list_func):
    """
    Start a background thread that logs bandwidth for all routers every 5 minutes.
    - get_router_list_func: function returning routers [{id, ip_address}, ...]
    """
    def loop():
        while True:
            routers = get_router_list_func()
            for r in routers:
                # Skip UniFi routers here to avoid double-logging; they are logged via UniFi API fetch
                try:
                    if str(r.get('brand', '')).lower() == 'unifi':
                        continue
                except Exception:
                    pass
                log_bandwidth(r['id'], r['ip_address'])
            time.sleep(LOG_INTERVAL)

    threading.Thread(target=loop, daemon=True).start()
