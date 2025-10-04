import time
from tkinter import messagebox
import ttkbootstrap as tb
from PIL import Image, ImageTk
from user_utils import verify_user
from client_window import show_client_window
from collections import defaultdict
from dashboard import show_dashboard
from device_utils import get_device_info
from db import log_user_login, create_login_sessions_table

login_attempts = defaultdict(list)

def is_rate_limited(username, window=60, max_attempts=5):
    now = time.time()
    attempts = login_attempts[username]

    # Keep only attempts in the last `window` seconds
    attempts = [t for t in attempts if now - t < window]
    login_attempts[username] = attempts

    if len(attempts) >= max_attempts:
        return True  # Too many attempts
    return False


def center_window(win, width, height, y_offset=-15):
    """Center the window on the screen, considering taskbar space."""
    screen_w = win.winfo_screenwidth()
    screen_h = win.winfo_screenheight()

    # Workable screen height (excludes taskbar if reported)
    work_h = win.winfo_vrootheight()
    if work_h <= 0 or work_h > screen_h:  # fallback if invalid
        work_h = screen_h

    x = (screen_w // 2) - (width // 2)
    y = (work_h // 2) - (height // 2) + y_offset

    win.geometry(f"{width}x{height}+{x}+{y}")


def show_login(root):
    root.title("WINYFI Login")
    center_window(root, 900, 600)  # ✅ Centered login window
    root.resizable(True, True)
    
    # Initialize database tables
    create_login_sessions_table()

    # Initialize banner label (initially with a placeholder)
    banner_label = tb.Label(root)
    banner_label.pack(fill="x")

    # Update banner image dynamically based on window size
    def update_banner(event=None):
        window_width = root.winfo_width()
        if window_width > 0:
            try:
                banner_img = Image.open("assets/images/Banner.png")
                new_height = int(window_width * 250 / 900)
                if new_height > 0:
                    banner_img = banner_img.resize(
                        (window_width, new_height),
                        Image.Resampling.LANCZOS
                    )
                    banner_photo = ImageTk.PhotoImage(banner_img)
                    if banner_label.winfo_exists():
                        banner_label.config(image=banner_photo)
                        banner_label.image = banner_photo
            except Exception as e:
                print(f"Error loading or resizing image: {e}")

    root.after(100, update_banner)
    root.bind("<Configure>", update_banner)

    # Login card
    card = tb.Frame(root, bootstyle="light", padding=30)
    card.place(relx=0.5, rely=0.65, anchor="center", relwidth=0.4)

    tb.Label(
        card,
        text="Please Login",
        font=("Segoe UI", 16, "bold"),
        bootstyle="primary"
    ).pack(pady=(0, 20))

    username_var = tb.StringVar()
    password_var = tb.StringVar()

    def add_placeholder(entry, text):
        entry.insert(0, text)
        entry.config(foreground='gray')
        entry.bind(
            "<FocusIn>",
            lambda e: (
                entry.delete(0, "end"),
                entry.config(foreground='black')
            ) if entry.get() == text else None
        )
        entry.bind(
            "<FocusOut>",
            lambda e: (
                entry.insert(0, text),
                entry.config(foreground='gray')
            ) if entry.get() == "" else None
        )

    # Username field
    username_entry = tb.Entry(
        card, textvariable=username_var, width=30, font=("Segoe UI", 12)
    )
    username_entry.pack(pady=5, fill="x")
    add_placeholder(username_entry, "Username")

    # Password field
    password_entry = tb.Entry(
        card, textvariable=password_var, width=30, show="*", font=("Segoe UI", 12)
    )
    password_entry.pack(pady=5, fill="x")
    add_placeholder(password_entry, "Password")

    def handle_login(event=None):
        login_button.config(text="Loading...", state="disabled")
        root.update()

        username = username_var.get()
        password = password_var.get()

        time.sleep(1.5)  # Simulated loading delay

        if is_rate_limited(username):
            messagebox.showerror(
                "Rate Limited",
                "Too many failed login attempts.\nPlease wait a minute and try again."
            )
            login_button.config(text="Login", state="normal")
            return

        user = verify_user(username, password)
        if not user:
            login_attempts[username].append(time.time())
            messagebox.showerror("Login Failed", "Invalid username or password.")
            login_button.config(text="Login", state="normal")
            return

        # Get device information for logging
        device_info = get_device_info()
        
        # Log the login session
        login_type = 'admin' if user.get('role') == 'admin' else 'client'
        log_user_login(
            user_id=user['id'],
            username=user['username'],
            device_ip=device_info.get('ip_address'),
            device_mac=device_info.get('mac_address'),
            device_hostname=device_info.get('hostname'),
            device_platform=device_info.get('platform'),
            user_agent=device_info.get('user_agent'),
            login_type=login_type
        )

        # ✅ Success → hide login window
        root.withdraw()

        if user.get('role') == 'admin':
            # Admin → open dashboard
            dashboard_window = tb.Toplevel(root)
            dashboard_window.title("Admin Dashboard")
            center_window(dashboard_window, 1000, 700)
            dashboard_window.resizable(True, True)

            # Get API base URL from environment or use default
            import os
            api_base_url = os.environ.get("WINYFI_API", "http://localhost:5000")
            show_dashboard(dashboard_window, user, api_base_url)

            def on_dashboard_close():
                """Confirm and exit the entire application when the admin window is closed."""
                if messagebox.askyesno("Exit", "Are you sure you want to exit?"):
                    try:
                        dashboard_window.destroy()
                    except Exception:
                        pass
                    # Destroy the hidden root to terminate the app cleanly
                    try:
                        root.destroy()
                    except Exception:
                        pass
                    # Hard-exit fallback to ensure full termination
                    try:
                        import os
                        os._exit(0)
                    except Exception:
                        pass

            dashboard_window.protocol("WM_DELETE_WINDOW", on_dashboard_close)
        else:
            # Non-admin → open client portal
            client_top = tb.Toplevel(root)
            client_top.title("Client Portal")
            center_window(client_top, 1000, 700)
            client_top.resizable(True, True)

            show_client_window(client_top, user)

            def on_client_close():
                """Confirm and exit the entire application when the client window is closed."""
                if messagebox.askyesno("Exit", "Are you sure you want to exit?"):
                    try:
                        client_top.destroy()
                    except Exception:
                        pass
                    # Destroy the hidden root to terminate the app cleanly
                    try:
                        root.destroy()
                    except Exception:
                        pass
                    # Hard-exit fallback to ensure full termination
                    try:
                        import os
                        os._exit(0)
                    except Exception:
                        pass

            client_top.protocol("WM_DELETE_WINDOW", on_client_close)

    # Login button
    login_button = tb.Button(
        card,
        text="Login",
        bootstyle="danger",
        width=20,
        command=handle_login,
        style="primary-outline"
    )
    login_button.pack(pady=(15, 0))

    # Bind Enter key
    root.bind("<Return>", handle_login)
