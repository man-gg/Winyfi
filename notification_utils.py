#!/usr/bin/env python3
"""
Notification System for Network Monitoring Dashboard
Uses MySQL for persistence via db.get_connection.
"""

import logging
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
from db import get_connection

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
        self.notification_callbacks = []
        self.enabled = True
        self.notification_settings = {
            NotificationType.LOOP_DETECTED: {"enabled": True, "priority": NotificationPriority.HIGH},
            NotificationType.ROUTER_OFFLINE: {"enabled": True, "priority": NotificationPriority.MEDIUM},
            NotificationType.ROUTER_ONLINE: {"enabled": True, "priority": NotificationPriority.LOW},
            NotificationType.BANDWIDTH_HIGH: {"enabled": True, "priority": NotificationPriority.MEDIUM},
            NotificationType.SYSTEM_ALERT: {"enabled": True, "priority": NotificationPriority.HIGH},
            NotificationType.MAINTENANCE: {"enabled": True, "priority": NotificationPriority.MEDIUM},
            NotificationType.SECURITY_ALERT: {"enabled": True, "priority": NotificationPriority.CRITICAL},
        }
        try:
            self._init_database()
        except Exception as e:
            logging.getLogger(__name__).warning(f"Notification DB init failed: {e}")
            self.enabled = False
    
    def _get_conn(self):
        return get_connection(max_retries=1, retry_delay=0, show_dialog=False)
        
    def _init_database(self):
        conn = self._get_conn(); cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                type VARCHAR(64) NOT NULL,
                title VARCHAR(255) NOT NULL,
                message TEXT NOT NULL,
                priority INT NOT NULL,
                data JSON NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                read_at TIMESTAMP NULL,
                dismissed_at TIMESTAMP NULL,
                user_id INT DEFAULT 1,
                status VARCHAR(32) DEFAULT 'created',
                display_attempts INT DEFAULT 0,
                last_display_attempt TIMESTAMP NULL
            ) ENGINE=InnoDB
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS notification_settings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                type VARCHAR(64) UNIQUE NOT NULL,
                enabled BOOLEAN NOT NULL DEFAULT 1,
                priority INT NOT NULL DEFAULT 2,
                sound_enabled BOOLEAN NOT NULL DEFAULT 1,
                popup_enabled BOOLEAN NOT NULL DEFAULT 1,
                email_enabled BOOLEAN NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS notification_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                notification_id INT,
                event_type VARCHAR(64) NOT NULL,
                message TEXT,
                details JSON,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_notification_id (notification_id),
                CONSTRAINT fk_notification_logs_notif FOREIGN KEY (notification_id)
                  REFERENCES notifications(id) ON DELETE CASCADE
            ) ENGINE=InnoDB
            """
        )
        for notif_type in NotificationType:
            cur.execute(
                """
                INSERT IGNORE INTO notification_settings
                (type, enabled, priority, sound_enabled, popup_enabled, email_enabled)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    notif_type.value,
                    self.notification_settings[notif_type]["enabled"],
                    self.notification_settings[notif_type]["priority"].value,
                    True, True, False,
                ),
            )
        conn.commit(); cur.close(); conn.close()
    
    def log_notification_event(self, notification_id: int, event_type: str, message: str, details: Dict = None):
        if not self.enabled:
            return
        conn = self._get_conn(); cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO notification_logs (notification_id, event_type, message, details)
            VALUES (%s, %s, %s, %s)
            """,
            (
                notification_id,
                event_type,
                message,
                json.dumps(details) if details else None,
            ),
        )
        conn.commit(); cur.close(); conn.close()
        
        # Also print to console for debugging
    
    def update_notification_status(self, notification_id: int, status: str, details: Dict = None):
        if not self.enabled:
            return
        conn = self._get_conn(); cur = conn.cursor()
        if status == "displayed":
            cur.execute(
                """
                UPDATE notifications 
                SET status = %s, display_attempts = display_attempts + 1, last_display_attempt = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (status, notification_id),
            )
        else:
            cur.execute("UPDATE notifications SET status = %s WHERE id = %s", (status, notification_id))
        conn.commit(); cur.close(); conn.close()
        
        # Log the status update
        self.log_notification_event(notification_id, "status_update", f"Status changed to {status}", details)
    
    def get_notification_logs(self, notification_id: int = None, limit: int = 100):
        if not self.enabled:
            return []
        conn = self._get_conn(); cur = conn.cursor(dictionary=True)
        if notification_id:
            cur.execute(
                """
                SELECT id, notification_id, event_type, message, details, timestamp
                FROM notification_logs
                WHERE notification_id=%s
                ORDER BY timestamp DESC
                LIMIT %s
                """,
                (notification_id, limit),
            )
        else:
            cur.execute(
                """
                SELECT id, notification_id, event_type, message, details, timestamp
                FROM notification_logs
                ORDER BY timestamp DESC
                LIMIT %s
                """,
                (limit,),
            )
        rows = cur.fetchall(); cur.close(); conn.close()
        logs = []
        for row in rows:
            details = row.get("details")
            logs.append({
                "id": row["id"],
                "notification_id": row["notification_id"],
                "event_type": row["event_type"],
                "message": row["message"],
                "details": json.loads(details) if details else None,
                "timestamp": row["timestamp"],
            })
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
        
        if not self.enabled:
            return None
        conn = self._get_conn(); cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO notifications (type, title, message, priority, data)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                notif_type.value,
                title,
                message,
                priority.value,
                json.dumps(data) if data else None,
            ),
        )
        notification_id = cur.lastrowid
        conn.commit(); cur.close(); conn.close()
        
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
        if not self.enabled:
            return self.notification_settings[notif_type]
        conn = self._get_conn(); cur = conn.cursor()
        cur.execute(
            """
            SELECT enabled, priority, sound_enabled, popup_enabled, email_enabled
            FROM notification_settings WHERE type = %s
            """,
            (notif_type.value,),
        )
        result = cur.fetchone(); cur.close(); conn.close()
        
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
        if not self.enabled:
            return
        conn = self._get_conn(); cur = conn.cursor()
        cur.execute(
            """
            UPDATE notification_settings 
            SET enabled = %s, priority = %s, sound_enabled = %s, popup_enabled = %s, email_enabled = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE type = %s
            """,
            (
                settings.get("enabled", True),
                settings.get("priority", 2),
                settings.get("sound_enabled", True),
                settings.get("popup_enabled", True),
                settings.get("email_enabled", False),
                notif_type.value,
            ),
        )
        conn.commit(); cur.close(); conn.close()
    
    def get_unread_notifications(self, limit: int = 50) -> List[Dict]:
        """Get unread notifications."""
        if not self.enabled:
            return []
        conn = self._get_conn(); cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT id, type, title, message, priority, data, created_at
            FROM notifications 
            WHERE read_at IS NULL AND dismissed_at IS NULL
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall(); cur.close(); conn.close()
        notifications = []
        for row in rows:
            data = row.get("data")
            notifications.append({
                "id": row["id"],
                "type": row["type"],
                "title": row["title"],
                "message": row["message"],
                "priority": row["priority"],
                "data": json.loads(data) if data else None,
                "created_at": row["created_at"],
            })
        return notifications
    
    def mark_as_read(self, notification_id: int):
        """Mark a notification as read."""
        if not self.enabled:
            return
        conn = self._get_conn(); cur = conn.cursor()
        cur.execute("UPDATE notifications SET read_at = CURRENT_TIMESTAMP WHERE id = %s", (notification_id,))
        conn.commit(); cur.close(); conn.close()
    
    def dismiss_notification(self, notification_id: int):
        """Dismiss a notification."""
        if not self.enabled:
            return
        conn = self._get_conn(); cur = conn.cursor()
        cur.execute("UPDATE notifications SET dismissed_at = CURRENT_TIMESTAMP WHERE id = %s", (notification_id,))
        conn.commit(); cur.close(); conn.close()
    
    def dismiss_all_notifications(self) -> int:
        """Dismiss ALL non-dismissed notifications in one batch.
        Returns the number of rows affected.
        """
        if not self.enabled:
            return 0
        conn = self._get_conn(); cur = conn.cursor()
        cur.execute(
            """
            UPDATE notifications 
            SET dismissed_at = CURRENT_TIMESTAMP 
            WHERE dismissed_at IS NULL
            """
        )
        affected = cur.rowcount if hasattr(cur, 'rowcount') else 0
        conn.commit(); cur.close(); conn.close(); return affected

    def mark_all_unread_as_read(self) -> int:
        """Mark ALL unread (and not dismissed) notifications as read in one batch.
        Returns the number of rows affected.
        """
        if not self.enabled:
            return 0
        conn = self._get_conn(); cur = conn.cursor()
        cur.execute(
            """
            UPDATE notifications 
            SET read_at = CURRENT_TIMESTAMP 
            WHERE read_at IS NULL AND dismissed_at IS NULL
            """
        )
        affected = cur.rowcount if hasattr(cur, 'rowcount') else 0
        conn.commit(); cur.close(); conn.close(); return affected
    
    def get_notification_count(self) -> int:
        """Get count of unread notifications."""
        if not self.enabled:
            return 0
        conn = self._get_conn(); cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*) FROM notifications 
            WHERE read_at IS NULL AND dismissed_at IS NULL
            """
        )
        count = cur.fetchone()[0]; cur.close(); conn.close(); return count
    
    def clear_old_notifications(self, days: int = 30):
        """Clear notifications older than specified days."""
        if not self.enabled:
            return
        conn = self._get_conn(); cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM notifications 
            WHERE created_at < DATE_SUB(NOW(), INTERVAL %s DAY)
            """,
            (int(days),),
        )
        conn.commit(); cur.close(); conn.close()

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
