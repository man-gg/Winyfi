#!/usr/bin/env python3
"""
Script to modify only the Show Clients function to be read-only
"""

# Read the file
with open('client_window/tabs/routers_tab.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Make the specific changes
# 1. Change Scan Now button to Refresh button
content = content.replace(
    'self.scan_btn = tb.Button(btn_frame, text="🔄 Scan Now", bootstyle="primary", \n                                command=self.start_client_scan, width=12)\n        self.scan_btn.pack(side="left", padx=2)',
    'self.refresh_btn = tb.Button(btn_frame, text="🔄 Refresh", bootstyle="primary", \n                                command=self.load_clients_from_db, width=12)\n        self.refresh_btn.pack(side="left", padx=2)'
)

# 2. Remove initial scan call
content = content.replace(
    '        # Start initial scan\n        self.start_client_scan()',
    '        # Load clients from database (read-only)\n        self.load_clients_from_db()'
)

# 3. Add load_clients_from_db method if it doesn't exist
if 'def load_clients_from_db(self):' not in content:
    # Find where to insert the method (after load_existing_clients)
    insert_point = content.find('    def load_existing_clients(self):')
    if insert_point != -1:
        # Find the end of load_existing_clients method
        method_end = content.find('\n    def ', insert_point + 1)
        if method_end == -1:
            method_end = len(content)
        
        # Insert the new method
        new_method = '''
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
'''
        content = content[:method_end] + new_method + content[method_end:]

# Write the modified content back
with open('client_window/tabs/routers_tab.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Successfully modified Show Clients function to be read-only")
print("Changes made:")
print("1. Changed 'Scan Now' button to 'Refresh' button")
print("2. Changed command from start_client_scan to load_clients_from_db")
print("3. Removed initial scan call")
print("4. Added load_clients_from_db method for database-only fetching")
