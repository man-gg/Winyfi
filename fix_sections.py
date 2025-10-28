with open('dashboard.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the corrupted emoji and add sections
old_text = '''        # Reports & Analysis section
        add_section_header("Reports & Analysis")
        add_sidebar_button("Reports", "�")

        # Notification bell button'''

new_text = '''        # Reports & Analysis section
        add_section_header("Reports & Analysis")
        add_sidebar_button("Reports", "📄")
        
        # Export button
        self.export_btn = tb.Button(
            self.sidebar,
            text="📁 Export To Csv",
            style='Sidebar.TButton',
            width=22,
            command=self.open_export_menu
        )
        self.export_btn.pack(pady=5)
        
        # Notifications section
        add_section_header("Notifications")

        # Notification bell button'''

content = content.replace(old_text, new_text)

# Now add Account & Settings section before settings dropdown
old_settings = '''        # Default tab
        show_page("Dashboard")

        self.build_bandwidth_tab()
        self.build_reports_tab()

        # Settings dropdown'''

new_settings = '''        # Default tab
        show_page("Dashboard")

        self.build_bandwidth_tab()
        self.build_reports_tab()

        # Account & Settings section
        add_section_header("Account & Settings")

        # Settings dropdown'''

content = content.replace(old_settings, new_settings)

# Remove the old export button at the bottom
old_export = '''        self.settings_dropdown.config(height=0)

        # Export button with dropdown
        self.export_btn = tb.Button(
            self.sidebar,
            text="⬇️ Export to CSV",
            width=22,
            style='Sidebar.TButton',
            command=self.open_export_menu
        )
        self.export_btn.pack(pady=(0,0))

        # === Routers Page Content ==='''

new_export = '''        self.settings_dropdown.config(height=0)

        # === Routers Page Content ==='''

content = content.replace(old_export, new_export)

with open('dashboard.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Dashboard fixed with sections!")
