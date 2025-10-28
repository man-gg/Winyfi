"""
Dashboard Integration Example for RouterBandwidthMonitor
Shows how to integrate bandwidth monitoring into your existing Winyfi dashboard.
"""

import ttkbootstrap as tb
from router_bandwidth_monitor import RouterBandwidthMonitor
import threading
import time
from datetime import datetime


class BandwidthMonitorDashboard:
    """
    Example integration of RouterBandwidthMonitor into Winyfi dashboard.
    Add this to your existing dashboard.py file.
    """
    
    def __init__(self, parent, db_connection):
        """
        Initialize bandwidth monitoring in dashboard.
        
        Args:
            parent: Parent tkinter frame
            db_connection: Database connection for loading routers
        """
        self.parent = parent
        self.db = db_connection
        
        # Initialize router bandwidth monitor
        self.router_monitor = RouterBandwidthMonitor(
            sampling_interval=5,
            history_size=60
        )
        
        # Load routers from database and start monitoring
        self._initialize_monitoring()
        
        # UI elements
        self.bandwidth_cards = {}
        self.update_interval = 5000  # 5 seconds (ms)
        
        # Start UI update loop
        self._start_ui_updates()
    
    def _initialize_monitoring(self):
        """Load routers from database and start monitoring."""
        try:
            # Fetch non-UniFi routers from database
            query = """
                SELECT ip, mac, name, brand, model 
                FROM routers 
                WHERE brand != 'UniFi' OR brand IS NULL
            """
            routers = self.db.execute(query).fetchall()
            
            print(f"📡 Loading {len(routers)} routers for bandwidth monitoring...")
            
            for router in routers:
                self.router_monitor.add_router(
                    ip=router['ip'],
                    mac=router.get('mac'),
                    name=router.get('name') or f"{router.get('brand', 'Router')} {router['ip']}"
                )
                print(f"  ✓ Added: {router['ip']} ({router.get('name', 'Unnamed')})")
            
            # Start monitoring
            self.router_monitor.start()
            print("✅ Router bandwidth monitoring started\n")
            
        except Exception as e:
            print(f"❌ Failed to initialize monitoring: {e}")
    
    def _start_ui_updates(self):
        """Start periodic UI updates."""
        def update_loop():
            while True:
                try:
                    self.parent.after(0, self._update_bandwidth_displays)
                    time.sleep(self.update_interval / 1000)
                except Exception as e:
                    print(f"UI update error: {e}")
        
        update_thread = threading.Thread(target=update_loop, daemon=True)
        update_thread.start()
    
    def _update_bandwidth_displays(self):
        """Update all bandwidth display cards."""
        all_bandwidth = self.router_monitor.get_all_routers_bandwidth()
        
        for bandwidth_data in all_bandwidth:
            router_ip = bandwidth_data['router_ip']
            
            if router_ip in self.bandwidth_cards:
                self._update_card(router_ip, bandwidth_data)
    
    def _update_card(self, router_ip, bandwidth_data):
        """Update a specific bandwidth card."""
        card_widgets = self.bandwidth_cards[router_ip]
        
        # Update download label
        card_widgets['download_label'].config(
            text=f"↓ {bandwidth_data['download_mbps']:.2f} Mbps"
        )
        
        # Update upload label
        card_widgets['upload_label'].config(
            text=f"↑ {bandwidth_data['upload_mbps']:.2f} Mbps"
        )
        
        # Update status color
        status_color = "green" if bandwidth_data['status'] == 'active' else "gray"
        card_widgets['status_indicator'].config(foreground=status_color)
        
        # Update timestamp
        timestamp = datetime.fromisoformat(bandwidth_data['timestamp'])
        card_widgets['timestamp_label'].config(
            text=f"Updated: {timestamp.strftime('%H:%M:%S')}"
        )
    
    def create_bandwidth_card(self, router_ip):
        """
        Create a bandwidth display card for a router.
        Call this when building your router list UI.
        """
        # Create card frame
        card = tb.Frame(self.parent, style='Card.TFrame', padding=10)
        
        # Get initial bandwidth data
        bandwidth_data = self.router_monitor.get_router_bandwidth(router_ip)
        
        if not bandwidth_data:
            return None
        
        # Router name header
        name_label = tb.Label(
            card,
            text=bandwidth_data['router_name'],
            font=('Segoe UI', 12, 'bold')
        )
        name_label.pack(pady=(0, 5))
        
        # IP address
        ip_label = tb.Label(
            card,
            text=router_ip,
            font=('Segoe UI', 9),
            foreground='gray'
        )
        ip_label.pack()
        
        # Download speed
        download_label = tb.Label(
            card,
            text=f"↓ {bandwidth_data['download_mbps']:.2f} Mbps",
            font=('Segoe UI', 11)
        )
        download_label.pack(pady=2)
        
        # Upload speed
        upload_label = tb.Label(
            card,
            text=f"↑ {bandwidth_data['upload_mbps']:.2f} Mbps",
            font=('Segoe UI', 11)
        )
        upload_label.pack(pady=2)
        
        # Status indicator
        status_color = "green" if bandwidth_data['status'] == 'active' else "gray"
        status_indicator = tb.Label(
            card,
            text="●",
            foreground=status_color,
            font=('Segoe UI', 16)
        )
        status_indicator.pack()
        
        # Timestamp
        timestamp = datetime.fromisoformat(bandwidth_data['timestamp'])
        timestamp_label = tb.Label(
            card,
            text=f"Updated: {timestamp.strftime('%H:%M:%S')}",
            font=('Segoe UI', 8),
            foreground='gray'
        )
        timestamp_label.pack()
        
        # Store references for updates
        self.bandwidth_cards[router_ip] = {
            'card': card,
            'download_label': download_label,
            'upload_label': upload_label,
            'status_indicator': status_indicator,
            'timestamp_label': timestamp_label
        }
        
        return card
    
    def show_bandwidth_details(self, router_ip):
        """
        Show detailed bandwidth window for a router.
        Call this when user clicks on a router card.
        """
        # Create detail window
        detail_window = tb.Toplevel(self.parent)
        detail_window.title(f"Bandwidth Details - {router_ip}")
        detail_window.geometry("600x500")
        
        # Header
        header = tb.Label(
            detail_window,
            text=f"Bandwidth Monitor - {router_ip}",
            font=('Segoe UI', 14, 'bold')
        )
        header.pack(pady=10)
        
        # Current stats frame
        current_frame = tb.LabelFrame(
            detail_window,
            text="Current Usage",
            padding=10
        )
        current_frame.pack(fill='x', padx=10, pady=5)
        
        bandwidth_data = self.router_monitor.get_router_bandwidth(router_ip)
        
        if bandwidth_data:
            tb.Label(
                current_frame,
                text=f"Download: {bandwidth_data['download_mbps']:.2f} Mbps",
                font=('Segoe UI', 11)
            ).pack()
            
            tb.Label(
                current_frame,
                text=f"Upload: {bandwidth_data['upload_mbps']:.2f} Mbps",
                font=('Segoe UI', 11)
            ).pack()
            
            tb.Label(
                current_frame,
                text=f"Packets: {bandwidth_data['packets']}",
                font=('Segoe UI', 10)
            ).pack()
        
        # Average stats frame
        avg_frame = tb.LabelFrame(
            detail_window,
            text="5-Minute Average",
            padding=10
        )
        avg_frame.pack(fill='x', padx=10, pady=5)
        
        avg_data = self.router_monitor.get_average_bandwidth(router_ip, minutes=5)
        
        if avg_data:
            tb.Label(
                avg_frame,
                text=f"Avg Download: {avg_data['avg_download_mbps']:.2f} Mbps",
                font=('Segoe UI', 11)
            ).pack()
            
            tb.Label(
                avg_frame,
                text=f"Avg Upload: {avg_data['avg_upload_mbps']:.2f} Mbps",
                font=('Segoe UI', 11)
            ).pack()
            
            tb.Label(
                avg_frame,
                text=f"Samples: {avg_data['sample_count']}",
                font=('Segoe UI', 9),
                foreground='gray'
            ).pack()
        
        # Peak stats frame
        peak_frame = tb.LabelFrame(
            detail_window,
            text="Peak Usage",
            padding=10
        )
        peak_frame.pack(fill='x', padx=10, pady=5)
        
        peak_data = self.router_monitor.get_peak_bandwidth(router_ip)
        
        if peak_data:
            tb.Label(
                peak_frame,
                text=f"Peak Download: {peak_data['peak_download_mbps']:.2f} Mbps",
                font=('Segoe UI', 11),
                foreground='blue'
            ).pack()
            
            tb.Label(
                peak_frame,
                text=f"Peak Upload: {peak_data['peak_upload_mbps']:.2f} Mbps",
                font=('Segoe UI', 11),
                foreground='red'
            ).pack()
        
        # History frame
        history_frame = tb.LabelFrame(
            detail_window,
            text="Recent History (Last 10)",
            padding=10
        )
        history_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Create scrollable text widget for history
        history_text = tb.Text(
            history_frame,
            height=10,
            font=('Consolas', 9)
        )
        history_text.pack(fill='both', expand=True)
        
        history = self.router_monitor.get_router_history(router_ip, limit=10)
        
        if history:
            history_text.insert('1.0', "Time          Download    Upload     Packets\n")
            history_text.insert('end', "=" * 50 + "\n")
            
            for entry in reversed(history):  # Show newest first
                timestamp = datetime.fromisoformat(entry['timestamp'])
                time_str = timestamp.strftime('%H:%M:%S')
                
                line = f"{time_str}    {entry['download_mbps']:>7.2f}    {entry['upload_mbps']:>7.2f}    {entry['packets']:>6}\n"
                history_text.insert('end', line)
        
        history_text.config(state='disabled')  # Make read-only
        
        # Close button
        tb.Button(
            detail_window,
            text="Close",
            command=detail_window.destroy
        ).pack(pady=10)
    
    def stop_monitoring(self):
        """Stop bandwidth monitoring. Call before app exit."""
        self.router_monitor.stop()
        print("✅ Bandwidth monitoring stopped")


# ============================================================================
# Integration into existing dashboard.py
# ============================================================================

def integrate_into_dashboard(dashboard_instance):
    """
    Example showing how to integrate into your existing dashboard.py
    
    Add this to your Dashboard.__init__() method:
    """
    
    # After your existing initialization code...
    
    # Initialize bandwidth monitoring
    dashboard_instance.bandwidth_monitor_dashboard = BandwidthMonitorDashboard(
        parent=dashboard_instance.root,
        db_connection=dashboard_instance.db
    )
    
    # Modify your show_routers() method to include bandwidth cards
    # Example modification:
    
    """
    def show_routers(self):
        # ... existing code to create router list ...
        
        for router in routers:
            router_ip = router['ip']
            
            # Create your existing router info frame
            router_frame = tb.Frame(...)
            
            # Add bandwidth card next to it
            bandwidth_card = self.bandwidth_monitor_dashboard.create_bandwidth_card(router_ip)
            if bandwidth_card:
                bandwidth_card.pack(side='right', padx=5)
            
            # Make router clickable to show details
            router_frame.bind(
                '<Button-1>',
                lambda e, ip=router_ip: self.bandwidth_monitor_dashboard.show_bandwidth_details(ip)
            )
    """
    
    # Add cleanup to your on_closing() method:
    """
    def on_closing(self):
        # ... existing cleanup code ...
        
        # Stop bandwidth monitoring
        if hasattr(self, 'bandwidth_monitor_dashboard'):
            self.bandwidth_monitor_dashboard.stop_monitoring()
        
        self.root.destroy()
    """


# ============================================================================
# Standalone Test
# ============================================================================

if __name__ == "__main__":
    """Test the integration standalone."""
    import sqlite3
    
    # Create test database
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Create test table
    cursor.execute("""
        CREATE TABLE routers (
            id INTEGER PRIMARY KEY,
            ip TEXT,
            mac TEXT,
            name TEXT,
            brand TEXT,
            model TEXT
        )
    """)
    
    # Add test routers
    cursor.execute("""
        INSERT INTO routers (ip, mac, name, brand, model)
        VALUES ('192.168.1.1', NULL, 'Main Router', 'TP-Link', 'Archer C7')
    """)
    cursor.execute("""
        INSERT INTO routers (ip, mac, name, brand, model)
        VALUES ('192.168.1.100', NULL, 'Living Room AP', 'Cisco', 'WAP121')
    """)
    conn.commit()
    
    # Create test window
    root = tb.Window(themename="flatly")
    root.title("Bandwidth Monitor Test")
    root.geometry("800x600")
    
    # Create dashboard
    dashboard = BandwidthMonitorDashboard(root, conn)
    
    # Create UI
    header = tb.Label(
        root,
        text="Router Bandwidth Monitor",
        font=('Segoe UI', 16, 'bold')
    )
    header.pack(pady=20)
    
    # Container for bandwidth cards
    cards_container = tb.Frame(root)
    cards_container.pack(fill='both', expand=True, padx=20, pady=10)
    
    # Add bandwidth cards for all routers
    routers = conn.execute("SELECT ip FROM routers").fetchall()
    for router in routers:
        card = dashboard.create_bandwidth_card(router['ip'])
        if card:
            card.pack(side='left', padx=10, pady=10, fill='both', expand=True)
            
            # Make card clickable
            card.bind(
                '<Button-1>',
                lambda e, ip=router['ip']: dashboard.show_bandwidth_details(ip)
            )
    
    # Instructions
    instructions = tb.Label(
        root,
        text="Click on a card to see detailed statistics\nGenerate network traffic to see bandwidth updates",
        font=('Segoe UI', 10),
        foreground='gray'
    )
    instructions.pack(pady=10)
    
    # Cleanup on close
    def on_closing():
        dashboard.stop_monitoring()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # Run
    root.mainloop()
