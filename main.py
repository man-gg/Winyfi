# main.py
import ttkbootstrap as tb
from login import show_login
import sys
import os

def check_database_before_start():
    """Check database connection before starting the application"""
    try:
        from db import check_mysql_server_status
        import tkinter as tk
        from tkinter import messagebox
        
        # Quick check if MySQL server is accessible
        server_accessible, message = check_mysql_server_status()
        
        if not server_accessible:
            # Create a temporary root window for the error dialog
            temp_root = tk.Tk()
            temp_root.withdraw()  # Hide the window
            
            # Show error dialog
            messagebox.showerror(
                "Database Connection Failed",
                "Cannot connect to MySQL database.\n\n"
                "Please start MySQL (XAMPP/WAMP) and try again."
            )
            
            # Clean up and exit
            temp_root.destroy()
            sys.exit(1)
            
    except Exception as e:
        # Fallback to create a simple error dialog
        import tkinter as tk
        from tkinter import messagebox
        
        try:
            temp_root = tk.Tk()
            temp_root.withdraw()  # Hide the window
            
            messagebox.showerror(
                "Database Error",
                "Unable to verify database connection.\n\n"
                "Please ensure MySQL is running and try again."
            )
            
            temp_root.destroy()
        except:
            # Ultimate fallback to terminal if GUI fails
            print("\n❌ Database Error")
            print("Unable to verify database connection.")
            print("Please ensure MySQL is running and try again.")
        
        sys.exit(1)

if __name__ == "__main__":
    # Check database connection before starting GUI
    check_database_before_start()
    
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

    # 4) Fire off your login (and then dashboard) as usual
    show_login(root)
    root.mainloop()
