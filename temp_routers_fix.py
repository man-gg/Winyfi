# Only modify these specific lines in routers_tab.py:

# Line 503-505: Change Scan Now button to Refresh button
# OLD:
# self.scan_btn = tb.Button(btn_frame, text="🔄 Scan Now", bootstyle="primary", 
#                         command=self.start_client_scan, width=12)
# self.scan_btn.pack(side="left", padx=2)

# NEW:
self.refresh_btn = tb.Button(btn_frame, text="🔄 Refresh", bootstyle="primary", 
                           command=self.load_clients_from_db, width=12)
self.refresh_btn.pack(side="left", padx=2)

# Line 578: Remove initial scan call
# OLD:
# self.start_client_scan()

# NEW:
self.load_clients_from_db()

# Also need to add load_clients_from_db method if it doesn't exist
def load_clients_from_db(self):
    """Load clients from database via API (READ-ONLY)"""
    try:
        response = requests.get(f"{self.api_base_url}/api/clients", timeout=5)
        if response.ok:
            data = response.json()
            self.client_data = data.get('clients', [])
            self.update_client_display()
            self.client_status_label.config(text="Clients loaded successfully", bootstyle="success")
        else:
            self.client_data = []
            self.client_status_label.config(text="Failed to load clients", bootstyle="danger")
    except Exception as e:
        print(f"❌ Error loading clients: {e}")
        self.client_data = []
        self.client_status_label.config(text="Error loading clients", bootstyle="danger")
    
    # Update last update time
    from datetime import datetime
    time_str = datetime.now().strftime("%H:%M:%S")
    self.client_last_update.config(text=f"Last update: {time_str}")
