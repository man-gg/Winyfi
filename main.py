# main.py
import ttkbootstrap as tb
from login import show_login
import sys
import os
import logging
import traceback


def _show_error_dialog(title: str, message: str, parent=None) -> None:
    """Best-effort GUI error dialog without crashing if Tk isn't ready."""
    try:
        import tkinter as tk
        from tkinter import messagebox

        # If no Tk root exists and no parent was provided, create a tiny hidden one
        created_temp_root = False
        if parent is None:
            try:
                parent = tk._default_root
            except Exception:
                parent = None

        if parent is None:
            parent = tk.Tk()
            parent.withdraw()
            created_temp_root = True

        messagebox.showerror(title, message, parent=parent)

        if created_temp_root:
            parent.destroy()
    except Exception:
        # Last resort: print to stderr
        print(f"\n[ERROR] {title}: {message}", file=sys.stderr)


def _format_exception(exc_type, exc, tb_obj) -> str:
    return "".join(traceback.format_exception(exc_type, exc, tb_obj))


def init_logging() -> str:
    """Configure logging to file and stderr. Returns the log file path."""
    log_file = os.path.join(os.path.dirname(__file__), "winyfi_error.log")
    try:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            handlers=[
                logging.FileHandler(log_file, encoding="utf-8"),
                logging.StreamHandler(sys.stderr),
            ],
            force=True,  # ensure we override previous configs
        )
    except Exception:
        # If file handler fails (e.g., permissions), fall back to stderr only
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            handlers=[logging.StreamHandler(sys.stderr)],
            force=True,
        )
        _show_error_dialog(
            "Logging Disabled",
            "Could not create winyfi_error.log; logging to console only.",
        )
    return log_file


def setup_global_exception_handlers(root_window) -> None:
    """Set global exception hooks so unexpected errors are logged and shown politely."""
    logger = logging.getLogger("winyfi")

    def _handle_any_exception(exc_type, exc, tb_obj):
        details = _format_exception(exc_type, exc, tb_obj)
        logger.error("Uncaught exception:\n%s", details)
        _show_error_dialog(
            "Unexpected Error",
            "Something went wrong. Details have been logged to winyfi_error.log.",
            parent=root_window,
        )

    def _tk_callback_exception(exc_type, exc, tb_obj):
        details = _format_exception(exc_type, exc, tb_obj)
        logger.error("Tkinter callback exception:\n%s", details)
        _show_error_dialog(
            "Operation Failed",
            "An action couldn't be completed. Details were saved to winyfi_error.log.",
            parent=root_window,
        )

    # Catch non-GUI uncaught exceptions
    sys.excepthook = _handle_any_exception

    # Catch exceptions raised inside Tk event callbacks
    try:
        root_window.report_callback_exception = _tk_callback_exception
    except Exception:
        # Some widget frameworks may not expose it; ignore silently
        pass

if __name__ == "__main__":
    # Initialize logging first so early errors are captured
    init_logging()
    
    # 1) Create your window with the flatly theme
    root = tb.Window(themename="flatly")

    # 2) Grab the Style instance and override the built-in 'primary' (and any other)
    style = root.style
    style.colors.set('primary', '#d9534f')   # your brand-red
    style.colors.set('danger',  '#c9302c')   # a slightly darker red for hovers, borders, etc.

    # 3) Now register your custom widget styles
    style.configure(
        'Sidebar.TFrame',
        background='#d9534f',
        borderwidth=0
    )
    style.configure(
        'Sidebar.TButton',
        background='#d9534f',
        foreground='white',
        font=('Segoe UI', 11, 'bold'),
    )
    style.map(
        'Sidebar.TButton',
        background=[('active', '#c9302c')]
    )

    style.configure(
        'RouterCard.TLabelframe',
        background='white',
        bordercolor='#d9534f',
        borderwidth=1,
        relief='flat'
    )
    style.configure(
        'RouterCard.TLabelframe.Label',
        background='white',
        foreground='#d9534f',
        font=('Segoe UI', 10, 'bold')
    )
    style.map(
        'RouterCard.TLabelframe',
        bordercolor=[('active', '#c9302c')]
    )

    # Hook global handlers now that Tk exists
    setup_global_exception_handlers(root)

    # 4) Fire off your login (and then dashboard) as usual
    show_login(root)
    root.mainloop()
