# Push Notification System for Network Monitoring Dashboard

## Overview

The notification system provides real-time push notifications for various network monitoring events including loop detection, router status changes, bandwidth alerts, and system notifications.

## Features

### 🔔 **Notification Types**
- **Loop Detection**: Alerts when network loops are detected
- **Router Status**: Notifications for router online/offline status changes
- **Bandwidth Alerts**: High bandwidth usage warnings
- **System Alerts**: General system notifications
- **Security Alerts**: Security-related notifications
- **Maintenance**: Maintenance and update notifications

### 🎨 **UI Components**
- **Toast Notifications**: Temporary popup notifications with auto-dismiss
- **Notification Panel**: Full notification management interface
- **Settings Panel**: Configure notification preferences
- **Badge Counter**: Real-time notification count display

### ⚙️ **Configuration**
- Enable/disable specific notification types
- Priority levels (Low, Medium, High, Critical)
- Sound and popup preferences
- Email notifications (future feature)

## Installation

The notification system is automatically integrated into the main dashboard. No additional installation steps are required.

## Usage

### For Administrators

1. **View Notifications**: Click the 🔔 bell icon in the sidebar to open the notification panel
2. **Manage Notifications**: Mark as read, dismiss, or clear all notifications
3. **Configure Settings**: Go to Settings → Notification Settings to customize preferences

### For Developers

#### Creating Notifications

```python
from notification_utils import (
    notify_loop_detected,
    notify_router_status_change,
    notify_bandwidth_high,
    notify_system_alert,
    notify_security_alert
)

# Loop detection notification
notify_loop_detected(severity_score=0.85, offenders=["aa:bb:cc:dd:ee:ff"], interface="Wi-Fi")

# Router status change
notify_router_status_change("Main Router", "192.168.1.1", is_online=False)

# High bandwidth usage
notify_bandwidth_high("Router Name", bandwidth_usage=95.5, threshold=80.0)

# System alert
notify_system_alert("Maintenance Notice", "System will be down for maintenance")

# Security alert
notify_security_alert("Security Breach", "Unauthorized access detected")
```

#### Custom Notifications

```python
from notification_utils import notification_manager, NotificationType, NotificationPriority

# Create custom notification
notification_id = notification_manager.create_notification(
    notif_type=NotificationType.SYSTEM_ALERT,
    title="Custom Alert",
    message="This is a custom notification",
    data={"custom_field": "value"},
    priority=NotificationPriority.HIGH
)
```

#### Notification Management

```python
# Get unread notifications
notifications = notification_manager.get_unread_notifications()

# Mark as read
notification_manager.mark_as_read(notification_id)

# Dismiss notification
notification_manager.dismiss_notification(notification_id)

# Get notification count
count = notification_manager.get_notification_count()
```

## Database Schema

### Notifications Table
```sql
CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    priority INTEGER NOT NULL,
    data TEXT,  -- JSON data for additional info
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP NULL,
    dismissed_at TIMESTAMP NULL,
    user_id INTEGER DEFAULT 1
);
```

### Notification Settings Table
```sql
CREATE TABLE notification_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT UNIQUE NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT 1,
    priority INTEGER NOT NULL DEFAULT 2,
    sound_enabled BOOLEAN NOT NULL DEFAULT 1,
    popup_enabled BOOLEAN NOT NULL DEFAULT 1,
    email_enabled BOOLEAN NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Integration Points

### Dashboard Integration
- **Loop Detection**: Automatic notifications when loops are detected
- **Router Monitoring**: Status change notifications in background thread
- **Bandwidth Monitoring**: High usage alerts (future implementation)
- **System Events**: Integration with various dashboard events

### UI Integration
- **Sidebar**: Notification bell with count badge
- **Settings Menu**: Notification settings access
- **Toast System**: Automatic popup notifications
- **Panel Management**: Dedicated notification management interface

## Testing

Run the test script to verify the notification system:

```bash
python test_notifications.py
```

This will:
1. Create sample notifications of each type
2. Open a test UI with notification management
3. Allow testing of all notification features

## Configuration

### Default Settings
- **Loop Detection**: Enabled, High Priority
- **Router Offline**: Enabled, Medium Priority
- **Router Online**: Enabled, Low Priority
- **Bandwidth High**: Enabled, Medium Priority
- **System Alert**: Enabled, High Priority
- **Security Alert**: Enabled, Critical Priority

### Customization
All settings can be modified through the notification settings panel or programmatically through the `notification_manager.update_notification_settings()` method.

## Future Enhancements

- **Email Notifications**: Send notifications via email
- **Push Notifications**: Browser push notifications
- **Mobile App**: Mobile notification support
- **Webhook Integration**: Send notifications to external services
- **Notification Templates**: Customizable notification templates
- **User Preferences**: Per-user notification preferences
- **Notification Scheduling**: Scheduled notification delivery

## Troubleshooting

### Common Issues

1. **Notifications not appearing**: Check if notification type is enabled in settings
2. **Toast notifications not showing**: Ensure the main window is visible and not minimized
3. **Database errors**: Verify database file permissions and integrity
4. **UI not updating**: Check if notification count refresh is working

### Debug Mode

Enable debug logging by adding print statements in the notification callback functions to track notification creation and processing.

## Support

For issues or questions about the notification system, please check the main dashboard documentation or contact the development team.

