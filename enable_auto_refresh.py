#!/usr/bin/env python3
"""
Script to enable auto-refresh by default for Show Clients function
"""

import re

# 1. Modify client-side (routers_tab.py)
print("Modifying client-side auto-refresh...")
with open('client_window/tabs/routers_tab.py', 'r', encoding='utf-8') as f:
    client_content = f.read()

# Change auto_refresh_enabled from False to True
client_content = client_content.replace(
    'self.client_auto_refresh_enabled = False',
    'self.client_auto_refresh_enabled = True'
)

# Change button text from "⏸️ Auto Refresh" to "⏸️ Stop Auto" (since it's enabled by default)
client_content = client_content.replace(
    'self.auto_refresh_btn = tb.Button(btn_frame, text="⏸️ Auto Refresh", bootstyle="warning",',
    'self.auto_refresh_btn = tb.Button(btn_frame, text="⏸️ Stop Auto", bootstyle="danger",'
)

# Start auto-refresh after loading clients
client_content = client_content.replace(
    '        # Load existing clients from database first\n        self.load_existing_clients()\n        \n        # Start initial scan\n        self.load_clients_from_db()',
    '        # Load existing clients from database first\n        self.load_existing_clients()\n        \n        # Load clients from database and start auto-refresh\n        self.load_clients_from_db()\n        self.start_auto_refresh()'
)

with open('client_window/tabs/routers_tab.py', 'w', encoding='utf-8') as f:
    f.write(client_content)

# 2. Modify admin-side (dashboard.py)
print("Modifying admin-side auto-refresh...")
with open('dashboard.py', 'r', encoding='utf-8') as f:
    admin_content = f.read()

# Change auto_refresh_enabled from False to True
admin_content = admin_content.replace(
    '        self.auto_refresh_enabled = False',
    '        self.auto_refresh_enabled = True'
)

# Change button text from "⏸️ Auto Refresh" to "⏸️ Stop Auto" (since it's enabled by default)
admin_content = admin_content.replace(
    '        self.auto_refresh_btn = tb.Button(btn_frame, text="⏸️ Auto Refresh", bootstyle="warning",',
    '        self.auto_refresh_btn = tb.Button(btn_frame, text="⏸️ Stop Auto", bootstyle="danger",'
)

# Start auto-refresh after loading clients
admin_content = admin_content.replace(
    '        # Load existing clients from database first\n        self.load_existing_clients()\n        \n        # Start initial scan\n        self.start_client_scan()',
    '        # Load existing clients from database first\n        self.load_existing_clients()\n        \n        # Start initial scan and auto-refresh\n        self.start_client_scan()\n        self.start_auto_refresh()'
)

with open('dashboard.py', 'w', encoding='utf-8') as f:
    f.write(admin_content)

print("✅ Successfully enabled auto-refresh by default for Show Clients function")
print("Changes made:")
print("1. Set auto_refresh_enabled = True by default")
print("2. Changed button text to 'Stop Auto' (since it's enabled)")
print("3. Changed button style to 'danger' (red) for stop button")
print("4. Added start_auto_refresh() call after loading clients")
print("5. Applied changes to both client-side and admin-side")
