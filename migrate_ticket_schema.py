#!/usr/bin/env python3
"""
Database migration script to add status and priority columns to ict_service_requests table.
Run this script to update your database schema for the enhanced ticket management system.
"""

from db import get_connection
import sys

def migrate_database():
    """Add missing columns to ict_service_requests table."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("Starting database migration...")
        
        # Check if status column exists
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'ict_service_requests' 
            AND COLUMN_NAME = 'status'
        """)
        
        status_exists = cursor.fetchone()[0] > 0
        
        if not status_exists:
            print("Adding 'status' column to ict_service_requests table...")
            cursor.execute("""
                ALTER TABLE ict_service_requests 
                ADD COLUMN status varchar(50) DEFAULT 'open' AFTER remarks
            """)
            
            # Update existing records
            cursor.execute("""
                UPDATE ict_service_requests 
                SET status = 'open' 
                WHERE status IS NULL OR status = ''
            """)
            print("✓ Status column added successfully")
        else:
            print("✓ Status column already exists")
        
        # Check if priority column exists
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'ict_service_requests' 
            AND COLUMN_NAME = 'priority'
        """)
        
        priority_exists = cursor.fetchone()[0] > 0
        
        if not priority_exists:
            print("Adding 'priority' column to ict_service_requests table...")
            cursor.execute("""
                ALTER TABLE ict_service_requests 
                ADD COLUMN priority varchar(20) DEFAULT 'Normal' AFTER status
            """)
            
            # Update existing records
            cursor.execute("""
                UPDATE ict_service_requests 
                SET priority = 'Normal' 
                WHERE priority IS NULL OR priority = ''
            """)
            print("✓ Priority column added successfully")
        else:
            print("✓ Priority column already exists")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("\n🎉 Database migration completed successfully!")
        print("You can now use the enhanced ticket management features.")
        
    except Exception as e:
        print(f"❌ Error during database migration: {e}")
        print("Please check your database connection and try again.")
        sys.exit(1)

if __name__ == "__main__":
    migrate_database()