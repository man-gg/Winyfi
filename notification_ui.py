#!/usr/bin/env python3
"""
Notification UI Components for Network Monitoring Dashboard
Provides toast notifications, notification panel, and settings interface.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from PIL import Image, ImageTk
import threading
import time
from datetime import datetime
from typing import Dict, List, Callable
from notification_utils import (
    notification_manager, 
    NotificationType, 
    NotificationPriority,
    get_notification_count,
    set_toast_callback
)

class ToastNotification:
    """A toast-style notification that appears temporarily."""
    
    def __init__(self, parent, title: str, message: str, priority: NotificationPriority, 
                 duration: int = 5000, on_dismiss: Callable = None):
        self.parent = parent
        self.title = title
        self.message = message
        self.priority = priority
        self.duration = duration
        self.on_dismiss = on_dismiss
        self.window = None
        self.auto_dismiss_task = None
        
        self._create_toast()
        self._show_toast()
    
    def _create_toast(self):
        """Create the toast notification window."""
        self.window = tk.Toplevel(self.parent)
        self.window.title("")
        self.window.overrideredirect(True)  # Remove window decorations
        self.window.attributes("-topmost", True)  # Always on top
        self.window.attributes("-alpha", 0.95)  # Slight transparency
        
        # Set size and position
        width = 350
        height = 120
        
        # Get screen dimensions
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        
        # Position in top-right corner
        x = screen_width - width - 20
        y = 20
        
        self.window.geometry(f"{width}x{height}+{x}+{y}")
        
        # Configure style based on priority
        if self.priority == NotificationPriority.CRITICAL:
            style = "danger"
            bg_color = "#dc3545"
        elif self.priority == NotificationPriority.HIGH:
            style = "warning"
            bg_color = "#fd7e14"
        elif self.priority == NotificationPriority.MEDIUM:
            style = "info"
            bg_color = "#0dcaf0"
        else:
            style = "success"
            bg_color = "#198754"
        
        # Initialize ttkbootstrap style for the window
        try:
            window_style = tb.Style()
        except:
            window_style = None
        
        # Main frame - use regular tkinter Frame if ttkbootstrap fails
        if window_style:
            main_frame = tb.Frame(self.window, style=f"{style}.TFrame", padding=15)
        else:
            main_frame = tk.Frame(self.window, bg=bg_color, padx=15, pady=15)
        main_frame.pack(fill="both", expand=True)
        
        # Header with title and close button
        if window_style:
            header_frame = tb.Frame(main_frame)
        else:
            header_frame = tk.Frame(main_frame)
        header_frame.pack(fill="x", pady=(0, 8))
        
        # Title
        if window_style:
            title_label = tb.Label(
                header_frame, 
                text=self.title, 
                font=("Segoe UI", 10, "bold"),
                style=f"{style}.TLabel"
            )
        else:
            title_label = tk.Label(
                header_frame, 
                text=self.title, 
                font=("Segoe UI", 10, "bold"),
                fg="white",
                bg=bg_color
            )
        title_label.pack(side="left", fill="x", expand=True)
        
        # Close button
        if window_style:
            close_btn = tb.Button(
                header_frame,
                text="×",
                style=f"{style}.TButton",
                width=3,
                command=self.dismiss
            )
        else:
            close_btn = tk.Button(
                header_frame,
                text="×",
                width=3,
                command=self.dismiss,
                fg="white",
                bg=bg_color,
                relief="flat"
            )
        close_btn.pack(side="right")
        
        # Message
        if window_style:
            message_label = tb.Label(
                main_frame,
                text=self.message,
                font=("Segoe UI", 9),
                style=f"{style}.TLabel",
                wraplength=300
            )
        else:
            message_label = tk.Label(
                main_frame,
                text=self.message,
                font=("Segoe UI", 9),
                fg="white",
                bg=bg_color,
                wraplength=300
            )
        message_label.pack(fill="x")
        
        # Progress bar for auto-dismiss
        if window_style:
            self.progress = tb.Progressbar(
                main_frame,
                mode="determinate",
                length=300,
                style=f"{style}.TProgressbar"
            )
        else:
            self.progress = tk.Frame(main_frame, height=4, bg="white")
        self.progress.pack(fill="x", pady=(8, 0))
        
        # Start progress animation
        self._start_progress_animation()
    
    def _start_progress_animation(self):
        """Start the progress bar animation for auto-dismiss."""
        if hasattr(self.progress, 'configure'):
            self.progress["maximum"] = 100
            self.progress["value"] = 0
        
        def update_progress():
            for i in range(101):
                try:
                    if self.window and self.window.winfo_exists():
                        if hasattr(self.progress, 'configure'):
                            self.progress["value"] = i
                        self.window.update()
                        time.sleep(self.duration / 1000 / 100)  # Convert to seconds
                    else:
                        break
                except Exception as e:
                    pass

            def dismiss(self):
                """Dismiss the toast notification."""
                try:
                    if self.window and self.window.winfo_exists():
                        # Fade out animation
                        def animate_out():
                            try:
                                # Fade out by reducing alpha
                                for i in range(20):
                                    if self.window and self.window.winfo_exists():
                                        alpha = 0.95 - (0.95 * (i + 1) / 20)  # Fade from 0.95 to 0
                                        self.window.attributes("-alpha", alpha)
                                        self.window.update()
                                        time.sleep(0.02)
                                    else:
                                        break
                                if self.window and self.window.winfo_exists():
                                    self.window.destroy()
                            except RuntimeError:
                                # Main thread is not in main loop - just destroy
                                try:
                                    if self.window and self.window.winfo_exists():
                                        self.window.destroy()
                                except:
                                    pass
                            except Exception:
                                pass
                        threading.Thread(target=animate_out, daemon=True).start()
                        if self.on_dismiss:
                            self.on_dismiss()
                except Exception as e:
                    pass
            # End of for loop in update_progress()
        
        threading.Thread(target=update_progress, daemon=True).start()

    def dismiss(self):
        """Dismiss the toast notification."""
        try:
            if self.window and self.window.winfo_exists():
                # Fade out animation
                def animate_out():
                    try:
                        # Fade out by reducing alpha
                        for i in range(20):
                            if self.window and self.window.winfo_exists():
                                alpha = 0.95 - (0.95 * (i + 1) / 20)  # Fade from 0.95 to 0
                                self.window.attributes("-alpha", alpha)
                                self.window.update()
                                time.sleep(0.02)
                            else:
                                break
                        if self.window and self.window.winfo_exists():
                            self.window.destroy()
                    except RuntimeError:
                        # Main thread is not in main loop - just destroy
                        try:
                            if self.window and self.window.winfo_exists():
                                self.window.destroy()
                        except:
                            pass
                    except Exception:
                        pass
                
                threading.Thread(target=animate_out, daemon=True).start()
                
                if self.on_dismiss:
                    self.on_dismiss()
        except Exception as e:
            pass


class NotificationPanel:
    """A panel that shows all notifications with management options."""
    
    def __init__(self, parent):
        self.parent = parent
        self.notifications = []
        self.notification_widgets = {}
        self.refresh_callback = None
        
        self._create_panel()
        self._load_notifications()
    
    def _create_panel(self):
        """Create the notification panel UI."""
        # Main frame
        self.main_frame = tb.Frame(self.parent)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Header
        header_frame = tb.Frame(self.main_frame)
        header_frame.pack(fill="x", pady=(0, 10))
        
        # Title
        title_label = tb.Label(
            header_frame,
            text="🔔 Notifications",
            font=("Segoe UI", 16, "bold")
        )
        title_label.pack(side="left")
        
        # Action buttons
        actions_frame = tb.Frame(header_frame)
        actions_frame.pack(side="right")
        
        # Mark all as read button
        mark_read_btn = tb.Button(
            actions_frame,
            text="Mark All Read",
            style="info.TButton",
            command=self.mark_all_read
        )
        mark_read_btn.pack(side="left", padx=(0, 5))
        
        # Clear all button
        clear_btn = tb.Button(
            actions_frame,
            text="Clear All",
            style="danger.TButton",
            command=self.clear_all
        )
        clear_btn.pack(side="left")
        
        # Notifications container
        self.notifications_frame = tb.Frame(self.main_frame)
        self.notifications_frame.pack(fill="both", expand=True)
        
        # Scrollable frame for notifications
        self.canvas = tk.Canvas(self.notifications_frame, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.notifications_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tb.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Bind mousewheel to canvas
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
    
    def _load_notifications(self):
        """Load notifications from database."""
        self.notifications = notification_manager.get_unread_notifications(100)
        self._refresh_ui()
    
    def _refresh_ui(self):
        """Refresh the notification UI."""
        # Clear existing widgets
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.notification_widgets.clear()
        
        if not self.notifications:
            # Show empty state
            empty_label = tb.Label(
                self.scrollable_frame,
                text="No notifications",
                font=("Segoe UI", 12),
                foreground="gray"
            )
            empty_label.pack(pady=50)
            return
        
        # Create notification widgets
        for i, notification in enumerate(self.notifications):
            self._create_notification_widget(notification, i)
    
    def _create_notification_widget(self, notification: Dict, index: int):
        """Create a widget for a single notification."""
        # Determine style based on priority
        priority = notification["priority"]
        if priority == 4:  # CRITICAL
            style = "danger"
            priority_text = "CRITICAL"
        elif priority == 3:  # HIGH
            style = "warning"
            priority_text = "HIGH"
        elif priority == 2:  # MEDIUM
            style = "info"
            priority_text = "MEDIUM"
        else:  # LOW
            style = "success"
            priority_text = "LOW"
        
        # Notification frame
        notif_frame = tb.LabelFrame(
            self.scrollable_frame,
            text=f"{notification['title']} - {priority_text}",
            style=f"{style}.TLabelFrame",
            padding=10
        )
        notif_frame.pack(fill="x", pady=5)
        
        # Message
        message_label = tb.Label(
            notif_frame,
            text=notification["message"],
            font=("Segoe UI", 9),
            wraplength=600
        )
        message_label.pack(anchor="w", pady=(0, 5))
        
        # Timestamp
        created_at = datetime.fromisoformat(notification["created_at"].replace("Z", "+00:00"))
        time_str = created_at.strftime("%Y-%m-%d %H:%M:%S")
        time_label = tb.Label(
            notif_frame,
            text=f"📅 {time_str}",
            font=("Segoe UI", 8),
            foreground="gray"
        )
        time_label.pack(anchor="w", pady=(0, 5))
        
        # Action buttons
        actions_frame = tb.Frame(notif_frame)
        actions_frame.pack(fill="x")
        
        # Mark as read button
        read_btn = tb.Button(
            actions_frame,
            text="Mark Read",
            style=f"{style}.TButton",
            command=lambda: self.mark_as_read(notification["id"])
        )
        read_btn.pack(side="left", padx=(0, 5))
        
        # Dismiss button
        dismiss_btn = tb.Button(
            actions_frame,
            text="Dismiss",
            style="secondary.TButton",
            command=lambda: self.dismiss_notification(notification["id"])
        )
        dismiss_btn.pack(side="left")
        
        # Store reference
        self.notification_widgets[notification["id"]] = notif_frame
    
    def mark_as_read(self, notification_id: int):
        """Mark a notification as read."""
        notification_manager.mark_as_read(notification_id)
        self._load_notifications()
        if self.refresh_callback:
            self.refresh_callback()
    
    def dismiss_notification(self, notification_id: int):
        """Dismiss a notification."""
        notification_manager.dismiss_notification(notification_id)
        self._load_notifications()
        if self.refresh_callback:
            self.refresh_callback()
    
    def mark_all_read(self):
        """Mark all notifications as read."""
        for notification in self.notifications:
            notification_manager.mark_as_read(notification["id"])
        self._load_notifications()
        if self.refresh_callback:
            self.refresh_callback()
    
    def clear_all(self):
        """Clear all notifications."""
        for notification in self.notifications:
            notification_manager.dismiss_notification(notification["id"])
        self._load_notifications()
        if self.refresh_callback:
            self.refresh_callback()
    
    def refresh(self):
        """Refresh the notification panel."""
        self._load_notifications()

class NotificationSettingsPanel:
    """A panel for managing notification settings."""
    
    def __init__(self, parent):
        self.parent = parent
        self.settings_widgets = {}
        
        self._create_panel()
        self._load_settings()
    
    def _create_panel(self):
        """Create the settings panel UI."""
        # Main frame
        self.main_frame = tb.Frame(self.parent)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Title
        title_label = tb.Label(
            self.main_frame,
            text="🔧 Notification Settings",
            font=("Segoe UI", 16, "bold")
        )
        title_label.pack(anchor="w", pady=(0, 20))
        
        # Settings container
        self.settings_frame = tb.Frame(self.main_frame)
        self.settings_frame.pack(fill="both", expand=True)
        
        # Create settings for each notification type
        for notif_type in NotificationType:
            self._create_setting_widget(notif_type)
        
        # Save button
        save_btn = tb.Button(
            self.main_frame,
            text="Save Settings",
            style="success.TButton",
            command=self.save_settings
        )
        save_btn.pack(pady=20)
    
    def _create_setting_widget(self, notif_type: NotificationType):
        """Create a setting widget for a notification type."""
        # Main setting frame
        setting_frame = tb.LabelFrame(
            self.settings_frame,
            text=notif_type.value.replace("_", " ").title(),
            padding=15
        )
        setting_frame.pack(fill="x", pady=5)
        
        # Enable checkbox
        enabled_var = tk.BooleanVar()
        enabled_cb = tb.Checkbutton(
            setting_frame,
            text="Enable notifications",
            variable=enabled_var,
            style="success.TCheckbutton"
        )
        enabled_cb.pack(anchor="w")
        
        # Priority selection
        priority_frame = tb.Frame(setting_frame)
        priority_frame.pack(fill="x", pady=(5, 0))
        
        priority_label = tb.Label(priority_frame, text="Priority:")
        priority_label.pack(side="left")
        
        priority_var = tk.StringVar()
        priority_combo = ttk.Combobox(
            priority_frame,
            textvariable=priority_var,
            values=["LOW", "MEDIUM", "HIGH", "CRITICAL"],
            state="readonly",
            width=10
        )
        priority_combo.pack(side="left", padx=(5, 0))
        
        # Sound checkbox
        sound_var = tk.BooleanVar()
        sound_cb = tb.Checkbutton(
            setting_frame,
            text="Play sound",
            variable=sound_var,
            style="info.TCheckbutton"
        )
        sound_cb.pack(anchor="w")
        
        # Popup checkbox
        popup_var = tk.BooleanVar()
        popup_cb = tb.Checkbutton(
            setting_frame,
            text="Show popup",
            variable=popup_var,
            style="info.TCheckbutton"
        )
        popup_cb.pack(anchor="w")
        
        # Store widgets
        self.settings_widgets[notif_type] = {
            "enabled": enabled_var,
            "priority": priority_var,
            "sound": sound_var,
            "popup": popup_var
        }
    
    def _load_settings(self):
        """Load settings from database."""
        for notif_type, widgets in self.settings_widgets.items():
            settings = notification_manager.get_notification_settings(notif_type)
            
            widgets["enabled"].set(settings["enabled"])
            widgets["priority"].set(NotificationPriority(settings["priority"]).name)
            widgets["sound"].set(settings["sound_enabled"])
            widgets["popup"].set(settings["popup_enabled"])
    
    def save_settings(self):
        """Save settings to database."""
        for notif_type, widgets in self.settings_widgets.items():
            settings = {
                "enabled": widgets["enabled"].get(),
                "priority": NotificationPriority[widgets["priority"].get()].value,
                "sound_enabled": widgets["sound"].get(),
                "popup_enabled": widgets["popup"].get(),
                "email_enabled": False  # Not implemented yet
            }
            
            notification_manager.update_notification_settings(notif_type, settings)
        
        # Show success message
        messagebox.showinfo("Success", "Notification settings saved successfully!")

class NotificationSystem:
    """Main notification system that coordinates all components."""
    
    def __init__(self, parent):
        self.parent = parent
        self.toast_notifications = []
        self.notification_panel = None
        self.settings_panel = None
        
        # Setup notification callbacks
        notification_manager.add_notification_callback(self._on_notification_created)
        # Also set as global callback
        set_toast_callback(self._on_notification_created)
    
    def _on_notification_created(self, notification_id, notif_type, title, message, priority, data):
        """Handle new notification creation."""
        
        # Log callback trigger
        from notification_utils import notification_manager
        notification_manager.log_notification_event(
            notification_id,
            "callback_triggered",
            f"Toast callback triggered for: {title}",
            {"title": title, "message": message, "priority": priority.value}
        )
        
        # Show toast notification
        self.show_toast(notification_id, title, message, priority)
    
    def show_toast(self, notification_id: int, title: str, message: str, priority: NotificationPriority):
        """Show a toast notification."""
        
        from notification_utils import notification_manager
        
        try:
            toast = ToastNotification(
                self.parent,
                title,
                message,
                priority,
                duration=5000,
                on_dismiss=lambda: self._remove_toast(toast)
            )
            self.toast_notifications.append(toast)
            
            # Log successful toast creation
            notification_manager.log_notification_event(
                notification_id,
                "toast_created",
                f"Toast notification created successfully: {title}",
                {"title": title, "message": message}
            )
            
            # Update notification status to displayed
            notification_manager.update_notification_status(notification_id, "displayed")
            
        except Exception as e:
            
            # Log toast creation error
            notification_manager.log_notification_event(
                notification_id,
                "error",
                f"Failed to create toast notification: {str(e)}",
                {"error": str(e), "title": title}
            )
    
    def _remove_toast(self, toast):
        """Remove a toast from the active list."""
        if toast in self.toast_notifications:
            self.toast_notifications.remove(toast)
    
    def create_notification_panel(self, parent):
        """Create the notification panel."""
        self.notification_panel = NotificationPanel(parent)
        return self.notification_panel
    
    def create_settings_panel(self, parent):
        """Create the settings panel."""
        self.settings_panel = NotificationSettingsPanel(parent)
        return self.settings_panel
    
    def get_notification_count(self):
        """Get the current notification count."""
        return notification_manager.get_notification_count()
    
    def refresh_notifications(self):
        """Refresh all notification displays."""
        if self.notification_panel:
            self.notification_panel.refresh()
