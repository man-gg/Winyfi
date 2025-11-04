#!/usr/bin/env python3
"""
Notification Performance Optimization Module
Prevents notification system from slowing down the dashboard or PC.
"""

import time
from typing import Callable, Any
import threading


class NotificationThrottler:
    """Throttle notification operations to prevent performance issues"""
    
    def __init__(self):
        self._last_update_time = {}
        self._cache = {}
        self._cache_ttl = {}
        self._locks = {}
        self._toast_queue = []
        self._max_toasts = 3  # Maximum simultaneous toast notifications
        self._min_interval = 1.0  # Minimum 1 second between similar operations
        
    def throttle(self, key: str, func: Callable, min_interval: float = None, *args, **kwargs):
        """
        Throttle a function call to prevent excessive execution
        
        Args:
            key: Unique identifier for the operation
            func: Function to execute
            min_interval: Minimum seconds between calls (default: self._min_interval)
            *args, **kwargs: Arguments for the function
            
        Returns:
            Result of function or cached result if throttled
        """
        if min_interval is None:
            min_interval = self._min_interval
            
        current_time = time.time()
        last_time = self._last_update_time.get(key, 0)
        
        # Check if enough time has passed
        if current_time - last_time < min_interval:
            # Return cached result if available
            if key in self._cache:
                return self._cache[key]
            return None
        
        # Execute function
        try:
            result = func(*args, **kwargs)
            self._last_update_time[key] = current_time
            self._cache[key] = result
            self._cache_ttl[key] = current_time + min_interval
            return result
        except Exception as e:
            print(f"Error in throttled function {key}: {e}")
            return None
    
    def get_cached(self, key: str, default=None):
        """Get cached value if still valid"""
        current_time = time.time()
        if key in self._cache and key in self._cache_ttl:
            if current_time < self._cache_ttl[key]:
                return self._cache[key]
        return default
    
    def clear_cache(self, key: str = None):
        """Clear cache for specific key or all keys"""
        if key:
            self._cache.pop(key, None)
            self._cache_ttl.pop(key, None)
        else:
            self._cache.clear()
            self._cache_ttl.clear()
    
    def can_show_toast(self):
        """Check if we can show another toast notification"""
        # Clean up old toasts
        current_time = time.time()
        self._toast_queue = [t for t in self._toast_queue if current_time - t < 5.0]
        
        # Check limit
        return len(self._toast_queue) < self._max_toasts
    
    def register_toast(self):
        """Register a new toast notification"""
        self._toast_queue.append(time.time())
    
    def set_max_toasts(self, max_toasts: int):
        """Set maximum simultaneous toasts"""
        self._max_toasts = max(1, max_toasts)


class CachedNotificationCount:
    """Cached notification count with automatic invalidation"""
    
    def __init__(self, get_count_func: Callable, cache_duration: float = 2.0):
        """
        Initialize cached counter
        
        Args:
            get_count_func: Function that returns the actual count
            cache_duration: How long to cache the count (seconds)
        """
        self._get_count = get_count_func
        self._cache_duration = cache_duration
        self._cached_count = None
        self._last_update = 0
        self._lock = threading.Lock()
        self._pending_update = False
    
    def get_count(self, force_refresh: bool = False) -> int:
        """
        Get notification count (cached or fresh)
        
        Args:
            force_refresh: Force a database query
            
        Returns:
            Notification count
        """
        current_time = time.time()
        
        with self._lock:
            # Return cached value if still valid and not forcing refresh
            if not force_refresh and self._cached_count is not None:
                if current_time - self._last_update < self._cache_duration:
                    return self._cached_count
            
            # Get fresh count
            try:
                self._cached_count = self._get_count()
                self._last_update = current_time
                return self._cached_count
            except Exception as e:
                print(f"Error getting notification count: {e}")
                # Return cached value if available, else 0
                return self._cached_count if self._cached_count is not None else 0
    
    def invalidate(self):
        """Force cache invalidation"""
        with self._lock:
            self._last_update = 0
    
    def update_async(self, callback: Callable = None):
        """
        Update count asynchronously
        
        Args:
            callback: Optional callback function to call with the new count
        """
        if self._pending_update:
            return  # Already updating
        
        self._pending_update = True
        
        def update_worker():
            try:
                count = self.get_count(force_refresh=True)
                if callback:
                    callback(count)
            finally:
                self._pending_update = False
        
        thread = threading.Thread(target=update_worker, daemon=True)
        thread.start()


class NotificationBatcher:
    """Batch multiple notifications to reduce UI updates"""
    
    def __init__(self, batch_delay: float = 0.5):
        """
        Initialize batcher
        
        Args:
            batch_delay: Seconds to wait before processing batch
        """
        self._batch_delay = batch_delay
        self._pending_notifications = []
        self._timer = None
        self._lock = threading.Lock()
        self._callback = None
    
    def set_callback(self, callback: Callable):
        """Set callback for batch processing"""
        self._callback = callback
    
    def add(self, notification_data: Any):
        """Add notification to batch"""
        with self._lock:
            self._pending_notifications.append(notification_data)
            
            # Cancel existing timer
            if self._timer:
                self._timer.cancel()
            
            # Start new timer
            self._timer = threading.Timer(self._batch_delay, self._process_batch)
            self._timer.daemon = True
            self._timer.start()
    
    def _process_batch(self):
        """Process accumulated notifications"""
        with self._lock:
            if not self._pending_notifications:
                return
            
            batch = self._pending_notifications.copy()
            self._pending_notifications.clear()
            
            if self._callback:
                try:
                    self._callback(batch)
                except Exception as e:
                    print(f"Error processing notification batch: {e}")
    
    def flush(self):
        """Process batch immediately"""
        if self._timer:
            self._timer.cancel()
        self._process_batch()


# Global instances
_throttler = NotificationThrottler()
_cached_count = None  # Will be initialized when needed
_batcher = NotificationBatcher()


def get_throttler() -> NotificationThrottler:
    """Get global throttler instance"""
    return _throttler


def get_cached_count() -> CachedNotificationCount:
    """Get global cached count instance"""
    return _cached_count


def initialize_cached_count(get_count_func: Callable, cache_duration: float = 2.0):
    """Initialize the global cached count"""
    global _cached_count
    _cached_count = CachedNotificationCount(get_count_func, cache_duration)
    return _cached_count


def get_batcher() -> NotificationBatcher:
    """Get global batcher instance"""
    return _batcher


def throttle_notification_count_update(update_func: Callable, *args, **kwargs):
    """
    Throttle notification count updates
    
    Args:
        update_func: Function to update the notification count
        *args, **kwargs: Arguments for the function
    """
    return _throttler.throttle("notification_count", update_func, 1.0, *args, **kwargs)


def can_show_toast() -> bool:
    """Check if we can show another toast notification"""
    return _throttler.can_show_toast()


def register_toast():
    """Register a new toast notification"""
    _throttler.register_toast()
