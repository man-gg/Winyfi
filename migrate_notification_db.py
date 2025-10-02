#!/usr/bin/env python3
"""
Migration script to update notification database schema
"""

import sqlite3
import os

def migrate_database():
    """Migrate the notification database to add new columns."""
    db_path = "network_monitoring.db"
    
    if not os.path.exists(db_path):
        print("Database doesn't exist, creating new one...")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if the new columns exist
        cursor.execute("PRAGMA table_info(notifications)")
        columns = [row[1] for row in cursor.fetchall()]
        
        print(f"Current columns: {columns}")
        
        # Add new columns if they don't exist
        new_columns = [
            ("status", "TEXT DEFAULT 'created'"),
            ("display_attempts", "INTEGER DEFAULT 0"),
            ("last_display_attempt", "TIMESTAMP NULL")
        ]
        
        for column_name, column_def in new_columns:
            if column_name not in columns:
                print(f"Adding column: {column_name}")
                cursor.execute(f"ALTER TABLE notifications ADD COLUMN {column_name} {column_def}")
            else:
                print(f"Column {column_name} already exists")
        
        # Create notification_logs table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notification_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                notification_id INTEGER,
                event_type TEXT NOT NULL,
                message TEXT,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (notification_id) REFERENCES notifications (id)
            )
        ''')
        
        conn.commit()
        print("✅ Database migration completed successfully!")
        
        # Verify the migration
        cursor.execute("PRAGMA table_info(notifications)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"Updated columns: {columns}")
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()

