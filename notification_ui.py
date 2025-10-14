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
        self._progress_after_id = None
        self._dismiss_after_id = None
        self._dismissed = False
        
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
                command=lambda: self.dismiss(immediate=True)
            )
        else:
            close_btn = tk.Button(
                header_frame,
                text="×",
                width=3,
                command=lambda: self.dismiss(immediate=True),
                fg="white",
                bg=bg_color,
                relief="flat"
            )
        close_btn.pack(side="right")

        # Make sure the first click is not eaten for focus activation
        def _on_close_click(event):
            self.dismiss(immediate=True)
            return "break"
        try:
            close_btn.bind("<Button-1>", _on_close_click, add="+")
        except Exception:
            pass
        try:
            close_btn.configure(takefocus=1, default="active")
        except Exception:
            pass
        try:
            # Focus the close button so a single click immediately activates
            self.window.after(0, close_btn.focus_set)
        except Exception:
            pass
        
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
    
    def _show_toast(self):
        """Finalize and show the toast window reliably."""
        if not self.window:
            return
        try:
            # Ensure on top and focused enough to receive clicks
            self.window.lift()
            self.window.attributes("-topmost", True)
            try:
                # Ensure geometry and widgets are realized so focus/click works on first try
                self.window.update_idletasks()
            except Exception:
                pass
            try:
                self.window.focus_force()
            except Exception:
                pass

            # Safety: handle window close requests (even though overrideredirect=True)
            try:
                self.window.protocol("WM_DELETE_WINDOW", lambda: self.dismiss(immediate=True))
            except Exception:
                pass

            # Cleanup timers if window is destroyed by any means
            self.window.bind("<Destroy>", lambda e: self._on_window_destroy(), add="+")

            # When the window gets mapped (shown), reinforce focus
            try:
                self.window.bind("<Map>", lambda e: self.window.focus_force(), add="+")
            except Exception:
                pass

            # Keep interactions limited to explicit controls (like the × button)
        except Exception:
            pass

    def _on_window_destroy(self):
        """Ensure timers are canceled if the window goes away."""
        self._dismissed = True
        try:
            if self.window and self.window.winfo_exists():
                if self._progress_after_id:
                    try:
                        self.window.after_cancel(self._progress_after_id)
                    except Exception:
                        pass
                if self._dismiss_after_id:
                    try:
                        self.window.after_cancel(self._dismiss_after_id)
                    except Exception:
                        pass
        except Exception:
            pass

    def _start_progress_animation(self):
        """Start the progress bar animation for auto-dismiss using Tk after timers."""
        try:
            if hasattr(self.progress, 'configure'):
                self.progress["maximum"] = 100
                self.progress["value"] = 0

            steps = 100
            # Minimum interval of 20ms to avoid excessive timer calls
            interval = max(20, int(self.duration / steps))

            def step(i=0):
                if self._dismissed or not (self.window and self.window.winfo_exists()):
                    return
                try:
                    if hasattr(self.progress, 'configure'):
                        self.progress["value"] = min(i, 100)
                except tk.TclError:
                    return

                if i < steps:
                    self._progress_after_id = self.window.after(interval, step, i + 1)
                else:
                    # Completed progress; schedule dismiss
                    self._dismiss_after_id = self.window.after(10, lambda: self.dismiss(immediate=False))

            # Kick off the progress
            self._progress_after_id = self.window.after(interval, step, 1)
        except Exception:
            # If anything goes wrong with progress, still schedule dismissal
            if self.window and self.window.winfo_exists():
                self._dismiss_after_id = self.window.after(self.duration, lambda: self.dismiss(immediate=False))

    def dismiss(self, immediate: bool = False):
        """Dismiss the toast notification."""
        if self._dismissed:
            return
        self._dismissed = True

        try:
            # Cancel any scheduled timers
            if self.window and self.window.winfo_exists():
                try:
                    if self._progress_after_id:
                        self.window.after_cancel(self._progress_after_id)
                except Exception:
                    pass
                try:
                    if self._dismiss_after_id:
                        self.window.after_cancel(self._dismiss_after_id)
                except Exception:
                    pass

            # If immediate, destroy without fade
            if immediate:
                try:
                    if self.window and self.window.winfo_exists():
                        self.window.destroy()
                finally:
                    if self.on_dismiss:
                        try:
                            self.on_dismiss()
                        except Exception:
                            pass
                return

            # Fade-out animation using after (UI thread-safe)
            def animate_out(step=0, total=20):
                if not (self.window and self.window.winfo_exists()):
                    return
                try:
                    alpha = max(0.0, 0.95 - (0.95 * (step + 1) / total))
                    self.window.attributes("-alpha", alpha)
                except tk.TclError:
                    # Some platforms may not support alpha on overrideredirect; destroy immediately
                    try:
                        if self.window and self.window.winfo_exists():
                            self.window.destroy()
                    finally:
                        if self.on_dismiss:
                            try:
                                self.on_dismiss()
                            except Exception:
                                pass
                    return
                if step + 1 < total:
                    self.window.after(20, animate_out, step + 1, total)
                else:
                    try:
                        if self.window and self.window.winfo_exists():
                            self.window.destroy()
                    finally:
                        if self.on_dismiss:
                            try:
                                self.on_dismiss()
                            except Exception:
                                pass

            if self.window and self.window.winfo_exists():
                self.window.after(0, animate_out)
            else:
                # If window doesn't exist, still call on_dismiss
                if self.on_dismiss:
                    try:
                        self.on_dismiss()
                    except Exception:
                        pass
        except Exception:
            # As a last resort, ensure on_dismiss gets called
            if self.on_dismiss:
                try:
                    self.on_dismiss()
                except Exception:
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
        
        # Set up safe, widget-scoped scroll bindings (avoid global bind_all)
        self._setup_scroll_bindings()

    def _setup_scroll_bindings(self):
        """Configure mouse wheel scrolling with safety checks and unbinds.
        Uses widget-specific binds to prevent callbacks after widget destruction.
        """
        # Windows/macOS wheel
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        # Linux wheel
        self.canvas.bind("<Button-4>", lambda e: self._on_scroll_units(-1))
        self.canvas.bind("<Button-5>", lambda e: self._on_scroll_units(1))

        # Ensure unbinding when the panel is destroyed
        self.main_frame.bind("<Destroy>", lambda e: self._unbind_scroll_bindings(), add="+")

    def _unbind_scroll_bindings(self):
        """Unbind mouse wheel events from the canvas if it still exists."""
        try:
            if hasattr(self, "canvas") and self.canvas and self.canvas.winfo_exists():
                self.canvas.unbind("<MouseWheel>")
                self.canvas.unbind("<Button-4>")
                self.canvas.unbind("<Button-5>")
        except tk.TclError:
            pass

    def _on_scroll_units(self, units: int):
        """Scroll the canvas by units safely (used for Linux Button-4/5)."""
        try:
            if hasattr(self, "canvas") and self.canvas and self.canvas.winfo_exists():
                self.canvas.yview_scroll(units, "units")
        except tk.TclError:
            # Canvas might have been destroyed between event and handler
            pass

    def _on_mousewheel(self, event):
        """Handle mouse wheel on Windows/macOS with safety checks."""
        try:
            if not (hasattr(self, "canvas") and self.canvas and self.canvas.winfo_exists()):
                return
            # On Windows/macOS, event.delta is typically multiples of 120
            delta = getattr(event, "delta", 0) or 0
            if delta:
                self.canvas.yview_scroll(int(-1 * (delta / 120)), "units")
        except tk.TclError:
            # Ignore if canvas has been destroyed
            pass
    
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
