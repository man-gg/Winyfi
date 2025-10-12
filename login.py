import time
from tkinter import messagebox
import ttkbootstrap as tb
from PIL import Image, ImageTk
import threading
from user_utils import verify_user
from client_window import show_client_window
from collections import defaultdict
from dashboard import show_dashboard
from device_utils import get_device_info
from db import (
    log_user_login,
    create_login_sessions_table,
    get_connection,
    DatabaseConnectionError,
    check_mysql_server_status,
)
import requests
import os

login_attempts = defaultdict(list)

def check_server_connectivity(timeout=1.2):
    """Fast, best-effort server reachability check (blocking, short timeout)."""
    try:
        api_base_url = os.environ.get("WINYFI_API", "http://localhost:5000").rstrip("/")
        response = requests.get(
            f"{api_base_url}/api/health",
            timeout=(min(0.8, timeout), timeout)
        )
        return response.status_code == 200
    except Exception:
        try:
            # Fallback: any endpoint response implies server is up
            api_base_url = os.environ.get("WINYFI_API", "http://localhost:5000").rstrip("/")
            response = requests.get(
                f"{api_base_url}/api/routers",
                timeout=(min(0.8, timeout), timeout)
            )
            return response.status_code in (200, 404, 500)
        except Exception:
            return False

def check_server_connectivity_async(root, callback, timeout=1.2):
    """Run the server check in a background thread and return result via callback(bool)."""
    def worker():
        ok = check_server_connectivity(timeout=timeout)
        try:
            root.after(0, lambda: callback(ok))
        except Exception:
            pass
    threading.Thread(target=worker, daemon=True).start()

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
    
    # Initialize database tables only for admin (client portal relies on API)
    # We'll lazily create this for admin users after verifying credentials.

    # Initialize banner label (initially with a placeholder)
    banner_label = tb.Label(root)
    banner_label.pack(fill="x")

    # Optimized banner rendering: load once, debounce resizes, reuse cached image
    _banner_src_img = {"img": None}
    _banner_after_id = {"id": None}
    _last_width = {"w": 0}

    def _do_resize():
        try:
            window_width = max(1, root.winfo_width())
            if window_width == _last_width["w"]:
                return
            if _banner_src_img["img"] is None:
                _banner_src_img["img"] = Image.open("assets/images/Banner.png")
            new_height = max(1, int(window_width * 250 / 900))
            resized = _banner_src_img["img"].resize(
                (window_width, new_height),
                Image.Resampling.BILINEAR
            )
            banner_photo = ImageTk.PhotoImage(resized)
            if banner_label.winfo_exists():
                banner_label.config(image=banner_photo)
                banner_label.image = banner_photo
                _last_width["w"] = window_width
        except Exception as e:
            print(f"Error loading or resizing image: {e}")

    def update_banner_debounced(event=None):
        if _banner_after_id["id"] is not None:
            try:
                root.after_cancel(_banner_after_id["id"])
            except Exception:
                pass
        _banner_after_id["id"] = root.after(120, _do_resize)

    root.after(100, _do_resize)
    root.bind("<Configure>", update_banner_debounced)

    # Login card
    card = tb.Frame(root, bootstyle="light", padding=30)
    card.place(relx=0.5, rely=0.65, anchor="center", relwidth=0.4)

    tb.Label(
        card,
        text="Please Login",
        font=("Segoe UI", 16, "bold"),
        bootstyle="primary"
    ).pack(pady=(0, 20))

    # Server status indicator for client logins
    server_status_frame = tb.Frame(card)
    server_status_frame.pack(pady=(0, 10))
    
    server_status_label = tb.Label(
        server_status_frame,
        text="🔄 Checking server...",
        font=("Segoe UI", 10),
        foreground="orange"
    )
    server_status_label.pack()
    
    _server_check_inflight = {"busy": False}
    _login_inflight = {"busy": False}

    def update_server_status():
        """Update server status indicator without blocking UI"""
        if _server_check_inflight["busy"]:
            return
        _server_check_inflight["busy"] = True

        def _on_result(ok):
            try:
                if ok:
                    server_status_label.config(text="🟢 Server: Online", foreground="green")
                else:
                    server_status_label.config(text="🔴 Server: Offline (Client login unavailable)", foreground="red")
            finally:
                _server_check_inflight["busy"] = False

        check_server_connectivity_async(root, _on_result, timeout=1.2)
    
    # Check server status after UI is ready
    root.after(1000, update_server_status)
    # Update every 10 seconds
    def periodic_server_check():
        update_server_status()
        root.after(10000, periodic_server_check)
    root.after(10000, periodic_server_check)

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
        # Prevent double-trigger (Enter key + button click)
        if _login_inflight["busy"]:
            return
        _login_inflight["busy"] = True

        def reset_login():
            try:
                login_button.config(text="Login", state="normal")
            except Exception:
                pass
            _login_inflight["busy"] = False

        login_button.config(text="Loading...", state="disabled")
        root.update()

        username = username_var.get()
        password = password_var.get()

    # Avoid artificial delays that freeze the UI

        if is_rate_limited(username):
            messagebox.showerror(
                "Rate Limited",
                "Too many failed login attempts.\nPlease wait a minute and try again."
            )
            reset_login()
            return

        # Fast pre-check: is the MySQL server reachable at all?
        try:
            server_ok, _ = check_mysql_server_status()
        except Exception:
            server_ok = False
        if not server_ok:
            messagebox.showerror(
                "Can't Reach Database",
                "Cannot connect to MySQL database.\n\n"
                "Please start MySQL (XAMPP/WAMP) and try again."
            )
            reset_login()
            return

        # Quick DB connection probe (validates DB and credentials setup)
        try:
            conn = get_connection(max_retries=1, retry_delay=0, show_dialog=False)
            try:
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.fetchone()
            finally:
                try:
                    cur.close()
                except Exception:
                    pass
                try:
                    conn.close()
                except Exception:
                    pass
        except (DatabaseConnectionError, Exception):
            messagebox.showerror(
                "Can't Reach Database",
                "Cannot connect to MySQL database.\n\n"
                "Please start MySQL (XAMPP/WAMP) and try again."
            )
            reset_login()
            return

        # Try to verify user, but catch DB connection errors and None result
        user = None
        db_error = None
        try:
            user = verify_user(username, password)
        except DatabaseConnectionError as db_exc:
            db_error = db_exc
        except Exception as exc:
            db_error = exc
        if db_error is not None:
            messagebox.showerror(
                "Can't Reach Database",
                "Cannot connect to MySQL database.\n\n"
                "Please start MySQL (XAMPP/WAMP) and try again."
            )
            reset_login()
            return
        if user is None:
            # If DB is up but user not found, show invalid login
            # If DB is down, previous block already handled
            login_attempts[username].append(time.time())
            messagebox.showerror("Login Failed", "Invalid username or password.")
            reset_login()
            return

        # Check server connectivity for client users; if unavailable, block client login
        if user.get('role') != 'admin':
            if not check_server_connectivity():
                messagebox.showerror(
                    "Server Connection Required", 
                    "Client login relies on the API server. Please ensure it is running.\n\n"
                    "• Start server/app.py\n"
                    "• Verify network connectivity\n"
                    "• Confirm server address in WINYFI_API"
                )
                reset_login()
                return

        # Get device information for logging
        device_info = get_device_info()

        # Decide login path: Admins log locally; Clients log via API (server logs session)
        login_type = 'admin' if user.get('role') == 'admin' else 'client'
        if login_type == 'admin':
            try:
                create_login_sessions_table()
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
            except Exception:
                # Non-blocking: if DB is unavailable, continue without logging
                pass
        else:
            # Client users authenticate via API so the server can record login_sessions
            try:
                api_base_url = os.environ.get("WINYFI_API", "http://localhost:5000").rstrip("/")
                payload = {
                    "username": username,
                    "password": password,
                    "device_mac": device_info.get('mac_address'),
                    "device_hostname": device_info.get('hostname'),
                    "device_platform": device_info.get('platform')
                }
                resp = requests.post(f"{api_base_url}/api/login", json=payload, timeout=(2, 5))
                if resp.status_code == 200:
                    try:
                        server_user = resp.json() or {}
                        # Prefer server's canonical user payload
                        if server_user.get('id'):
                            user = server_user
                    except Exception:
                        # If parsing fails, continue with local user object
                        pass
                elif resp.status_code == 401:
                    messagebox.showerror("Login Failed", "Invalid username or password (server).")
                    reset_login()
                    return
                else:
                    messagebox.showerror("Server Error", f"Login API error: HTTP {resp.status_code}")
                    reset_login()
                    return
            except requests.exceptions.RequestException as e:
                messagebox.showerror("Server Error", f"Unable to contact login API. Please try again.\n\nDetails: {e}")
                reset_login()
                return

        # ✅ Success → hide login window
        root.withdraw()

        if user.get('role') == 'admin':
            # Admin → open dashboard
            dashboard_window = tb.Toplevel(root)
            dashboard_window.title("Admin Dashboard")
            center_window(dashboard_window, 1000, 700)
            dashboard_window.resizable(True, True)

            # Get API base URL from environment or use default
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
                        os._exit(0)
                    except Exception:
                        pass

            dashboard_window.protocol("WM_DELETE_WINDOW", on_dashboard_close)
            _login_inflight["busy"] = False
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
                        os._exit(0)
                    except Exception:
                        pass

            client_top.protocol("WM_DELETE_WINDOW", on_client_close)
            _login_inflight["busy"] = False

    # Info note about login requirements
    info_frame = tb.Frame(card)
    info_frame.pack(pady=(10, 0))
    
    info_label = tb.Label(
        info_frame,
        text="ℹ️ Note: Client login requires server connection.\nAdmin users can login offline.",
        font=("Segoe UI", 9),
        foreground="gray",
        justify="center"
    )
    info_label.pack()

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
