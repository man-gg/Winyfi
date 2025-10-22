"""
Bandwidth Tracker Module
Handles cumulative bandwidth tracking for UniFi devices with delta calculations.
"""

from datetime import datetime
from typing import Dict, Tuple, Optional
from db import get_connection, execute_with_error_handling
import logging

logger = logging.getLogger(__name__)


class BandwidthTracker:
    """
    Tracks bandwidth usage over time with in-memory cache and database persistence.
    Handles cumulative byte counters and computes deltas between checks.
    """
    
    def __init__(self):
        # In-memory cache: {router_id: {'rx_bytes': int, 'tx_bytes': int, 'timestamp': datetime}}
        self._cache = {}
        self._initialized = False
    
    def initialize_from_db(self):
        """Load last known values from database into cache."""
        if self._initialized:
            return
        
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Get the most recent bandwidth snapshot for each router
            cursor.execute("""
                SELECT router_id, rx_bytes_total, tx_bytes_total, timestamp
                FROM bandwidth_snapshots
                WHERE (router_id, timestamp) IN (
                    SELECT router_id, MAX(timestamp)
                    FROM bandwidth_snapshots
                    GROUP BY router_id
                )
            """)
            
            rows = cursor.fetchall()
            for row in rows:
                self._cache[row['router_id']] = {
                    'rx_bytes': row['rx_bytes_total'] or 0,
                    'tx_bytes': row['tx_bytes_total'] or 0,
                    'timestamp': row['timestamp']
                }
            
            cursor.close()
            conn.close()
            
            self._initialized = True
            logger.info(f"📊 Bandwidth tracker initialized with {len(self._cache)} router(s)")
            
        except Exception as e:
            logger.error(f"Failed to initialize bandwidth tracker from database: {e}")
            self._initialized = True  # Mark as initialized anyway to avoid repeated failures
    
    def compute_delta(
        self, 
        router_id: int, 
        current_rx: int, 
        current_tx: int
    ) -> Tuple[int, int, bool]:
        """
        Compute bandwidth delta since last check.
        
        Args:
            router_id: Router database ID
            current_rx: Current RX bytes counter
            current_tx: Current TX bytes counter
        
        Returns:
            Tuple of (rx_diff, tx_diff, is_reset)
            - rx_diff: Bytes received since last check
            - tx_diff: Bytes transmitted since last check
            - is_reset: True if counter was reset (reboot detected)
        """
        # Ensure cache is initialized
        if not self._initialized:
            self.initialize_from_db()
        
        # Get previous values from cache
        previous = self._cache.get(router_id)
        
        if previous is None:
            # First time seeing this router - no delta to compute
            self._cache[router_id] = {
                'rx_bytes': current_rx,
                'tx_bytes': current_tx,
                'timestamp': datetime.now()
            }
            return (0, 0, False)
        
        prev_rx = previous['rx_bytes']
        prev_tx = previous['tx_bytes']
        
        # Detect counter reset (router reboot)
        is_reset = (current_rx < prev_rx) or (current_tx < prev_tx)
        
        if is_reset:
            # Counter was reset - treat as new baseline
            logger.warning(f"🔄 Router {router_id} counter reset detected (reboot?)")
            rx_diff = 0
            tx_diff = 0
        else:
            # Normal case - compute delta
            rx_diff = current_rx - prev_rx
            tx_diff = current_tx - prev_tx
        
        # Update cache with current values
        self._cache[router_id] = {
            'rx_bytes': current_rx,
            'tx_bytes': current_tx,
            'timestamp': datetime.now()
        }
        
        return (rx_diff, tx_diff, is_reset)
    
    def save_snapshot(
        self,
        router_id: int,
        rx_bytes_total: int,
        tx_bytes_total: int,
        rx_diff: int,
        tx_diff: int
    ) -> bool:
        """
        Save bandwidth snapshot to database.
        
        Args:
            router_id: Router database ID
            rx_bytes_total: Total cumulative RX bytes
            tx_bytes_total: Total cumulative TX bytes
            rx_diff: Bytes received since last snapshot
            tx_diff: Bytes transmitted since last snapshot
        
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO bandwidth_snapshots 
                (router_id, rx_bytes_total, tx_bytes_total, rx_bytes_diff, tx_bytes_diff)
                VALUES (%s, %s, %s, %s, %s)
            """, (router_id, rx_bytes_total, tx_bytes_total, rx_diff, tx_diff))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save bandwidth snapshot for router {router_id}: {e}")
            return False
    
    def update_router_totals(self, router_id: int, rx_diff: int, tx_diff: int) -> bool:
        """
        Update cumulative bandwidth totals in routers table.
        
        Args:
            router_id: Router database ID
            rx_diff: Bytes to add to RX total
            tx_diff: Bytes to add to TX total
        
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Use MySQL's ability to increment safely
            cursor.execute("""
                UPDATE routers 
                SET 
                    total_rx_bytes = COALESCE(total_rx_bytes, 0) + %s,
                    total_tx_bytes = COALESCE(total_tx_bytes, 0) + %s,
                    last_bandwidth_update = NOW()
                WHERE id = %s
            """, (rx_diff, tx_diff, router_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update router totals for router {router_id}: {e}")
            return False
    
    def format_bytes(self, bytes_value: int) -> str:
        """Format bytes into human-readable string."""
        if bytes_value < 1024:
            return f"{bytes_value} B"
        elif bytes_value < 1024 * 1024:
            return f"{bytes_value / 1024:.2f} KB"
        elif bytes_value < 1024 * 1024 * 1024:
            return f"{bytes_value / (1024 * 1024):.2f} MB"
        else:
            return f"{bytes_value / (1024 * 1024 * 1024):.2f} GB"


# Global singleton instance
_bandwidth_tracker = None


def get_bandwidth_tracker() -> BandwidthTracker:
    """Get or create the global bandwidth tracker instance."""
    global _bandwidth_tracker
    if _bandwidth_tracker is None:
        _bandwidth_tracker = BandwidthTracker()
    return _bandwidth_tracker
