#!/usr/bin/env python3
"""
Notification System for Network Monitoring Dashboard
Handles push notifications for various events like loop detection, router status changes, etc.
"""

import sqlite3
import json
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from enum import Enum
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *

class NotificationType(Enum):
    LOOP_DETECTED = "loop_detected"
    ROUTER_OFFLINE = "router_offline"
    ROUTER_ONLINE = "router_online"
    BANDWIDTH_HIGH = "bandwidth_high"
    SYSTEM_ALERT = "system_alert"
    MAINTENANCE = "maintenance"
    SECURITY_ALERT = "security_alert"

class NotificationPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

class NotificationManager:
    def __init__(self, db_path="network_monitoring.db"):
        self.db_path = db_path
        self.notification_callbacks = []
        self.notification_settings = {
            NotificationType.LOOP_DETECTED: {"enabled": True, "priority": NotificationPriority.HIGH},
            NotificationType.ROUTER_OFFLINE: {"enabled": True, "priority": NotificationPriority.MEDIUM},
            NotificationType.ROUTER_ONLINE: {"enabled": True, "priority": NotificationPriority.LOW},
            NotificationType.BANDWIDTH_HIGH: {"enabled": True, "priority": NotificationPriority.MEDIUM},
            NotificationType.SYSTEM_ALERT: {"enabled": True, "priority": NotificationPriority.HIGH},
            NotificationType.MAINTENANCE: {"enabled": True, "priority": NotificationPriority.MEDIUM},
            NotificationType.SECURITY_ALERT: {"enabled": True, "priority": NotificationPriority.CRITICAL},
        }
        self._init_database()
        
    def _init_database(self):
        """Initialize notification database tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Notifications table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                priority INTEGER NOT NULL,
                data TEXT,  -- JSON data for additional info
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                read_at TIMESTAMP NULL,
                dismissed_at TIMESTAMP NULL,
                user_id INTEGER DEFAULT 1,  -- For future multi-user support
                status TEXT DEFAULT 'created',  -- created, displayed, read, dismissed
                display_attempts INTEGER DEFAULT 0,
                last_display_attempt TIMESTAMP NULL
            )
        ''')
        
        # Notification settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notification_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT UNIQUE NOT NULL,
                enabled BOOLEAN NOT NULL DEFAULT 1,
                priority INTEGER NOT NULL DEFAULT 2,
                sound_enabled BOOLEAN NOT NULL DEFAULT 1,
                popup_enabled BOOLEAN NOT NULL DEFAULT 1,
                email_enabled BOOLEAN NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Notification logs table for debugging
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notification_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                notification_id INTEGER,
                event_type TEXT NOT NULL,  -- created, callback_triggered, toast_created, toast_displayed, error
                message TEXT,
                details TEXT,  -- JSON data for additional details
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (notification_id) REFERENCES notifications (id)
            )
        ''')
        
        # Insert default settings if not exists
        for notif_type in NotificationType:
            cursor.execute('''
                INSERT OR IGNORE INTO notification_settings 
                (type, enabled, priority, sound_enabled, popup_enabled, email_enabled)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                notif_type.value,
                self.notification_settings[notif_type]["enabled"],
                self.notification_settings[notif_type]["priority"].value,
                True, True, False
            ))
        
        conn.commit()
        conn.close()
    
    def log_notification_event(self, notification_id: int, event_type: str, message: str, details: Dict = None):
        """Log a notification event for debugging."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO notification_logs (notification_id, event_type, message, details)
            VALUES (?, ?, ?, ?)
        ''', (
            notification_id,
            event_type,
            message,
            json.dumps(details) if details else None
        ))
        
        conn.commit()
        conn.close()
        
        # Also print to console for debugging
    
    def update_notification_status(self, notification_id: int, status: str, details: Dict = None):
        """Update notification status and log the event."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if status == "displayed":
            cursor.execute('''
                UPDATE notifications 
                SET status = ?, display_attempts = display_attempts + 1, last_display_attempt = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (status, notification_id))
        else:
            cursor.execute('''
                UPDATE notifications SET status = ? WHERE id = ?
            ''', (status, notification_id))
        
        conn.commit()
        conn.close()
        
        # Log the status update
        self.log_notification_event(notification_id, "status_update", f"Status changed to {status}", details)
    
    def get_notification_logs(self, notification_id: int = None, limit: int = 100):
        """Get notification logs for debugging."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if notification_id:
            cursor.execute('''
                SELECT * FROM notification_logs 
                WHERE notification_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (notification_id, limit))
        else:
            cursor.execute('''
                SELECT * FROM notification_logs 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (limit,))
        
        logs = []
        for row in cursor.fetchall():
            logs.append({
                "id": row[0],
                "notification_id": row[1],
                "event_type": row[2],
                "message": row[3],
                "details": json.loads(row[4]) if row[4] else None,
                "timestamp": row[5]
            })
        
        conn.close()
        return logs
    
    def add_notification_callback(self, callback: Callable):
        """Add a callback function to be called when notifications are created."""
        self.notification_callbacks.append(callback)
    
    def create_notification(self, 
                          notif_type: NotificationType, 
                          title: str, 
                          message: str, 
                          data: Dict = None,
                          priority: NotificationPriority = None) -> int:
        """Create a new notification."""
        # Check if this notification type is enabled
        settings = self.get_notification_settings(notif_type)
        if not settings["enabled"]:
            return None
            
        # Use provided priority or get from settings
        if priority is None:
            priority = NotificationPriority(settings["priority"])
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO notifications (type, title, message, priority, data)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            notif_type.value,
            title,
            message,
            priority.value,
            json.dumps(data) if data else None
        ))
        
        notification_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Log notification creation
        self.log_notification_event(
            notification_id, 
            "created", 
            f"Notification created: {title}",
            {
                "type": notif_type.value,
                "priority": priority.value,
                "data": data
            }
        )
        
        # Notify callbacks
        for i, callback in enumerate(self.notification_callbacks):
            try:
                callback(notification_id, notif_type, title, message, priority, data)
                
                # Log callback success
                self.log_notification_event(
                    notification_id,
                    "callback_triggered",
                    f"Callback {i+1} executed successfully",
                    {"callback_index": i+1}
                )
            except Exception as e:
                
                # Log callback error
                self.log_notification_event(
                    notification_id,
                    "error",
                    f"Callback {i+1} failed: {str(e)}",
                    {"callback_index": i+1, "error": str(e)}
                )
        
        return notification_id
    
    def get_notification_settings(self, notif_type: NotificationType) -> Dict:
        """Get notification settings for a specific type."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT enabled, priority, sound_enabled, popup_enabled, email_enabled
            FROM notification_settings WHERE type = ?
        ''', (notif_type.value,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                "enabled": bool(result[0]),
                "priority": result[1],
                "sound_enabled": bool(result[2]),
                "popup_enabled": bool(result[3]),
                "email_enabled": bool(result[4])
            }
        else:
            return self.notification_settings[notif_type]
    
    def update_notification_settings(self, notif_type: NotificationType, settings: Dict):
        """Update notification settings for a specific type."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE notification_settings 
            SET enabled = ?, priority = ?, sound_enabled = ?, popup_enabled = ?, email_enabled = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE type = ?
        ''', (
            settings.get("enabled", True),
            settings.get("priority", 2),
            settings.get("sound_enabled", True),
            settings.get("popup_enabled", True),
            settings.get("email_enabled", False),
            notif_type.value
        ))
        
        conn.commit()
        conn.close()
    
    def get_unread_notifications(self, limit: int = 50) -> List[Dict]:
        """Get unread notifications."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, type, title, message, priority, data, created_at
            FROM notifications 
            WHERE read_at IS NULL AND dismissed_at IS NULL
            ORDER BY created_at DESC
            LIMIT ?
        ''', (limit,))
        
        notifications = []
        for row in cursor.fetchall():
            notifications.append({
                "id": row[0],
                "type": row[1],
                "title": row[2],
                "message": row[3],
                "priority": row[4],
                "data": json.loads(row[5]) if row[5] else None,
                "created_at": row[6]
            })
        
        conn.close()
        return notifications
    
    def mark_as_read(self, notification_id: int):
        """Mark a notification as read."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE notifications SET read_at = CURRENT_TIMESTAMP WHERE id = ?
        ''', (notification_id,))
        
        conn.commit()
        conn.close()
    
    def dismiss_notification(self, notification_id: int):
        """Dismiss a notification."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE notifications SET dismissed_at = CURRENT_TIMESTAMP WHERE id = ?
        ''', (notification_id,))
        
        conn.commit()
        conn.close()
    
    def get_notification_count(self) -> int:
        """Get count of unread notifications."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) FROM notifications 
            WHERE read_at IS NULL AND dismissed_at IS NULL
        ''')
        
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def clear_old_notifications(self, days: int = 30):
        """Clear notifications older than specified days."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM notifications 
            WHERE created_at < datetime('now', '-{} days')
        '''.format(days))
        
        conn.commit()
        conn.close()

# Global notification manager instance
notification_manager = NotificationManager()

# Global callback for toast notifications
_toast_callback = None

def set_toast_callback(callback):
    """Set the global toast callback."""
    global _toast_callback
    _toast_callback = callback
    # Add the callback to the notification manager
    notification_manager.add_notification_callback(callback)

def get_toast_callback():
    """Get the global toast callback."""
    return _toast_callback

# Convenience functions for common notifications
def notify_loop_detected(severity_score: float, offenders: List[str], interface: str = "Wi-Fi"):
    """Create a loop detection notification."""
    title = "🔄 Loop Detected"
    message = f"Network loop detected on {interface}. Severity: {severity_score:.2f}. Offenders: {len(offenders)}"
    
    data = {
        "severity_score": severity_score,
        "offenders": offenders,
        "interface": interface,
        "offender_count": len(offenders)
    }
    
    return notification_manager.create_notification(
        NotificationType.LOOP_DETECTED,
        title,
        message,
        data,
        NotificationPriority.HIGH if severity_score > 0.7 else NotificationPriority.MEDIUM
    )

def notify_router_status_change(router_name: str, router_ip: str, is_online: bool):
    """Create a router status change notification."""
    status = "Online" if is_online else "Offline"
    emoji = "🟢" if is_online else "🔴"
    
    title = f"{emoji} Router {status}"
    message = f"{router_name} ({router_ip}) is now {status.lower()}"
    
    data = {
        "router_name": router_name,
        "router_ip": router_ip,
        "is_online": is_online,
        "status": status
    }
    
    notif_type = NotificationType.ROUTER_ONLINE if is_online else NotificationType.ROUTER_OFFLINE
    priority = NotificationPriority.LOW if is_online else NotificationPriority.CRITICAL  # Red color for offline
    
    return notification_manager.create_notification(notif_type, title, message, data, priority)

def notify_bandwidth_high(router_name: str, bandwidth_usage: float, threshold: float = 80.0):
    """Create a high bandwidth usage notification."""
    title = "📊 High Bandwidth Usage"
    message = f"{router_name} bandwidth usage is {bandwidth_usage:.1f}% (threshold: {threshold}%)"
    
    data = {
        "router_name": router_name,
        "bandwidth_usage": bandwidth_usage,
        "threshold": threshold
    }
    
    return notification_manager.create_notification(
        NotificationType.BANDWIDTH_HIGH,
        title,
        message,
        data,
        NotificationPriority.MEDIUM
    )

def notify_system_alert(title: str, message: str, priority: NotificationPriority = NotificationPriority.MEDIUM):
    """Create a system alert notification."""
    return notification_manager.create_notification(
        NotificationType.SYSTEM_ALERT,
        title,
        message,
        None,
        priority
    )

def notify_security_alert(title: str, message: str, data: Dict = None):
    """Create a security alert notification."""
    return notification_manager.create_notification(
        NotificationType.SECURITY_ALERT,
        title,
        message,
        data,
        NotificationPriority.CRITICAL
    )

def get_notification_count():
    """Get the current notification count."""
    return notification_manager.get_notification_count()
